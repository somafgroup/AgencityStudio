from django.contrib import admin

from .models import SensitivityResultArtifact, SensitivityStudy


@admin.register(SensitivityStudy)
class SensitivityStudyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "analysis_run",
        "study_number",
        "study_type",
        "status",
        "agencitylab_version",
        "created_at",
    )
    list_filter = ("study_type", "status", "agencitylab_version")
    search_fields = ("id", "analysis_run__analysis__name", "execution_fingerprint")
    readonly_fields = (
        "analysis_run",
        "study_number",
        "study_type",
        "status",
        "canonical_result_sha256",
        "source_sha256",
        "system_revision",
        "system_configuration_fingerprint",
        "mapping_snapshot",
        "fixed_parameter_snapshot",
        "grid_type",
        "grid_unit",
        "requested_grid",
        "study_configuration",
        "public_api_identifier",
        "scientific_status",
        "agencitylab_version",
        "studio_version",
        "python_version",
        "execution_fingerprint",
        "result_sha256",
        "warnings",
        "error_category",
        "error_message",
        "created_by",
        "created_at",
        "queued_at",
        "started_at",
        "completed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SensitivityResultArtifact)
class SensitivityResultArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "study", "format", "schema_version", "size_bytes", "created_at")
    search_fields = ("id", "study__id", "sha256")
    readonly_fields = (
        "study",
        "storage_path",
        "format",
        "schema_version",
        "sha256",
        "size_bytes",
        "manifest",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
