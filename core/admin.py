from django.contrib import admin

from .models import AuditoriaStock, DetalleVenta, Producto, Temporada, Venta


@admin.register(Temporada)
class TemporadaAdmin(admin.ModelAdmin):
    list_display = ('id_temporada', 'nombre', 'es_activa')
    list_filter = ('es_activa',)
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'sku',
        'nombre_comun',
        'id_temporada',
        'precio_unitario',
        'stock_actual',
        'stock_minimo',
        'es_fijo',
        'activo',
    )
    list_filter = ('activo', 'es_fijo', 'id_temporada')
    search_fields = ('sku', 'nombre_comun', 'nombre_cientifico')


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0
    readonly_fields = ('id_producto', 'cantidad', 'precio_unit_hist', 'subtotal')
    can_delete = False


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        'id_venta',
        'fecha_hora',
        'id_usuario',
        'metodo_pago',
        'total_neto',
        'monto_iva',
        'total_bruto',
        'idempotency_key',
    )
    list_filter = ('metodo_pago', 'fecha_hora')
    search_fields = ('id_venta', 'idempotency_key', 'id_usuario__username')
    readonly_fields = ('fecha_hora', 'idempotency_key')
    inlines = [DetalleVentaInline]


@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin):
    list_display = (
        'id_detalle',
        'id_venta',
        'id_producto',
        'cantidad',
        'precio_unit_hist',
        'subtotal',
    )
    search_fields = ('id_producto__nombre_comun', 'id_producto__sku')


@admin.register(AuditoriaStock)
class AuditoriaStockAdmin(admin.ModelAdmin):
    list_display = (
        'id_auditoria',
        'fecha_hora',
        'id_producto',
        'id_usuario',
        'stock_anterior',
        'stock_nuevo',
        'motivo_ajuste',
    )
    list_filter = ('fecha_hora', 'id_usuario')
    search_fields = ('id_producto__sku', 'id_producto__nombre_comun', 'motivo_ajuste')
    readonly_fields = (
        'id_auditoria',
        'id_producto',
        'id_usuario',
        'fecha_hora',
        'stock_anterior',
        'stock_nuevo',
        'motivo_ajuste',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
