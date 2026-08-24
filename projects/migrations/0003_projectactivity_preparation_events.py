from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_projectactivity_dataset_events"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectactivity",
            name="event",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"),
                    ("UPDATED", "Updated"),
                    ("ARCHIVED", "Archived"),
                    ("RESTORED", "Restored"),
                    ("DUPLICATED", "Duplicated"),
                    ("DATASET_CREATED", "Dataset created"),
                    ("DATASET_IMPORT", "Dataset import started"),
                    ("DATASET_READY", "Dataset ready"),
                    ("DATASET_FAILED", "Dataset import failed"),
                    ("DATASET_VERSION", "Dataset version added"),
                    ("DATASET_UPDATED", "Dataset updated"),
                    ("DATASET_DELETED", "Dataset deleted"),
                    ("PREP_CREATED", "Preparation created"),
                    ("PREP_STARTED", "Preparation started"),
                    ("PREP_READY", "Preparation completed"),
                    ("PREP_FAILED", "Preparation failed"),
                    ("PREP_DUPLICATED", "Preparation duplicated"),
                    ("PREP_DELETED", "Preparation deleted"),
                ],
                max_length=16,
            ),
        ),
    ]
