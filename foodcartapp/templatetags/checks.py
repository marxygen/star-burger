from django import template

register = template.Library()


@register.filter
def isstring(value):
    return isinstance(value, str)


@register.filter
def is_nonempty_list(value):
    return isinstance(value, list) and value
