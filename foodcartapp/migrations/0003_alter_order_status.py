# Generated by Django 3.2.15 on 2023-02-21 11:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("foodcartapp", "0002_alter_order_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("SUBMITTED", "В обработке"),
                    ("IN_PROGRESS", "Готовится"),
                    ("IN_DELIVERY", "Доставляется"),
                    ("DELIVERED", "Доставлен"),
                ],
                db_index=True,
                default="SUBMITTED",
                max_length=11,
                verbose_name="Статус заказа",
            ),
        ),
    ]
