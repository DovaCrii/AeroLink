"""AL-107: the device inventory endpoint AeroControl mirrors."""

from aerolink.models import DeviceKind, Workspace

URL = "/api/v1/devices/"
BATTERY = {"kind": "battery"}


class TestAuthentication:
    def test_without_a_credential_it_refuses(self, client, configured_token):
        response = client.get(URL, params=BATTERY)

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Token"

    def test_a_wrong_credential_is_refused(self, client, configured_token):
        response = client.get(
            URL, params=BATTERY, headers={"Authorization": "Token nope"}
        )

        assert response.status_code == 401

    def test_the_right_credential_under_the_wrong_scheme_is_refused(
        self, client, configured_token
    ):
        response = client.get(
            URL,
            params=BATTERY,
            headers={"Authorization": f"Bearer {configured_token}"},
        )

        assert response.status_code == 401

    def test_with_no_token_configured_it_fails_closed(self, client, monkeypatch):
        """The most important test here. Not 401 -- that would send an operator
        to rotate a token that does not exist -- and above all not open. The
        consumer turns any non-200 into a loudly failed job."""
        from aerolink.config import get_settings

        monkeypatch.delenv("SERVICE_TOKEN", raising=False)
        monkeypatch.delenv("SERVICE_TOKEN_WORKSPACE", raising=False)
        get_settings.cache_clear()

        response = client.get(
            URL, params=BATTERY, headers={"Authorization": "Token anything"}
        )

        assert response.status_code == 503
        get_settings.cache_clear()

    def test_an_unresolvable_workspace_is_503_not_an_empty_list(
        self, client, auth_headers
    ):
        """An empty list would be indistinguishable from a genuinely empty
        inventory, and the consumer would mirror that quiet lie."""
        response = client.get(URL, params=BATTERY, headers=auth_headers)

        assert response.status_code == 503


class TestTheAircraftBoundary:
    def test_asking_for_aircraft_is_forbidden(self, client, auth_headers, workspace):
        """AL-R4 / ADR-0002 §3: the padrón is AeroControl's. This is that rule
        as an assertion instead of a paragraph."""
        response = client.get(URL, params={"kind": "aircraft"}, headers=auth_headers)

        assert response.status_code == 403
        assert "padr" in response.json()["detail"]

    def test_an_unknown_kind_is_rejected(self, client, auth_headers, workspace):
        response = client.get(URL, params={"kind": "banana"}, headers=auth_headers)

        assert response.status_code == 422

    def test_kind_is_required(self, client, auth_headers, workspace):
        """No default: returning everything would leak aircraft, and returning
        nothing would be a confusing silent success."""
        response = client.get(URL, headers=auth_headers)

        assert response.status_code == 422


class TestTheInventory:
    def test_returns_the_workspaces_batteries(self, client, auth_headers, make_device):
        make_device(
            serial="TB65-AAA",
            metadata={
                "cycle_count": 120,
                "health_percent": 93,
                "firmware_version": "03.00.05",
            },
        )

        response = client.get(URL, params=BATTERY, headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        item = body["results"][0]
        assert item["serial_number"] == "TB65-AAA"
        assert item["cycle_count"] == 120
        assert item["health_percent"] == 93
        assert item["firmware_version"] == "03.00.05"

    def test_another_workspace_is_not_visible(
        self, client, auth_headers, make_device, db_session
    ):
        other = Workspace(name="Otro", slug="otro")
        db_session.add(other)
        db_session.commit()
        make_device(serial="TB65-OTHER", in_workspace=other)

        response = client.get(URL, params=BATTERY, headers=auth_headers)

        assert response.json()["count"] == 0

    def test_only_the_requested_kind(self, client, auth_headers, make_device):
        make_device(serial="TB65-AAA")
        make_device(serial="PAY-1", kind=DeviceKind.PAYLOAD)

        response = client.get(URL, params=BATTERY, headers=auth_headers)

        assert [i["serial_number"] for i in response.json()["results"]] == ["TB65-AAA"]

    def test_an_empty_inventory_is_200_not_404(self, client, auth_headers, workspace):
        response = client.get(URL, params=BATTERY, headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == {"results": [], "count": 0}

    def test_the_body_is_not_cached(self, client, auth_headers, workspace):
        """It carries equipment serials."""
        response = client.get(URL, params=BATTERY, headers=auth_headers)

        assert response.headers["Cache-Control"] == "no-store"


class TestTheMapping:
    def _item(self, client, auth_headers):
        return client.get(URL, params=BATTERY, headers=auth_headers).json()["results"][
            0
        ]

    def test_serials_are_normalized(self, client, auth_headers, make_device):
        make_device(serial=" tb65 aaa ")

        assert self._item(client, auth_headers)["serial_number"] == "TB65AAA"

    def test_two_rows_normalizing_to_the_same_serial_yield_one_entry(
        self, client, auth_headers, make_device
    ):
        """Emitting both would let the consumer's last write win at random."""
        make_device(serial="TB65AAA")
        make_device(serial="tb65aaa")

        response = client.get(URL, params=BATTERY, headers=auth_headers)

        assert response.json()["count"] == 1

    def test_absent_optional_fields_are_omitted_not_null(
        self, client, auth_headers, make_device
    ):
        """The consumer reads an absent key as "AeroLink did not say" and keeps
        what it already knew."""
        make_device(serial="TB65-AAA", model=None)

        item = self._item(client, auth_headers)

        assert "cycle_count" not in item
        assert "model" not in item

    def test_an_unknown_status_is_omitted(self, client, auth_headers, make_device):
        make_device(serial="TB65-AAA", status="unknown")

        assert "status" not in self._item(client, auth_headers)

    def test_a_retired_status_maps_through(self, client, auth_headers, make_device):
        make_device(serial="TB65-AAA", status="decommissioned")

        assert self._item(client, auth_headers)["status"] == "retired"

    def test_values_of_the_wrong_type_are_dropped(
        self, client, auth_headers, make_device
    ):
        """AeroControl silently ignores a value of the wrong type, so passing
        "120" through would make the number vanish with no error anywhere."""
        make_device(
            serial="TB65-AAA",
            metadata={
                "cycle_count": "120",
                "health_percent": 150,
                "firmware_version": "  ",
            },
        )

        item = self._item(client, auth_headers)

        assert "cycle_count" not in item
        assert "health_percent" not in item
        assert "firmware_version" not in item

    def test_a_boolean_is_not_a_cycle_count(self, client, auth_headers, make_device):
        """`isinstance(True, int)` is True in Python, so an errant boolean would
        arrive as cycle_count=1 and look like real data."""
        make_device(serial="TB65-AAA", metadata={"cycle_count": True})

        assert "cycle_count" not in self._item(client, auth_headers)

    def test_a_negative_cycle_count_is_dropped(self, client, auth_headers, make_device):
        make_device(serial="TB65-AAA", metadata={"cycle_count": -1})

        assert "cycle_count" not in self._item(client, auth_headers)

    def test_the_aircraft_serial_is_normalized_too(
        self, client, auth_headers, make_device
    ):
        make_device(serial="TB65-AAA", metadata={"aircraft_serial": " air 9 "})

        assert self._item(client, auth_headers)["aircraft_serial"] == "AIR9"
