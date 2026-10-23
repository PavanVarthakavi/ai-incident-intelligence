import math
from datetime import UTC, datetime

from pydantic import BaseModel

from app.integrations.base import BackendError, JsonHttpClient


class Series(BaseModel):
    labels: dict[str, str]
    points: list[tuple[datetime, float]]


class PrometheusClient(JsonHttpClient):
    name = "prometheus"

    async def ping(self) -> None:
        await self.request("GET", "/-/ready")

    async def query_range(
        self, promql: str, start: datetime, end: datetime, step_s: int
    ) -> list[Series]:
        body = await self.get_json(
            "/api/v1/query_range",
            params={
                "query": promql,
                "start": start.timestamp(),
                "end": end.timestamp(),
                "step": step_s,
            },
        )
        if body.get("status") != "success" or body["data"]["resultType"] != "matrix":
            raise BackendError(self.name, f"query failed: {body.get('error', 'unexpected result')}")
        return [
            Series(
                labels=item["metric"],
                points=[
                    (datetime.fromtimestamp(ts, UTC), float(value))
                    for ts, value in item["values"]
                    if math.isfinite(float(value))  # drop NaN/Inf (e.g. 0/0 ratios)
                ],
            )
            for item in body["data"]["result"]
        ]
