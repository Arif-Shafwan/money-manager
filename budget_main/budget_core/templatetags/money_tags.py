from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def ring(amount):
    # Return CSS ring color based on sign
    try:
        amount = float(amount)
    except:
        return ''
    if amount > 0: return 'ring-emerald-400'
    if amount < 0: return 'ring-rose-400'
    return 'ring-slate-300'

register = template.Library()

@register.filter
def add_class(field, css):
    return field.as_widget(attrs={**field.field.widget.attrs, 'class': css})

@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def sub(value, arg):
    try:
        return Decimal(value or 0) - Decimal(arg or 0)
    except Exception:
        try:
            return (float(value or 0) - float(arg or 0))
        except Exception:
            return 0