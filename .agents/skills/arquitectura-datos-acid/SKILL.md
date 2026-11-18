---
name: arquitectura-datos-acid
description: Implementa el modelo relacional 3FN en PostgreSQL, transacciones atómicas ACID, bloqueo pesimista select_for_update, cálculo de IVA DL 825 y bitácora de auditoría.
---
# Skill: Persistencia 3FN, Transacciones ACID y Tributación DL 825

## Cuándo aplicar
Al crear o modificar `models.py`, migraciones, `services/transaccion.py`, `services/tributario.py` o `services/inventario.py`.

## Especificación Exacta de Modelos (`models.py`)
1. `Temporada`:
   - `id_temporada = models.AutoField(primary_key=True)`
   - `nombre = models.CharField(max_length=50, unique=True)`
   - `es_activa = models.BooleanField(default=False)`
2. `Producto`:
   - `id_producto = models.AutoField(primary_key=True)`
   - `sku = models.CharField(max_length=20, unique=True)` (ej. `VIV-001`)
   - `id_temporada = models.ForeignKey(Temporada, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos')`
   - `nombre_comun = models.CharField(max_length=150, db_index=True)`
   - `nombre_cientifico = models.CharField(max_length=150, blank=True, default='')`
   - `precio_unitario = models.PositiveIntegerField()` (CheckConstraint `>= 0`)
   - `stock_actual = models.PositiveIntegerField(default=0)` (CheckConstraint `>= 0`)
   - `stock_minimo = models.PositiveIntegerField(default=5)`
   - `es_fijo = models.BooleanField(default=False)`
   - `descripcion_cuidados = models.TextField(blank=True, default='')`
   - `url_imagen = models.ImageField(upload_to='productos/', null=True, blank=True)`
   - `activo = models.BooleanField(default=True)`
3. `Venta`:
   - `id_venta = models.AutoField(primary_key=True)`
   - `id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)`
   - `fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)`
   - `total_bruto = models.PositiveIntegerField()`
   - `total_neto = models.PositiveIntegerField()`
   - `monto_iva = models.PositiveIntegerField()`
   - `metodo_pago = models.CharField(max_length=30, choices=[('Efectivo', 'Efectivo'), ('POS Tarjeta', 'POS Tarjeta'), ('Transferencia', 'Transferencia')])`
   - `idempotency_key = models.UUIDField(unique=True, editable=False)`
4. `DetalleVenta`:
   - `id_detalle = models.AutoField(primary_key=True)`
   - `id_venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')`
   - `id_producto = models.ForeignKey(Producto, on_delete=models.PROTECT)`
   - `cantidad = models.PositiveIntegerField()` (CheckConstraint `> 0`)
   - `precio_unit_hist = models.PositiveIntegerField()` (Congela el precio al instante de la venta)
   - `subtotal = models.PositiveIntegerField()`
5. `AuditoriaStock`:
   - `id_auditoria = models.AutoField(primary_key=True)`
   - `id_producto = models.ForeignKey(Producto, on_delete=models.PROTECT)`
   - `id_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)`
   - `fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)`
   - `stock_anterior = models.PositiveIntegerField()`
   - `stock_nuevo = models.PositiveIntegerField()`
   - `motivo_ajuste = models.CharField(max_length=255)`

## Reglas de Implementación en Servicios
- En `services/transaccion.py -> registrar_venta_meson(usuario, items, metodo_pago, idempotency_key)`:
  1. Verificar si `Venta.objects.filter(idempotency_key=idempotency_key).exists()`; si existe, retornarla inmediatamente.
  2. Abrir `with transaction.atomic():`.
  3. Obtener IDs ordenados ascendentemente para prevenir deadlocks y ejecutar `productos = {p.id_producto: p for p in Producto.objects.select_for_update().filter(id_producto__in=ids, activo=True).order_by('id_producto')}`.
  4. Validar que cada producto exista y que `producto.stock_actual >= cantidad`. Si no, lanzar `ValidationError(f"Stock insuficiente para {producto.nombre_comun}. Disponible: {producto.stock_actual}")`.
  5. Calcular `total_bruto = sum(p.precio_unitario * cant)`, `total_neto = round(total_bruto / 1.19)`, `monto_iva = total_bruto - total_neto`.
  6. Crear `Venta`, iterar creando `DetalleVenta`, actualizar `stock_actual` y crear el registro correspondiente en `AuditoriaStock` con motivo `f"Venta #{venta.id_venta}: Venta mesón ({metodo_pago})"`.