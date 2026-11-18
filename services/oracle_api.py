from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
from requests.auth import HTTPBasicAuth

PO_RESOURCE = "/fscmRestApi/resources/11.13.18.05/purchaseOrders"


class InstanceUrlError(ValueError):
    pass


@dataclass(frozen=True)
class ConnectionResult:
    success: bool
    message: str
    host: str
    po_count_in_response: int | None = None


def normalize_instance_url(value: str) -> tuple[str, str]:
    url = (value or "").strip()
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise InstanceUrlError("Enter a valid Oracle Fusion instance URL.") from exc

    if (
        parsed.scheme.lower() != "https"
        or not host.endswith(".oraclecloud.com")
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in url)
    ):
        raise InstanceUrlError(
            "Use the HTTPS base URL of an Oracle Fusion instance, "
            "such as https://example.fa.region.oraclecloud.com. "
            "Do not include a REST path, port, credentials, or query string."
        )
    return f"https://{host}", host


def test_connection(instance_url: str, username: str, password: str) -> ConnectionResult:
    base_url, host = normalize_instance_url(instance_url)
    if not (username or "").strip() or not password:
        return ConnectionResult(False, "Enter both a username and a password.", host)

    try:
        response = requests.get(
            f"{base_url}{PO_RESOURCE}",
            auth=HTTPBasicAuth(username.strip(), password),
            headers={"Accept": "application/json"},
            params={"limit": 1},
            timeout=(5, 20),
            allow_redirects=False,
            verify=True,
        )
    except requests.Timeout:
        return ConnectionResult(False, "Connection timed out. Check Oracle network access.", host)
    except requests.SSLError:
        return ConnectionResult(False, "TLS certificate verification failed.", host)
    except requests.RequestException:
        return ConnectionResult(False, "Cannot reach Oracle Fusion. Check the URL and network access.", host)

    if response.status_code == 401:
        return ConnectionResult(False, "Authentication failed (HTTP 401). Check credentials.", host)
    if response.status_code == 403:
        return ConnectionResult(
            False,
            "Access forbidden (HTTP 403). Check Procurement PO viewing roles and privileges.",
            host,
        )
    if response.status_code == 404:
        return ConnectionResult(
            False,
            "Purchase Orders REST endpoint not found (HTTP 404). Check the instance URL.",
            host,
        )
    if 300 <= response.status_code < 400:
        return ConnectionResult(
            False, "Oracle returned a redirect. Redirects are blocked for credential safety.", host
        )
    if response.status_code == 429:
        return ConnectionResult(False, "Oracle rate limit reached (HTTP 429). Try again later.", host)
    if response.status_code != 200:
        return ConnectionResult(
            False, f"Oracle returned HTTP {response.status_code}. Review API access.", host
        )

    try:
        payload = response.json()
    except ValueError:
        return ConnectionResult(
            False,
            "The endpoint responded with HTTP 200 but did not return valid JSON.",
            host,
        )

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return ConnectionResult(
            False,
            "The response does not match the Oracle purchaseOrders REST collection.",
            host,
        )
    return ConnectionResult(
        True,
        "Connection successful. Read-only Purchase Orders REST API is accessible.",
        host,
        len(payload["items"]),
    )
