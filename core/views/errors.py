from core.decorators import render_403


def error_403_view(request, exception=None):
    """Manejador global handler403 para PermissionDenied en DEBUG=True y DEBUG=False."""
    mensaje = str(exception).strip() if exception else ''
    return render_403(request, mensaje=mensaje)
