# AGENTS.md — Constitución Técnica: Sistema Web Vivero Leufucades

## 1. Identidad del Proyecto y Contexto Operativo
- **Sistema:** Plataforma web centralizada de gestión de inventario estacional (hortalizas, almácigos y plantines), punto de venta presencial en mesón (POS interno) y catálogo comercial público Mobile-First para **Vivero Leufucades** (Región de Los Ríos, Chile).
- **Restricción Crítica de Entorno:** El vivero opera en zona semirrural conectada vía enlace satelital **Starlink** (latencia 35–75 ms, susceptible a microcortes climáticos) y un computador de escritorio en mesón (Full HD `1920x1080`) respaldado por UPS.
- **Metodología:** eXtreme Programming (XP). Código limpio, diseño simple, sin sobreingeniería, pruebas unitarias obligatorias por cada historia de usuario (`HU-01` a `HU-08`).

## 2. Stack Tecnológico y Arquitectura Obligatoria
- **Lenguaje:** Python 3.12+ (estricto cumplimiento de PEP 8).
- **Framework Web:** Django 5.x bajo patrón **MVT + Capa de Servicios (`services/`)**.
  - Las vistas (`views.py`) **NUNCA** contienen lógica de negocio pesada, cálculos tributarios ni consultas complejas directas; solo validan formularios/permisos y delegan a `services/`.
- **Base de Datos:** PostgreSQL 16 (3FN) en producción vía **Neon Serverless Postgres** (`DATABASE_URL` con `conn_max_age=600` y `conn_health_checks=True`). En desarrollo local puede usarse SQLite o PostgreSQL local si `DATABASE_URL` está vacío.
- **Frontend:** Django Template Language (DTL) con **Server-Side Rendering (SSR)**, HTML5 semántico, Tailwind CSS y JavaScript Vanilla modular (`< 15 KB`).
  - **PROHIBIDO:** React, Vue, Angular, Next.js o APIs REST innecesarias que dupliquen viajes de red sobre Starlink.
- **Procesamiento:** `Pillow` (compresión `.webp`) y `openpyxl` (reportes `.xlsx` en RAM).
- **Despliegue y Almacenamiento Cloud:** **Render Cloud** (PaaS Web Service con Gunicorn + WhiteNoise), **Neon** (DBaaS PostgreSQL 16) y **Cloudinary** (Cloud Object Storage & CDN para imágenes `.webp` persistentes).

## 3. Reglas de Negocio Inquebrantables (Contratos de Dominio)
1. **Cálculo Tributario Chileno (Decreto Ley N.º 825 — IVA 19%):**
   - Todos los precios unitarios y totales de venta se expresan en **Pesos Chilenos ($CLP) enteros**, sin decimales.
   - El precio de catálogo es **Bruto (IVA incluido)**.
   - Fórmula obligatoria en backend:
     - `total_neto = round(total_bruto / 1.19)`
     - `monto_iva = total_bruto - total_neto`
   - Todo comprobante digital debe exhibir explícitamente: *"Comprobante de Control Interno — No Válido como Boleta Electrónica SII"*.
2. **Atomicidad, Concurrencia e Idempotencia (ACID):**
   - Toda venta y ajuste de inventario debe ejecutarse dentro de `with transaction.atomic():`.
   - Bloquear filas antes de leer/descontar stock: `Producto.objects.select_for_update().filter(id_producto__in=ids).order_by('id_producto')`.
   - Toda petición `POST` de venta en mesón debe enviar un `idempotency_key` (`uuid4`). Si el UUID ya existe en `Venta`, retornar la venta existente sin volver a descontar stock (mitiga doble clic ante microcortes de Starlink).
3. **Estacionalidad vs. Productos Permanentes:**
   - Solo **1 temporada comercial** puede tener `es_activa = True` simultáneamente. Al activar una temporada, desactivar las demás dentro de una transacción atómica.
   - El catálogo público por defecto muestra: `(id_temporada.es_activa == True OR es_fijo == True) AND activo == True`.
   - **Prohibido el borrado físico (`DELETE`)** de productos con ventas o auditoría; usar borrado lógico (`activo = False`).
4. **Umbral de Stock Crítico (`<= 5` unidades):**
   - Todo producto activo con `stock_actual <= stock_minimo` (default `5`) debe disparar una alerta visual inmediata en el Dashboard Operacional y en el listado de Inventario.
5. **Bitácora Inmutable de Auditoría (`AUDITORIA_STOCK`):**
   - Cualquier cambio en `stock_actual` (venta en mesón, ingreso de cosecha o merma) debe insertar un registro en `AuditoriaStock` con `id_producto`, `id_usuario`, `fecha_hora`, `stock_anterior`, `stock_nuevo` y `motivo_ajuste`.
   - Ningún rol (ni siquiera Administradora) puede editar o eliminar filas de `AuditoriaStock` desde la aplicación web.
6. **Presupuesto de Rendimiento Satelital (RNF-01):**
   - Peso total por vista inicial: **< 1.5 MB**.
   - Tiempo de respuesta en servidor: **< 2.5 s**.
   - Toda imagen subida se convierte a `.webp` (`max_width=800px`, `quality=80`, peso `< 120 KB`) y las etiquetas `<img>` usan `loading="lazy"`.

## 4. Sistema de Diseño: "Botánico Minimalista" (Cero Saturación)
- **Proporción cromática:** 85% fondos neutros limpios, 10% verde bosque profundo, 5% acentos semánticos.
- **Paleta Exacta:**
  - Fondo de pantalla (`bg-canvas`): `#F9FAF8`
  - Tarjetas y contenedores (`bg-surface`): `#FFFFFF` con borde `1px solid #E2E8E4`
  - Color Primario (Sidebar fijo de viewport, botones principales, encabezados): `#1B4332` (Verde Bosque Profundo)
  - Hover Primario: `#2D6A4F` (Verde Hoja)
  - Badge Temporada Activa / Acento suave: Fondo `#D8F3DC`, Texto `#1B4332`
  - Badge Producto Permanente (`es_fijo`): Fondo `#FEF3C7`, Texto `#92400E` (Ámbar tierra suave)
  - Texto Principal: `#1F2933` | Texto Secundario: `#52606D`
  - Alerta Stock Crítico (`<= 5`): Fondo `#FEF2F2`, Borde `#FECACA`, Texto `#991B1B`
- **Ergonomía y Responsividad:** Catálogo público diseñado bajo enfoque **Mobile-First** con Skeleton Loaders; panel interno con sidebar fijo en alto de pantalla (`h-screen`) y scroll independiente en el área principal; botones con altura mínima de `44px` y navegación por teclado (`Tab` / `Enter`).

## 5. Seguridad (OWASP ASVS y Ley 21.719)
- Roles estrictos mediante `django.contrib.auth.models.Group`:
  1. `Administradora General`: Acceso total (Dashboard, Inventario CRUD, Mermas, Temporadas, POS Ventas, Auditoría, Exportar Excel `.xlsx`).
  2. `Operador de Mesón`: Acceso restringido solo a Dashboard básico, Consulta de Stock y Punto de Venta (`POS`). Cualquier intento de acceso por URL a `/inventario/crear/`, `/inventario/auditoria/` o `/reportes/` debe retornar **HTTP 403 Forbidden**.
- Todos los formularios `POST` exigen `{% csrf_token %}`.
- El catálogo público es 100% anónimo (minimización de datos Ley N.º 21.719).

## 6. Rendimiento, Assets Estáticos y Despliegue Seguro (Producción)
- **Separación Estricta de Assets (`static/`):** Ningún archivo `.html` en `templates/` debe contener bloques `<style>` ni `<script>` extensos inline. Todo estilo personalizado reside en `static/css/botanico.css` y toda lógica cliente en `static/js/` (`catalogo.js`, `pos.js`, `panel.js`), cargados mediante `{% static '...' %}` con atributo `defer` para aprovechar la caché inmutable de **WhiteNoise** (`CompressedManifestStaticFilesStorage`).
- **Compresión y Optimización de Consultas:** `django.middleware.gzip.GZipMiddleware` debe ubicarse como primer middleware para comprimir las respuestas SSR. Toda consulta en vistas debe usar `select_related()`, `prefetch_related()` o `.only()` para eliminar consultas $N+1$ y reducir el tráfico con Neon PostgreSQL.
- **Despliegue Idempotente (`build.sh`):** El script de construcción en Render ejecuta exclusivamente `pip install -r requirements.txt`, `python manage.py collectstatic --noinput` y `python manage.py migrate`. **PROHIBIDO** ejecutar `seed_vivero` de forma automática durante los despliegues en producción para proteger la integridad de los datos históricos.