# Generated for AgencityStudio Plan 11.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analyses", "0002_diagnostic_runs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="analysis",
            name="analysis_kind",
            field=models.CharField(
                choices=[
                    ("CANONICAL_SCALAR", "Canonical scalar"),
                    ("MULTIVARIATE", "Multivariate Agencity"),
                ],
                default="CANONICAL_SCALAR",
                max_length=32,
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
        migrations.CreateModel(
            name="AnalysisRunComponent",
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
                ("position", models.PositiveIntegerField()),
                ("source_column_identity", models.CharField(max_length=160)),
                ("source_column_position", models.PositiveIntegerField()),
                ("source_name", models.CharField(blank=True, max_length=255)),
                ("display_name", models.CharField(blank=True, max_length=255)),
                ("unit", models.CharField(blank=True, max_length=80)),
                ("parameter_snapshot", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "observable_definition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="multivariate_run_components",
                        to="systems.observabledefinition",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="components",
                        to="analyses.analysisrun",
                    ),
                ),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.AddConstraint(
            model_name="analysisruncomponent",
            constraint=models.UniqueConstraint(
                fields=("run", "position"),
                name="analysis_component_position_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="analysisruncomponent",
            constraint=models.CheckConstraint(
                condition=models.Q(("position__gt", 0)),
                name="analysis_component_position_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="analysisruncomponent",
            constraint=models.CheckConstraint(
                condition=models.Q(("source_column_position__gt", 0)),
                name="analysis_component_column_positive",
            ),
        ),
        migrations.AddIndex(
            model_name="analysisruncomponent",
            index=models.Index(
                fields=["run", "position"],
                name="analysis_component_order_idx",
            ),
        ),
    ]
