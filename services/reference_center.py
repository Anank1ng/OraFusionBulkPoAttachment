import re

import requests
from requests.auth import HTTPBasicAuth

from services.oracle_api import PO_RESOURCE, normalize_instance_url

MAX_REFERENCE_LOOKUPS = 20
PO_NUMBER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,29}\Z")

REFERENCE_COLUMNS = (
    "OrderNumber",
    "POHeaderId",
    "SoldToLegalEntity",
    "ProcurementBU",
    "Supplier",
    "Status",
    "LookupStatus",
    "Message",
)


class ReferenceLookupError(ValueError):
    pass


def parse_po_numbers(raw_text: str) -> list[str]:
    values = re.split(r"[,;\n]+", raw_text or "")
    unique = list(dict.fromkeys(value.strip() for value in values if value.strip()))
    if not unique:
        raise ReferenceLookupError("Provide at least one PO Number.")
    if len(unique) > MAX_REFERENCE_LOOKUPS:
        raise ReferenceLookupError(
            f"Reference Center currently supports up to {MAX_REFERENCE_LOOKUPS} unique "
            "PO Numbers per request."
        )
    for number in unique:
        if not PO_NUMBER_PATTERN.fullmatch(number):
            raise ReferenceLookupError(
                "PO Numbers must be 1-30 characters and use only letters, numbers, "
                "dots, underscores, dashes, or slashes."
            )
    return unique


def _error(number: str, code: str, message: str) -> dict:
    return {
        "OrderNumber": number,
        "POHeaderId": "",
        "SoldToLegalEntity": "",
        "ProcurementBU": "",
        "Supplier": "",
        "Status": "",
        "LookupStatus": code,
        "Message": message,
    }


def _extract_purchase_order(item: dict, number: str) -> dict:
    return {
        "OrderNumber": number,
        "POHeaderId": item.get("POHeaderId") or "",
        "SoldToLegalEntity": item.get("SoldToLegalEntity") or "",
        "ProcurementBU": item.get("ProcurementBU") or "",
        "Supplier": item.get("Supplier") or "",
        "Status": item.get("Status") or item.get("StatusCode") or "",
        "LookupStatus": "",
        "Message": "",
    }


def lookup_po_references(
    instance_url: str,
    username: str,
    password: str,
    po_numbers: list[str],
    sold_to_legal_entity: str = "",
) -> list[dict]:
    base_url, _ = normalize_instance_url(instance_url)
    if not (username or "").strip() or not password:
        raise ReferenceLookupError("Oracle Username and Password are required.")

    if not po_numbers or len(po_numbers) > MAX_REFERENCE_LOOKUPS:
        raise ReferenceLookupError(
            f"Provide 1-{MAX_REFERENCE_LOOKUPS} PO Numbers for this lookup."
        )
    if any(not PO_NUMBER_PATTERN.fullmatch(number) for number in po_numbers):
        raise ReferenceLookupError("One or more PO Numbers contain unsupported characters.")

    selected_entity = sold_to_legal_entity.strip()
    rows = []
    for number in po_numbers:
        try:
            response = requests.get(
                f"{base_url}{PO_RESOURCE}",
                auth=HTTPBasicAuth(username.strip(), password),
                headers={"Accept": "application/json"},
                params={"q": f"OrderNumber='{number}'", "limit": 50},
                timeout=(5, 20),
                allow_redirects=False,
                verify=True,
            )
        except requests.exceptions.Timeout:
            rows.append(_error(number, "API_ERROR", "Connection timeout."))
            continue
        except requests.exceptions.SSLError:
            rows.append(_error(number, "API_ERROR", "TLS verification failed."))
            continue
        except requests.exceptions.RequestException:
            rows.append(_error(number, "API_ERROR", "Could not reach Oracle REST API."))
            continue

        if response.status_code != 200:
            rows.append(
                _error(
                    number,
                    "API_ERROR",
                    f"Oracle returned HTTP {response.status_code}. "
                    "Check instance, role, or API access.",
                )
            )
            continue

        try:
            payload = response.json()
        except ValueError:
            rows.append(_error(number, "API_ERROR", "Oracle returned invalid JSON."))
            continue

        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            rows.append(_error(number, "API_ERROR", "Unexpected Oracle response format."))
            continue

        matches = [
            item
            for item in payload["items"]
            if isinstance(item, dict)
            and str(item.get("OrderNumber") or "") == number
            and (
                not selected_entity
                or str(item.get("SoldToLegalEntity") or "") == selected_entity
            )
        ]
        has_more = payload.get("hasMore") is True

        if not matches:
            if has_more:
                rows.append(
                    _error(
                        number,
                        "NEEDS_REVIEW",
                        "Oracle returned a partial result page. Narrow the search.",
                    )
                )
            else:
                rows.append(
                    _error(
                        number,
                        "NOT_FOUND",
                        "No matching PO visible to this account and legal entity filter.",
                    )
                )
            continue

        ambiguous = len(matches) != 1 or has_more
        for item in matches:
            result = _extract_purchase_order(item, number)
            result["LookupStatus"] = (
                "AMBIGUOUS" if ambiguous else "MATCHED"
            )
            if not result["POHeaderId"]:
                result["LookupStatus"] = "NEEDS_REVIEW"
                result["Message"] = "Oracle did not return POHeaderId."
            elif ambiguous:
                result["Message"] = (
                    "Multiple possible POs or more result pages. "
                    "Select a legal entity before upload."
                )
            else:
                result["Message"] = "PO Number and POHeaderId resolved from Oracle."
            rows.append(result)

    return rows
