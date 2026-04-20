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
