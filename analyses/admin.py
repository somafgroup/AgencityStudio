from django.contrib import admin

from .models import Analysis, AnalysisResultArtifact, AnalysisRun, RunStatus


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
