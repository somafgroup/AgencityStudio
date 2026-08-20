from django.urls import path

from common.views import health

urlpatterns = [
    path("health/", health, name="health"),
]
