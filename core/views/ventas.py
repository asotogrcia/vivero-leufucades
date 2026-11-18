import json
import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from core.decorators import requiere_operador_o_admin
from core.models import Producto, Venta
from services.transaccion import registrar_venta_meson

LEYENDA_CONTROL_INTERNO_SII = (
    'Comprobante de Control Interno — No Válido como Boleta Electrónica SII'
)


def _extraer_items_carrito(request) -> list[dict[str, int]]:
    """Extrae las líneas del carrito desde POST soportando JSON o arreglos de formulario."""
    for campo_json in ('items_json', 'carrito_json', 'items'):
        raw_json = request.POST.get(campo_json, '').strip()
        if raw_json:
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                raise ValidationError('El formato del carrito enviado no es válido.') from exc

            if isinstance(data, dict):
                return [
                    {'id_producto': int(k), 'cantidad': int(v)}
                    for k, v in data.items()
                ]
            if isinstance(data, list):
                return data
            raise ValidationError('El formato del carrito enviado no es válido.')

    ids_post = request.POST.getlist('id_producto') or request.POST.getlist('producto_id')
    cantidades_post = request.POST.getlist('cantidad')

    if ids_post and cantidades_post:
        if len(ids_post) != len(cantidades_post):
            raise ValidationError('Los productos y cantidades enviados no coinciden.')
        items_lista = []
        for raw_id, raw_cant in zip(ids_post, cantidades_post):
            try:
                cant_int = int(raw_cant)
                id_int = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    'Las cantidades e identificadores deben ser números enteros.'
                ) from exc
            if cant_int > 0:
                items_lista.append({'id_producto': id_int, 'cantidad': cant_int})
        return items_lista

    items_prefijo = []
    for key, value in request.POST.items():
        if key.startswith('cantidad_'):
            raw_id = key.replace('cantidad_', '', 1)
            try:
                id_int = int(raw_id)
                cant_int = int(value or 0)
            except (TypeError, ValueError):
                continue
            if cant_int > 0:
                items_prefijo.append({'id_producto': id_int, 'cantidad': cant_int})

    return items_prefijo


@method_decorator(requiere_operador_o_admin, name='dispatch')
class VentaMesonView(View):
    """Punto de Venta presencial en mesón (POS) con protección de idempotencia."""

    template_name = 'ventas/pos.html'

    def _obtener_productos_disponibles(self):
        return (
            Producto.objects.select_related('id_temporada')
            .filter(activo=True)
            .order_by('nombre_comun', 'sku')
        )

    def _build_context(
        self,
        idempotency_key=None,
        metodo_pago_seleccionado=Venta.METODO_EFECTIVO,
        error_message=None,
    ):
        return {
            'productos': self._obtener_productos_disponibles(),
            'idempotency_key': idempotency_key or uuid.uuid4(),
            'metodos_pago': Venta.METODOS_PAGO_CHOICES,
            'metodo_pago_seleccionado': metodo_pago_seleccionado,
            'error_message': error_message,
        }

    def get(self, request):
        return render(
            request,
            self.template_name,
            self._build_context(idempotency_key=uuid.uuid4()),
        )

    def post(self, request):
        metodo_pago = request.POST.get('metodo_pago', Venta.METODO_EFECTIVO).strip()
        idempotency_key = request.POST.get('idempotency_key', '').strip()

        try:
            items = _extraer_items_carrito(request)
            venta = registrar_venta_meson(
                usuario=request.user,
                items=items,
                metodo_pago=metodo_pago,
                idempotency_key=idempotency_key,
            )
            messages.success(
                request,
                f'Venta #{venta.id_venta} registrada exitosamente.',
            )
            return redirect(f'/ventas/comprobante/{venta.id_venta}/')
        except ValidationError as exc:
            if hasattr(exc, 'message') and exc.message:
                mensaje = exc.message
            elif hasattr(exc, 'messages') and exc.messages:
                mensaje = '; '.join(exc.messages)
            else:
                mensaje = str(exc)

            messages.error(request, mensaje)
            return render(
                request,
                self.template_name,
                self._build_context(
                    idempotency_key=uuid.uuid4(),
                    metodo_pago_seleccionado=metodo_pago or Venta.METODO_EFECTIVO,
                    error_message=mensaje,
                ),
            )


@method_decorator(requiere_operador_o_admin, name='dispatch')
class ComprobanteVentaView(View):
    """Comprobante digital de control interno para una venta registrada en mesón."""

    template_name = 'ventas/comprobante.html'

    def get(self, request, id_venta=None, id=None):
        folio_id = id_venta if id_venta is not None else id
        venta = get_object_or_404(
            Venta.objects.select_related('id_usuario').prefetch_related(
                'detalles__id_producto'
            ),
            pk=folio_id,
        )
        detalles = venta.detalles.all().order_by('id_detalle')

        return render(
            request,
            self.template_name,
            {
                'venta': venta,
                'detalles': detalles,
                'leyenda_sii': LEYENDA_CONTROL_INTERNO_SII,
            },
        )
