# Generated for AgencityStudio Plan 13.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analyses", "0003_multivariate_analysis"),
    ]

    operations = [
        migrations.AlterField(
            model_name="analysis",
            name="analysis_kind",
            field=models.CharField(
                choices=[
                    ("CANONICAL_SCALAR", "Canonical scalar"),
                    ("MULTIVARIATE", "Multivariate Agencity"),
                    ("OBSERVABLE_SPATIAL_FIELD", "Observable spatial Agencity field"),
                    ("RESEARCH_FIELD", "Research autonomous field"),
                ],
                default="CANONICAL_SCALAR",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="analysisrun",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("RAW_DATASET_VERSION", "Original Dataset Version"),
                    ("PREPARED_DATA", "Prepared Data"),
                    ("RESEARCH_FIELD_INPUT", "Immutable Research field input"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="analysisrun",
            name="system_revision",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="analysis_runs",
                to="systems.systemrevision",
            ),
        ),
        migrations.AlterField(
            model_name="analysisrun",
            name="system_observable",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="analysis_runs",
                to="systems.observabledefinition",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="analysisrun",
            name="analysis_run_exactly_one_source",
        ),
        migrations.AddConstraint(
            model_name="analysisrun",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        source_type="RESEARCH_FIELD_INPUT",
                        source_dataset_version__isnull=True,
                        source_prepared_artifact__isnull=True,
                    )
                    | (
                        ~models.Q(source_type="RESEARCH_FIELD_INPUT")
                        & (
                            models.Q(
                                source_dataset_version__isnull=False,
                                source_prepared_artifact__isnull=True,
                            )
                            | models.Q(
                                source_dataset_version__isnull=True,
                                source_prepared_artifact__isnull=False,
                            )
                        )
                    )
                ),
                name="analysis_run_source_contract",
            ),
        ),
        migrations.CreateModel(
            name="ResearchFieldInputArtifact",
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
                ("format", models.CharField(default="ZIP_NPY_JSON", max_length=32)),
                (
                    "schema_version",
                    models.CharField(default="research-input-v1", max_length=16),
                ),
                ("sha256", models.CharField(max_length=64)),
                ("size_bytes", models.BigIntegerField()),
                ("manifest", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="research_input_artifact",
                        to="analyses.analysisrun",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="researchfieldinputartifact",
            constraint=models.CheckConstraint(
                condition=models.Q(("size_bytes__gte", 0)),
                name="research_input_size_nonnegative",
            ),
        ),
    ]
