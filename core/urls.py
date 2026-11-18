from django.urls import path

from core.views.auth_panel import (
    DashboardOperacionalView,
    LoginViveroView,
    LogoutViveroView,
)

app_name = 'core'

urlpatterns = [
    path('panel/login/', LoginViveroView.as_view(), name='login'),
    path('panel/logout/', LogoutViveroView.as_view(), name='logout'),
    path('panel/', DashboardOperacionalView.as_view(), name='dashboard'),
]
