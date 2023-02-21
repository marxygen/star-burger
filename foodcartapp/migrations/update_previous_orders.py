from django.db import migrations


def update_previous_orders(apps, schema_editor):
    OrderedItem = apps.get_model("foodcartapp", "OrderedItem")
    for ordered_item in OrderedItem.objects.all():
        ordered_item.product_price = ordered_item.quantity * ordered_item.product.price
        ordered_item.save()


class Migration(migrations.Migration):

    dependencies = [
        ("foodcartapp", "0040_ordereditem_product_price"),
    ]

    operations = [
        migrations.RunPython(update_previous_orders),
    ]
