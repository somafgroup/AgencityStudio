# Generated for AgencityStudio Plan 9.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("analyses", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiagnosticRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("run_number", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("QUEUED", "Queued"),
                            ("RUNNING", "Running"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="QUEUED",
                        max_length=16,
                    ),
                ),
                ("canonical_result_sha256", models.CharField(max_length=64)),
                ("diagnostic_configuration", models.JSONField(default=dict)),
                ("diagnostic_api_identifiers", models.JSONField(default=list)),
                ("diagnostic_schema_version", models.CharField(default="1", max_length=16)),
                ("agencitylab_version", models.CharField(max_length=32)),
                ("studio_version", models.CharField(max_length=32)),
                ("python_version", models.CharField(max_length=64)),
                ("execution_fingerprint", models.CharField(max_length=64)),
                ("result_sha256", models.CharField(blank=True, max_length=64)),
                ("warnings", models.JSONField(blank=True, default=list)),
                (
                    "error_category",
                    models.CharField(
                        blank=True,
                        choices=[
                            (
                                "LAB_DIAGNOSTIC_VALIDATION_ERROR",
                                "AgencityLab diagnostic validation error",
                            ),
                            (
                                "LAB_DIAGNOSTIC_EXECUTION_ERROR",
                                "AgencityLab diagnostic execution error",
                            ),
                            ("RESULT_INPUT_ERROR", "Canonical result input error"),
                            ("STORAGE_ERROR", "Diagnostic result storage error"),
                            ("STUDIO_INTERNAL_ERROR", "Studio internal error"),
                        ],
                        max_length=48,
                    ),
                ),
                ("error_message", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("queued_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "analysis_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="diagnostic_runs",
                        to="analyses.analysisrun",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="diagnostic_runs_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-run_number"]},
        ),
        migrations.CreateModel(
            name="DiagnosticResultArtifact",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("storage_path", models.CharField(max_length=600, unique=True)),
                ("format", models.CharField(default="ZIP_JSON", max_length=32)),
                ("schema_version", models.CharField(default="1", max_length=16)),
                ("sha256", models.CharField(max_length=64)),
                ("size_bytes", models.BigIntegerField()),
                ("manifest", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "diagnostic_run",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="result_artifact",
                        to="analyses.diagnosticrun",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="diagnosticrun",
            constraint=models.UniqueConstraint(
                fields=("analysis_run", "run_number"),
                name="diagnostic_run_number_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="diagnosticrun",
            constraint=models.CheckConstraint(
                condition=models.Q(("run_number__gt", 0)),
                name="diagnostic_run_number_positive",
            ),
        ),
        migrations.AddIndex(
            model_name="diagnosticrun",
            index=models.Index(
                fields=["analysis_run", "-run_number"],
                name="diagnostic_run_order_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="diagnosticrun",
            index=models.Index(
                fields=["status", "-created_at"],
                name="diagnostic_run_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="diagnosticrun",
            index=models.Index(
                fields=["execution_fingerprint"],
                name="diagnostic_run_fp_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="diagnosticresultartifact",
            constraint=models.CheckConstraint(
                condition=models.Q(("size_bytes__gte", 0)),
                name="diagnostic_result_size_nonnegative",
            ),
        ),
    ]
