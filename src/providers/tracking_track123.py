from __future__ import annotations

from dataclasses import dataclass

import httpx


class Track123ClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class Track123TrackingUpdate:
    tracking_number: str
    carrier: str | None
    status: str | None
    location: str | None
    tracking_time: str | None
    payload: dict[str, object]


class Track123Client:
    def __init__(
        self,
        *,
        api_secret: str,
        base_url: str = "https://api.track123.com",
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_secret = api_secret.strip()
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def import_tracking(self, *, tracking_number: str, courier_code: str | None = None) -> dict[str, object]:
        payload: dict[str, object] = {"trackNo": tracking_number}
        if courier_code:
            payload["courierCode"] = courier_code
        return await self._post_json("/gateway/open-api/tk/v2/track/import", [payload], operation="track123_import")

    async def query_tracking(self, *, tracking_number: str, courier_code: str | None = None) -> Track123TrackingUpdate:
        payload = await self._post_json(
            "/gateway/open-api/tk/v2/track/query",
            {"trackNos": [tracking_number]},
            operation="track123_query",
        )
        return self.parse_tracking_update(payload, fallback_tracking_number=tracking_number, fallback_carrier=courier_code)

    async def _post_json(self, path: str, json_payload: object, *, operation: str) -> dict[str, object]:
        if not self.api_secret:
            raise Track123ClientError("Track123 API secret is not configured")
        try:
            response = await self._client.post(
                path,
                headers={
                    "Track123-Api-Secret": self.api_secret,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json=json_payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise Track123ClientError(f"{operation} request failed: {exc}") from exc
        try:
            parsed = response.json()
        except ValueError as exc:
            raise Track123ClientError(f"{operation} returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise Track123ClientError(f"{operation} returned non-object JSON")
        code = parsed.get("code")
        if code not in {None, "00000", 0, "0"}:
            message = parsed.get("message") or parsed.get("msg") or parsed.get("error") or "Track123 request failed"
            raise Track123ClientError(str(message))
        return parsed

    @classmethod
    def parse_tracking_update(
        cls,
        payload: dict[str, object],
        *,
        fallback_tracking_number: str,
        fallback_carrier: str | None = None,
    ) -> Track123TrackingUpdate:
        record = cls._first_tracking_record(payload)
        event = cls._latest_event(record)
        status = cls._first_text(
            event,
            record,
            keys=(
                "trackingDetail",
                "trackingInfo",
                "eventDetail",
                "description",
                "transitStatus",
                "trackingStatus",
                "status",
            ),
        )
        location = cls._first_text(
            event,
            record,
            keys=("location", "eventLocation", "trackingLocation", "checkpointLocation", "currentLocation"),
        )
        tracking_time = cls._first_text(
            event,
            record,
            keys=("trackingTime", "eventTime", "time", "lastTrackingTime", "updateTime", "deliveredTime"),
        )
        carrier = cls._carrier(record) or fallback_carrier
        tracking_number = cls._first_text(record, keys=("trackNo", "trackingNumber", "tracking_number")) or fallback_tracking_number
        return Track123TrackingUpdate(
            tracking_number=tracking_number,
            carrier=carrier,
            status=status,
            location=location,
            tracking_time=tracking_time,
            payload=payload,
        )

    @classmethod
    def _first_tracking_record(cls, payload: dict[str, object]) -> dict[str, object]:
        data = payload.get("data")
        candidates = [data, payload]
        for candidate in candidates:
            if isinstance(candidate, dict):
                accepted = candidate.get("accepted")
                if isinstance(accepted, dict):
                    content = accepted.get("content")
                    if isinstance(content, list):
                        first = next((item for item in content if isinstance(item, dict)), None)
                        if first is not None:
                            return first
                content = candidate.get("content")
                if isinstance(content, list):
                    first = next((item for item in content if isinstance(item, dict)), None)
                    if first is not None:
                        return first
                trackings = candidate.get("trackings")
                if isinstance(trackings, list):
                    first = next((item for item in trackings if isinstance(item, dict)), None)
                    if first is not None:
                        return first
        return {}

    @classmethod
    def _latest_event(cls, record: dict[str, object]) -> dict[str, object]:
        for key in ("trackInfo", "trackingDetails", "trackingItems", "events", "originInfo", "transitInfo"):
            value = record.get(key)
            if isinstance(value, list):
                first = next((item for item in value if isinstance(item, dict)), None)
                if first is not None:
                    return first
            if isinstance(value, dict):
                nested = cls._latest_event(value)
                if nested:
                    return nested
        return {}

    @staticmethod
    def _carrier(record: dict[str, object]) -> str | None:
        local = record.get("localLogisticsInfo")
        if isinstance(local, dict):
            for key in ("courierCode", "courierNameEN", "courierName"):
                value = str(local.get(key) or "").strip().lower()
                if value:
                    return value
        for key in ("courierCode", "carrierCode", "carrier"):
            value = str(record.get(key) or "").strip().lower()
            if value:
                return value
        return None

    @staticmethod
    def _first_text(*sources: dict[str, object], keys: tuple[str, ...]) -> str | None:
        for source in sources:
            for key in keys:
                value = str(source.get(key) or "").strip()
                if value:
                    return value
        return None
