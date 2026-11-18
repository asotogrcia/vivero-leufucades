import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

MAX_ANCHO_PX = 800
MAX_PESO_BYTES = 120 * 1024
CALIDAD_INICIAL = 80
CALIDAD_RECOMPRESION = 65


def optimizar_imagen_webp(archivo_imagen) -> ContentFile:
    """Valida, redimensiona (max 800px) y comprime una imagen a formato WebP (< 120 KB)."""
    if archivo_imagen is None:
        raise ValidationError('No se proporcionó ningún archivo de imagen.')

    if hasattr(archivo_imagen, 'seek'):
        archivo_imagen.seek(0)

    try:
        with Image.open(archivo_imagen) as img_verificacion:
            img_verificacion.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError('El archivo proporcionado no es una imagen válida.') from exc

    if hasattr(archivo_imagen, 'seek'):
        archivo_imagen.seek(0)

    with Image.open(archivo_imagen) as img:
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGBA')
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        if img.width > MAX_ANCHO_PX:
            nuevo_alto = max(1, int((MAX_ANCHO_PX / img.width) * img.height))
            img = img.resize((MAX_ANCHO_PX, nuevo_alto), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format='WEBP', quality=CALIDAD_INICIAL, method=6)

        if buffer.tell() > MAX_PESO_BYTES:
            buffer = io.BytesIO()
            img.save(buffer, format='WEBP', quality=CALIDAD_RECOMPRESION, method=6)

        nombre_archivo = f'{uuid.uuid4().hex[:12]}.webp'
        return ContentFile(buffer.getvalue(), name=nombre_archivo)
