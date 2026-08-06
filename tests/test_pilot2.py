from aerolink.pilot2 import diagnostic_page


def test_diagnostic_page_only_embeds_a_complete_runtime_license() -> None:
    without_license = diagnostic_page(app_id="app-id")
    with_license = diagnostic_page("app-id", "app-key", "license")

    assert "const licenseConfig = null" in without_license.body.decode()
    assert '"appId": "app-id"' in with_license.body.decode()


def test_diagnostic_page_is_not_cacheable() -> None:
    response = diagnostic_page("app-id", "app-key", "license")

    assert response.headers["cache-control"] == "no-store"
