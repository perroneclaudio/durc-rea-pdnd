from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("durc", "0008_configurazioneregistroimprese_visuraregistroimprese"),
    ]

    operations = [
        migrations.AddField(
            model_name="durc",
            name="risposta_inps",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
