from typing import Any

from app.integrations.base import BackendError, JsonHttpClient


class OpenSearchClient(JsonHttpClient):
    name = "opensearch"

    async def ping(self) -> None:
        health = await self.get_json("/_cluster/health")
        if health.get("status") == "red":
            raise BackendError(self.name, "cluster health is red")

    async def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        """Run a search. Raises ``NotFoundError`` if the index does not exist."""
        return await self.post_json(f"/{index}/_search", body)

    def doc_url(self, index: str, doc_id: str) -> str:
        return self.url(f"/{index}/_doc/{doc_id}")
