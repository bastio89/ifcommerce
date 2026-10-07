"""API-Key-Format und -Hashing (identisch zur Implementierung im Next.js-Dashboard).

Format:  dc_sk_<40 Zeichen Base62>   (Secret Key, Server-zu-Server)
         dc_pk_<40 Zeichen Base62>   (Publishable Key, Browser-Widget)

Gespeichert wird nur SHA-256(key) als Hex. Bei ~238 Bit Zufall ist ein
Brute-Force gegen den Hash ausgeschlossen; ein (langsamer) Passwort-Hash ist
daher nicht nötig und würde nur die Latenz jedes API-Calls erhöhen.
"""

from __future__ import annotations

import hashlib
import hmac
import re

from fastapi.security import APIKeyHeader

API_KEY_PATTERN = re.compile(r"^dc_(?P<kind>sk|pk)_[A-Za-z0-9]{40}$")
API_KEY_HEADER = APIKeyHeader(
    name="x-api-key",
    scheme_name="ApiKeyAuth",
    description="Secret API key (dc_sk_) or origin-bound publishable key (dc_pk_).",
    auto_error=False,
)


def looks_like_api_key(raw: str) -> bool:
    return API_KEY_PATTERN.fullmatch(raw) is not None


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
