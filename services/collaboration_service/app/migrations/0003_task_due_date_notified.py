from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_task_workspacefile"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="due_date_notified",
            field=models.BooleanField(default=False),
        ),
    ]
