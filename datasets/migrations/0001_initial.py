import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0002_projectactivity_dataset_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dataset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="datasets_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="datasets",
                        to="projects.project",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at", "name"]},
        ),
        migrations.CreateModel(
            name="DatasetVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version_number", models.PositiveIntegerField()),
                ("source_kind", models.CharField(choices=[("UPLOAD", "Upload"), ("PASTE", "Pasted data")], max_length=16)),
                ("source_format", models.CharField(choices=[("CSV", "CSV"), ("TSV", "TSV"), ("TXT", "Structured text"), ("XLSX", "XLSX")], max_length=16)),
                ("source_path", models.CharField(max_length=600, unique=True)),
                ("original_filename", models.CharField(max_length=255)),
                ("source_size_bytes", models.BigIntegerField()),
                ("source_sha256", models.CharField(max_length=64)),
                ("media_type", models.CharField(blank=True, max_length=160)),
                ("import_status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Inspecting"), ("READY", "Ready"), ("FAILED", "Failed")], default="PENDING", max_length=16)),
                ("importer_id", models.CharField(blank=True, max_length=64)),
                ("importer_schema_version", models.CharField(default="1", max_length=16)),
                ("import_options", models.JSONField(blank=True, default=dict)),
                ("detected_options", models.JSONField(blank=True, default=dict)),
                ("inspection_generation", models.PositiveIntegerField(default=1)),
                ("row_count", models.BigIntegerField(blank=True, null=True)),
                ("column_count", models.PositiveIntegerField(blank=True, null=True)),
                ("inspection_summary", models.JSONField(blank=True, default=dict)),
                ("quality_issues", models.JSONField(blank=True, default=list)),
                ("failure_summary", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dataset_versions_confirmed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dataset_versions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "dataset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="datasets.dataset",
                    ),
                ),
            ],
            options={"ordering": ["-version_number"]},
        ),
        migrations.AddField(
            model_name="dataset",
            name="current_version",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="datasets.datasetversion",
            ),
        ),
        migrations.CreateModel(
            name="DatasetColumn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(help_text="One-based source column position.")),
                ("source_name", models.CharField(blank=True, max_length=255)),
                ("display_name", models.CharField(max_length=255)),
                ("inferred_type", models.CharField(choices=[("NUMERIC", "Numeric"), ("DATETIME", "Date/time"), ("BOOLEAN", "Boolean"), ("TEXT", "Text"), ("MIXED", "Mixed"), ("EMPTY", "Empty")], max_length=16)),
                ("role", models.CharField(choices=[("OTHER", "Other"), ("TIME", "Time"), ("OBSERVABLE", "Observable")], default="OTHER", max_length=16)),
                ("unit", models.CharField(blank=True, max_length=80)),
                ("missing_count", models.BigIntegerField(default=0)),
                ("non_numeric_count", models.BigIntegerField(default=0)),
                ("non_finite_count", models.BigIntegerField(default=0)),
                ("summary", models.JSONField(blank=True, default=dict)),
                (
                    "dataset_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="columns",
                        to="datasets.datasetversion",
                    ),
                ),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.AddConstraint(
            model_name="dataset",
            constraint=models.UniqueConstraint(fields=("project", "slug"), name="dataset_project_slug_unique"),
        ),
        migrations.AddIndex(
            model_name="dataset",
            index=models.Index(fields=["project", "-updated_at"], name="dataset_project_updated_idx"),
        ),
        migrations.AddConstraint(
            model_name="datasetversion",
            constraint=models.UniqueConstraint(fields=("dataset", "version_number"), name="dataset_version_number_unique"),
        ),
        migrations.AddConstraint(
            model_name="datasetversion",
            constraint=models.CheckConstraint(condition=models.Q(("source_size_bytes__gte", 0)), name="dataset_version_size_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="datasetversion",
            index=models.Index(fields=["dataset", "-version_number"], name="dataset_version_order_idx"),
        ),
        migrations.AddIndex(
            model_name="datasetversion",
            index=models.Index(fields=["import_status", "-created_at"], name="dataset_import_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="datasetcolumn",
            constraint=models.UniqueConstraint(fields=("dataset_version", "position"), name="dataset_column_position_unique"),
        ),
        migrations.AddConstraint(
            model_name="datasetcolumn",
            constraint=models.UniqueConstraint(condition=models.Q(("role", "TIME")), fields=("dataset_version",), name="dataset_single_time_column"),
        ),
    ]
