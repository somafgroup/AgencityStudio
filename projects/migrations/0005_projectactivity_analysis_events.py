from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0004_projectactivity_system_events")]

    operations = [
        migrations.AlterField(
            model_name="projectactivity",
            name="event",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"), ("UPDATED", "Updated"), ("ARCHIVED", "Archived"),
                    ("RESTORED", "Restored"), ("DUPLICATED", "Duplicated"),
                    ("DATASET_CREATED", "Dataset created"), ("DATASET_IMPORT", "Dataset import started"),
                    ("DATASET_READY", "Dataset ready"), ("DATASET_FAILED", "Dataset import failed"),
                    ("DATASET_VERSION", "Dataset version added"), ("DATASET_UPDATED", "Dataset updated"),
                    ("DATASET_DELETED", "Dataset deleted"), ("PREP_CREATED", "Preparation created"),
                    ("PREP_STARTED", "Preparation started"), ("PREP_READY", "Preparation completed"),
                    ("PREP_FAILED", "Preparation failed"), ("PREP_DUPLICATED", "Preparation duplicated"),
                    ("PREP_DELETED", "Preparation deleted"), ("SYS_CREATED", "System created"),
                    ("SYS_REVISED", "System revised"), ("SYS_DUPLICATED", "System duplicated"),
                    ("SYS_ARCHIVED", "System archived"), ("SYS_RESTORED", "System restored"),
                    ("SYS_DELETED", "System deleted"), ("ANALYSIS_CREATED", "Analysis created"),
                    ("ANALYSIS_UPDATED", "Analysis updated"), ("ANALYSIS_RUN_QUEUED", "Analysis run queued"),
                    ("ANALYSIS_RUN_COMPLETED", "Analysis run completed"), ("ANALYSIS_RUN_FAILED", "Analysis run failed"),
                    ("ANALYSIS_ARCHIVED", "Analysis archived"), ("ANALYSIS_DELETED", "Analysis deleted"),
                ],
                max_length=32,
            ),
        ),
    ]
