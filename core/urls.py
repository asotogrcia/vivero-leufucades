from django.urls import path

from core.views.auth_panel import (
    DashboardOperacionalView,
    LoginViveroView,
    LogoutViveroView,
)
from core.views.catalogo import CatalogoListView

app_name = 'core'

urlpatterns = [
    path('', CatalogoListView.as_view(), name='catalogo'),
    path('panel/login/', LoginViveroView.as_view(), name='login'),
    path('panel/logout/', LogoutViveroView.as_view(), name='logout'),
    path('panel/', DashboardOperacionalView.as_view(), name='dashboard'),
]
