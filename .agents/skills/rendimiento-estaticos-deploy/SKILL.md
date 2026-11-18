---
name: rendimiento-estaticos-deploy
description: Extrae CSS y JS inline de plantillas HTML hacia static/, configura GZipMiddleware, caché WhiteNoise y script build.sh sin seed automático para Render.
---
# Skill: Optimización de Assets Estáticos y Despliegue Seguro

## Cuándo aplicar
Al refactorizar plantillas HTML para extraer CSS/JS, optimizar tiempos de carga sobre Starlink o modificar scripts de despliegue en Render.

## Directrices Técnicas
1. **Estructura de Archivos Estáticos:**
   - `static/css/botanico.css`: Variables CSS (`--verde-bosque: #1B4332`, `--canvas: #F9FAF8`), estilos de scrollbar oculto para carrusel móvil, transiciones de Skeleton Loaders y reglas `@media print` limpias para el comprobante de caja.
   - `static/js/catalogo.js`: Lógica del modal/drawer de ficha técnica hortícola, ocultamiento suave de Skeleton Loaders en evento `load` de imágenes y activación de grilla Skeleton al enviar filtros.
   - `static/js/pos.js`: Lógica interactiva del Punto de Venta en Mesón (buscador instantáneo en cliente, control de cantidades `+`/`-`, validación contra stock máximo y cálculo dinámico en vivo de Base Neta `round(total/1.19)` e IVA 19%).
   - `static/js/panel.js`: Control de apertura/cierre del sidebar móvil (drawer) y confirmaciones de acciones críticas.
2. **Carga No Bloqueante:**
   - Todos los archivos JS propios deben incluirse en `base_publico.html` o `base_panel.html` mediante `<script src="{% static '...' %}" defer></script>` al final del `<body>` o en el `<head>`.
3. **Middleware y Caché:**
   - Incluir `'django.middleware.gzip.GZipMiddleware'` como primer middleware en `config/settings.py`.
4. **Script de Despliegue (`build.sh`):**
   - Crear `build.sh` en la raíz con `set -o errexit`, `pip install -r requirements.txt`, `python manage.py collectstatic --noinput` y `python manage.py migrate` (sin `seed_vivero`).