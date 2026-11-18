import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

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
