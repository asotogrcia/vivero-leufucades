from functools import wraps

from django.shortcuts import render

GRUPO_ADMINISTRADORA = 'Administradora General'
GRUPO_OPERADOR = 'Operador de Mesón'


def render_403(request, mensaje: str = ''):
    """Renderiza la vista personalizada HTTP 403 con diseño Botánico Minimalista."""
    return render(
        request,
        '403.html',
        {'mensaje': mensaje},
        status=403,
    )


def usuario_es_administradora(user) -> bool:
    """Retorna True si el usuario es superusuario o pertenece a Administradora General."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_ADMINISTRADORA).exists()


def usuario_es_operador_o_admin(user) -> bool:
    """Retorna True si el usuario pertenece a Administradora General u Operador de Mesón."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(
        name__in=[GRUPO_ADMINISTRADORA, GRUPO_OPERADOR]
    ).exists()


def requiere_administradora(view_func):
    """Restringe el acceso únicamente a Administradora General o superusuarios."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not usuario_es_administradora(request.user):
            return render_403(
                request,
                mensaje='Acceso denegado: Se requiere perfil de Administradora General.',
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def requiere_operador_o_admin(view_func):
    """Restringe el acceso a Administradora General u Operador de Mesón."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not usuario_es_operador_o_admin(request.user):
            return render_403(
                request,
                mensaje=(
                    'Acceso denegado: Se requiere perfil de Administradora General '
                    'o Operador de Mesón.'
                ),
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view
