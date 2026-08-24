from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0003_projectactivity_preparation_events"),
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
                    ("SYS_CREATED", "System created"),
                    ("SYS_REVISED", "System revised"),
                    ("SYS_DUPLICATED", "System duplicated"),
                    ("SYS_ARCHIVED", "System archived"),
                    ("SYS_RESTORED", "System restored"),
                    ("SYS_DELETED", "System deleted"),
                ],
                max_length=16,
            ),
        ),
    ]
