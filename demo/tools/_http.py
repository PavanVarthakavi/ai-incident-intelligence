"""Tiny JSON-over-HTTP helper (standard library only, so tools run without installs)."""

import json
import urllib.error
import urllib.request
from typing import Any


class HttpError(RuntimeError):
    pass


def request(method: str, url: str, body: Any = None, timeout: float = 5.0) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise HttpError(f"{method} {url} -> {exc.code}: {exc.read().decode()[:300]}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HttpError(f"{method} {url} failed: {exc}") from None
    return json.loads(payload) if payload else None
