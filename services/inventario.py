from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import AuditoriaStock, Producto, Temporada

TIPO_MOVIMIENTO_INGRESO = 'ingreso'
TIPO_MOVIMIENTO_MERMA = 'merma'


def _resolver_temporada(valor):
    """Acepta una instancia de Temporada, un ID entero o None."""
    if valor is None or valor == '':
        return None
    if isinstance(valor, Temporada):
        return valor
    return Temporada.objects.get(pk=int(valor))


def crear_o_actualizar_producto(datos, imagen, usuario, producto_id=None) -> Producto:
    """Crea o actualiza un producto de forma atómica optimizando su imagen a WebP.

    Si es creación y stock_actual > 0, registra el ingreso inicial en AuditoriaStock.
    Si es actualización y cambia stock_actual, registra la variación en AuditoriaStock.
    """
    with transaction.atomic():
        temporada = _resolver_temporada(datos.get('id_temporada'))
        es_fijo = bool(datos.get('es_fijo', False))

        if producto_id is None:
            stock_inicial = int(datos.get('stock_actual', 0))
            producto = Producto(
                sku=str(datos['sku']).strip(),
                id_temporada=temporada,
                nombre_comun=str(datos['nombre_comun']).strip(),
                nombre_cientifico=str(datos.get('nombre_cientifico', '') or '').strip(),
                precio_unitario=int(datos['precio_unitario']),
                stock_actual=stock_inicial,
                stock_minimo=int(datos.get('stock_minimo', 5)),
                es_fijo=es_fijo,
                descripcion_cuidados=str(datos.get('descripcion_cuidados', '') or '').strip(),
                activo=bool(datos.get('activo', True)),
            )
            if imagen is not None:
                producto.url_imagen = imagen
            producto.save()

            if stock_inicial > 0:
                AuditoriaStock.objects.create(
                    id_producto=producto,
                    id_usuario=usuario,
                    stock_anterior=0,
                    stock_nuevo=stock_inicial,
                    motivo_ajuste='[Ingreso Cosecha] Stock inicial al crear especie',
                )
            return producto

        producto = Producto.objects.select_for_update().filter(pk=producto_id).first()
        if producto is None:
            raise ValidationError('El producto especificado no existe.')

        stock_anterior = producto.stock_actual
        producto.sku = str(datos['sku']).strip()
        producto.id_temporada = temporada
        producto.nombre_comun = str(datos['nombre_comun']).strip()
        producto.nombre_cientifico = str(datos.get('nombre_cientifico', '') or '').strip()
        producto.precio_unitario = int(datos['precio_unitario'])
        producto.stock_minimo = int(datos.get('stock_minimo', producto.stock_minimo))
        producto.es_fijo = es_fijo
        producto.descripcion_cuidados = str(
            datos.get('descripcion_cuidados', '') or ''
        ).strip()
        if 'activo' in datos:
            producto.activo = bool(datos['activo'])

        nuevo_stock = (
            int(datos['stock_actual'])
            if 'stock_actual' in datos and datos['stock_actual'] is not None
            else stock_anterior
        )
        if nuevo_stock < 0:
            raise ValidationError('El stock actual no puede ser negativo.')
        producto.stock_actual = nuevo_stock

        if imagen is not None:
            producto.url_imagen = imagen

        producto.save()

        if nuevo_stock != stock_anterior:
            prefijo = '[Ingreso Cosecha]' if nuevo_stock > stock_anterior else '[Merma / Ajuste]'
            AuditoriaStock.objects.create(
                id_producto=producto,
                id_usuario=usuario,
                stock_anterior=stock_anterior,
                stock_nuevo=nuevo_stock,
                motivo_ajuste=f'{prefijo} Ajuste directo en edición de ficha',
            )

        return producto


def ajustar_stock_producto(
    producto_id: int,
    usuario,
    tipo_movimiento: str,
    cantidad: int,
    motivo: str,
) -> AuditoriaStock:
    """Ajusta el stock de un producto con bloqueo pesimista y auditoría inmutable."""
    try:
        cantidad_int = int(cantidad)
    except (TypeError, ValueError) as exc:
        raise ValidationError('La cantidad debe ser un número entero positivo.') from exc

    if cantidad_int <= 0:
        raise ValidationError('La cantidad del ajuste debe ser mayor a cero.')

    motivo_limpio = (motivo or '').strip()
    if not motivo_limpio:
        raise ValidationError('El motivo del ajuste es obligatorio.')

    tipo_norm = (tipo_movimiento or '').strip().lower()
    if tipo_norm not in (TIPO_MOVIMIENTO_INGRESO, TIPO_MOVIMIENTO_MERMA):
        raise ValidationError('Tipo de movimiento no válido.')

    with transaction.atomic():
        producto = Producto.objects.select_for_update().filter(pk=producto_id).first()
        if producto is None:
            raise ValidationError('El producto especificado no existe.')

        stock_anterior = producto.stock_actual
        if tipo_norm == TIPO_MOVIMIENTO_INGRESO:
            stock_nuevo = stock_anterior + cantidad_int
            prefijo = '[Ingreso Cosecha]'
        else:
            stock_nuevo = stock_anterior - cantidad_int
            if stock_nuevo < 0:
                raise ValidationError(
                    f'Stock insuficiente para {producto.nombre_comun}. '
                    f'Disponible: {stock_anterior} un.'
                )
            prefijo = '[Merma / Ajuste]'

        producto.stock_actual = stock_nuevo
        producto.save(update_fields=['stock_actual'])

        motivo_ajuste = f'{prefijo} {motivo_limpio}'[:255]
        return AuditoriaStock.objects.create(
            id_producto=producto,
            id_usuario=usuario,
            stock_anterior=stock_anterior,
            stock_nuevo=stock_nuevo,
            motivo_ajuste=motivo_ajuste,
        )


def desactivar_producto(producto_id: int) -> Producto:
    """Realiza borrado lógico (activo=False) de un producto dentro de una transacción."""
    with transaction.atomic():
        producto = Producto.objects.select_for_update().filter(pk=producto_id).first()
        if producto is None:
            raise ValidationError('El producto especificado no existe.')
        producto.activo = False
        producto.save(update_fields=['activo'])
        return producto


def activar_temporada_comercial(temporada_id: int) -> Temporada:
    """Desactiva todas las temporadas y activa únicamente la temporada indicada."""
    with transaction.atomic():
        temporada = Temporada.objects.select_for_update().filter(pk=temporada_id).first()
        if temporada is None:
            raise ValidationError('La temporada seleccionada no existe.')

        Temporada.objects.update(es_activa=False)
        Temporada.objects.filter(pk=temporada_id).update(es_activa=True)
        temporada.refresh_from_db()
        return temporada
