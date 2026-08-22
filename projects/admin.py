"""Django Admin configuration for Projects and application activity."""

from django.contrib import admin

from .models import Project, ProjectActivity


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "status", "created_by", "created_at", "updated_at")
    list_filter = ("status", "workspace")
    search_fields = ("name", "description", "domain", "slug")
    readonly_fields = ("id", "slug", "created_at", "updated_at", "archived_at")
    list_select_related = ("workspace", "created_by")


@admin.register(ProjectActivity)
class ProjectActivityAdmin(admin.ModelAdmin):
    list_display = ("project", "event", "actor", "created_at")
    list_filter = ("event",)
    search_fields = ("project__name", "detail", "actor__email")
    readonly_fields = ("project", "event", "actor", "detail", "created_at")
    list_select_related = ("project", "actor")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
