from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.transaction import atomic
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from foodcartapp.models import OrderedItem, Order, Product, OrderStatus


class OrderedItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        required=True, queryset=Product.objects.available()
    )
    quantity = serializers.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1000)], required=True
    )

    class Meta:
        model = OrderedItem
        fields = ("product", "quantity")


class OrderSerializer(serializers.ModelSerializer):
    products = OrderedItemSerializer(
        many=True, required=True, source="ordered_items", allow_empty=False
    )
    firstname = serializers.CharField(source="first_name", required=True)
    lastname = serializers.CharField(source="last_name", required=True)
    phonenumber = PhoneNumberField(source="phone_number", required=True)
    address = serializers.CharField(source="delivery_address", required=True)
    # Probably would be good to allow the user to add comments, not just the administrator
    comment = serializers.CharField(required=False)

    total_amount = serializers.FloatField(read_only=True)
    status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = (
            "products",
            "firstname",
            "lastname",
            "phonenumber",
            "address",
            "id",
            "total_amount",
            "status",
            "comment",
            "creation_date",
            "call_date",
            "delivery_date"
        )
        read_only_fields = ("id", "total_amount", 'status', "creation_date", "call_date", "delivery_date")

    @atomic
    def create(self, validated_data):
        ordered_items_data = validated_data.pop("ordered_items")
        order = Order.objects.create(**validated_data)
        for entity in ordered_items_data:
            OrderedItem.objects.create(**entity, order=order)
        return order

    def get_status(self, instance: Order) -> str:
        return OrderStatus[instance.status].value
