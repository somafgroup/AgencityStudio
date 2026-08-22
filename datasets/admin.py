from django.contrib import admin

from .models import Dataset, DatasetColumn, DatasetVersion


class DatasetVersionInline(admin.TabularInline):
    model = DatasetVersion
    extra = 0
    can_delete = False
    fields = (
        "version_number",
        "import_status",
        "original_filename",
        "source_sha256",
        "row_count",
        "column_count",
        "created_at",
    )
    readonly_fields = fields
    show_change_link = True


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "current_version", "created_by", "updated_at")
    search_fields = ("name", "description", "project__name")
    list_select_related = ("project", "current_version", "created_by")
    readonly_fields = (
        "id",
        "project",
        "slug",
        "created_by",
        "current_version",
        "created_at",
        "updated_at",
    )
    inlines = (DatasetVersionInline,)

    def has_delete_permission(self, request, obj=None):
        """Require the Data Workspace service path so artifact cleanup cannot be bypassed."""
        return False


@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = (
        "dataset",
        "version_number",
        "import_status",
        "original_filename",
        "source_sha256",
        "created_at",
    )
    list_filter = ("import_status", "source_format", "source_kind")
    search_fields = ("dataset__name", "original_filename", "source_sha256")
    list_select_related = ("dataset", "created_by")
    readonly_fields = (
        "id",
        "dataset",
        "version_number",
        "source_kind",
        "source_format",
        "source_path",
        "original_filename",
        "source_size_bytes",
        "source_sha256",
        "media_type",
        "import_status",
        "importer_id",
        "importer_schema_version",
        "import_options",
        "detected_options",
        "inspection_generation",
        "row_count",
        "column_count",
        "inspection_summary",
        "quality_issues",
        "failure_summary",
        "created_by",
        "created_at",
        "processed_at",
        "confirmed_at",
        "confirmed_by",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        """DatasetVersion cleanup must go through the provenance-aware service layer."""
        return False


@admin.register(DatasetColumn)
class DatasetColumnAdmin(admin.ModelAdmin):
    list_display = ("dataset_version", "position", "display_name", "inferred_type", "role", "unit")
    list_filter = ("inferred_type", "role")
    search_fields = ("display_name", "source_name", "dataset_version__dataset__name")
    list_select_related = ("dataset_version", "dataset_version__dataset")
    readonly_fields = (
        "dataset_version",
        "position",
        "source_name",
        "display_name",
        "inferred_type",
        "missing_count",
        "non_numeric_count",
        "non_finite_count",
        "summary",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
