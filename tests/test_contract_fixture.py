"""The contract test that spans both repositories (ADR-0002 fase 2b).

`tests/fixtures/battery_inventory.json` is the shape AeroLink promises and the
shape AeroControl consumes. This side asserts the endpoint produces it; the
other side runs `manage.py sync_batteries --from-file` against the same file
(`apps/registry/test_x4b_battery_sync.py`).

That is what makes the contract verifiable **today**, with the `devices` table
empty and AeroLink two milestones away from real telemetry. If either side
drifts, one of the two suites goes red instead of the mismatch surfacing during
a deploy.

Serials are invented -- AGENTS.md forbids real ones in git.
"""

import json
from pathlib import Path

from aerolink.models import DeviceKind

FIXTURE = Path(__file__).parent / "fixtures" / "battery_inventory.json"
URL = "/api/v1/devices/"


def test_the_endpoint_reproduces_the_published_fixture(
    client, auth_headers, make_device
):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))

    for item in expected["results"]:
        metadata = {
            key: item[key]
            for key in ("cycle_count", "health_percent", "firmware_version")
            if key in item
        }
        if "aircraft_serial" in item:
            metadata["aircraft_serial"] = item["aircraft_serial"]
        make_device(
            serial=item["serial_number"],
            kind=DeviceKind.BATTERY,
            model=item.get("model"),
            status=item.get("status", "active"),
            metadata=metadata,
        )

    response = client.get(URL, params={"kind": "battery"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == expected
