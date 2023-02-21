from typing import Tuple
import requests

from django.conf import settings


def resolve_location_for_address(address: str) -> Tuple[float, float] | None:
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(
        base_url,
        params={
            "geocode": address,
            "apikey": settings.YANDEX_API_KEY,
            "format": "json",
        },
    )
    if not response.ok:
        return None

    found_places = response.json()["response"]["GeoObjectCollection"]["featureMember"]

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant["GeoObject"]["Point"]["pos"].split(" ")
    return lon, lat
