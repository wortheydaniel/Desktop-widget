from __future__ import annotations

import json
import urllib.request

from . import APP_ID, __version__

USER_AGENT = f"{APP_ID}/{__version__} (desktop widget; +https://github.com/wortheydaniel/desktop-widget)"


def get(url: str, timeout: float = 12.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https only, fixed hosts/feeds)
        return resp.read(5_000_000)


def get_json(url: str, timeout: float = 12.0):
    return json.loads(get(url, timeout))
