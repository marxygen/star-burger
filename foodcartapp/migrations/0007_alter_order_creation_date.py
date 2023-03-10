# Generated by Django 3.2.15 on 2023-02-21 11:30

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("foodcartapp", "0006_auto_20230221_1429"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="creation_date",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                verbose_name="Дата создания",
            ),
        ),
    ]
