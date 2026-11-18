import re

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


@register.filter
def pildoras_horticolas(descripcion: str) -> list[dict]:
    """
    Extrae hasta 3 píldoras visuales de cuidado hortícola (Riego, Luz, Cosecha/Sustrato)
    desde el campo descripcion_cuidados.
    """
    texto = (descripcion or '').strip()
    if not texto:
        return [
            {'tipo': 'riego', 'etiqueta': 'Riego', 'valor': 'Según humedad'},
            {'tipo': 'luz', 'etiqueta': 'Luz', 'valor': 'Consultar en mesón'},
        ]

    patrones = [
        ('riego', 'Riego', r'Riego:\s*([^.]+)'),
        ('luz', 'Luz', r'Luz:\s*([^.]+)'),
        ('cosecha', 'Cosecha', r'Cosecha:\s*([^.]+)'),
        ('sustrato', 'Sustrato', r'Sustrato:\s*([^.]+)'),
    ]

    pildoras = []
    for tipo, etiqueta, patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            valor = match.group(1).strip()
            if len(valor) > 28:
                valor = valor[:25].rstrip() + '...'
            pildoras.append({'tipo': tipo, 'etiqueta': etiqueta, 'valor': valor})
        if len(pildoras) == 3:
            break

    if not pildoras:
        lower = texto.lower()
        luz_val = 'Pleno sol' if 'sol' in lower else ('Semisombra' if 'sombra' in lower else 'Luz filtrada')
        riego_val = 'Moderado' if 'moderado' in lower else ('Frecuente' if 'frecuente' in lower or 'húmedo' in lower else 'Regular')
        pildoras = [
            {'tipo': 'riego', 'etiqueta': 'Riego', 'valor': riego_val},
            {'tipo': 'luz', 'etiqueta': 'Luz', 'valor': luz_val},
            {'tipo': 'sustrato', 'etiqueta': 'Cultivo', 'valor': 'Región de Los Ríos'},
        ]

    return pildoras
