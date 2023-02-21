import math
from collections import defaultdict
from typing import List
from geopy import distance
from django.utils import timezone
from enum import Enum

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum, F
from django.db.models.signals import pre_save
from django.dispatch import receiver
from phonenumber_field.modelfields import PhoneNumberField

from geocoder import resolve_location_for_address

DATETIME_FORMAT = "%H:%M:%S %d.%m.%Y"


class OrderStatus(Enum):
    SUBMITTED = "В обработке"
    IN_PROGRESS = "Готовится"
    IN_DELIVERY = "Доставляется"
    DELIVERED = "Доставлен"

    @classmethod
    def to_list(cls) -> list:
        return [(field.name, field.value) for field in cls]


class Restaurant(models.Model):
    name = models.CharField("название", max_length=50)
    address = models.CharField(
        "адрес",
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        "контактный телефон",
        max_length=50,
        blank=True,
    )
    latitude = models.DecimalField(
        decimal_places=5, max_digits=8, null=True, blank=True, verbose_name="Широта"
    )
    longitude = models.DecimalField(
        decimal_places=5, max_digits=8, null=True, blank=True, verbose_name="Долгота"
    )

    class Meta:
        verbose_name = "ресторан"
        verbose_name_plural = "рестораны"

    def __str__(self):
        return self.name

    def get_distance_to(self, address_lat: float, address_long: float) -> float | None:
        if not all([address_lat, address_long, self.latitude, self.longitude]):
            return None
        kms = distance.distance(
            (address_lat, address_long), (self.latitude, self.longitude)
        ).km
        if kms:
            return round(kms, 3)
        return None


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = RestaurantMenuItem.objects.filter(availability=True).values_list(
            "product"
        )
        return self.filter(pk__in=products)


class ProductCategory(models.Model):
    name = models.CharField("название", max_length=50)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField("название", max_length=50)
    category = models.ForeignKey(
        ProductCategory,
        verbose_name="категория",
        related_name="products",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        "цена", max_digits=8, decimal_places=2, validators=[MinValueValidator(0)]
    )
    image = models.ImageField("картинка")
    special_status = models.BooleanField(
        "спец.предложение",
        default=False,
        db_index=True,
    )
    description = models.TextField(
        "описание",
        max_length=200,
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"

    def __str__(self):
        return self.name


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name="menu_items",
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="menu_items",
        verbose_name="продукт",
    )
    availability = models.BooleanField("в продаже", default=True, db_index=True)

    class Meta:
        verbose_name = "пункт меню ресторана"
        verbose_name_plural = "пункты меню ресторана"
        unique_together = [["restaurant", "product"]]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"


class OrderQuerySet(models.QuerySet):
    """
    Calculates total order amount
    """

    def total_amount(self, exclude_delivered: bool = True):
        queryset = self
        if exclude_delivered:
            queryset = queryset.exclude(status=OrderStatus.DELIVERED.name)
        return queryset.annotate(
            total_amount=Sum(
                F("ordered_items__quantity") * F("ordered_items__product_price"),
                output_field=models.FloatField(),
            )
        )


class Order(models.Model):
    first_name = models.CharField(max_length=150, verbose_name="Имя")
    last_name = models.CharField(max_length=150, verbose_name="Фамилия")
    phone_number = PhoneNumberField(verbose_name="Номер телефона")
    delivery_address = models.TextField(verbose_name="Адрес доставки")
    status = models.CharField(
        choices=OrderStatus.to_list(),
        max_length=11,
        verbose_name="Статус заказа",
        default="SUBMITTED",
        db_index=True,
    )
    comment = models.TextField(blank=True, null=False, verbose_name="Комментарий")
    creation_date = models.DateTimeField(
        default=timezone.now, verbose_name="Дата создания", db_index=True
    )
    call_date = models.DateTimeField(verbose_name="Дата звонка", null=True, blank=True)
    delivery_date = models.DateTimeField(
        verbose_name="Дата доставки", null=True, blank=True
    )
    payment_type = models.CharField(
        verbose_name="Тип оплаты",
        choices=(
            ("CASH", "Наличными при доставке"),
            ("ONLINE", "On-line, при создании"),
        ),
        default="CASH",
        max_length=6,
        db_index=True,
    )
    executing_restaurant = models.ForeignKey(
        to=Restaurant,
        verbose_name="Ресторан, готовящий заказ",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    delivery_latitude = models.DecimalField(
        decimal_places=5,
        max_digits=8,
        null=True,
        blank=True,
        verbose_name="Широта адреса доставки",
    )
    delivery_longitude = models.DecimalField(
        decimal_places=5,
        max_digits=8,
        null=True,
        blank=True,
        verbose_name="Долгота адреса доставки",
    )

    def __str__(self):
        return (
            f"[{OrderStatus[self.status].value}] Заказ на {len(self.ordered_items.all())} позиций "
            f"от {self.first_name} {self.last_name} ({self.phone_number}), {self.delivery_address} "
            f"(создан {self.creation_date.strftime(DATETIME_FORMAT)})"
        )

    def get_matching_restaurants(
        self, order_by_remoteness: bool = True
    ) -> List[Restaurant]:
        """Return a list of restaurants that can fullfull this order"""
        products = [o.product for o in self.ordered_items.select_related().all()]
        menu_items = RestaurantMenuItem.objects.select_related().filter(
            availability=True
        )

        matching_restaurants = defaultdict(int)
        for menu_item in menu_items:
            if menu_item.product in products:
                matching_restaurants[menu_item.restaurant] += 1

        matching_restaurants = [
            restaurant
            for restaurant, available_products in matching_restaurants.items()
            if available_products == len(products)
        ]

        if order_by_remoteness:
            matching_restaurants = sorted(
                matching_restaurants,
                key=lambda restaurant: restaurant.get_distance_to(
                    self.delivery_latitude, self.delivery_longitude
                )
                or math.inf,
            )
        return matching_restaurants

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    objects = OrderQuerySet.as_manager()


class OrderedItem(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.DO_NOTHING, verbose_name="Товар"
    )
    quantity = models.IntegerField(
        verbose_name="Количество",
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
    )
    product_price = models.DecimalField(
        verbose_name="Цена товара",
        decimal_places=2,
        max_digits=6,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
    )
    order = models.ForeignKey(
        to=Order, related_name="ordered_items", on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.product}, {self.quantity} шт."

    class Meta:
        verbose_name = "Заказанный товар"
        verbose_name_plural = "Заказанные товары"


@receiver(signal=pre_save, sender=OrderedItem)
def update_ordered_item_price(sender, instance: OrderedItem, **kwargs):
    """Update price of an ordered item at the moment of creation"""
    if instance.id is None:
        # An instance is being created
        instance.product_price = instance.product.price * instance.quantity
    else:
        # Do not allow to change `product_price` field
        previous_product_price = OrderedItem.objects.get(id=instance.id).product_price
        if previous_product_price != instance.product_price:
            instance.product_price = previous_product_price


@receiver(signal=pre_save, sender=Restaurant)
def update_restaurant_location(sender, instance: Restaurant, **kwargs):
    previous_location = Restaurant.objects.get(id=instance.id)

    if previous_location.address != instance.address and instance.address:
        latitude, longitude = resolve_location_for_address(instance.address)
        if latitude and longitude:
            instance.latitude, instance.longitude = latitude, longitude


@receiver(signal=pre_save, sender=Order)
def update_order(sender, instance: Order, **kwargs):
    previous_order_instance = Order.objects.get(id=instance.id)

    # If `executing_restaurant` has been set to a value, set the order to be in progress
    if (
        previous_order_instance.executing_restaurant != instance.executing_restaurant
        and instance.executing_restaurant is not None
    ):
        instance.status = OrderStatus.IN_PROGRESS.name

    # Calculate distance if any of the addresses have been changed
    if (
        previous_order_instance.delivery_address != instance.delivery_address
        and instance.delivery_address
    ):
        latitude, longitude = resolve_location_for_address(instance.delivery_address)
        if latitude and longitude:
            instance.delivery_latitude, instance.delivery_longitude = (
                latitude,
                longitude,
            )
