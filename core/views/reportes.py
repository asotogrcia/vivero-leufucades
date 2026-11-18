from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.decorators import requiere_administradora
from core.models import Venta
from services.exportador import (
    NOMBRE_MESES,
    TZ_SANTIAGO,
    generar_reporte_ventas_xlsx,
    obtener_rango_periodo_santiago,
    obtener_ventas_periodo_qs,
)

XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)


def _parsear_entero_opcional(
    raw_val: str | None,
    minimo: int,
    maximo: int,
) -> int | None:
    """Convierte un parámetro GET en entero acotado o None si representa 'todos'."""
    texto = (raw_val or '').strip().lower()
    if not texto or texto == 'todos':
        return None
    try:
        valor = int(texto)
    except ValueError:
        return None
    if minimo <= valor <= maximo:
        return valor
    return None


@method_decorator(requiere_administradora, name='dispatch')
class ReporteExcelView(View):
    """Resumen mensual/histórico de ventas y exportación contable a Excel (.xlsx)."""

    template_name = 'reportes/reportes.html'

    def _obtener_anios_disponibles(self, anio_seleccionado: int | None) -> list[int]:
        anio_actual = timezone.now().astimezone(TZ_SANTIAGO).year
        anios = {anio_actual}
        for dt in Venta.objects.values_list('fecha_hora', flat=True).iterator(
            chunk_size=500
        ):
            anios.add(timezone.localtime(dt, TZ_SANTIAGO).year)
        if anio_seleccionado is not None:
            anios.add(anio_seleccionado)
        return sorted(anios, reverse=True)

    def get(self, request):
        mes_int = _parsear_entero_opcional(request.GET.get('mes'), 1, 12)
        anio_int = _parsear_entero_opcional(request.GET.get('anio'), 2000, 2100)

        if mes_int is not None and anio_int is None:
            anio_int = timezone.now().astimezone(TZ_SANTIAGO).year

        _, _, periodo_slug, etiqueta_periodo = obtener_rango_periodo_santiago(
            mes=mes_int,
            anio=anio_int,
        )

        descargar = request.GET.get('descargar', '').strip().lower()
        formato = request.GET.get('formato', '').strip().lower()
        if descargar in ('1', 'true', 'xlsx') or formato == 'xlsx':
            archivo_xlsx = generar_reporte_ventas_xlsx(mes=mes_int, anio=anio_int)
            filename = f'Reporte_Ventas_Vivero_{periodo_slug}.xlsx'
            response = HttpResponse(
                archivo_xlsx.getvalue(),
                content_type=XLSX_CONTENT_TYPE,
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        ventas_qs = obtener_ventas_periodo_qs(mes=mes_int, anio=anio_int)
        resumen = ventas_qs.aggregate(
            cantidad_ventas=Count('id_venta'),
            total_bruto=Coalesce(Sum('total_bruto'), 0),
            total_neto=Coalesce(Sum('total_neto'), 0),
            monto_iva=Coalesce(Sum('monto_iva'), 0),
        )

        context = {
            'ventas': ventas_qs,
            'resumen': resumen,
            'mes_seleccionado': mes_int,
            'anio_seleccionado': anio_int,
            'meses_choices': list(NOMBRE_MESES.items()),
            'anios_disponibles': self._obtener_anios_disponibles(anio_int),
            'etiqueta_periodo': etiqueta_periodo,
            'periodo_slug': periodo_slug,
        }
        return render(request, self.template_name, context)
