# Generated for AgencityStudio Plan 7.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("datasets", "0002_data_preparation"),
        ("projects", "0004_projectactivity_system_events"),
        ("systems", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Analysis",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("analysis_kind", models.CharField(choices=[("CANONICAL_SCALAR", "Canonical scalar")], default="CANONICAL_SCALAR", max_length=32)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")], default="ACTIVE", max_length=16)),
                ("draft_configuration", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analyses_created", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="analyses", to="projects.project")),
            ],
            options={"ordering": ["-updated_at", "name"]},
        ),
        migrations.CreateModel(
            name="AnalysisRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("run_number", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("QUEUED", "Queued"), ("RUNNING", "Running"), ("COMPLETED", "Completed"), ("FAILED", "Failed"), ("CANCELLED", "Cancelled")], default="QUEUED", max_length=16)),
                ("source_type", models.CharField(choices=[("RAW_DATASET_VERSION", "Original Dataset Version"), ("PREPARED_DATA", "Prepared Data")], max_length=32)),
                ("source_sha256", models.CharField(max_length=64)),
                ("source_snapshot", models.JSONField(default=dict)),
                ("mapping_snapshot", models.JSONField(default=dict)),
                ("system_configuration_fingerprint", models.CharField(blank=True, max_length=64)),
                ("parameter_snapshot", models.JSONField(default=dict)),
                ("analysis_options", models.JSONField(default=dict)),
                ("agencitylab_version", models.CharField(max_length=32)),
                ("studio_version", models.CharField(max_length=32)),
                ("python_version", models.CharField(max_length=64)),
                ("execution_fingerprint", models.CharField(max_length=64)),
                ("result_sha256", models.CharField(blank=True, max_length=64)),
                ("effective_context", models.JSONField(blank=True, default=dict)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("error_category", models.CharField(blank=True, choices=[("LAB_VALIDATION_ERROR", "AgencityLab validation error"), ("LAB_EXECUTION_ERROR", "AgencityLab execution error"), ("SOURCE_ERROR", "Source data error"), ("STORAGE_ERROR", "Result storage error"), ("STUDIO_INTERNAL_ERROR", "Studio internal error")], max_length=32)),
                ("error_message", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("queued_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="analyses.analysis")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analysis_runs_created", to=settings.AUTH_USER_MODEL)),
                ("source_dataset_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="analysis_runs", to="datasets.datasetversion")),
                ("source_prepared_artifact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="analysis_runs", to="datasets.prepareddataartifact")),
                ("system_observable", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="analysis_runs", to="systems.observabledefinition")),
                ("system_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="analysis_runs", to="systems.systemrevision")),
            ],
            options={"ordering": ["-run_number"]},
        ),
        migrations.CreateModel(
            name="AnalysisResultArtifact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("storage_path", models.CharField(max_length=600, unique=True)),
                ("format", models.CharField(default="ZIP_NPY_JSON", max_length=32)),
                ("schema_version", models.CharField(default="1", max_length=16)),
                ("sha256", models.CharField(max_length=64)),
                ("size_bytes", models.BigIntegerField()),
                ("manifest", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="result_artifact", to="analyses.analysisrun")),
            ],
        ),
        migrations.AddIndex(model_name="analysis", index=models.Index(fields=["project", "status", "-updated_at"], name="analysis_project_state_idx")),
        migrations.AddConstraint(model_name="analysisrun", constraint=models.UniqueConstraint(fields=("analysis", "run_number"), name="analysis_run_number_unique")),
        migrations.AddConstraint(model_name="analysisrun", constraint=models.CheckConstraint(condition=models.Q(("run_number__gt", 0)), name="analysis_run_number_positive")),
        migrations.AddConstraint(model_name="analysisrun", constraint=models.CheckConstraint(condition=models.Q(models.Q(("source_dataset_version__isnull", False), ("source_prepared_artifact__isnull", True)), models.Q(("source_dataset_version__isnull", True), ("source_prepared_artifact__isnull", False)), _connector="OR"), name="analysis_run_exactly_one_source")),
        migrations.AddIndex(model_name="analysisrun", index=models.Index(fields=["analysis", "-run_number"], name="analysis_run_order_idx")),
        migrations.AddIndex(model_name="analysisrun", index=models.Index(fields=["status", "-created_at"], name="analysis_run_status_idx")),
        migrations.AddIndex(model_name="analysisrun", index=models.Index(fields=["execution_fingerprint"], name="analysis_run_fingerprint_idx")),
        migrations.AddConstraint(model_name="analysisresultartifact", constraint=models.CheckConstraint(condition=models.Q(("size_bytes__gte", 0)), name="analysis_result_size_nonnegative")),
    ]
