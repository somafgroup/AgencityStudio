from django.urls import path

from . import views

app_name = "workspaces"

urlpatterns = [
    path("", views.workspace_list, name="list"),
    path("new/", views.create_workspace, name="create"),
    path("invitations/<str:token>/", views.accept_invitation_view, name="accept-invitation"),
    path("<slug:slug>/", views.overview, name="overview"),
    path("<slug:slug>/activate/", views.activate_workspace, name="activate"),
    path("<slug:slug>/settings/", views.settings_view, name="settings"),
    path("<slug:slug>/members/", views.members, name="members"),
    path("<slug:slug>/members/invite/", views.invite, name="invite"),
    path("<slug:slug>/members/<int:membership_id>/role/", views.change_role, name="change-role"),
    path(
        "<slug:slug>/members/<int:membership_id>/remove/",
        views.remove_member_view,
        name="remove-member",
    ),
    path("<slug:slug>/leave/", views.leave_workspace, name="leave"),
    path(
        "<slug:slug>/invitations/<int:invitation_id>/revoke/",
        views.revoke_invitation_view,
        name="revoke-invitation",
    ),
    path("<slug:slug>/delete/", views.delete_workspace_view, name="delete"),
]
