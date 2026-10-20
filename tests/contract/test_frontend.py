from fastapi.testclient import TestClient

from bikeshare.api.main import app

client = TestClient(app)


def test_dashboard_introduction_and_shared_assets_are_served():
    page = client.get("/dashboard")
    assert page.status_code == 200
    assert 'id="project-question"' in page.text
    assert "A good ride needs" in page.text
    assert 'id="ranking-minimum"' in page.text
    assert 'id="clear-station"' in page.text
    for name in ("maps.js", "maps.css", "dashboard-logic.js", "refinements.css"):
        assert f"/assets/{name}" in page.text
        assert client.get(f"/assets/{name}").status_code == 200


def test_finder_states_current_ranking_and_map_privacy():
    page = client.get("/demo")
    assert page.status_code == 200
    assert "Changing arrival time does not change" in page.text
    assert "external street-map services receive the viewed map area" in page.text
    assert "assessed at the same arrival time" not in page.text
