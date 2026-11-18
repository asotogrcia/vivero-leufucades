import io
import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
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

        self.assertNotIn('/inventario/crear/', html)
        self.assertNotIn('/temporadas/', html)
        self.assertNotIn('/inventario/auditoria/', html)
        self.assertNotIn('/reportes/', html)

    def test_dashboard_administradora_muestra_opciones_admin(self):
        req = _attach_session(self.factory.get(reverse('core:dashboard')))
        req.user = self.admin_user
        resp = DashboardOperacionalView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

        html = resp.content.decode('utf-8')
        self.assertIn('/inventario/crear/', html)
        self.assertIn('/temporadas/', html)
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
            with override_settings(MEDIA_ROOT=tmp_media):
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
            with override_settings(MEDIA_ROOT=tmp_media):
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
