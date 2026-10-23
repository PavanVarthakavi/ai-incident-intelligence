from typing import Any

import httpx


class BackendError(Exception):
    """A backend could not be queried. The message is safe to show to users."""

    def __init__(self, backend: str, message: str) -> None:
        super().__init__(f"{backend}: {message}")
        self.backend = backend
        self.message = message


class NotFoundError(BackendError):
    """The requested resource (index, trace, ...) does not exist."""


class JsonHttpClient:
    """Shared request handling for JSON-over-HTTP backends."""

    name: str = "backend"

    def __init__(self, base_url: str, http: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        json: Any = None,
    ) -> httpx.Response:
        try:
            response = await self._http.request(method, self.url(path), params=params, json=json)
        except httpx.TimeoutException:
            raise BackendError(self.name, f"timed out calling {path}") from None
        except httpx.HTTPError as exc:
            raise BackendError(self.name, f"cannot reach {self.base_url}: {exc}") from None
        if response.status_code == 404:
            raise NotFoundError(self.name, f"{path} not found")
        if response.is_error:
            raise BackendError(
                self.name, f"{path} returned HTTP {response.status_code}: {response.text[:200]}"
            )
        return response

    async def get_json(self, path: str, **kwargs: Any) -> Any:
        return self._decode(await self.request("GET", path, **kwargs), path)

    async def post_json(self, path: str, body: Any) -> Any:
        return self._decode(await self.request("POST", path, json=body), path)

    def _decode(self, response: httpx.Response, path: str) -> Any:
        try:
            return response.json()
        except ValueError:
            raise BackendError(self.name, f"{path} returned invalid JSON") from None
