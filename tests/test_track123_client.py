from __future__ import annotations

import pytest
import httpx

from providers.tracking_track123 import Track123Client, Track123ClientError


@pytest.mark.asyncio
async def test_track123_client_imports_tracking_with_user_supplied_shape():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": "00000", "data": {"accepted": {"content": []}}})

    client = Track123Client(
        api_secret="secret-test",
        base_url="https://api.track123.test",
        transport=httpx.MockTransport(handler),
    )

    response = await client.import_tracking(tracking_number="771700723045", courier_code="fedex")
    await client.close()

    assert response["code"] == "00000"
    assert requests[0].url.path == "/gateway/open-api/tk/v2/track/import"
    assert requests[0].headers["Track123-Api-Secret"] == "secret-test"
    assert requests[0].read() == b'[{"trackNo":"771700723045","courierCode":"fedex"}]'


@pytest.mark.asyncio
async def test_track123_client_lists_couriers_with_user_supplied_shape():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"code": "00000", "data": [{"courierCode": "fedex", "courierName": "FedEx"}]},
        )

    client = Track123Client(
        api_secret="secret-test",
        base_url="https://api.track123.test",
        transport=httpx.MockTransport(handler),
    )

    response = await client.list_couriers()
    await client.close()

    assert response["code"] == "00000"
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/gateway/open-api/tk/v2.1/courier/list"
    assert requests[0].headers["Track123-Api-Secret"] == "secret-test"
    assert requests[0].headers["accept"] == "application/json"


@pytest.mark.asyncio
async def test_track123_client_retries_a0706_rate_limit(monkeypatch):
    monkeypatch.setattr(Track123Client, "_min_endpoint_interval_seconds", 0)
    monkeypatch.setattr(Track123Client, "_rate_limit_retry_delays", (0,))
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"code": "A0706", "message": "Too Many Requests"})
        return httpx.Response(
            200,
            json={
                "code": "00000",
                "data": {
                    "accepted": {
                        "content": [
                            {
                                "trackNo": "123123122222",
                                "transitStatus": "IN_TRANSIT",
                            }
                        ]
                    }
                },
            },
        )

    client = Track123Client(
        api_secret="secret-test",
        base_url="https://api.track123.test",
        transport=httpx.MockTransport(handler),
    )

    update = await client.query_tracking(tracking_number="123123122222", courier_code="fedex")
    await client.close()

    assert update.status == "in transit"
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_track123_client_reports_repeated_a0706_rate_limit(monkeypatch):
    monkeypatch.setattr(Track123Client, "_min_endpoint_interval_seconds", 0)
    monkeypatch.setattr(Track123Client, "_rate_limit_retry_delays", (0,))

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": "A0706", "message": "Too Many Requests"})

    client = Track123Client(
        api_secret="secret-test",
        base_url="https://api.track123.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(Track123ClientError, match="rate limited"):
        await client.list_couriers()
    await client.close()


@pytest.mark.asyncio
async def test_track123_client_queries_tracking_with_user_supplied_shape():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "code": "00000",
                "data": {
                    "accepted": {
                        "content": [
                            {
                                "trackNo": "123123122222",
                                "transitStatus": "IN_TRANSIT",
                            }
                        ]
                    }
                },
            },
        )

    client = Track123Client(
        api_secret="secret-test",
        base_url="https://api.track123.test",
        transport=httpx.MockTransport(handler),
    )

    update = await client.query_tracking(tracking_number="123123122222", courier_code="fedex")
    await client.close()

    assert update.tracking_number == "123123122222"
    assert update.status_code == "IN_TRANSIT"
    assert update.status == "in transit"
    assert requests[0].url.path == "/gateway/open-api/tk/v2/track/query"
    assert requests[0].headers["Track123-Api-Secret"] == "secret-test"
    assert requests[0].read() == b'{"trackNos":["123123122222"]}'


def test_track123_client_parses_tracking_update():
    update = Track123Client.parse_tracking_update(
        {
            "code": "00000",
            "data": {
                "accepted": {
                    "content": [
                        {
                            "trackNo": "398891812948",
                            "transitStatus": "DELIVERED",
                            "lastTrackingTime": "2026-02-26 10:41:14",
                            "localLogisticsInfo": {"courierCode": "fedex"},
                            "trackInfo": [
                                {
                                    "trackingDetail": "Delivered, Left in patio/carport.",
                                    "trackingTime": "2026-02-26 10:41:14",
                                    "location": "Lafayette, LA, US",
                                }
                            ],
                        }
                    ]
                }
            },
        },
        fallback_tracking_number="398891812948",
        fallback_carrier=None,
    )

    assert update.tracking_number == "398891812948"
    assert update.carrier == "fedex"
    assert update.status_code == "DELIVERED"
    assert update.status == "delivered"
    assert update.location == "Lafayette, LA, US"
