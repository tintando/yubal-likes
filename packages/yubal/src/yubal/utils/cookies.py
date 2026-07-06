"""Cookie conversion utilities for ytmusicapi authentication.

Converts Netscape cookie format (used by yt-dlp) to ytmusicapi auth format.
"""

import hashlib
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Origin for SAPISIDHASH calculation
YTM_ORIGIN = "https://music.youtube.com"

# Essential cookies required for YouTube Music authentication.
# Browser cookie exports often include many unnecessary cookies that can cause
# HTTP 413 (Request Entity Too Large) errors. Only these are needed for auth.
ESSENTIAL_COOKIES = frozenset(
    {
        # Core auth cookies (SAPISID variants)
        "__Secure-3PAPISID",
        "__Secure-1PAPISID",
        "SAPISID",
        "APISID",
        # Session IDs
        "SID",
        "HSID",
        "SSID",
        "__Secure-1PSID",
        "__Secure-3PSID",
        # Session validation
        "SIDCC",
        "__Secure-1PSIDCC",
        "__Secure-3PSIDCC",
        # Session timestamps
        "__Secure-1PSIDTS",
        "__Secure-3PSIDTS",
        # Login info
        "LOGIN_INFO",
    }
)

# Minimum required cookies for authentication to work.
# If any of these are missing, auth will fail with "Sign in" response.
REQUIRED_AUTH_COOKIES = frozenset(
    {
        "SID",
        "HSID",
        "SSID",
    }
)

# Minimum number of essential cookies expected from a valid browser export.
# If fewer than this are found, the cookies may be from a non-authenticated session.
MIN_EXPECTED_COOKIES = 5


def parse_netscape_cookies(cookies_path: Path) -> dict[str, str]:
    """Parse Netscape format cookies.txt into a dict.

    Args:
        cookies_path: Path to cookies.txt file.

    Returns:
        Dict mapping cookie name to value.
    """
    cookies: dict[str, str] = {}

    try:
        content = cookies_path.read_text()
    except OSError as e:
        logger.warning("Failed to read cookies file: %s", e)
        return cookies

    for line in content.splitlines():
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Netscape format: domain, flag, path, secure, expiry, name, value
        parts = line.split("\t")
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            cookies[name] = value

    return cookies


def filter_essential_cookies(cookies: dict[str, str]) -> dict[str, str]:
    """Filter cookies to only those essential for YouTube Music authentication.

    Browser cookie exports often include many unnecessary cookies (tracking,
    preferences, etc.) that bloat the Cookie header. Large headers cause
    HTTP 413 errors from YouTube's servers.

    Args:
        cookies: Dict mapping cookie name to value.

    Returns:
        Dict containing only cookies required for authentication.
    """
    return {k: v for k, v in cookies.items() if k in ESSENTIAL_COOKIES}


def validate_auth_cookies(cookies: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate that cookies contain the minimum required for authentication.

    Args:
        cookies: Dict mapping cookie name to value.

    Returns:
        Tuple of (is_valid, list of missing required cookies).
    """
    missing = [name for name in REQUIRED_AUTH_COOKIES if name not in cookies]
    return len(missing) == 0, missing


def build_cookie_header(cookies: dict[str, str]) -> str:
    """Build Cookie header string from cookie dict.

    Args:
        cookies: Dict mapping cookie name to value.

    Returns:
        Cookie header string (name=value; name2=value2; ...).
    """
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def get_sapisid(cookies: dict[str, str]) -> str | None:
    """Extract SAPISID value from cookies.

    Tries __Secure-3PAPISID first (newer), then SAPISID (older).

    Args:
        cookies: Dict mapping cookie name to value.

    Returns:
        SAPISID value or None if not found.
    """
    return cookies.get("__Secure-3PAPISID") or cookies.get("SAPISID")


def generate_sapisidhash(sapisid: str, origin: str = YTM_ORIGIN) -> str:
    """Generate SAPISIDHASH authorization value.

    Algorithm reverse-engineered from YouTube's auth system.
    See: https://stackoverflow.com/a/32065323/5726546

    Args:
        sapisid: SAPISID cookie value.
        origin: Origin URL for the hash.

    Returns:
        SAPISIDHASH authorization header value.
    """
    timestamp = str(int(time.time()))
    hash_input = f"{timestamp} {sapisid} {origin}"
    # SECURITY NOTE: SHA-1 is required by YouTube's SAPISIDHASH authentication
    # protocol. This is YouTube's legacy auth system, not a choice we can change.
    # The hash is used for request signing, not password storage.
    sha1_hash = hashlib.sha1(hash_input.encode("utf-8")).hexdigest()
    return f"SAPISIDHASH {timestamp}_{sha1_hash}"


def cookies_to_ytmusic_auth(
    cookies_path: Path, authuser: str = "0"
) -> dict[str, str] | None:
    """Convert cookies.txt to ytmusicapi authentication headers.

    Args:
        cookies_path: Path to Netscape format cookies.txt file.
        authuser: Google account index when multiple accounts share cookies.
            Browser exports include session data for every signed-in account;
            this header tells YouTube which one to use ("0" = primary).

    Returns:
        Dict with auth headers for ytmusicapi, or None if auth not possible.
        The dict can be passed directly to YTMusic() constructor.
    """
    if not cookies_path.exists():
        logger.debug("Cookies file not found: %s", cookies_path)
        return None

    cookies = parse_netscape_cookies(cookies_path)
    if not cookies:
        logger.debug("No cookies parsed from file")
        return None

    sapisid = get_sapisid(cookies)
    if not sapisid:
        logger.warning("No SAPISID cookie found - authentication not possible")
        return None

    # Filter to essential cookies only to avoid HTTP 413 errors.
    # Browser exports can include 90KB+ of cookies, but YouTube's servers
    # reject requests with headers that large.
    filtered = filter_essential_cookies(cookies)
    logger.debug(
        "Filtered cookies from %d to %d for ytmusicapi auth",
        len(cookies),
        len(filtered),
    )

    # Validate that required session cookies are present
    is_valid, missing = validate_auth_cookies(filtered)
    if not is_valid:
        logger.warning(
            "Cookies may be incomplete - missing required cookies: %s. "
            "Authentication may fail. Please export cookies while logged into "
            "YouTube Music.",
            ", ".join(missing),
        )

    # Warn if very few essential cookies found (likely non-authenticated export)
    if len(filtered) < MIN_EXPECTED_COOKIES:
        logger.warning(
            "Only %d essential cookies found (expected at least %d). "
            "Cookies may have been exported from a non-authenticated session.",
            len(filtered),
            MIN_EXPECTED_COOKIES,
        )

    cookie_header = build_cookie_header(filtered)
    authorization = generate_sapisidhash(sapisid)

    # Return headers in the format ytmusicapi expects
    return {
        "accept": "*/*",
        "authorization": authorization,
        "content-type": "application/json",
        "x-goog-authuser": authuser,
        "x-origin": YTM_ORIGIN,
        "cookie": cookie_header,
    }


def list_authenticated_accounts(
    cookies_path: Path, max_authuser: int = 5
) -> list[dict[str, str | None]]:
    """Discover Google accounts available for the given cookies file.

    Probes ``x-goog-authuser`` indices 0..max_authuser-1 in parallel by
    calling ``YTMusic.get_account_info()`` for each one. Indices that respond
    with a valid account name are returned, deduplicated. The same browser
    cookies grant access to every account currently signed into that browser;
    the authuser header selects which one YouTube uses for a given request.

    Args:
        cookies_path: Path to Netscape format cookies.txt file.
        max_authuser: Number of indices to probe (0..max_authuser-1).

    Returns:
        List of dicts with keys ``authuser``, ``accountName``,
        ``channelHandle``, ``accountPhotoUrl``. Empty list if no account
        responds (e.g. cookies invalid).
    """
    # Local import to avoid pulling ytmusicapi for callers that only parse cookies.
    from concurrent.futures import ThreadPoolExecutor

    from ytmusicapi import YTMusic

    if cookies_to_ytmusic_auth(cookies_path) is None:
        return []

    def probe(index: int) -> dict[str, str | None] | None:
        auth = cookies_to_ytmusic_auth(cookies_path, authuser=str(index))
        if auth is None:
            return None
        try:
            info = YTMusic(auth=auth).get_account_info()
            name = info.get("accountName")
        except Exception as e:  # probing: any failure means "no account here"
            logger.debug("authuser=%d probe failed: %s", index, e)
            return None
        if not name:
            return None
        return {
            "authuser": str(index),
            "accountName": name,
            "channelHandle": info.get("channelHandle"),
            "accountPhotoUrl": info.get("accountPhotoUrl"),
        }

    with ThreadPoolExecutor(max_workers=max_authuser) as pool:
        results = pool.map(probe, range(max_authuser))

    # YouTube may answer with the default account for indices that don't
    # exist; keep only the lowest index for each distinct account.
    accounts: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for account in results:
        if account is None:
            continue
        key = (account["accountName"], account["channelHandle"])
        if key in seen:
            continue
        seen.add(key)
        accounts.append(account)
    return accounts


def is_authenticated_cookies(cookies_path: Path) -> bool:
    """Check if cookies file contains YouTube Music authentication.

    Args:
        cookies_path: Path to cookies.txt file.

    Returns:
        True if file exists and contains SAPISID cookie.
    """
    if not cookies_path.exists():
        return False

    cookies = parse_netscape_cookies(cookies_path)
    return get_sapisid(cookies) is not None
