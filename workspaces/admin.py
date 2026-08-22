"""Django Admin views for workspace operators."""

from django.contrib import admin

from .models import Workspace, WorkspaceInvitation, WorkspaceMembership


class WorkspaceMembershipInline(admin.TabularInline):
    model = WorkspaceMembership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "slug", "created_at")
    list_filter = ("type",)
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("personal_owner",)
    inlines = (WorkspaceMembershipInline,)


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "joined_at")
    list_filter = ("role", "workspace__type")
    search_fields = ("user__email", "user__display_name", "workspace__name")
    autocomplete_fields = ("user", "workspace")
    readonly_fields = ("joined_at",)


@admin.register(WorkspaceInvitation)
class WorkspaceInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "workspace", "role", "status", "created_at", "expires_at")
    list_filter = ("status", "role")
    search_fields = ("email", "workspace__name")
    autocomplete_fields = ("workspace", "invited_by")
    readonly_fields = ("token_digest", "created_at", "accepted_at")
