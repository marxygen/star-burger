from django.db.transaction import atomic
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from foodcartapp.models import OrderedItem, Order, Product


class OrderedItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        required=True, queryset=Product.objects.available()
    )

    class Meta:
        model = OrderedItem
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    products = OrderedItemSerializer(many=True, required=True, source="ordered_items")
    firstname = serializers.CharField(source="first_name", required=True)
    lastname = serializers.CharField(source="last_name", required=True)
    phonenumber = PhoneNumberField(source="phone_number", required=True)
    address = serializers.CharField(source="delivery_address", required=True)

    class Meta:
        model = Order
        fields = ("products", "firstname", "lastname", "phonenumber", "address")

    @atomic
    def create(self, validated_data):
        ordered_items = [
            OrderedItem.objects.create(**entity)
            for entity in validated_data.pop("ordered_items")
        ]
        order = Order.objects.create(**validated_data)
        order.ordered_items.set(ordered_items)
        return order
