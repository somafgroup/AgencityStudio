from django.urls import reverse

from common import views


def test_health_endpoint(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "AgencityStudio"}


def test_readiness_reports_ready_dependencies(client, monkeypatch):
    monkeypatch.setattr(views, "_database_status", lambda: "available")
    monkeypatch.setattr(views, "_broker_status", lambda: "available")
    monkeypatch.setattr(views, "get_lab_version", lambda: "1.2.0")
    monkeypatch.setattr(views, "lab_is_compatible", lambda: True)

    response = client.get(reverse("readiness"))

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"]["agencitylab"] == {
        "status": "compatible",
        "version": "1.2.0",
    }


def test_readiness_fails_when_broker_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(views, "_database_status", lambda: "available")
    monkeypatch.setattr(views, "_broker_status", lambda: "unavailable")
    monkeypatch.setattr(views, "get_lab_version", lambda: "1.2.0")
    monkeypatch.setattr(views, "lab_is_compatible", lambda: True)

    response = client.get(reverse("readiness"))

    assert response.status_code == 503
    assert response.json()["status"] == "not-ready"
    assert response.json()["dependencies"]["broker"] == "unavailable"
