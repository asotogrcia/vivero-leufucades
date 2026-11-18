import io
import tempfile
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import openpyxl
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from services.media_webp import MAX_PESO_BYTES, optimizar_imagen_webp

from core.decorators import (
    GRUPO_ADMINISTRADORA,
    GRUPO_OPERADOR,
    requiere_administradora,
    requiere_operador_o_admin,
)
from core.models import AuditoriaStock, Producto, Temporada, Venta
from core.views.auth_panel import (
    DashboardOperacionalView,
    LoginViveroView,
    LogoutViveroView,
)

User = get_user_model()

LOCAL_MEDIA_STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


def _attach_session(request):
    middleware = SessionMiddleware(lambda req: HttpResponse())
    middleware.process_request(request)
    request.session.save()
    return request


class RBACDecoratorsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.grupo_admin = Group.objects.create(name=GRUPO_ADMINISTRADORA)
        self.grupo_operador = Group.objects.create(name=GRUPO_OPERADOR)

        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='Password123!',
        )
        self.admin_user.groups.add(self.grupo_admin)

        self.operador_user = User.objects.create_user(
            username='oper_test',
            password='Password123!',
        )
        self.operador_user.groups.add(self.grupo_operador)

        self.super_user = User.objects.create_superuser(
            username='super_test',
            email='super@test.cl',
            password='Password123!',
        )

        self.plain_user = User.objects.create_user(
            username='plain_test',
            password='Password123!',
        )

    def test_requiere_administradora_permite_admin_y_superuser(self):
        @requiere_administradora
        def vista_protegida(request):
            return HttpResponse('OK')

        for user in (self.admin_user, self.super_user):
            request = self.factory.get('/ruta-admin/')
            request.user = user
            response = vista_protegida(request)
            self.assertEqual(response.status_code, 200)

    def test_requiere_administradora_deniega_operador_y_otros(self):
        @requiere_administradora
        def vista_protegida(request):
            return HttpResponse('OK')

        for user in (self.operador_user, self.plain_user, AnonymousUser()):
            request = self.factory.get('/ruta-admin/')
            request.user = user
            response = vista_protegida(request)
            self.assertEqual(response.status_code, 403)
            self.assertIn(
                'Acceso denegado: Se requiere perfil de Administradora General.',
                response.content.decode('utf-8'),
            )

    def test_requiere_operador_o_admin(self):
        @requiere_operador_o_admin
        def vista_panel(request):
            return HttpResponse('OK')

        for user in (self.admin_user, self.operador_user, self.super_user):
            request = self.factory.get('/panel/')
            request.user = user
            response = vista_panel(request)
            self.assertEqual(response.status_code, 200)

        for user in (self.plain_user, AnonymousUser()):
            request = self.factory.get('/panel/')
            request.user = user
            response = vista_panel(request)
            self.assertEqual(response.status_code, 403)


class AuthAndDashboardViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.grupo_admin = Group.objects.create(name=GRUPO_ADMINISTRADORA)
        self.grupo_operador = Group.objects.create(name=GRUPO_OPERADOR)

        self.admin_user = User.objects.create_user(
            username='admin_vivero',
            password='ViveroAdmin2026!',
        )
        self.admin_user.groups.add(self.grupo_admin)

        self.operador_user = User.objects.create_user(
            username='operador_meson',
            password='ViveroOper2026!',
        )
        self.operador_user.groups.add(self.grupo_operador)

        self.temporada = Temporada.objects.create(
            nombre='Primavera',
            es_activa=True,
        )

        self.prod_normal = Producto.objects.create(
            sku='VIV-010',
            id_temporada=self.temporada,
            nombre_comun='Arrayán Chileno',
            precio_unitario=8900,
            stock_actual=12,
            stock_minimo=5,
            activo=True,
        )
        self.prod_critico = Producto.objects.create(
            sku='VIV-011',
            id_temporada=self.temporada,
            nombre_comun='Copihue Rojo',
            precio_unitario=14500,
            stock_actual=3,
            stock_minimo=5,
            activo=True,
        )
        self.prod_agotado = Producto.objects.create(
            sku='VIV-012',
            id_temporada=self.temporada,
            nombre_comun='Notro Austral',
            precio_unitario=11000,
            stock_actual=0,
            stock_minimo=5,
            activo=True,
        )
        self.prod_inactivo = Producto.objects.create(
            sku='VIV-013',
            id_temporada=self.temporada,
            nombre_comun='Especie Inactiva',
            precio_unitario=5000,
            stock_actual=0,
            stock_minimo=5,
            activo=False,
        )

        Venta.objects.create(
            id_usuario=self.operador_user,
            total_bruto=11900,
            total_neto=10000,
            monto_iva=1900,
            metodo_pago=Venta.METODO_EFECTIVO,
            idempotency_key=uuid.uuid4(),
        )

        for idx in range(8):
            AuditoriaStock.objects.create(
                id_producto=self.prod_normal,
                id_usuario=self.admin_user,
                stock_anterior=10 + idx,
                stock_nuevo=11 + idx,
                motivo_ajuste=f'Ajuste #{idx + 1}',
            )

    def test_login_get_y_post_valido_e_invalido(self):
        get_req = _attach_session(self.factory.get(reverse('core:login')))
        get_req.user = AnonymousUser()
        get_resp = LoginViveroView.as_view()(get_req)
        self.assertEqual(get_resp.status_code, 200)
        self.assertIn('csrfmiddlewaretoken', get_resp.content.decode('utf-8'))

        bad_req = _attach_session(
            self.factory.post(
                reverse('core:login'),
                {'username': 'operador_meson', 'password': 'WrongPassword'},
            )
        )
        bad_req.user = AnonymousUser()
        bad_resp = LoginViveroView.as_view()(bad_req)
        self.assertEqual(bad_resp.status_code, 200)
        self.assertIn('Usuario o contraseña incorrectos.', bad_resp.content.decode('utf-8'))

        ok_req = _attach_session(
            self.factory.post(
                reverse('core:login'),
                {'username': 'operador_meson', 'password': 'ViveroOper2026!'},
            )
        )
        ok_req.user = AnonymousUser()
        ok_resp = LoginViveroView.as_view()(ok_req)
        self.assertEqual(ok_resp.status_code, 302)
        self.assertEqual(ok_resp.url, '/panel/')

    def test_login_rechaza_post_sin_csrf(self):
        req = _attach_session(
            self.factory.post(
                reverse('core:login'),
                {'username': 'operador_meson', 'password': 'ViveroOper2026!'},
            )
        )
        req.user = AnonymousUser()
        req._dont_enforce_csrf_checks = False
        view = LoginViveroView.as_view()
        csrf_middleware = CsrfViewMiddleware(lambda r: view(r))
        resp = csrf_middleware.process_view(req, view, (), {})
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)

    def test_logout_solo_post_y_redirige_a_raiz(self):
        get_req = _attach_session(self.factory.get(reverse('core:logout')))
        get_req.user = self.operador_user
        get_resp = LogoutViveroView.as_view()(get_req)
        self.assertEqual(get_resp.status_code, 405)

        post_req = _attach_session(self.factory.post(reverse('core:logout')))
        post_req.user = self.operador_user
        post_resp = LogoutViveroView.as_view()(post_req)
        self.assertEqual(post_resp.status_code, 302)
        self.assertEqual(post_resp.url, '/')

    def test_dashboard_bloqueado_para_anonimo(self):
        req = _attach_session(self.factory.get(reverse('core:dashboard')))
        req.user = AnonymousUser()
        resp = DashboardOperacionalView.as_view()(req)
        self.assertEqual(resp.status_code, 403)

    def test_dashboard_operador_oculta_opciones_admin_y_muestra_kpis(self):
        req = _attach_session(self.factory.get(reverse('core:dashboard')))
        req.user = self.operador_user
        resp = DashboardOperacionalView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

        html = resp.content.decode('utf-8')
        self.assertIn('Ciclo Activo: Primavera', html)
        self.assertIn('$11.900', html)
        self.assertIn('Alerta de Stock Crítico', html)
        self.assertIn('Copihue Rojo', html)
        self.assertIn('Notro Austral', html)
        self.assertIn('Ajuste #8', html)
        self.assertNotIn('Ajuste #1', html)

        self.assertNotIn('/inventario/nuevo/', html)
        self.assertNotIn('/inventario/maestros/', html)
        self.assertNotIn('/inventario/auditoria/', html)
        self.assertNotIn('/reportes/', html)

    def test_dashboard_administradora_muestra_opciones_admin(self):
        req = _attach_session(self.factory.get(reverse('core:dashboard')))
        req.user = self.admin_user
        resp = DashboardOperacionalView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

        html = resp.content.decode('utf-8')
        self.assertIn('/inventario/nuevo/', html)
        self.assertIn('/inventario/maestros/', html)
        self.assertIn('/inventario/auditoria/', html)
        self.assertIn('/reportes/', html)


class MediaWebPTests(TestCase):
    def _crear_imagen_bytes(self, size=(1200, 900), mode='RGB', fmt='PNG') -> io.BytesIO:
        buf = io.BytesIO()
        img = Image.new(mode, size, color=(34, 139, 34))
        img.save(buf, format=fmt)
        buf.seek(0)
        return buf

    def test_optimizar_imagen_webp_redimensiona_y_convierte_a_webp(self):
        archivo = SimpleUploadedFile(
            'planta.png',
            self._crear_imagen_bytes(size=(1600, 1200), mode='RGBA', fmt='PNG').read(),
            content_type='image/png',
        )
        resultado = optimizar_imagen_webp(archivo)

        self.assertTrue(resultado.name.endswith('.webp'))
        self.assertLessEqual(resultado.size, MAX_PESO_BYTES)

        with Image.open(io.BytesIO(resultado.read())) as img_out:
            self.assertEqual(img_out.format, 'WEBP')
            self.assertEqual(img_out.width, 800)
            self.assertEqual(img_out.height, 600)

    def test_optimizar_imagen_webp_rechaza_archivo_no_valido(self):
        archivo_falso = SimpleUploadedFile(
            'malicioso.jpg',
            b'esto no es una imagen real',
            content_type='image/jpeg',
        )
        with self.assertRaises(ValidationError):
            optimizar_imagen_webp(archivo_falso)

    def test_producto_save_optimiza_imagen_nueva_y_no_reprocesa_al_actualizar_stock(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media, STORAGES=LOCAL_MEDIA_STORAGES):
                archivo = SimpleUploadedFile(
                    'copihue.png',
                    self._crear_imagen_bytes(size=(1000, 500), fmt='PNG').read(),
                    content_type='image/png',
                )
                producto = Producto.objects.create(
                    sku='VIV-IMG-01',
                    nombre_comun='Copihue Prueba',
                    precio_unitario=9900,
                    stock_actual=10,
                    url_imagen=archivo,
                )
                nombre_guardado = producto.url_imagen.name
                self.assertTrue(nombre_guardado.endswith('.webp'))

                producto.stock_actual = 8
                producto.save()
                producto.refresh_from_db()
                self.assertEqual(producto.url_imagen.name, nombre_guardado)


class CatalogoPublicoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.primavera = Temporada.objects.create(nombre='Primavera', es_activa=True)
        self.invierno = Temporada.objects.create(nombre='Invierno', es_activa=False)

        self.prod_primavera = Producto.objects.create(
            sku='CAT-001',
            id_temporada=self.primavera,
            nombre_comun='Hortensia Azul',
            nombre_cientifico='Hydrangea macrophylla',
            precio_unitario=7500,
            stock_actual=14,
            es_fijo=False,
            descripcion_cuidados='Semisombra y riego moderado.',
            activo=True,
        )
        self.prod_fijo = Producto.objects.create(
            sku='CAT-002',
            id_temporada=self.invierno,
            nombre_comun='Tierra de Hoja 25L',
            nombre_cientifico='',
            precio_unitario=4500,
            stock_actual=0,
            es_fijo=True,
            activo=True,
        )
        self.prod_invierno = Producto.objects.create(
            sku='CAT-003',
            id_temporada=self.invierno,
            nombre_comun='Camelia Blanca',
            nombre_cientifico='Camellia japonica',
            precio_unitario=12900,
            stock_actual=6,
            es_fijo=False,
            activo=True,
        )
        self.prod_inactivo = Producto.objects.create(
            sku='CAT-004',
            id_temporada=self.primavera,
            nombre_comun='Producto Oculto',
            precio_unitario=3000,
            stock_actual=5,
            es_fijo=True,
            activo=False,
        )

    def _get_catalogo(self, params=None):
        from core.views.catalogo import CatalogoListView

        req = self.factory.get(reverse('core:catalogo'), params or {})
        req.user = AnonymousUser()
        resp = CatalogoListView.as_view()(req)
        if hasattr(resp, 'render'):
            resp.render()
        return resp

    def test_catalogo_publico_sin_login_filtra_ciclo_actual_y_fijos(self):
        resp = self._get_catalogo()
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')

        self.assertIn('Ciclo Activo: Primavera', html)
        self.assertIn('Hortensia Azul', html)
        self.assertIn('Hydrangea macrophylla', html)
        self.assertIn('Tierra de Hoja 25L', html)
        self.assertIn('$7.500', html)
        self.assertIn('Disponible', html)
        self.assertIn('Agotado', html)
        self.assertNotIn('14', html.split('Hortensia Azul')[1][:150])
        self.assertNotIn('Camelia Blanca', html)
        self.assertNotIn('Producto Oculto', html)

    def test_catalogo_filtros_temporada_y_busqueda(self):
        resp_fijos = self._get_catalogo({'temporada': 'fijos'})
        html_fijos = resp_fijos.content.decode('utf-8')
        self.assertIn('Tierra de Hoja 25L', html_fijos)
        self.assertNotIn('Hortensia Azul', html_fijos)

        resp_inv = self._get_catalogo({'temporada': str(self.invierno.id_temporada)})
        html_inv = resp_inv.content.decode('utf-8')
        self.assertIn('Camelia Blanca', html_inv)
        self.assertNotIn('Hortensia Azul', html_inv)

        resp_todas = self._get_catalogo({'temporada': 'todas'})
        html_todas = resp_todas.content.decode('utf-8')
        self.assertIn('Hortensia Azul', html_todas)
        self.assertIn('Camelia Blanca', html_todas)
        self.assertIn('Tierra de Hoja 25L', html_todas)
        self.assertNotIn('Producto Oculto', html_todas)

        resp_q = self._get_catalogo({'temporada': 'todas', 'q': 'Camellia'})
        html_q = resp_q.content.decode('utf-8')
        self.assertIn('Camelia Blanca', html_q)
        self.assertNotIn('Hortensia Azul', html_q)

        resp_sku = self._get_catalogo({'q': 'CAT-001'})
        html_sku = resp_sku.content.decode('utf-8')
        self.assertIn('Hortensia Azul', html_sku)
        self.assertNotIn('Tierra de Hoja 25L', html_sku)


class InventarioServicesAndFormsTests(TestCase):
    def setUp(self):
        self.grupo_admin = Group.objects.create(name=GRUPO_ADMINISTRADORA)
        self.admin_user = User.objects.create_user(
            username='admin_inv',
            password='Password123!',
        )
        self.admin_user.groups.add(self.grupo_admin)

        self.primavera = Temporada.objects.create(nombre='Primavera', es_activa=True)
        self.otono = Temporada.objects.create(nombre='Otoño', es_activa=False)

    def _crear_imagen_png(self) -> SimpleUploadedFile:
        buf = io.BytesIO()
        Image.new('RGB', (1000, 800), color=(27, 67, 50)).save(buf, format='PNG')
        buf.seek(0)
        return SimpleUploadedFile('especie.png', buf.read(), content_type='image/png')

    def test_crear_y_actualizar_producto_con_webp_y_auditoria_inicial(self):
        from services.inventario import crear_o_actualizar_producto

        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media, STORAGES=LOCAL_MEDIA_STORAGES):
                producto = crear_o_actualizar_producto(
                    datos={
                        'sku': 'VIV-100',
                        'id_temporada': self.primavera,
                        'nombre_comun': 'Ulmo Patagónico',
                        'nombre_cientifico': 'Eucryphia cordifolia',
                        'precio_unitario': 15900,
                        'stock_actual': 8,
                        'stock_minimo': 5,
                        'es_fijo': False,
                        'descripcion_cuidados': 'Sol directo.',
                    },
                    imagen=self._crear_imagen_png(),
                    usuario=self.admin_user,
                )
                self.assertTrue(producto.url_imagen.name.endswith('.webp'))
                aud = AuditoriaStock.objects.get(id_producto=producto)
                self.assertEqual(aud.stock_anterior, 0)
                self.assertEqual(aud.stock_nuevo, 8)
                self.assertIn('[Ingreso Cosecha]', aud.motivo_ajuste)

                actualizado = crear_o_actualizar_producto(
                    datos={
                        'sku': 'VIV-100',
                        'id_temporada': self.otono,
                        'nombre_comun': 'Ulmo Patagónico Grande',
                        'nombre_cientifico': 'Eucryphia cordifolia',
                        'precio_unitario': 18900,
                        'stock_actual': 8,
                        'stock_minimo': 5,
                        'es_fijo': False,
                        'descripcion_cuidados': 'Sol directo y riego.',
                    },
                    imagen=None,
                    usuario=self.admin_user,
                    producto_id=producto.id_producto,
                )
                self.assertEqual(actualizado.nombre_comun, 'Ulmo Patagónico Grande')
                self.assertEqual(actualizado.precio_unitario, 18900)
                self.assertEqual(AuditoriaStock.objects.filter(id_producto=producto).count(), 1)

    def test_ajustar_stock_producto_ingreso_merma_y_validacion_negativo(self):
        from services.inventario import ajustar_stock_producto

        prod = Producto.objects.create(
            sku='VIV-101',
            id_temporada=self.primavera,
            nombre_comun='Arrayán',
            precio_unitario=7000,
            stock_actual=10,
        )

        aud_ing = ajustar_stock_producto(
            producto_id=prod.id_producto,
            usuario=self.admin_user,
            tipo_movimiento='ingreso',
            cantidad=5,
            motivo='Cosecha sector norte',
        )
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 15)
        self.assertEqual(aud_ing.stock_anterior, 10)
        self.assertEqual(aud_ing.stock_nuevo, 15)
        self.assertTrue(aud_ing.motivo_ajuste.startswith('[Ingreso Cosecha]'))

        aud_merma = ajustar_stock_producto(
            producto_id=prod.id_producto,
            usuario=self.admin_user,
            tipo_movimiento='merma',
            cantidad=4,
            motivo='Daño por helada',
        )
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 11)
        self.assertEqual(aud_merma.stock_anterior, 15)
        self.assertEqual(aud_merma.stock_nuevo, 11)
        self.assertTrue(aud_merma.motivo_ajuste.startswith('[Merma / Ajuste]'))

        with self.assertRaises(ValidationError):
            ajustar_stock_producto(
                producto_id=prod.id_producto,
                usuario=self.admin_user,
                tipo_movimiento='merma',
                cantidad=20,
                motivo='Exceso',
            )
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 11)

    def test_activar_temporada_comercial_solo_una_activa(self):
        from services.inventario import activar_temporada_comercial

        activar_temporada_comercial(self.otono.id_temporada)
        self.primavera.refresh_from_db()
        self.otono.refresh_from_db()
        self.assertFalse(self.primavera.es_activa)
        self.assertTrue(self.otono.es_activa)
        self.assertEqual(Temporada.objects.filter(es_activa=True).count(), 1)

    def test_producto_form_validaciones_coherencia_y_negativos(self):
        from core.forms import AjusteStockForm, ProductoForm

        form_sin_temp = ProductoForm(
            data={
                'sku': 'VIV-200',
                'nombre_comun': 'Menta',
                'precio_unitario': 2500,
                'stock_actual': 10,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': '',
            }
        )
        self.assertFalse(form_sin_temp.is_valid())
        self.assertIn('id_temporada', form_sin_temp.errors)

        form_fijo_con_temp = ProductoForm(
            data={
                'sku': 'VIV-201',
                'nombre_comun': 'Tierra de Hoja',
                'precio_unitario': 4500,
                'stock_actual': 10,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': self.primavera.id_temporada,
            }
        )
        self.assertFalse(form_fijo_con_temp.is_valid())
        self.assertIn('id_temporada', form_fijo_con_temp.errors)

        form_neg = ProductoForm(
            data={
                'sku': 'VIV-202',
                'nombre_comun': 'Lavanda',
                'precio_unitario': -100,
                'stock_actual': -1,
                'stock_minimo': 5,
                'es_fijo': True,
                'id_temporada': '',
            }
        )
        self.assertFalse(form_neg.is_valid())
        self.assertIn('precio_unitario', form_neg.errors)
        self.assertIn('stock_actual', form_neg.errors)

        form_ajuste_sin_motivo = AjusteStockForm(
            data={'tipo_movimiento': 'ingreso', 'cantidad': 3, 'motivo': '   '}
        )
        self.assertFalse(form_ajuste_sin_motivo.is_valid())
        self.assertIn('motivo', form_ajuste_sin_motivo.errors)


class InventarioViewsRBACTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.grupo_admin = Group.objects.create(name=GRUPO_ADMINISTRADORA)
        self.grupo_operador = Group.objects.create(name=GRUPO_OPERADOR)

        self.admin_user = User.objects.create_user(
            username='admin_views',
            password='Password123!',
        )
        self.admin_user.groups.add(self.grupo_admin)

        self.operador_user = User.objects.create_user(
            username='operador_views',
            password='Password123!',
        )
        self.operador_user.groups.add(self.grupo_operador)

        self.primavera = Temporada.objects.create(nombre='Primavera', es_activa=True)
        self.invierno = Temporada.objects.create(nombre='Invierno', es_activa=False)

        self.prod_ok = Producto.objects.create(
            sku='INV-001',
            id_temporada=self.primavera,
            nombre_comun='Canelo Chileno',
            precio_unitario=9500,
            stock_actual=12,
            stock_minimo=5,
            activo=True,
        )
        self.prod_critico = Producto.objects.create(
            sku='INV-002',
            id_temporada=self.primavera,
            nombre_comun='Chilco Nativo',
            precio_unitario=6500,
            stock_actual=3,
            stock_minimo=5,
            activo=True,
        )
        self.prod_agotado = Producto.objects.create(
            sku='INV-003',
            id_temporada=self.primavera,
            nombre_comun='Michay',
            precio_unitario=7200,
            stock_actual=0,
            stock_minimo=5,
            activo=True,
        )

    def _call_view(self, view_func, method, path, user, data=None, **kwargs):
        from django.contrib.messages.middleware import MessageMiddleware

        if method == 'GET':
            req = self.factory.get(path, data or {})
        else:
            req = self.factory.post(path, data or {})
        _attach_session(req)
        MessageMiddleware(lambda r: HttpResponse()).process_request(req)
        req.user = user
        resp = view_func(req, **kwargs)
        if hasattr(resp, 'render'):
            resp.render()
        return resp

    def test_rutas_inventario_retornan_403_para_operador_y_anonimo(self):
        from core.views.inventario import (
            AjusteStockView,
            AuditoriaListView,
            InventarioListView,
            MaestrosTemporadasView,
            ProductoCreateView,
            ProductoDesactivarView,
            ProductoUpdateView,
        )

        casos_get = [
            (InventarioListView.as_view(), reverse('core:inventario_list'), {}),
            (ProductoCreateView.as_view(), reverse('core:producto_nuevo'), {}),
            (ProductoCreateView.as_view(), reverse('core:producto_crear'), {}),
            (
                ProductoUpdateView.as_view(),
                reverse('core:producto_editar', args=[self.prod_ok.id_producto]),
                {'producto_id': self.prod_ok.id_producto},
            ),
            (MaestrosTemporadasView.as_view(), reverse('core:inventario_maestros'), {}),
            (AuditoriaListView.as_view(), reverse('core:inventario_auditoria'), {}),
        ]
        casos_post = [
            (
                ProductoDesactivarView.as_view(),
                reverse('core:producto_desactivar', args=[self.prod_ok.id_producto]),
                {'producto_id': self.prod_ok.id_producto},
            ),
            (
                AjusteStockView.as_view(),
                reverse('core:producto_ajustar', args=[self.prod_ok.id_producto]),
                {'producto_id': self.prod_ok.id_producto},
            ),
        ]

        for user in (AnonymousUser(), self.operador_user):
            for view_fn, ruta, kw in casos_get:
                resp = self._call_view(view_fn, 'GET', ruta, user, **kw)
                self.assertEqual(resp.status_code, 403)
            for view_fn, ruta, kw in casos_post:
                resp = self._call_view(view_fn, 'POST', ruta, user, **kw)
                self.assertEqual(resp.status_code, 403)

    def test_flujo_completo_administradora_inventario_temporadas_y_auditoria(self):
        from core.views.inventario import (
            AjusteStockView,
            AuditoriaListView,
            InventarioListView,
            MaestrosTemporadasView,
            ProductoCreateView,
            ProductoDesactivarView,
        )

        resp_list = self._call_view(
            InventarioListView.as_view(),
            'GET',
            reverse('core:inventario_list'),
            self.admin_user,
        )
        self.assertEqual(resp_list.status_code, 200)
        html_list = resp_list.content.decode('utf-8')
        self.assertIn('Canelo Chileno', html_list)
        self.assertIn('Chilco Nativo', html_list)
        self.assertIn('#FEF2F2', html_list)
        self.assertIn('#991B1B', html_list)

        resp_crit = self._call_view(
            InventarioListView.as_view(),
            'GET',
            reverse('core:inventario_list'),
            self.admin_user,
            data={'estado': 'critico'},
        )
        html_crit = resp_crit.content.decode('utf-8')
        self.assertIn('Chilco Nativo', html_crit)
        self.assertIn('Michay', html_crit)
        self.assertNotIn('Canelo Chileno', html_crit)

        resp_agot = self._call_view(
            InventarioListView.as_view(),
            'GET',
            reverse('core:inventario_list'),
            self.admin_user,
            data={'estado': 'agotados'},
        )
        html_agot = resp_agot.content.decode('utf-8')
        self.assertIn('Michay', html_agot)
        self.assertNotIn('Chilco Nativo', html_agot)

        # Crear producto
        resp_create = self._call_view(
            ProductoCreateView.as_view(),
            'POST',
            reverse('core:producto_nuevo'),
            self.admin_user,
            data={
                'sku': 'INV-004',
                'nombre_comun': 'Quillay',
                'nombre_cientifico': 'Quillaja saponaria',
                'id_temporada': self.primavera.id_temporada,
                'precio_unitario': 11500,
                'stock_actual': 7,
                'stock_minimo': 5,
                'descripcion_cuidados': 'Pleno sol.',
            },
        )
        self.assertEqual(resp_create.status_code, 302)
        quillay = Producto.objects.get(sku='INV-004')
        self.assertEqual(quillay.stock_actual, 7)

        # Ajustar stock
        resp_ajuste = self._call_view(
            AjusteStockView.as_view(),
            'POST',
            reverse('core:producto_ajustar', args=[quillay.id_producto]),
            self.admin_user,
            data={
                'tipo_movimiento': 'merma',
                'cantidad': 2,
                'motivo': 'Traslado interno',
            },
            producto_id=quillay.id_producto,
        )
        self.assertEqual(resp_ajuste.status_code, 302)
        quillay.refresh_from_db()
        self.assertEqual(quillay.stock_actual, 5)

        # Desactivar producto (borrado lógico)
        resp_desact = self._call_view(
            ProductoDesactivarView.as_view(),
            'POST',
            reverse('core:producto_desactivar', args=[quillay.id_producto]),
            self.admin_user,
            producto_id=quillay.id_producto,
        )
        self.assertEqual(resp_desact.status_code, 302)
        quillay.refresh_from_db()
        self.assertFalse(quillay.activo)

        # Maestros de temporadas: crear y activar
        resp_temp_crear = self._call_view(
            MaestrosTemporadasView.as_view(),
            'POST',
            reverse('core:inventario_maestros'),
            self.admin_user,
            data={'action': 'crear', 'nombre': 'Verano'},
        )
        self.assertEqual(resp_temp_crear.status_code, 302)
        verano = Temporada.objects.get(nombre='Verano')

        resp_temp_act = self._call_view(
            MaestrosTemporadasView.as_view(),
            'POST',
            reverse('core:inventario_maestros'),
            self.admin_user,
            data={'action': 'activar', 'temporada_id': verano.id_temporada},
        )
        self.assertEqual(resp_temp_act.status_code, 302)
        verano.refresh_from_db()
        self.primavera.refresh_from_db()
        self.assertTrue(verano.es_activa)
        self.assertFalse(self.primavera.es_activa)

        # Auditoría
        resp_aud = self._call_view(
            AuditoriaListView.as_view(),
            'GET',
            reverse('core:inventario_auditoria'),
            self.admin_user,
        )
        self.assertEqual(resp_aud.status_code, 200)
        html_aud = resp_aud.content.decode('utf-8')
        self.assertIn('INV-004', html_aud)
        self.assertIn('Traslado interno', html_aud)
        self.assertIn('(-2)', html_aud)


class VentasPOSServiceAndViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.grupo_admin = Group.objects.create(name=GRUPO_ADMINISTRADORA)
        self.grupo_operador = Group.objects.create(name=GRUPO_OPERADOR)

        self.admin_user = User.objects.create_user(
            username='admin_pos',
            password='Password123!',
        )
        self.admin_user.groups.add(self.grupo_admin)

        self.operador_user = User.objects.create_user(
            username='operador_pos',
            password='Password123!',
            first_name='Camila',
            last_name='Ríos',
        )
        self.operador_user.groups.add(self.grupo_operador)

        self.primavera = Temporada.objects.create(nombre='Primavera', es_activa=True)

        self.prod_5000 = Producto.objects.create(
            sku='POS-001',
            id_temporada=self.primavera,
            nombre_comun='Helecho Costilla de Vaca',
            precio_unitario=5000,
            stock_actual=6,
            stock_minimo=5,
            activo=True,
        )
        self.prod_8900 = Producto.objects.create(
            sku='POS-002',
            id_temporada=self.primavera,
            nombre_comun='Arrayán de Valdivia',
            precio_unitario=8900,
            stock_actual=4,
            stock_minimo=5,
            activo=True,
        )
        self.prod_agotado = Producto.objects.create(
            sku='POS-003',
            id_temporada=self.primavera,
            nombre_comun='Murtilla Austral',
            precio_unitario=6500,
            stock_actual=0,
            stock_minimo=5,
            activo=True,
        )

    def _call_view(self, view_func, method, path, user, data=None, **kwargs):
        from django.contrib.messages.middleware import MessageMiddleware

        if method == 'GET':
            req = self.factory.get(path, data or {})
        else:
            req = self.factory.post(path, data or {})
        _attach_session(req)
        MessageMiddleware(lambda r: HttpResponse()).process_request(req)
        req.user = user
        resp = view_func(req, **kwargs)
        if hasattr(resp, 'render'):
            resp.render()
        return resp

    def test_hu04_venta_calculo_iva_dl825_idempotencia_y_auditoria(self):
        from services.transaccion import registrar_venta_meson

        idem_key = uuid.uuid4()
        venta = registrar_venta_meson(
            usuario=self.operador_user,
            items=[{'id_producto': self.prod_5000.id_producto, 'cantidad': 1}],
            metodo_pago=Venta.METODO_EFECTIVO,
            idempotency_key=idem_key,
        )

        self.assertEqual(venta.total_bruto, 5000)
        self.assertEqual(venta.total_neto, 4202)
        self.assertEqual(venta.monto_iva, 798)
        self.assertEqual(venta.total_neto + venta.monto_iva, venta.total_bruto)

        self.prod_5000.refresh_from_db()
        self.assertEqual(self.prod_5000.stock_actual, 5)
        self.assertTrue(self.prod_5000.es_stock_critico)

        # Congelamiento de precio histórico
        self.prod_5000.precio_unitario = 7900
        self.prod_5000.save(update_fields=['precio_unitario'])
        detalle = venta.detalles.first()
        self.assertEqual(detalle.precio_unit_hist, 5000)
        self.assertEqual(detalle.subtotal, 5000)

        # Auditoría inmutable creada
        auditoria = AuditoriaStock.objects.get(id_producto=self.prod_5000)
        self.assertEqual(auditoria.stock_anterior, 6)
        self.assertEqual(auditoria.stock_nuevo, 5)
        self.assertEqual(
            auditoria.motivo_ajuste,
            f'Venta #{venta.id_venta}: Venta mesón (Efectivo)',
        )

        # Reenvío con el mismo idempotency_key no descuenta stock de nuevo
        venta_duplicada = registrar_venta_meson(
            usuario=self.operador_user,
            items=[{'id_producto': self.prod_5000.id_producto, 'cantidad': 1}],
            metodo_pago=Venta.METODO_EFECTIVO,
            idempotency_key=str(idem_key),
        )
        self.assertEqual(venta_duplicada.id_venta, venta.id_venta)
        self.prod_5000.refresh_from_db()
        self.assertEqual(self.prod_5000.stock_actual, 5)
        self.assertEqual(Venta.objects.count(), 1)
        self.assertEqual(AuditoriaStock.objects.count(), 1)

    def test_registrar_venta_meson_rollback_ante_stock_insuficiente(self):
        from services.transaccion import registrar_venta_meson

        with self.assertRaises(ValidationError) as ctx:
            registrar_venta_meson(
                usuario=self.operador_user,
                items=[
                    {'id_producto': self.prod_5000.id_producto, 'cantidad': 2},
                    {'id_producto': self.prod_8900.id_producto, 'cantidad': 10},
                ],
                metodo_pago=Venta.METODO_POS_TARJETA,
                idempotency_key=uuid.uuid4(),
            )

        self.assertIn('Stock insuficiente para Arrayán de Valdivia', str(ctx.exception))
        self.prod_5000.refresh_from_db()
        self.prod_8900.refresh_from_db()
        self.assertEqual(self.prod_5000.stock_actual, 6)
        self.assertEqual(self.prod_8900.stock_actual, 4)
        self.assertEqual(Venta.objects.count(), 0)
        self.assertEqual(AuditoriaStock.objects.count(), 0)

    def test_vistas_pos_y_comprobante_rbac_y_flujo_completo(self):
        from core.views.ventas import ComprobanteVentaView, VentaMesonView

        # Anónimo recibe 403
        resp_anon = self._call_view(
            VentaMesonView.as_view(),
            'GET',
            reverse('core:venta_meson'),
            AnonymousUser(),
        )
        self.assertEqual(resp_anon.status_code, 403)

        # GET POS como operador
        resp_get = self._call_view(
            VentaMesonView.as_view(),
            'GET',
            reverse('core:venta_meson'),
            self.operador_user,
        )
        self.assertEqual(resp_get.status_code, 200)
        html_pos = resp_get.content.decode('utf-8')
        self.assertIn('Helecho Costilla de Vaca', html_pos)
        self.assertIn('Murtilla Austral', html_pos)
        self.assertIn('Sin Stock', html_pos)
        self.assertIn('Confirmar Venta y Emitir Comprobante', html_pos)
        self.assertIn('name="idempotency_key"', html_pos)

        # POST exitoso redirige a comprobante
        idem_post = str(uuid.uuid4())
        resp_post = self._call_view(
            VentaMesonView.as_view(),
            'POST',
            reverse('core:venta_meson'),
            self.operador_user,
            data={
                'idempotency_key': idem_post,
                'metodo_pago': Venta.METODO_TRANSFERENCIA,
                'items_json': f'[{{"id_producto": {self.prod_5000.id_producto}, "cantidad": 2}}]',
            },
        )
        self.assertEqual(resp_post.status_code, 302)
        venta_creada = Venta.objects.get(idempotency_key=idem_post)
        self.assertEqual(resp_post.url, f'/ventas/comprobante/{venta_creada.id_venta}/')

        # GET Comprobante
        resp_comp = self._call_view(
            ComprobanteVentaView.as_view(),
            'GET',
            reverse('core:comprobante_venta', args=[venta_creada.id_venta]),
            self.operador_user,
            id_venta=venta_creada.id_venta,
        )
        self.assertEqual(resp_comp.status_code, 200)
        html_comp = resp_comp.content.decode('utf-8')
        self.assertIn(
            'Comprobante de Control Interno — No Válido como Boleta Electrónica SII',
            html_comp,
        )
        self.assertIn('$10.000', html_comp)
        self.assertIn('$8.403', html_comp)
        self.assertIn('$1.597', html_comp)
        self.assertIn('data-print', html_comp)
        self.assertIn('js/panel.', html_comp)
        self.assertNotIn('onclick=', html_comp)
        self.assertIn('Nueva Venta', html_comp)


class AuditoriaQAXPTests(TestCase):
    """Suite obligatoria XP/BDD (HU-01 a HU-08) exigida por el skill auditoria-qa-xp."""

    def setUp(self):
        self.factory = RequestFactory()
        self.grupo_admin = Group.objects.create(name=GRUPO_ADMINISTRADORA)
        self.grupo_operador = Group.objects.create(name=GRUPO_OPERADOR)

        self.admin_user = User.objects.create_user(
            username='admin_qa',
            password='Password123!',
            first_name='Elena',
            last_name='Vargas',
        )
        self.admin_user.groups.add(self.grupo_admin)

        self.operador_user = User.objects.create_user(
            username='operador_qa',
            password='Password123!',
            first_name='Tomás',
            last_name='Muñoz',
        )
        self.operador_user.groups.add(self.grupo_operador)

        self.primavera = Temporada.objects.create(nombre='Primavera', es_activa=True)
        self.verano = Temporada.objects.create(nombre='Verano', es_activa=False)

    def _get_vista(self, path: str, user, data=None):
        """Resuelve la ruta real y ejecuta la vista con sesión (compatible Python 3.12-3.14)."""
        from django.contrib.messages.middleware import MessageMiddleware
        from django.urls import resolve

        match = resolve(path)
        req = self.factory.get(path, data or {})
        _attach_session(req)
        MessageMiddleware(lambda r: HttpResponse()).process_request(req)
        req.user = user
        resp = match.func(req, *match.args, **match.kwargs)
        if hasattr(resp, 'render'):
            resp.render()
        return resp

    def _crear_jpg_bytes(self, size=(1200, 900)) -> bytes:
        buf = io.BytesIO()
        Image.new('RGB', size, color=(27, 67, 50)).save(buf, format='JPEG', quality=95)
        buf.seek(0)
        return buf.read()

    def test_hu01_catalogo_publico_estacional_y_fijos(self):
        Producto.objects.create(
            sku='HU01-PRIM',
            id_temporada=self.primavera,
            nombre_comun='Copihue de Primavera',
            precio_unitario=12500,
            stock_actual=8,
            es_fijo=False,
            activo=True,
        )
        Producto.objects.create(
            sku='HU01-FIJO',
            id_temporada=None,
            nombre_comun='Sustrato Nativo 25L',
            precio_unitario=4900,
            stock_actual=15,
            es_fijo=True,
            activo=True,
        )
        Producto.objects.create(
            sku='HU01-VER',
            id_temporada=self.verano,
            nombre_comun='Girasol de Verano',
            precio_unitario=3500,
            stock_actual=10,
            es_fijo=False,
            activo=True,
        )
        Producto.objects.create(
            sku='HU01-INACT',
            id_temporada=self.primavera,
            nombre_comun='Especie Desactivada',
            precio_unitario=6000,
            stock_actual=5,
            es_fijo=True,
            activo=False,
        )

        resp = self._get_vista('/', AnonymousUser())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('Copihue de Primavera', html)
        self.assertIn('Sustrato Nativo 25L', html)
        self.assertNotIn('Girasol de Verano', html)
        self.assertNotIn('Especie Desactivada', html)

    def test_hu02_rbac_bloqueo_operador_en_reportes_y_auditoria(self):
        self.assertTrue(
            self.client.login(username='operador_qa', password='Password123!')
        )

        resp_reportes = self.client.get('/reportes/')
        self.assertEqual(resp_reportes.status_code, 403)

        resp_auditoria = self.client.get('/inventario/auditoria/')
        self.assertEqual(resp_auditoria.status_code, 403)

        resp_crear = self.client.get('/inventario/crear/')
        self.assertEqual(resp_crear.status_code, 403)

        self.client.logout()
        self.assertEqual(self._get_vista('/reportes/', self.admin_user).status_code, 200)
        self.assertEqual(
            self._get_vista('/inventario/auditoria/', self.admin_user).status_code,
            200,
        )

    def test_hu03_inventario_rechaza_stock_negativo_y_convierte_webp(self):
        from core.forms import ProductoForm

        form_negativo = ProductoForm(
            data={
                'sku': 'HU03-NEG',
                'nombre_comun': 'Arrayán Blanco',
                'precio_unitario': 7500,
                'stock_actual': -3,
                'stock_minimo': 5,
                'es_fijo': False,
                'id_temporada': self.primavera.id_temporada,
            }
        )
        self.assertFalse(form_negativo.is_valid())
        self.assertIn('stock_actual', form_negativo.errors)

        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                Producto.objects.create(
                    sku='HU03-DB-NEG',
                    id_temporada=self.primavera,
                    nombre_comun='Prueba DB Negativa',
                    precio_unitario=5000,
                    stock_actual=-1,
                )

        self.assertTrue(
            self.client.login(username='admin_qa', password='Password123!')
        )
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media, STORAGES=LOCAL_MEDIA_STORAGES):
                imagen_jpg = SimpleUploadedFile(
                    'foto_vivero.jpg',
                    self._crear_jpg_bytes(size=(1600, 1200)),
                    content_type='image/jpeg',
                )
                resp = self.client.post(
                    '/inventario/crear/',
                    {
                        'sku': 'HU03-WEBP',
                        'nombre_comun': 'Maqui Patagónico',
                        'nombre_cientifico': 'Aristotelia chilensis',
                        'id_temporada': self.primavera.id_temporada,
                        'precio_unitario': 9800,
                        'stock_actual': 10,
                        'stock_minimo': 5,
                        'descripcion_cuidados': 'Semisombra.',
                        'url_imagen': imagen_jpg,
                    },
                )
                self.assertEqual(resp.status_code, 302)
                producto = Producto.objects.get(sku='HU03-WEBP')
                self.assertTrue(producto.url_imagen.name.endswith('.webp'))
                self.assertLessEqual(producto.url_imagen.size, MAX_PESO_BYTES)
                with Image.open(producto.url_imagen.path) as img_webp:
                    self.assertEqual(img_webp.format, 'WEBP')
                    self.assertLessEqual(img_webp.width, 800)

    def test_hu04_venta_calculo_iva_dl825_e_idempotencia(self):
        prod = Producto.objects.create(
            sku='HU04-001',
            id_temporada=self.primavera,
            nombre_comun='Helecho Nativo',
            precio_unitario=5000,
            stock_actual=10,
            stock_minimo=5,
            activo=True,
        )
        self.assertTrue(
            self.client.login(username='operador_qa', password='Password123!')
        )

        idem_key = str(uuid.uuid4())
        payload = {
            'idempotency_key': idem_key,
            'metodo_pago': Venta.METODO_EFECTIVO,
            'items_json': f'[{{"id_producto": {prod.id_producto}, "cantidad": 1}}]',
        }

        resp1 = self.client.post('/ventas/pos/', payload)
        self.assertEqual(resp1.status_code, 302)

        venta = Venta.objects.get(idempotency_key=idem_key)
        self.assertEqual(venta.total_bruto, 5000)
        self.assertEqual(venta.total_neto, 4202)
        self.assertEqual(venta.monto_iva, 798)
        self.assertEqual(resp1.url, f'/ventas/comprobante/{venta.id_venta}/')

        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 9)

        # Reenvío idempotente con el mismo UUID no debe descontar stock ni duplicar venta
        resp2 = self.client.post('/ventas/pos/', payload)
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(resp2.url, f'/ventas/comprobante/{venta.id_venta}/')
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 9)
        self.assertEqual(Venta.objects.filter(idempotency_key=idem_key).count(), 1)

    def test_hu05_alerta_stock_critico_frontera(self):
        from services.transaccion import registrar_venta_meson

        prod = Producto.objects.create(
            sku='HU05-001',
            id_temporada=self.primavera,
            nombre_comun='Maitén del Sur',
            precio_unitario=6500,
            stock_actual=6,
            stock_minimo=5,
            activo=True,
        )
        self.assertFalse(prod.es_stock_critico)

        html_sin_alerta = self._get_vista(
            '/panel/',
            self.operador_user,
        ).content.decode('utf-8')
        self.assertNotIn('Alerta de Stock Crítico', html_sin_alerta)

        # Rebajar 1 unidad: stock queda en 5 (umbral crítico <= 5)
        registrar_venta_meson(
            usuario=self.operador_user,
            items=[{'id_producto': prod.id_producto, 'cantidad': 1}],
            metodo_pago=Venta.METODO_EFECTIVO,
            idempotency_key=uuid.uuid4(),
        )
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 5)
        self.assertTrue(prod.es_stock_critico)

        html_con_alerta = self._get_vista(
            '/panel/',
            self.operador_user,
        ).content.decode('utf-8')
        self.assertIn('Alerta de Stock Crítico', html_con_alerta)
        self.assertIn('Maitén del Sur', html_con_alerta)

        # Agotar las 5 unidades restantes
        registrar_venta_meson(
            usuario=self.operador_user,
            items=[{'id_producto': prod.id_producto, 'cantidad': 5}],
            metodo_pago=Venta.METODO_POS_TARJETA,
            idempotency_key=uuid.uuid4(),
        )
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 0)

        # Con stock=0 debe bloquearse cualquier nueva venta
        with self.assertRaises(ValidationError):
            registrar_venta_meson(
                usuario=self.operador_user,
                items=[{'id_producto': prod.id_producto, 'cantidad': 1}],
                metodo_pago=Venta.METODO_EFECTIVO,
                idempotency_key=uuid.uuid4(),
            )
        prod.refresh_from_db()
        self.assertEqual(prod.stock_actual, 0)

    def test_hu06_exportacion_excel_valida(self):
        tz_cl = ZoneInfo('America/Santiago')
        usuario_formula = User.objects.create_user(
            username='op_formula',
            password='Password123!',
            first_name='=SUM(1,1)',
            last_name='Prueba',
        )

        # Venta 1: Noviembre 2026 (nombre con posible formula injection)
        v1 = Venta.objects.create(
            id_usuario=usuario_formula,
            total_bruto=5000,
            total_neto=4202,
            monto_iva=798,
            metodo_pago=Venta.METODO_EFECTIVO,
            idempotency_key=uuid.uuid4(),
        )
        Venta.objects.filter(pk=v1.pk).update(
            fecha_hora=datetime(2026, 11, 10, 15, 30, tzinfo=tz_cl)
        )

        # Venta 2: 30 de Noviembre 2026 22:30 America/Santiago (01:30 UTC del 1 de Dic)
        v2 = Venta.objects.create(
            id_usuario=self.operador_user,
            total_bruto=11900,
            total_neto=10000,
            monto_iva=1900,
            metodo_pago=Venta.METODO_TRANSFERENCIA,
            idempotency_key=uuid.uuid4(),
        )
        Venta.objects.filter(pk=v2.pk).update(
            fecha_hora=datetime(2026, 11, 30, 22, 30, tzinfo=tz_cl)
        )

        # Venta 3: Octubre 2026 (no debe entrar en filtro 11/2026, sí en histórico)
        v3 = Venta.objects.create(
            id_usuario=self.admin_user,
            total_bruto=23800,
            total_neto=20000,
            monto_iva=3800,
            metodo_pago=Venta.METODO_POS_TARJETA,
            idempotency_key=uuid.uuid4(),
        )
        Venta.objects.filter(pk=v3.pk).update(
            fecha_hora=datetime(2026, 10, 15, 11, 0, tzinfo=tz_cl)
        )

        self.assertTrue(
            self.client.login(username='admin_qa', password='Password123!')
        )

        # Vista HTML del período Noviembre 2026
        resp_html = self._get_vista(
            '/reportes/',
            self.admin_user,
            {'mes': '11', 'anio': '2026'},
        )
        self.assertEqual(resp_html.status_code, 200)
        html = resp_html.content.decode('utf-8')
        self.assertIn('Noviembre 2026', html)
        self.assertIn('$16.900', html)
        self.assertIn('$14.202', html)
        self.assertIn('$2.698', html)

        # Descarga .xlsx filtrado por Noviembre 2026
        resp_xlsx = self.client.get(
            '/reportes/',
            {'mes': '11', 'anio': '2026', 'descargar': '1'},
        )
        self.assertEqual(resp_xlsx.status_code, 200)
        self.assertEqual(
            resp_xlsx['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertEqual(
            resp_xlsx['Content-Disposition'],
            'attachment; filename="Reporte_Ventas_Vivero_2026_11.xlsx"',
        )

        wb = openpyxl.load_workbook(io.BytesIO(resp_xlsx.content), data_only=True)
        ws = wb['Ventas Vivero']

        cabeceras = [ws.cell(row=4, column=c).value for c in range(1, 8)]
        self.assertEqual(
            cabeceras,
            [
                'Folio',
                'Fecha y Hora',
                'Operador',
                'Método de Pago',
                'Total Bruto ($CLP)',
                'Base Neta ($CLP)',
                'IVA 19% ($CLP)',
            ],
        )
        self.assertTrue(ws.cell(row=4, column=1).fill.start_color.rgb.endswith('1B4332'))

        # Sanitización contra formula injection en operador (fila 5)
        operador_celda = str(ws.cell(row=5, column=3).value)
        self.assertFalse(operador_celda.startswith(('=', '+', '-', '@')))
        self.assertEqual(ws.cell(row=5, column=5).number_format, '$#,##0')

        # Deben existir exactamente 2 filas de datos (filas 5 y 6) y totales en fila 7
        self.assertEqual(ws.cell(row=5, column=5).value, 5000)
        self.assertEqual(ws.cell(row=6, column=5).value, 11900)
        self.assertEqual(ws.cell(row=7, column=1).value, 'TOTALES CONSOLIDADOS')
        self.assertEqual(ws.cell(row=7, column=5).value, 16900)
        self.assertEqual(ws.cell(row=7, column=6).value, 14202)
        self.assertEqual(ws.cell(row=7, column=7).value, 2698)
        self.assertTrue(ws.cell(row=7, column=1).fill.start_color.rgb.endswith('D8F3DC'))
        self.assertTrue(ws.cell(row=7, column=1).font.bold)

        # Descarga consolidada histórica ("todos")
        resp_hist = self.client.get(
            '/reportes/',
            {'mes': 'todos', 'anio': 'todos', 'descargar': '1'},
        )
        self.assertEqual(resp_hist.status_code, 200)
        self.assertEqual(
            resp_hist['Content-Disposition'],
            'attachment; filename="Reporte_Ventas_Vivero_Historico.xlsx"',
        )
        wb_hist = openpyxl.load_workbook(io.BytesIO(resp_hist.content), data_only=True)
        ws_hist = wb_hist['Ventas Vivero']
        self.assertEqual(ws_hist.cell(row=8, column=1).value, 'TOTALES CONSOLIDADOS')
        self.assertEqual(ws_hist.cell(row=8, column=5).value, 40700)
        self.assertEqual(ws_hist.cell(row=8, column=6).value, 34202)
        self.assertEqual(ws_hist.cell(row=8, column=7).value, 6498)

    def test_hu07_unicidad_temporada_activa(self):
        self.assertTrue(
            self.client.login(username='admin_qa', password='Password123!')
        )
        resp = self.client.post(
            '/temporadas/',
            {'action': 'activar', 'temporada_id': self.verano.id_temporada},
        )
        self.assertEqual(resp.status_code, 302)

        self.primavera.refresh_from_db()
        self.verano.refresh_from_db()
        self.assertTrue(self.verano.es_activa)
        self.assertFalse(self.primavera.es_activa)
        self.assertEqual(Temporada.objects.filter(es_activa=True).count(), 1)

    def test_hu08_auditoria_inmutable_se_registra_automaticamente(self):
        from services.inventario import ajustar_stock_producto
        from services.transaccion import registrar_venta_meson

        prod = Producto.objects.create(
            sku='HU08-001',
            id_temporada=self.primavera,
            nombre_comun='Avellano Chileno',
            precio_unitario=14000,
            stock_actual=10,
            stock_minimo=5,
            activo=True,
        )

        # 1. Auditoría por venta en mesón (-3 unidades)
        venta = registrar_venta_meson(
            usuario=self.operador_user,
            items=[{'id_producto': prod.id_producto, 'cantidad': 3}],
            metodo_pago=Venta.METODO_EFECTIVO,
            idempotency_key=uuid.uuid4(),
        )
        aud_venta = AuditoriaStock.objects.get(
            id_producto=prod,
            id_usuario=self.operador_user,
        )
        self.assertEqual(aud_venta.stock_anterior, 10)
        self.assertEqual(aud_venta.stock_nuevo, 7)
        self.assertEqual(aud_venta.stock_nuevo - aud_venta.stock_anterior, -3)
        self.assertIn(f'Venta #{venta.id_venta}', aud_venta.motivo_ajuste)

        # 2. Auditoría por merma administrativa (-2 unidades)
        aud_merma = ajustar_stock_producto(
            producto_id=prod.id_producto,
            usuario=self.admin_user,
            tipo_movimiento='merma',
            cantidad=2,
            motivo='Hojas quemadas por sol',
        )
        self.assertEqual(aud_merma.id_usuario, self.admin_user)
        self.assertEqual(aud_merma.stock_anterior, 7)
        self.assertEqual(aud_merma.stock_nuevo, 5)
        self.assertEqual(aud_merma.stock_nuevo - aud_merma.stock_anterior, -2)
        self.assertIn('[Merma / Ajuste]', aud_merma.motivo_ajuste)

        self.assertEqual(AuditoriaStock.objects.filter(id_producto=prod).count(), 2)

        resp_aud = self._get_vista('/inventario/auditoria/', self.admin_user)
        self.assertEqual(resp_aud.status_code, 200)
        html_aud = resp_aud.content.decode('utf-8')
        self.assertIn('HU08-001', html_aud)
        self.assertIn('(-3)', html_aud)
        self.assertIn('(-2)', html_aud)


class HorticolaSeedAndUITests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_seed_vivero_reset_y_catalogo_horticola(self):
        from django.core.management import call_command

        from core.views.catalogo import CatalogoListView

        temp_vieja = Temporada.objects.create(nombre='Vieja', es_activa=True)
        Producto.objects.create(
            sku='OLD-999',
            id_temporada=temp_vieja,
            nombre_comun='Planta Antigua',
            precio_unitario=5000,
            stock_actual=10,
            activo=True,
        )

        call_command('seed_vivero', '--reset', stdout=io.StringIO())

        self.assertFalse(Producto.objects.filter(sku='OLD-999').exists())
        self.assertEqual(Producto.objects.count(), 12)
        self.assertEqual(Producto.objects.filter(es_fijo=True).count(), 4)
        self.assertEqual(Producto.objects.filter(es_fijo=False).count(), 8)
        self.assertEqual(Temporada.objects.filter(es_activa=True).count(), 1)
        self.assertTrue(Temporada.objects.get(nombre='Primavera').es_activa)

        self.assertTrue(Producto.objects.get(sku='HOR-FIJ-03').es_stock_critico)
        self.assertTrue(Producto.objects.get(sku='HOR-PRI-03').es_stock_critico)
        self.assertEqual(Producto.objects.get(sku='HOR-PRI-05').stock_actual, 0)

        req = self.factory.get(reverse('core:catalogo'))
        req.user = AnonymousUser()
        resp = CatalogoListView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        resp.render()
        html = resp.content.decode('utf-8')
        self.assertIn('Catálogo de Hortalizas, Almácigos y Plantines', html)
        self.assertIn('Almácigo Tomate Limachino', html)
        self.assertIn('Sustrato Almácigos Hortalizas 25L', html)
        self.assertIn('catalogo-skeleton-grid', html)
        self.assertIn('ficha-modal', html)
        self.assertIn('Ver detalles de cultivo', html)
        self.assertIn('Riego:', html)

    def test_sidebar_viewport_locked_y_badge_stock_critico(self):
        from django.core.management import call_command

        call_command('seed_vivero', '--reset', stdout=io.StringIO())
        admin_user = User.objects.get(username='admin_vivero')

        req = _attach_session(self.factory.get(reverse('core:dashboard')))
        req.user = admin_user
        resp = DashboardOperacionalView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('h-screen overflow-hidden flex', html)
        self.assertIn('Operación Diaria', html)
        self.assertIn('Catálogo e Inventario', html)
        self.assertIn('Control y Finanzas', html)
        self.assertIn('Ver Catálogo Público', html)
        self.assertIn('Control de Inventario', html)

    def test_estaticos_sin_cdn_y_modal_catalogo_completo(self):
        from django.core.management import call_command
        from core.views.catalogo import CatalogoListView

        call_command('seed_vivero', '--reset', stdout=io.StringIO())
        admin_user = User.objects.get(username='admin_vivero')

        # 1. Catálogo público: sin CDN, con tailwind.min.css, botanico.css, catalogo.js y atributos modal
        req_cat = self.factory.get(reverse('core:catalogo'))
        req_cat.user = AnonymousUser()
        resp_cat = CatalogoListView.as_view()(req_cat)
        resp_cat.render()
        html_cat = resp_cat.content.decode('utf-8')
        self.assertNotIn('cdn.tailwindcss.com', html_cat)
        self.assertRegex(html_cat, r'css/tailwind\.min(\.[a-f0-9]+)?\.css')
        self.assertRegex(html_cat, r'css/botanico(\.[a-f0-9]+)?\.css')
        self.assertRegex(html_cat, r'js/catalogo(\.[a-f0-9]+)?\.js')
        self.assertIn('data-open-modal', html_cat)
        self.assertIn('data-close-modal', html_cat)
        self.assertIn('data-imagen=', html_cat)
        self.assertIn('ficha-modal', html_cat)

        # 2. Panel interno: sin CDN, con tailwind.min.css y botanico.css
        req_panel = _attach_session(self.factory.get(reverse('core:dashboard')))
        req_panel.user = admin_user
        resp_panel = DashboardOperacionalView.as_view()(req_panel)
        html_panel = resp_panel.content.decode('utf-8')
        self.assertNotIn('cdn.tailwindcss.com', html_panel)
        self.assertRegex(html_panel, r'css/tailwind\.min(\.[a-f0-9]+)?\.css')
        self.assertRegex(html_panel, r'css/botanico(\.[a-f0-9]+)?\.css')

        # 3. Login: sin CDN, con tailwind.min.css
        req_login = _attach_session(self.factory.get(reverse('core:login')))
        req_login.user = AnonymousUser()
        resp_login = LoginViveroView.as_view()(req_login)
        html_login = resp_login.content.decode('utf-8')
        self.assertNotIn('cdn.tailwindcss.com', html_login)
        self.assertRegex(html_login, r'css/tailwind\.min(\.[a-f0-9]+)?\.css')




