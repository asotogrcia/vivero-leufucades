---
name: auditoria-qa-xp
description: Escribe pruebas unitarias y de integración automatizadas bajo Django TestCase para validar las 8 Historias de Usuario (BDD), concurrencia, IVA y seguridad RBAC.
---
# Skill: Suite de Pruebas Automatizadas XP (Django TestCase)

## Cuándo aplicar
Al implementar o auditar `tests.py` y el pipeline de integración continua `.github/workflows/ci.yml`.

## Casos de Prueba Obligatorios (`tests.py`)
1. `test_hu01_catalogo_publico_estacional_y_fijos`: Verifica que `/` retorne HTTP 200 sin login y liste solo productos activos de la temporada activa + productos con `es_fijo=True`.
2. `test_hu02_rbac_bloqueo_operador_en_reportes_y_auditoria`: Inicia sesión como `Operador de Mesón` y verifica que `GET /reportes/` y `GET /inventario/auditoria/` retornen `403 Forbidden`.
3. `test_hu03_inventario_rechaza_stock_negativo_y_convierte_webp`: Verifica rechazo de stock `< 0` y conversión real de imagen JPG de prueba a `.webp` `< 120 KB`.
4. `test_hu04_venta_calculo_iva_dl825_e_idempotencia`: Prueba venta de `$5.000 CLP` -> verifica `total_neto == 4202` y `monto_iva == 798`, descuento de stock y que reenviar el mismo `idempotency_key` no descuente stock dos veces.
5. `test_hu05_alerta_stock_critico_frontera`: Prueba `stock=6` (sin alerta), rebaja 1 unidad -> `stock=5` (dispara alerta crítica) y bloquea venta cuando `stock=0`.
6. `test_hu06_exportacion_excel_valida`: Descarga el `.xlsx` con filtro de mes/año, lo lee con `openpyxl.load_workbook` y verifica que los totales coincidan con la base de datos.
7. `test_hu07_unicidad_temporada_activa`: Activa "Verano" y verifica que "Primavera" pase automáticamente a `es_activa=False`.
8. `test_hu08_auditoria_inmutable_se_registra_automaticamente`: Verifica creación de asiento en `AuditoriaStock` con usuario y diferencial exacto tras venta y tras merma.