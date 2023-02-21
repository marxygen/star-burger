from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.transaction import atomic
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from foodcartapp.models import OrderedItem, Order, Product


class OrderedItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        required=True, queryset=Product.objects.available()
    )
    quantity = serializers.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(1000)], required=True)

    class Meta:
        model = OrderedItem
        fields = ('product', 'quantity')


class OrderSerializer(serializers.ModelSerializer):
    products = OrderedItemSerializer(many=True, required=True, source="ordered_items", allow_empty=False)
    firstname = serializers.CharField(source="first_name", required=True)
    lastname = serializers.CharField(source="last_name", required=True)
    phonenumber = PhoneNumberField(source="phone_number", required=True)
    address = serializers.CharField(source="delivery_address", required=True)

    total_amount = serializers.FloatField()

    class Meta:
        model = Order
        fields = ("products", "firstname", "lastname", "phonenumber", "address", "id", "total_amount")
        read_only_fields = ("id", "total_amount", *fields)

    @atomic
    def create(self, validated_data):
        ordered_items_data = validated_data.pop("ordered_items")
        order = Order.objects.create(**validated_data)
        for entity in ordered_items_data:
            OrderedItem.objects.create(**entity, order=order)
        return order
