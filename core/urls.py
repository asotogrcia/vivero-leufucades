from django.urls import path

from core.views.auth_panel import (
    DashboardOperacionalView,
    LoginViveroView,
    LogoutViveroView,
)
from core.views.catalogo import CatalogoListView
from core.views.inventario import (
    AjusteStockView,
    AuditoriaListView,
    InventarioListView,
    MaestrosTemporadasView,
    ProductoCreateView,
    ProductoDesactivarView,
    ProductoUpdateView,
)

app_name = 'core'

urlpatterns = [
    path('', CatalogoListView.as_view(), name='catalogo'),
    path('panel/login/', LoginViveroView.as_view(), name='login'),
    path('panel/logout/', LogoutViveroView.as_view(), name='logout'),
    path('panel/', DashboardOperacionalView.as_view(), name='dashboard'),
    path('inventario/', InventarioListView.as_view(), name='inventario_list'),
    path('inventario/nuevo/', ProductoCreateView.as_view(), name='producto_nuevo'),
    path('inventario/crear/', ProductoCreateView.as_view(), name='producto_crear'),
    path(
        'inventario/editar/<int:producto_id>/',
        ProductoUpdateView.as_view(),
        name='producto_editar',
    ),
    path(
        'inventario/desactivar/<int:producto_id>/',
        ProductoDesactivarView.as_view(),
        name='producto_desactivar',
    ),
    path(
        'inventario/ajustar/<int:producto_id>/',
        AjusteStockView.as_view(),
        name='producto_ajustar',
    ),
    path(
        'inventario/maestros/',
        MaestrosTemporadasView.as_view(),
        name='inventario_maestros',
    ),
    path(
        'temporadas/',
        MaestrosTemporadasView.as_view(),
        name='temporadas_alias',
    ),
    path(
        'inventario/auditoria/',
        AuditoriaListView.as_view(),
        name='inventario_auditoria',
    ),
]
