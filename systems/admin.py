from django.contrib import admin

from .models import ObservableDefinition, ScientificReference, System, SystemRevision


@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "status", "current_revision", "created_by", "updated_at")
    list_filter = ("status", "project__workspace")
    search_fields = ("name", "description", "project__name")
    list_select_related = ("project", "project__workspace", "current_revision", "created_by")
    readonly_fields = ("id", "slug", "current_revision", "duplicated_from", "created_by", "created_at", "updated_at", "archived_at")


@admin.register(SystemRevision)
class SystemRevisionAdmin(admin.ModelAdmin):
    list_display = ("system", "revision_number", "documentation_status", "created_by", "created_at")
    list_filter = ("documentation_status",)
    search_fields = ("system__name", "domain", "system_type", "configuration_fingerprint")
    list_select_related = ("system", "system__project", "created_by")

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ObservableDefinition)
class ObservableDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "revision", "unit", "nature", "is_primary")
    list_filter = ("nature", "is_primary")
    search_fields = ("name", "symbol", "revision__system__name")
    list_select_related = ("revision", "revision__system")

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScientificReference)
class ScientificReferenceAdmin(admin.ModelAdmin):
    list_display = ("__str__", "revision", "doi", "url")
    search_fields = ("title", "citation", "doi", "revision__system__name")
    list_select_related = ("revision", "revision__system")

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
