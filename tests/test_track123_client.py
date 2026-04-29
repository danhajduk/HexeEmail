from __future__ import annotations

import pytest
import httpx

from providers.tracking_track123 import Track123Client


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
    assert update.status == "Delivered, Left in patio/carport."
    assert update.location == "Lafayette, LA, US"
