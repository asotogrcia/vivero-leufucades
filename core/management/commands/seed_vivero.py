from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import AuditoriaStock, Producto, Temporada


class Command(BaseCommand):
    help = (
        'Pobla de forma idempotente los grupos RBAC, usuarios base, '
        'las 4 temporadas y el catálogo inicial de productos de Vivero Leufucades.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        # 1. Grupos RBAC
        grupo_admin, _ = Group.objects.get_or_create(name='Administradora General')
        grupo_operador, _ = Group.objects.get_or_create(name='Operador de Mesón')
        self.stdout.write(self.style.SUCCESS('✔ Grupos RBAC verificados.'))

        # 2. Usuarios base
        admin_user, created_admin = User.objects.update_or_create(
            username='admin_vivero',
            defaults={
                'email': 'admin@viveroleufucades.cl',
                'first_name': 'Administradora',
                'last_name': 'Leufucades',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )
        admin_user.set_password('ViveroAdmin2026!')
        admin_user.save()
        admin_user.groups.set([grupo_admin])

        operador_user, created_oper = User.objects.update_or_create(
            username='operador_meson',
            defaults={
                'email': 'meson@viveroleufucades.cl',
                'first_name': 'Operador',
                'last_name': 'Mesón',
                'is_staff': False,
                'is_superuser': False,
                'is_active': True,
            },
        )
        operador_user.set_password('ViveroOper2026!')
        operador_user.save()
        operador_user.groups.set([grupo_operador])
        self.stdout.write(
            self.style.SUCCESS('✔ Usuarios admin_vivero y operador_meson configurados.')
        )

        # 3. Las 4 temporadas comerciales (solo Primavera activa)
        temporadas_config = [
            ('Primavera', True),
            ('Verano', False),
            ('Otoño', False),
            ('Invierno', False),
        ]
        temporadas_map = {}
        for nombre_temp, activa in temporadas_config:
            temp, _ = Temporada.objects.update_or_create(
                nombre=nombre_temp,
                defaults={'es_activa': activa},
            )
            temporadas_map[nombre_temp] = temp
        primavera = temporadas_map['Primavera']
        self.stdout.write(self.style.SUCCESS('✔ 4 Temporadas configuradas (Primavera activa).'))

        # 4. Los 4 productos permanentes (es_fijo=True, id_temporada=None)
        productos_permanentes = [
            {
                'sku': 'VIV-001',
                'nombre_comun': 'Sustrato Universal 25L',
                'nombre_cientifico': 'Mezcla orgánica enriquecida',
                'precio_unitario': 6500,
                'stock_actual': 25,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Almacenar en lugar fresco y seco. Ideal para trasplantes '
                    'de especies de interior y exterior.'
                ),
            },
            {
                'sku': 'VIV-002',
                'nombre_comun': 'Humus de Lombriz 10kg',
                'nombre_cientifico': 'Eisenia fetida humus',
                'precio_unitario': 5900,
                'stock_actual': 20,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Abono orgánico de liberación lenta. Aplicar una capa de 2 cm '
                    'alrededor del tallo cada 45 días.'
                ),
            },
            {
                'sku': 'VIV-003',
                'nombre_comun': 'Ficus Lyrata',
                'nombre_cientifico': 'Ficus lyrata',
                'precio_unitario': 14900,
                'stock_actual': 4,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Luz indirecta abundante, riego moderado cuando los primeros '
                    '3 cm del sustrato estén secos. Evitar corrientes frías.'
                ),
            },
            {
                'sku': 'VIV-004',
                'nombre_comun': 'Helecho Boston',
                'nombre_cientifico': 'Nephrolepis exaltata',
                'precio_unitario': 7500,
                'stock_actual': 18,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Semisombra húmeda. Mantener el sustrato ligeramente húmedo '
                    'sin encharcar; pulverizar follaje en días secos.'
                ),
            },
        ]

        # 5. Las 6 especies estacionales asociadas a Primavera
        productos_primavera = [
            {
                'sku': 'VIV-005',
                'nombre_comun': 'Azalea Rosada',
                'nombre_cientifico': 'Rhododendron indicum',
                'precio_unitario': 8900,
                'stock_actual': 15,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Sustrato ácido bien drenado, semisombra luminosa y riego '
                    'frecuente durante la floración primaveral.'
                ),
            },
            {
                'sku': 'VIV-006',
                'nombre_comun': 'Hortensia Azul',
                'nombre_cientifico': 'Hydrangea macrophylla',
                'precio_unitario': 9500,
                'stock_actual': 12,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Exposición de media sombra en climas del sur. Riego abundante '
                    'en primavera y verano; suelo ácido para mantener tonos azules.'
                ),
            },
            {
                'sku': 'VIV-007',
                'nombre_comun': 'Lavanda Francesa',
                'nombre_cientifico': 'Lavandula dentata',
                'precio_unitario': 4500,
                'stock_actual': 22,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Pleno sol y excelente drenaje. Riego espaciado y poda ligera '
                    'tras la floración para estimular nuevo follaje.'
                ),
            },
            {
                'sku': 'VIV-008',
                'nombre_comun': 'Copihue Rojo',
                'nombre_cientifico': 'Lapageria rosea',
                'precio_unitario': 18500,
                'stock_actual': 3,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Trepadora nativa del bosque valdiviano. Requiere sombra o '
                    'semisombra fresca, alta humedad ambiental y suelo rico en hoja.'
                ),
            },
            {
                'sku': 'VIV-009',
                'nombre_comun': 'Arrayán Chileno',
                'nombre_cientifico': 'Luma apiculata',
                'precio_unitario': 11900,
                'stock_actual': 10,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Especie nativa perenne de corteza canela. Prefiere suelos húmedos '
                    'con buen drenaje y exposición soleada a semisombra.'
                ),
            },
            {
                'sku': 'VIV-010',
                'nombre_comun': 'Camelia Blanca',
                'nombre_cientifico': 'Camellia japonica',
                'precio_unitario': 12500,
                'stock_actual': 0,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Ubicación protegida del viento y heladas tardías. Sustrato ácido '
                    'húmedo y luz filtrada.'
                ),
            },
        ]

        todos_productos = productos_permanentes + productos_primavera

        for datos in todos_productos:
            sku = datos['sku']
            producto, created = Producto.objects.update_or_create(
                sku=sku,
                defaults={
                    'nombre_comun': datos['nombre_comun'],
                    'nombre_cientifico': datos['nombre_cientifico'],
                    'precio_unitario': datos['precio_unitario'],
                    'stock_actual': datos['stock_actual'],
                    'stock_minimo': datos['stock_minimo'],
                    'es_fijo': datos['es_fijo'],
                    'id_temporada': datos['id_temporada'],
                    'descripcion_cuidados': datos['descripcion_cuidados'],
                    'activo': True,
                },
            )
            if created or not AuditoriaStock.objects.filter(id_producto=producto).exists():
                AuditoriaStock.objects.create(
                    id_producto=producto,
                    id_usuario=admin_user,
                    stock_anterior=0,
                    stock_nuevo=producto.stock_actual,
                    motivo_ajuste='Carga inicial de inventario (seed_vivero)',
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'✔ {len(todos_productos)} productos iniciales (4 permanentes y 6 de Primavera) '
                'poblados exitosamente.'
            )
        )
