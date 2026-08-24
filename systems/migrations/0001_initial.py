# Generated for AgencityStudio Plan 6.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0003_projectactivity_preparation_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="System",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")], default="ACTIVE", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="systems_created", to=settings.AUTH_USER_MODEL)),
                ("duplicated_from", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="duplicates", to="systems.system")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="systems", to="projects.project")),
            ],
            options={"ordering": ["-updated_at", "name"]},
        ),
        migrations.CreateModel(
            name="SystemRevision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision_number", models.PositiveIntegerField()),
                ("documentation_status", models.CharField(choices=[("DRAFT", "Draft"), ("DOCUMENTED", "Documented")], default="DRAFT", max_length=16)),
                ("description", models.TextField(blank=True)),
                ("domain", models.CharField(blank=True, max_length=160)),
                ("system_type", models.CharField(blank=True, max_length=160)),
                ("mechanism", models.TextField(blank=True)),
                ("environment", models.CharField(blank=True, max_length=160)),
                ("measurement_context", models.TextField(blank=True)),
                ("scientific_notes", models.TextField(blank=True)),
                ("revision_reason", models.TextField(blank=True)),
                ("a_ref_value", models.FloatField(blank=True, null=True)),
                ("a_ref_value_text", models.CharField(blank=True, max_length=80)),
                ("a_ref_unit", models.CharField(blank=True, max_length=80)),
                ("a_ref_origin", models.CharField(blank=True, choices=[("PHYSICAL_MEASUREMENT", "Physical measurement"), ("CALIBRATION", "Calibration"), ("MANUFACTURER", "Manufacturer specification"), ("LITERATURE", "Scientific literature"), ("MODEL", "Model specification"), ("PROTOCOL", "Experimental protocol"), ("CONVENTION", "Convention"), ("OTHER", "Other")], max_length=32)),
                ("a_ref_origin_detail", models.CharField(blank=True, max_length=255)),
                ("a_ref_justification", models.TextField(blank=True)),
                ("tau_value", models.FloatField(blank=True, null=True)),
                ("tau_value_text", models.CharField(blank=True, max_length=80)),
                ("tau_unit", models.CharField(blank=True, max_length=80)),
                ("tau_origin", models.CharField(blank=True, choices=[("PHYSICAL_MEASUREMENT", "Physical measurement"), ("CALIBRATION", "Calibration"), ("MANUFACTURER", "Manufacturer specification"), ("LITERATURE", "Scientific literature"), ("MODEL", "Model specification"), ("PROTOCOL", "Experimental protocol"), ("CONVENTION", "Convention"), ("OTHER", "Other")], max_length=32)),
                ("tau_origin_detail", models.CharField(blank=True, max_length=255)),
                ("tau_justification", models.TextField(blank=True)),
                ("w_mode", models.CharField(choices=[("UNSPECIFIED", "Unspecified"), ("EXPLICIT", "Explicit")], default="UNSPECIFIED", max_length=16)),
                ("w_value", models.FloatField(blank=True, null=True)),
                ("w_value_text", models.CharField(blank=True, max_length=80)),
                ("w_unit", models.CharField(blank=True, max_length=80)),
                ("w_origin", models.CharField(blank=True, choices=[("PHYSICAL_MEASUREMENT", "Physical measurement"), ("CALIBRATION", "Calibration"), ("MANUFACTURER", "Manufacturer specification"), ("LITERATURE", "Scientific literature"), ("MODEL", "Model specification"), ("PROTOCOL", "Experimental protocol"), ("CONVENTION", "Convention"), ("OTHER", "Other")], max_length=32)),
                ("w_origin_detail", models.CharField(blank=True, max_length=255)),
                ("w_justification", models.TextField(blank=True)),
                ("p_c_mode", models.CharField(choices=[("FIXED", "Fixed scalar")], default="FIXED", max_length=16)),
                ("p_c_value", models.FloatField(blank=True, null=True)),
                ("p_c_value_text", models.CharField(blank=True, max_length=80)),
                ("p_c_unit", models.CharField(blank=True, max_length=80)),
                ("p_c_origin", models.CharField(blank=True, choices=[("PHYSICAL_MEASUREMENT", "Physical measurement"), ("CALIBRATION", "Calibration"), ("MANUFACTURER", "Manufacturer specification"), ("LITERATURE", "Scientific literature"), ("MODEL", "Model specification"), ("PROTOCOL", "Experimental protocol"), ("CONVENTION", "Convention"), ("OTHER", "Other")], max_length=32)),
                ("p_c_origin_detail", models.CharField(blank=True, max_length=255)),
                ("p_c_justification", models.TextField(blank=True)),
                ("configuration_fingerprint", models.CharField(blank=True, editable=False, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="system_revisions_created", to=settings.AUTH_USER_MODEL)),
                ("system", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="systems.system")),
            ],
            options={"ordering": ["-revision_number"]},
        ),
        migrations.CreateModel(
            name="ObservableDefinition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("position", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=180)),
                ("symbol", models.CharField(blank=True, max_length=80)),
                ("description", models.TextField(blank=True)),
                ("unit", models.CharField(blank=True, max_length=80)),
                ("observable_kind", models.CharField(blank=True, max_length=120)),
                ("nature", models.CharField(choices=[("MEASUREMENT", "Measurement"), ("SIMULATION", "Simulation"), ("DERIVED", "Derived physical quantity"), ("OTHER", "Other")], max_length=16)),
                ("source_description", models.TextField(blank=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("revision", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="observables", to="systems.systemrevision")),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.CreateModel(
            name="ScientificReference",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("citation", models.TextField()),
                ("doi", models.CharField(blank=True, max_length=255)),
                ("url", models.URLField(blank=True, max_length=500)),
                ("notes", models.TextField(blank=True)),
                ("supports_a_ref", models.BooleanField(default=False)),
                ("supports_tau", models.BooleanField(default=False)),
                ("supports_w", models.BooleanField(default=False)),
                ("supports_p_c", models.BooleanField(default=False)),
                ("revision", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="references", to="systems.systemrevision")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddField(
            model_name="system",
            name="current_revision",
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="systems.systemrevision"),
        ),
        migrations.AddConstraint(
            model_name="system",
            constraint=models.UniqueConstraint(fields=("project", "slug"), name="system_project_slug_unique"),
        ),
        migrations.AddIndex(
            model_name="system",
            index=models.Index(fields=["project", "status", "-updated_at"], name="system_project_state_idx"),
        ),
        migrations.AddConstraint(
            model_name="systemrevision",
            constraint=models.UniqueConstraint(fields=("system", "revision_number"), name="system_revision_number_unique"),
        ),
        migrations.AddConstraint(
            model_name="systemrevision",
            constraint=models.CheckConstraint(condition=models.Q(("revision_number__gt", 0)), name="system_revision_number_positive"),
        ),
        migrations.AddIndex(
            model_name="systemrevision",
            index=models.Index(fields=["system", "-revision_number"], name="system_revision_order_idx"),
        ),
        migrations.AddConstraint(
            model_name="observabledefinition",
            constraint=models.UniqueConstraint(fields=("revision", "position"), name="system_observable_position_unique"),
        ),
        migrations.AddConstraint(
            model_name="observabledefinition",
            constraint=models.UniqueConstraint(condition=models.Q(("is_primary", True)), fields=("revision",), name="system_single_primary_observable"),
        ),
    ]
