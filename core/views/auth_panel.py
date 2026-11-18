from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from core.decorators import (
    requiere_operador_o_admin,
    usuario_es_operador_o_admin,
)
from core.models import AuditoriaStock, Producto, Temporada, Venta

TZ_SANTIAGO = ZoneInfo('America/Santiago')


class LoginViveroView(View):
    """Autenticación segura para el panel interno de Vivero Leufucades."""

    template_name = 'panel/login.html'

    def _get_redirect_url(self, request) -> str:
        next_url = request.POST.get('next') or request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url
        return '/panel/'

    def get(self, request):
        if usuario_es_operador_o_admin(request.user):
            return redirect('core:dashboard')
        return render(
            request,
            self.template_name,
            {'next': request.GET.get('next', '')},
        )

    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            return render(
                request,
                self.template_name,
                {
                    'error_message': 'Ingresa tu usuario y contraseña para continuar.',
                    'username_value': username,
                    'next': request.POST.get('next', ''),
                },
            )

        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active or not usuario_es_operador_o_admin(user):
            return render(
                request,
                self.template_name,
                {
                    'error_message': 'Usuario o contraseña incorrectos.',
                    'username_value': username,
                    'next': request.POST.get('next', ''),
                },
            )

        login(request, user)
        return redirect(self._get_redirect_url(request))


class LogoutViveroView(View):
    """Cierre de sesión exclusivo por POST con redirección al catálogo público."""

    http_method_names = ['post']

    def post(self, request):
        logout(request)
        return redirect('/')


@method_decorator(requiere_operador_o_admin, name='dispatch')
class DashboardOperacionalView(View):
    """Panel operacional con KPIs del día, alertas de stock crítico y auditoría reciente."""

    template_name = 'panel/dashboard.html'

    def get(self, request):
        ahora_santiago = timezone.now().astimezone(TZ_SANTIAGO)
        inicio_dia = ahora_santiago.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_dia = inicio_dia + timedelta(days=1)

        ventas_hoy = Venta.objects.filter(
            fecha_hora__gte=inicio_dia,
            fecha_hora__lt=fin_dia,
        ).aggregate(
            total_clp=Coalesce(Sum('total_bruto'), 0),
            cantidad_ventas=Count('id_venta'),
        )

        resumen_productos = Producto.objects.filter(activo=True).aggregate(
            total_especies_activas=Count('id_producto'),
            total_stock_critico=Count(
                'id_producto',
                filter=Q(stock_actual__lte=F('stock_minimo')),
            ),
            total_agotadas=Count(
                'id_producto',
                filter=Q(stock_actual=0),
            ),
        )

        productos_criticos = (
            Producto.objects.filter(
                activo=True,
                stock_actual__lte=F('stock_minimo'),
            )
            .select_related('id_temporada')
            .order_by('stock_actual', 'nombre_comun')
        )

        ultimas_auditorias = AuditoriaStock.objects.select_related(
            'id_producto',
            'id_usuario',
        ).order_by('-fecha_hora', '-id_auditoria')[:6]

        temporada_activa = Temporada.objects.filter(es_activa=True).first()

        context = {
            'fecha_hoy': ahora_santiago.date(),
            'ventas_hoy': ventas_hoy,
            'resumen_productos': resumen_productos,
            'productos_criticos': productos_criticos,
            'ultimas_auditorias': ultimas_auditorias,
            'temporada_activa': temporada_activa,
        }
        return render(request, self.template_name, context)
