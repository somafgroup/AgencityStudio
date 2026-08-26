# Generated for AgencityStudio Plan 10.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("analyses", "0002_diagnostic_runs"),
        ("systems", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SensitivityStudy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("study_number", models.PositiveIntegerField()),
                ("study_type", models.CharField(choices=[("TAU_MULTISCALE", "Tau multiscale"), ("W_SENSITIVITY", "Window sensitivity")], max_length=32)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("QUEUED", "Queued"), ("RUNNING", "Running"), ("COMPLETED", "Completed"), ("FAILED", "Failed"), ("CANCELLED", "Cancelled")], default="QUEUED", max_length=16)),
                ("canonical_result_sha256", models.CharField(max_length=64)),
                ("source_sha256", models.CharField(max_length=64)),
                ("system_configuration_fingerprint", models.CharField(blank=True, max_length=64)),
                ("mapping_snapshot", models.JSONField(default=dict)),
                ("fixed_parameter_snapshot", models.JSONField(default=dict)),
                ("grid_type", models.CharField(choices=[("EXPLICIT", "Explicit list"), ("LINEAR", "Linear range"), ("LOG", "Logarithmic range")], max_length=16)),
                ("grid_unit", models.CharField(max_length=80)),
                ("requested_grid", models.JSONField(default=list)),
                ("study_configuration", models.JSONField(default=dict)),
                ("public_api_identifier", models.CharField(max_length=160)),
                ("scientific_status", models.CharField(default="SENSITIVITY_STUDY", max_length=64)),
                ("agencitylab_version", models.CharField(max_length=32)),
                ("studio_version", models.CharField(max_length=32)),
                ("python_version", models.CharField(max_length=64)),
                ("execution_fingerprint", models.CharField(max_length=64)),
                ("result_sha256", models.CharField(blank=True, max_length=64)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("error_category", models.CharField(blank=True, choices=[("LAB_SENSITIVITY_VALIDATION_ERROR", "AgencityLab sensitivity validation error"), ("LAB_SENSITIVITY_EXECUTION_ERROR", "AgencityLab sensitivity execution error"), ("RESULT_INPUT_ERROR", "Base run input error"), ("STORAGE_ERROR", "Sensitivity result storage error"), ("STUDIO_INTERNAL_ERROR", "Studio internal error")], max_length=48)),
                ("error_message", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("queued_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("analysis_run", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sensitivity_studies", to="analyses.analysisrun")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sensitivity_studies_created", to=settings.AUTH_USER_MODEL)),
                ("system_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sensitivity_studies", to="systems.systemrevision")),
            ],
            options={"ordering": ["-study_number"]},
        ),
        migrations.CreateModel(
            name="SensitivityResultArtifact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("storage_path", models.CharField(max_length=600, unique=True)),
                ("format", models.CharField(default="ZIP_NPY_JSON", max_length=32)),
                ("schema_version", models.CharField(default="1", max_length=16)),
                ("sha256", models.CharField(max_length=64)),
                ("size_bytes", models.BigIntegerField()),
                ("manifest", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("study", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="result_artifact", to="sensitivity.sensitivitystudy")),
            ],
        ),
        migrations.AddConstraint(
            model_name="sensitivitystudy",
            constraint=models.UniqueConstraint(fields=("analysis_run", "study_number"), name="sensitivity_study_number_unique"),
        ),
        migrations.AddConstraint(
            model_name="sensitivitystudy",
            constraint=models.CheckConstraint(condition=models.Q(("study_number__gt", 0)), name="sensitivity_study_number_positive"),
        ),
        migrations.AddIndex(
            model_name="sensitivitystudy",
            index=models.Index(fields=["analysis_run", "-study_number"], name="sensitivity_order_idx"),
        ),
        migrations.AddIndex(
            model_name="sensitivitystudy",
            index=models.Index(fields=["status", "-created_at"], name="sensitivity_status_idx"),
        ),
        migrations.AddIndex(
            model_name="sensitivitystudy",
            index=models.Index(fields=["execution_fingerprint"], name="sensitivity_fp_idx"),
        ),
        migrations.AddConstraint(
            model_name="sensitivityresultartifact",
            constraint=models.CheckConstraint(condition=models.Q(("size_bytes__gte", 0)), name="sensitivity_result_size_nonnegative"),
        ),
    ]
