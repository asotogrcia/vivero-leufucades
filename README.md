# Sistema Web Vivero Leufucades

Plataforma web centralizada de gestión de inventario estacional, punto de venta presencial en mesón (POS interno) y catálogo comercial público para **Vivero Leufucades** (Región de Los Ríos, Chile).

## Stack Tecnológico

- **Backend:** Python 3.12+ / Django 5.x (MVT + capa `services/`)
- **Base de Datos:** PostgreSQL 16 (producción) / SQLite (desarrollo local por defecto)
- **Frontend:** Django Templates (DTL) con Server-Side Rendering, Tailwind CSS y JavaScript Vanilla
- **Procesamiento y Reportes:** `Pillow` (compresión automática a `.webp` < 120 KB) y `openpyxl` (reportes `.xlsx`)
- **Almacenamiento Multimedia (`MEDIA`):** Cloudinary en producción (`django-cloudinary-storage`) o almacenamiento local en `MEDIA_ROOT` cuando no hay credenciales configuradas

## Variables de Entorno

Copia `.env.example` a `.env` y configura según el entorno:

```env
SECRET_KEY=django-insecure-change-me-in-production
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=

# Cloudinary (opcional en local; obligatorio en producción para MEDIA persistente)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

### Almacenamiento Multimedia con Cloudinary

- `CLOUDINARY_CLOUD_NAME`: Nombre del cloud de Cloudinary. Si está definido, Django usa `cloudinary_storage.storage.MediaCloudinaryStorage` para `STORAGES["default"]` (y `DEFAULT_FILE_STORAGE`). Si está vacío o no existe, utiliza `FileSystemStorage` local en `MEDIA_ROOT`.
- `CLOUDINARY_API_KEY`: API Key de tu cuenta de Cloudinary.
- `CLOUDINARY_API_SECRET`: API Secret de tu cuenta de Cloudinary.

Las imágenes de productos subidas a través de la aplicación se optimizan automáticamente a formato `.webp` (< 120 KB, ancho máximo 800 px) en `services/media_webp.py` antes de enviarse al backend de almacenamiento.

## Ejecución Local y Pruebas

```bash
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py test
```
