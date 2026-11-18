from django import template

register = template.Library()


@register.filter
def clp(value) -> str:
    """Formatea un entero en Pesos Chilenos ($CLP) sin decimales."""
    try:
        monto = int(round(value or 0))
    except (TypeError, ValueError):
        return '$0'
    return f'${monto:,}'.replace(',', '.')
