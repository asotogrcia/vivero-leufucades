from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import AuditoriaStock, DetalleVenta, Producto, Temporada, Venta


class Command(BaseCommand):
    help = (
        'Pobla de forma idempotente los grupos RBAC, usuarios base, '
        'las 4 temporadas y el catálogo hortícola de Vivero Leufucades.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help=(
                'Elimina productos, auditorías, ventas y temporadas previas '
                'antes de sembrar el catálogo hortícola.'
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        if options.get('reset'):
            DetalleVenta.objects.all().delete()
            Venta.objects.all().delete()
            AuditoriaStock.objects.all().delete()
            Producto.objects.all().delete()
            Temporada.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    '↺ Datos previos de productos, auditoría, ventas y temporadas eliminados (--reset).'
                )
            )

        # 1. Grupos RBAC
        grupo_admin, _ = Group.objects.get_or_create(name='Administradora General')
        grupo_operador, _ = Group.objects.get_or_create(name='Operador de Mesón')
        self.stdout.write(self.style.SUCCESS('✔ Grupos RBAC verificados.'))

        # 2. Usuarios base
        admin_user, _ = User.objects.update_or_create(
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

        operador_user, _ = User.objects.update_or_create(
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
        verano = temporadas_map['Verano']
        invierno = temporadas_map['Invierno']
        self.stdout.write(self.style.SUCCESS('✔ 4 Temporadas configuradas (Primavera activa).'))

        # 4. Los 4 productos permanentes (es_fijo=True, id_temporada=None)
        productos_permanentes = [
            {
                'sku': 'HOR-FIJ-01',
                'nombre_comun': 'Sustrato Almácigos Hortalizas 25L',
                'nombre_cientifico': 'Mezcla orgánica para almácigos',
                'precio_unitario': 6500,
                'stock_actual': 24,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Riego: Humedecer antes de sembrar. '
                    'Luz: Almacenar bajo techo. '
                    'Sustrato: Turba, perlita y compost tamizado. '
                    'Mezcla liviana de excelente aireación y drenaje para germinación de almácigos y repique de plantines hortícolas.'
                ),
            },
            {
                'sku': 'HOR-FIJ-02',
                'nombre_comun': 'Humus de Lombriz Orgánico 10kg',
                'nombre_cientifico': 'Eisenia fetida humus',
                'precio_unitario': 5900,
                'stock_actual': 18,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Riego: Incorporar y regar suave. '
                    'Luz: Conservar en lugar fresco. '
                    'Sustrato: Abono orgánico 100% maduro. '
                    'Mejora la retención de humedad y aporta microorganismos benéficos al hoyo de plantación de hortalizas.'
                ),
            },
            {
                'sku': 'HOR-FIJ-03',
                'nombre_comun': 'Lechuga Costina Hidropónica / Invernadero',
                'nombre_cientifico': 'Lactuca sativa var. longifolia',
                'precio_unitario': 1800,
                'stock_actual': 4,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Riego: Frecuente sin encharcar. '
                    'Luz: Semisombra o sol suave. '
                    'Cosecha: 45-55 días. '
                    'Plantín vigoroso adaptado a cultivo bajo plástico o cama alta en la Región de Los Ríos.'
                ),
            },
            {
                'sku': 'HOR-FIJ-04',
                'nombre_comun': 'Perejil Liso de Corte Continuo',
                'nombre_cientifico': 'Petroselinum crispum',
                'precio_unitario': 1500,
                'stock_actual': 22,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': None,
                'descripcion_cuidados': (
                    'Riego: Regular manteniendo humedad. '
                    'Luz: Sol o semisombra luminosa. '
                    'Cosecha: 60 días (rebrote continuo). '
                    'Cosechar tallos exteriores desde la base sin dañar el brote central para producción durante todo el año.'
                ),
            },
        ]

        # 5. Las 8 hortalizas de temporada (Primavera activa, Verano e Invierno)
        productos_temporada = [
            {
                'sku': 'HOR-PRI-01',
                'nombre_comun': 'Almácigo Tomate Limachino',
                'nombre_cientifico': 'Solanum lycopersicum',
                'precio_unitario': 2500,
                'stock_actual': 35,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Riego: Profundo en la base, evitar mojar hojas. '
                    'Luz: Pleno sol (6-8 h). '
                    'Cosecha: 75-85 días desde trasplante. '
                    'Trasplantar enterrando parte del tallo en suelo rico en humus y colocar tutor al superar los 35 cm.'
                ),
            },
            {
                'sku': 'HOR-PRI-02',
                'nombre_comun': 'Plantín Lechuga Escarola',
                'nombre_cientifico': 'Cichorium endivia',
                'precio_unitario': 1600,
                'stock_actual': 40,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Riego: Frecuente y ligero. '
                    'Luz: Sol suave o semisombra. '
                    'Cosecha: 55-65 días. '
                    'Plantar a 25-30 cm entre plantas en camellón suelto; tolera bien las mañanas frescas del sur.'
                ),
            },
            {
                'sku': 'HOR-PRI-03',
                'nombre_comun': 'Almácigo Pimentón Rojo Calahorra',
                'nombre_cientifico': 'Capsicum annuum',
                'precio_unitario': 2800,
                'stock_actual': 3,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Riego: Moderado y constante. '
                    'Luz: Pleno sol protegido del viento. '
                    'Cosecha: 80-95 días. '
                    'Ideal para invernadero o rincón abrigado; evitar heladas tardías y abonar con humus al trasplante.'
                ),
            },
            {
                'sku': 'HOR-PRI-04',
                'nombre_comun': 'Plantín Acelga Verde Penca Blanca',
                'nombre_cientifico': 'Beta vulgaris var. cicla',
                'precio_unitario': 1500,
                'stock_actual': 28,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Riego: Regular 2-3 veces por semana. '
                    'Luz: Sol directo o semisombra. '
                    'Cosecha: 50-60 días. '
                    'Muy rústica para el clima lluvioso de Los Ríos; cortar hojas externas para estimular nuevos brotes.'
                ),
            },
            {
                'sku': 'HOR-PRI-05',
                'nombre_comun': 'Almácigo Zapallo Italiano',
                'nombre_cientifico': 'Cucurbita pepo',
                'precio_unitario': 2200,
                'stock_actual': 0,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Riego: Abundante en la base. '
                    'Luz: Pleno sol. '
                    'Cosecha: 50-60 días. '
                    'Trasplantar sin dañar el pan de raíces dejando 80 cm entre plantas en suelo fértil y bien drenado.'
                ),
            },
            {
                'sku': 'HOR-PRI-06',
                'nombre_comun': 'Plantín Cilantro Criollo',
                'nombre_cientifico': 'Coriandrum sativum',
                'precio_unitario': 1400,
                'stock_actual': 32,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': primavera,
                'descripcion_cuidados': (
                    'Riego: Frecuente sin encharcar. '
                    'Luz: Semisombra luminosa. '
                    'Cosecha: 35-45 días. '
                    'Evitar estrés hídrico para retrasar la subida a flor; ideal para siembra escalonada en huerta familiar.'
                ),
            },
            {
                'sku': 'HOR-VER-01',
                'nombre_comun': 'Almácigo Albahaca Genovesa',
                'nombre_cientifico': 'Ocimum basilicum',
                'precio_unitario': 1900,
                'stock_actual': 15,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': verano,
                'descripcion_cuidados': (
                    'Riego: Diario suave en verano. '
                    'Luz: Pleno sol cálido. '
                    'Cosecha: 45-60 días. '
                    'Despuntar las yemas florales para mantener hojas tiernas y aromáticas; sensible al frío nocturno.'
                ),
            },
            {
                'sku': 'HOR-INV-01',
                'nombre_comun': 'Plantín Repollo Crespo de Invierno',
                'nombre_cientifico': 'Brassica oleracea',
                'precio_unitario': 1700,
                'stock_actual': 25,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': invierno,
                'descripcion_cuidados': (
                    'Riego: Moderado, aprovechando lluvia invernal. '
                    'Luz: Sol pleno a semisombra. '
                    'Cosecha: 85-100 días. '
                    'Excelente resistencia a heladas y humedad de la Región de Los Ríos; plantar a 45 cm de distancia.'
                ),
            },
        ]

        todos_productos = productos_permanentes + productos_temporada

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
                    motivo_ajuste='Carga inicial catálogo hortícola (seed_vivero)',
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'✔ {len(todos_productos)} productos hortícolas '
                '(4 permanentes y 8 estacionales) poblados exitosamente.'
            )
        )
