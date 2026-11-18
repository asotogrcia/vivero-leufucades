from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q


class Temporada(models.Model):
    id_temporada = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    es_activa = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Temporada'
        verbose_name_plural = 'Temporadas'
        ordering = ['id_temporada']

    def __str__(self) -> str:
        estado = 'Activa' if self.es_activa else 'Inactiva'
        return f'{self.nombre} ({estado})'


class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    sku = models.CharField(max_length=20, unique=True)
    id_temporada = models.ForeignKey(
        Temporada,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos',
    )
    nombre_comun = models.CharField(max_length=150, db_index=True)
    nombre_cientifico = models.CharField(max_length=150, blank=True, default='')
    precio_unitario = models.PositiveIntegerField()
    stock_actual = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)
    es_fijo = models.BooleanField(default=False)
    descripcion_cuidados = models.TextField(blank=True, default='')
    url_imagen = models.ImageField(
        upload_to='productos/',
        null=True,
        blank=True,
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre_comun']
        constraints = [
            CheckConstraint(
                condition=Q(stock_actual__gte=0),
                name='chk_producto_stock_actual_gte_0',
            ),
            CheckConstraint(
                condition=Q(precio_unitario__gte=0),
                name='chk_producto_precio_unitario_gte_0',
            ),
        ]

    @property
    def es_stock_critico(self) -> bool:
        return self.stock_actual <= self.stock_minimo

    def __str__(self) -> str:
        return f'[{self.sku}] {self.nombre_comun} (${self.precio_unitario:,})'


class Venta(models.Model):
    METODO_EFECTIVO = 'Efectivo'
    METODO_POS_TARJETA = 'POS Tarjeta'
    METODO_TRANSFERENCIA = 'Transferencia'

    METODOS_PAGO_CHOICES = [
        (METODO_EFECTIVO, 'Efectivo'),
        (METODO_POS_TARJETA, 'POS Tarjeta'),
        (METODO_TRANSFERENCIA, 'Transferencia'),
    ]

    id_venta = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ventas',
    )
    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    total_bruto = models.PositiveIntegerField()
    total_neto = models.PositiveIntegerField()
    monto_iva = models.PositiveIntegerField()
    metodo_pago = models.CharField(
        max_length=30,
        choices=METODOS_PAGO_CHOICES,
    )
    idempotency_key = models.UUIDField(unique=True, editable=False)

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_hora']

    def __str__(self) -> str:
        return f'Venta #{self.id_venta} - ${self.total_bruto:,} ({self.metodo_pago})'


class DetalleVenta(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    id_venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name='detalles',
    )
    id_producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='detalles_venta',
    )
    cantidad = models.PositiveIntegerField()
    precio_unit_hist = models.PositiveIntegerField()
    subtotal = models.PositiveIntegerField()

    class Meta:
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalles de Venta'
        constraints = [
            CheckConstraint(
                condition=Q(cantidad__gt=0),
                name='chk_detalleventa_cantidad_gt_0',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.cantidad}x {self.id_producto.nombre_comun} (Venta #{self.id_venta_id})'


class AuditoriaStock(models.Model):
    id_auditoria = models.AutoField(primary_key=True)
    id_producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='auditorias',
    )
    id_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='auditorias_stock',
    )
    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    stock_anterior = models.PositiveIntegerField()
    stock_nuevo = models.PositiveIntegerField()
    motivo_ajuste = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Auditoría de Stock'
        verbose_name_plural = 'Auditorías de Stock'
        ordering = ['-fecha_hora']

    def __str__(self) -> str:
        return (
            f'Auditoría #{self.id_auditoria} - {self.id_producto.sku}: '
            f'{self.stock_anterior} -> {self.stock_nuevo} ({self.motivo_ajuste})'
        )
