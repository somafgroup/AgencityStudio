from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]

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
                ],
                max_length=16,
            ),
        )
    ]
