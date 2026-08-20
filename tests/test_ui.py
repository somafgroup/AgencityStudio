import pytest
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_and_primary_sections_render(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"Welcome to AgencityStudio" in response.content

    for name in ("projects", "datasets", "analyses", "compare", "reports", "examples", "advanced"):
        response = client.get(reverse(name))
        assert response.status_code == 200
        assert b"No placeholder scientific data has been fabricated" in response.content


def test_about_exposes_non_sensitive_versions(client):
    response = client.get(reverse("about"))
    assert response.status_code == 200
    assert b"AgencityStudio" in response.content
    assert b"AgencityLab" in response.content
    assert b"labbridge" in response.content


def test_custom_404_page_is_used(client):
    response = client.get("/this-route-does-not-exist/")
    assert response.status_code == 404
    assert b"Page not found" in response.content


def test_dev_ui_hidden_outside_debug(client):
    response = client.get(reverse("dev-ui"))
    assert response.status_code == 404


@override_settings(DEBUG=True)
def test_dev_ui_available_in_debug(client):
    response = client.get(reverse("dev-ui"))
    assert response.status_code == 200
    assert b"UI reference" in response.content


@pytest.mark.django_db
def test_system_status_partial_renders(client):
    response = client.get(reverse("system-status-partial"))
    assert response.status_code == 200
    assert b"System status" in response.content
