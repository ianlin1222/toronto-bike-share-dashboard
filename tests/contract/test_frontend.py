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
    for name in ("maps.js", "maps.css", "dashboard-logic.js", "refinements.css",
                 "dashboard-analysis.js", "dashboard-analysis.css"):
        assert f"/assets/{name}" in page.text
        assert client.get(f"/assets/{name}").status_code == 200


def test_analytical_views_have_explanations_controls_and_inspectors():
    page = client.get("/dashboard").text
    assert 'href="#deeper-analysis"' in page
    assert 'id="analysis-minimum"' in page
    for name in ("distribution", "scatter", "daytype", "quality"):
        assert f'id="{name}-chart"' in page
    for name in ("distribution", "scatter", "daytypes", "quality"):
        assert f'data-analysis="{name}"' in page
    assert "not 100 independent samples" in page
    assert "Missing polls and quarantined records are outside this chart" in page


def test_finder_states_current_ranking_and_map_privacy():
    page = client.get("/demo")
    assert page.status_code == 200
    assert "Changing arrival time does not change" in page.text
    assert "external street-map services receive the viewed map area" in page.text
    assert "assessed at the same arrival time" not in page.text
