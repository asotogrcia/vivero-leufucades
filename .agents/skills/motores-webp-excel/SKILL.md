---
name: motores-webp-excel
description: Implementa la compresión automática de imágenes botánicas a formato WebP con Pillow (< 120 KB) y la generación de reportes mensuales contables .xlsx en memoria con openpyxl.
---
# Skill: Procesamiento Multimedia WebP y Exportación Contable Excel

## Cuándo aplicar
Al implementar subida de fotografías de productos (`services/media_webp.py`) o el módulo de reportería mensual (`services/exportador.py` y `views/reportes.py`).

## 1. Compresión WebP (`services/media_webp.py`)
- Función `optimizar_imagen_webp(archivo_imagen) -> ContentFile`:
  1. Abrir con `Image.open(archivo_imagen)` y ejecutar `img.verify()` (reabrir después de verify) para descartar archivos corruptos o maliciosos.
  2. Convertir modo de color: si `img.mode in ('RGBA', 'P')` convertir a `'RGBA'`, de lo contrario `'RGB'`.
  3. Redimensionar manteniendo relación de aspecto si `img.width > 800`: calcular `nuevo_alto = int((800 / img.width) * img.height)` y aplicar `img.resize((800, nuevo_alto), Image.Resampling.LANCZOS)`.
  4. Guardar en `buffer = io.BytesIO()` con `img.save(buffer, format='WEBP', quality=80, method=6)`.
  5. Si `buffer.tell() > 120 * 1024`, recomprimir con `quality=65`.
  6. Retornar `ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex[:12]}.webp")`.

## 2. Exportación Contable Excel (`services/exportador.py`)
- Función `generar_reporte_ventas_xlsx(mes: int | None, anio: int | None) -> io.BytesIO`:
  1. Filtrar `Venta.objects.select_related('id_usuario').order_by('fecha_hora')`. Si se indican `mes` y `anio`, filtrar en zona horaria local `America/Santiago`.
  2. Crear `wb = openpyxl.Workbook()` y `ws = wb.active` (`ws.title = "Ventas Vivero"`).
  3. Escribir encabezado corporativo en fila 1-2 y cabeceras de tabla en fila 4: `['Folio Venta', 'Fecha y Hora', 'Operador Responsable', 'Método de Pago', 'Total Bruto ($CLP)', 'Base Neta ($CLP)', 'IVA 19% ($CLP)']`.
  4. Estilizar fila 4 con relleno sólido `#1B4332`, fuente blanca en negrita y bordes finos.
  5. Iterar sobre el queryset usando `.iterator(chunk_size=500)`. Sanitizar textos (`str(val).lstrip('=+-@')`) para evitar *CSV/Excel Formula Injection*.
  6. Aplicar formato numérico `"$#,##0"` a las columnas monetarias (E, F, G).
  7. Al final de las filas, agregar fila de **TOTALES CONSOLIDADOS** con `=SUM(...)` o sumatoria exacta calculada en Python, resaltada en negrita con fondo `#D8F3DC`.
  8. Ajustar automáticamente el ancho de columnas y guardar en `output = io.BytesIO(); wb.save(output); output.seek(0)`.