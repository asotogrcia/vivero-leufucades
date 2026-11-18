from django.db.models import F

from core.decorators import (
    GRUPO_ADMINISTRADORA,
    GRUPO_OPERADOR,
    usuario_es_administradora,
    usuario_es_operador_o_admin,
)
from core.models import Producto, Temporada


def panel_context(request):
    """Expone datos de rol RBAC, temporada activa y conteo de stock crítico para el panel."""
    rutas_panel = ('/panel', '/inventario', '/ventas', '/pos', '/temporadas', '/reportes')
    if not request.path.startswith(rutas_panel):
        return {}

    user = getattr(request, 'user', None)
    es_admin = usuario_es_administradora(user) if user else False
    es_operador_admin = usuario_es_operador_o_admin(user) if user else False

    rol_usuario = ''
    if es_admin:
        rol_usuario = GRUPO_ADMINISTRADORA
    elif es_operador_admin:
        rol_usuario = GRUPO_OPERADOR

    temporada_activa = Temporada.objects.filter(es_activa=True).first()
    stock_critico_count = Producto.objects.filter(
        activo=True,
        stock_actual__lte=F('stock_minimo'),
    ).count()

    return {
        'es_administradora': es_admin,
        'es_operador_o_admin': es_operador_admin,
        'rol_usuario': rol_usuario,
        'temporada_activa': temporada_activa,
        'stock_critico_count': stock_critico_count,
    }
