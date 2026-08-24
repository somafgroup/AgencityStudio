from django.contrib import admin

from .models import (
    DataPreparation,
    Dataset,
    DatasetColumn,
    DatasetVersion,
    PreparedDataArtifact,
)


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


@admin.register(DataPreparation)
class DataPreparationAdmin(admin.ModelAdmin):
    list_display = ("name", "source_version", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "source_version__dataset__name", "recipe_hash")
    list_select_related = ("source_version", "source_version__dataset", "created_by")
    readonly_fields = (
        "id",
        "source_version",
        "status",
        "recipe",
        "recipe_hash",
        "engine_id",
        "engine_version",
        "studio_version",
        "python_version",
        "dependency_versions",
        "execution_metadata",
        "warnings",
        "failure_summary",
        "created_by",
        "created_at",
        "updated_at",
        "queued_at",
        "started_at",
        "finished_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PreparedDataArtifact)
class PreparedDataArtifactAdmin(admin.ModelAdmin):
    list_display = ("preparation", "prepared_sha256", "row_count", "column_count", "created_at")
    search_fields = ("preparation__name", "prepared_sha256")
    list_select_related = ("preparation", "preparation__source_version")
    readonly_fields = (
        "id",
        "preparation",
        "storage_path",
        "output_format",
        "media_type",
        "size_bytes",
        "prepared_sha256",
        "row_count",
        "column_count",
        "column_metadata",
        "inspection_summary",
        "quality_issues",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
