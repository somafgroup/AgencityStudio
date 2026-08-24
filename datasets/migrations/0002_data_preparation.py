import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("datasets", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataPreparation",
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
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("QUEUED", "Queued"),
                            ("PROCESSING", "Processing"),
                            ("READY", "Ready"),
                            ("FAILED", "Failed"),
                        ],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("recipe", models.JSONField(blank=True, default=list)),
                ("recipe_hash", models.CharField(blank=True, max_length=64)),
                ("engine_id", models.CharField(blank=True, max_length=80)),
                ("engine_version", models.CharField(blank=True, max_length=32)),
                ("studio_version", models.CharField(blank=True, max_length=32)),
                ("python_version", models.CharField(blank=True, max_length=64)),
                ("dependency_versions", models.JSONField(blank=True, default=dict)),
                ("execution_metadata", models.JSONField(blank=True, default=dict)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("failure_summary", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("queued_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="data_preparations_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="preparations",
                        to="datasets.datasetversion",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="datapreparation",
            index=models.Index(
                fields=["source_version", "status", "-created_at"],
                name="data_prep_source_status_idx",
            ),
        ),
        migrations.CreateModel(
            name="PreparedDataArtifact",
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
                ("output_format", models.CharField(default="CSV", max_length=16)),
                ("media_type", models.CharField(default="text/csv", max_length=160)),
                ("size_bytes", models.BigIntegerField()),
                ("prepared_sha256", models.CharField(max_length=64)),
                ("row_count", models.BigIntegerField()),
                ("column_count", models.PositiveIntegerField()),
                ("column_metadata", models.JSONField(default=list)),
                ("inspection_summary", models.JSONField(blank=True, default=dict)),
                ("quality_issues", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "preparation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifact",
                        to="datasets.datapreparation",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="prepareddataartifact",
            constraint=models.CheckConstraint(
                condition=models.Q(("size_bytes__gte", 0)),
                name="prepared_artifact_size_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="prepareddataartifact",
            constraint=models.CheckConstraint(
                condition=models.Q(("row_count__gte", 0)),
                name="prepared_artifact_rows_nonnegative",
            ),
        ),
    ]
