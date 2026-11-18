import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import AuditoriaStock, DetalleVenta, Producto, Venta

METODOS_PAGO_VALIDOS = {
    Venta.METODO_EFECTIVO,
    Venta.METODO_POS_TARJETA,
    Venta.METODO_TRANSFERENCIA,
}


def _normalizar_idempotency_key(idempotency_key) -> uuid.UUID:
    """Valida y convierte la clave de idempotencia a un objeto UUID."""
    if isinstance(idempotency_key, uuid.UUID):
        return idempotency_key
    try:
        return uuid.UUID(str(idempotency_key).strip())
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError(
            'La clave de idempotencia (idempotency_key) no tiene un formato UUID válido.'
        ) from exc


def _normalizar_items(items) -> dict[int, int]:
    """Valida y consolida las líneas del carro en un diccionario {id_producto: cantidad}.

    Acepta una lista de diccionarios ([{'id_producto': 1, 'cantidad': 2}, ...])
    o un diccionario ({1: 2}).
    """
    if not items:
        raise ValidationError('El carro de venta no puede estar vacío.')

    cantidades_por_id: dict[int, int] = {}

    if isinstance(items, dict):
        iterable = [
            {'id_producto': prod_id, 'cantidad': cant}
            for prod_id, cant in items.items()
        ]
    elif isinstance(items, (list, tuple)):
        iterable = items
    else:
        raise ValidationError('Formato de ítems de venta no válido.')

    for linea in iterable:
        if not isinstance(linea, dict):
            raise ValidationError('Cada ítem del carro debe ser un diccionario válido.')

        raw_id = linea.get('id_producto', linea.get('producto_id'))
        raw_cant = linea.get('cantidad')

        try:
            id_producto = int(raw_id)
            cantidad = int(raw_cant)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                'Los identificadores de producto y cantidades deben ser números enteros.'
            ) from exc

        if id_producto <= 0:
            raise ValidationError('Identificador de producto no válido.')
        if cantidad <= 0:
            raise ValidationError('La cantidad de cada producto debe ser mayor a cero.')

        cantidades_por_id[id_producto] = cantidades_por_id.get(id_producto, 0) + cantidad

    if not cantidades_por_id:
        raise ValidationError('El carro de venta no puede estar vacío.')

    return cantidades_por_id


def calcular_segregacion_iva_dl825(total_bruto: int) -> tuple[int, int]:
    """Calcula Monto Neto e IVA (19%) según Decreto Ley N.º 825 en pesos enteros."""
    total_bruto_int = int(total_bruto)
    total_neto = round(total_bruto_int / 1.19)
    monto_iva = total_bruto_int - total_neto
    return total_neto, monto_iva


def registrar_venta_meson(
    usuario,
    items,
    metodo_pago: str,
    idempotency_key,
) -> Venta:
    """Registra una venta presencial en mesón de forma atómica, idempotente y con bloqueo pesimista.

    1. Verifica idempotencia por `idempotency_key`. Si ya existe la venta, la retorna sin reprocesar.
    2. Abre `transaction.atomic()` y bloquea los productos en orden ascendente de `id_producto`.
    3. Valida existencia y stock disponible (`stock_actual >= cantidad`).
    4. Calcula desglose tributario DL 825 (`total_neto = round(total_bruto / 1.19)`).
    5. Crea `Venta`, `DetalleVenta` (congelando `precio_unit_hist`), descuenta `stock_actual`
       y registra cada movimiento en `AuditoriaStock`.
    """
    uuid_key = _normalizar_idempotency_key(idempotency_key)

    if Venta.objects.filter(idempotency_key=uuid_key).exists():
        return Venta.objects.get(idempotency_key=uuid_key)

    if usuario is None or not getattr(usuario, 'is_authenticated', False):
        raise ValidationError('Se requiere un operador autenticado para registrar la venta.')

    metodo_limpio = (metodo_pago or '').strip()
    if metodo_limpio not in METODOS_PAGO_VALIDOS:
        raise ValidationError('Selecciona un método de pago válido (Efectivo, POS Tarjeta o Transferencia).')

    cantidades_por_id = _normalizar_items(items)
    ids = sorted(cantidades_por_id.keys())

    with transaction.atomic():
        venta_existente = Venta.objects.filter(idempotency_key=uuid_key).first()
        if venta_existente is not None:
            return venta_existente

        productos_qs = (
            Producto.objects.select_for_update()
            .filter(id_producto__in=ids, activo=True)
            .order_by('id_producto')
        )
        productos = {p.id_producto: p for p in productos_qs}

        for id_prod in ids:
            producto = productos.get(id_prod)
            if producto is None:
                raise ValidationError(
                    f'El producto con ID #{id_prod} no existe o no se encuentra activo.'
                )
            cantidad_solicitada = cantidades_por_id[id_prod]
            if producto.stock_actual < cantidad_solicitada:
                raise ValidationError(
                    f'Stock insuficiente para {producto.nombre_comun}. '
                    f'Disponible: {producto.stock_actual}'
                )

        total_bruto = sum(
            productos[id_prod].precio_unitario * cantidades_por_id[id_prod]
            for id_prod in ids
        )
        total_neto = round(total_bruto / 1.19)
        monto_iva = total_bruto - total_neto

        venta = Venta.objects.create(
            id_usuario=usuario,
            total_bruto=total_bruto,
            total_neto=total_neto,
            monto_iva=monto_iva,
            metodo_pago=metodo_limpio,
            idempotency_key=uuid_key,
        )

        motivo_auditoria = f'Venta #{venta.id_venta}: Venta mesón ({metodo_limpio})'

        for id_prod in ids:
            producto = productos[id_prod]
            cantidad = cantidades_por_id[id_prod]
            precio_hist = producto.precio_unitario
            subtotal = precio_hist * cantidad

            DetalleVenta.objects.create(
                id_venta=venta,
                id_producto=producto,
                cantidad=cantidad,
                precio_unit_hist=precio_hist,
                subtotal=subtotal,
            )

            stock_anterior = producto.stock_actual
            stock_nuevo = stock_anterior - cantidad
            producto.stock_actual = stock_nuevo
            producto.save(update_fields=['stock_actual'])

            AuditoriaStock.objects.create(
                id_producto=producto,
                id_usuario=usuario,
                stock_anterior=stock_anterior,
                stock_nuevo=stock_nuevo,
                motivo_ajuste=motivo_auditoria,
            )

        return venta
