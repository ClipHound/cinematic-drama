from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="episode",
            name="thumbnail",
            field=models.ImageField(blank=True, upload_to="thumbnails/"),
        ),
    ]
