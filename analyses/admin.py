from django.contrib import admin

from .models import (
    Analysis,
    AnalysisResultArtifact,
    AnalysisRun,
    AnalysisRunComponent,
    DiagnosticResultArtifact,
    DiagnosticRun,
    RunStatus,
)


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "analysis_kind", "status", "updated_at")
    list_filter = ("analysis_kind", "status")
    search_fields = ("name", "project__name")
    readonly_fields = ("id", "created_by", "created_at", "updated_at")


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):
    list_display = ("analysis", "run_number", "status", "agencitylab_version", "created_at")
    list_filter = ("status", "source_type", "agencitylab_version")
    search_fields = ("id", "analysis__name", "execution_fingerprint", "source_sha256")

    def get_readonly_fields(self, request, obj=None):
        scientific = (
            "id", "analysis", "run_number", "source_type", "source_dataset_version",
            "source_prepared_artifact", "source_sha256", "source_snapshot", "mapping_snapshot",
            "system_revision", "system_observable", "system_configuration_fingerprint",
            "parameter_snapshot", "analysis_options", "agencitylab_version", "studio_version",
            "python_version", "execution_fingerprint", "result_sha256", "effective_context",
            "warnings", "created_by", "created_at", "queued_at", "started_at", "completed_at",
        )
        if obj and obj.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            return (*scientific, "status", "error_category", "error_message")
        return scientific

    def has_add_permission(self, request):
        return False


@admin.register(AnalysisRunComponent)
class AnalysisRunComponentAdmin(admin.ModelAdmin):
    list_display = ("run", "position", "observable_definition", "source_column_position")
    search_fields = (
        "run__id",
        "run__analysis__name",
        "observable_definition__name",
        "source_column_identity",
    )
    readonly_fields = (
        "id",
        "run",
        "position",
        "observable_definition",
        "source_column_identity",
        "source_column_position",
        "source_name",
        "display_name",
        "unit",
        "parameter_snapshot",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AnalysisResultArtifact)
class AnalysisResultArtifactAdmin(admin.ModelAdmin):
    list_display = ("run", "format", "schema_version", "size_bytes", "created_at")
    search_fields = ("run__id", "sha256", "storage_path")
    readonly_fields = (
        "id", "run", "storage_path", "format", "schema_version", "sha256", "size_bytes",
        "manifest", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DiagnosticRun)
class DiagnosticRunAdmin(admin.ModelAdmin):
    list_display = (
        "analysis_run",
        "run_number",
        "status",
        "agencitylab_version",
        "created_at",
    )
    list_filter = ("status", "agencitylab_version")
    search_fields = (
        "id",
        "analysis_run__analysis__name",
        "canonical_result_sha256",
        "execution_fingerprint",
    )

    def get_readonly_fields(self, request, obj=None):
        scientific = (
            "id",
            "analysis_run",
            "run_number",
            "canonical_result_sha256",
            "diagnostic_configuration",
            "diagnostic_api_identifiers",
            "diagnostic_schema_version",
            "agencitylab_version",
            "studio_version",
            "python_version",
            "execution_fingerprint",
            "result_sha256",
            "warnings",
            "created_by",
            "created_at",
            "queued_at",
            "started_at",
            "completed_at",
        )
        if obj and obj.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            return (*scientific, "status", "error_category", "error_message")
        return scientific

    def has_add_permission(self, request):
        return False


@admin.register(DiagnosticResultArtifact)
class DiagnosticResultArtifactAdmin(admin.ModelAdmin):
    list_display = (
        "diagnostic_run",
        "format",
        "schema_version",
        "size_bytes",
        "created_at",
    )
    search_fields = ("diagnostic_run__id", "sha256", "storage_path")
    readonly_fields = (
        "id",
        "diagnostic_run",
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
