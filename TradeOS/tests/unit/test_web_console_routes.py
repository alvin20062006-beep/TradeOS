from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def test_web_console_index_is_served() -> None:
    response = client.get("/console/")

    assert response.status_code == 200
    assert "TradeOS Web Console" in response.text
    assert "./assets/app.css" in response.text


def test_web_console_asset_is_served() -> None:
    response = client.get("/console/assets/app.js")

    assert response.status_code == 200
    assert "dashboardView" in response.text
    assert "dataSourcesView" in response.text
    assert "diagnosticsView" in response.text


def test_data_source_capabilities_route_exposes_boundaries() -> None:
    response = client.get("/api/v1/data-sources/capabilities")

    assert response.status_code == 200
    payload = response.json()
    statuses = {item["provider_id"]: item["status"] for item in payload["capabilities"]}
    assert statuses["yahoo_market"] == "REAL"
    assert statuses["intraday_bars_proxy"] == "PROXY"
    assert statuses["level2_orderbook"] == "PLACEHOLDER"


def test_data_source_profiles_route_returns_default_profile() -> None:
    response = client.get("/api/v1/data-sources/profiles")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_profile_id"] == "default-live"
    assert any(profile["profile_id"] == "default-live" for profile in payload["profiles"])


def test_placeholder_provider_test_never_reports_success() -> None:
    response = client.post(
        "/api/v1/data-sources/test",
        json={"provider_id": "level2_orderbook", "symbol": "AAPL"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"]["status"] == "PLACEHOLDER"
