from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from core.decorators import requiere_administradora
from core.forms import AjusteStockForm, ProductoForm, TemporadaForm
from core.models import AuditoriaStock, Producto, Temporada
from services.inventario import (
    activar_temporada_comercial,
    ajustar_stock_producto,
    crear_o_actualizar_producto,
    desactivar_producto,
)


@method_decorator(requiere_administradora, name='dispatch')
class InventarioListView(ListView):
    """Listado maestro de inventario con filtros por búsqueda y estado de stock."""

    model = Producto
    template_name = 'inventario/inventario_list.html'
    context_object_name = 'productos'
    paginate_by = 20

    def _resolver_estado(self) -> str:
        estado = self.request.GET.get('estado', 'todos').strip().lower()
        if estado in ('todos', 'critico', 'agotados'):
            return estado
        return 'todos'

    def get_queryset(self):
        queryset = (
            Producto.objects.select_related('id_temporada')
            .filter(activo=True)
            .order_by('nombre_comun', 'sku')
        )

        estado = self._resolver_estado()
        if estado == 'critico':
            queryset = queryset.filter(stock_actual__lte=F('stock_minimo'))
        elif estado == 'agotados':
            queryset = queryset.filter(stock_actual=0)

        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(nombre_comun__icontains=query)
                | Q(nombre_cientifico__icontains=query)
                | Q(sku__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resumen = Producto.objects.filter(activo=True).aggregate(
            total_activos=Count('id_producto'),
            total_criticos=Count(
                'id_producto',
                filter=Q(stock_actual__lte=F('stock_minimo')),
            ),
            total_agotados=Count('id_producto', filter=Q(stock_actual=0)),
        )
        context.update(
            {
                'query': self.request.GET.get('q', '').strip(),
                'estado_seleccionado': self._resolver_estado(),
                'resumen_inventario': resumen,
                'ajuste_form': AjusteStockForm(),
            }
        )
        return context


@method_decorator(requiere_administradora, name='dispatch')
class ProductoCreateView(View):
    """Creación de nueva especie/producto con optimización automática a WebP."""

    template_name = 'inventario/producto_form.html'

    def get(self, request):
        return render(
            request,
            self.template_name,
            {'form': ProductoForm(), 'modo': 'crear'},
        )

    def post(self, request):
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                producto = crear_o_actualizar_producto(
                    datos=form.cleaned_data,
                    imagen=request.FILES.get('url_imagen'),
                    usuario=request.user,
                )
                messages.success(
                    request,
                    f'Especie "{producto.nombre_comun}" ({producto.sku}) creada correctamente.',
                )
                return redirect('core:inventario_list')
            except ValidationError as exc:
                form.add_error(None, exc.message if hasattr(exc, 'message') else str(exc))

        return render(
            request,
            self.template_name,
            {'form': form, 'modo': 'crear'},
        )


@method_decorator(requiere_administradora, name='dispatch')
class ProductoUpdateView(View):
    """Edición de ficha de especie/producto existente."""

    template_name = 'inventario/producto_form.html'

    def get(self, request, producto_id):
        producto = get_object_or_404(Producto, pk=producto_id)
        form = ProductoForm(instance=producto)
        return render(
            request,
            self.template_name,
            {'form': form, 'producto': producto, 'modo': 'editar'},
        )

    def post(self, request, producto_id):
        producto = get_object_or_404(Producto, pk=producto_id)
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            try:
                imagen = request.FILES.get('url_imagen')
                actualizado = crear_o_actualizar_producto(
                    datos=form.cleaned_data,
                    imagen=imagen,
                    usuario=request.user,
                    producto_id=producto.id_producto,
                )
                messages.success(
                    request,
                    f'Especie "{actualizado.nombre_comun}" actualizada correctamente.',
                )
                return redirect('core:inventario_list')
            except ValidationError as exc:
                form.add_error(None, exc.message if hasattr(exc, 'message') else str(exc))

        return render(
            request,
            self.template_name,
            {'form': form, 'producto': producto, 'modo': 'editar'},
        )


@method_decorator(requiere_administradora, name='dispatch')
class ProductoDesactivarView(View):
    """Borrado lógico (activo=False) de producto exclusivo por POST."""

    http_method_names = ['post']

    def post(self, request, producto_id):
        producto = get_object_or_404(Producto, pk=producto_id)
        desactivar_producto(producto.id_producto)
        messages.success(
            request,
            f'Especie "{producto.nombre_comun}" ({producto.sku}) desactivada del catálogo.',
        )
        return redirect('core:inventario_list')


@method_decorator(requiere_administradora, name='dispatch')
class AjusteStockView(View):
    """Ejecuta ingreso de cosecha o merma/ajuste con bloqueo pesimista y auditoría."""

    http_method_names = ['post']

    def _redirect_destino(self, request):
        next_url = request.POST.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect('core:inventario_list')

    def post(self, request, producto_id):
        get_object_or_404(Producto, pk=producto_id)
        form = AjusteStockForm(request.POST)
        if not form.is_valid():
            errores = '; '.join(
                err for lista in form.errors.values() for err in lista
            )
            messages.error(request, f'Error en ajuste de stock: {errores}')
            return self._redirect_destino(request)

        try:
            auditoria = ajustar_stock_producto(
                producto_id=producto_id,
                usuario=request.user,
                tipo_movimiento=form.cleaned_data['tipo_movimiento'],
                cantidad=form.cleaned_data['cantidad'],
                motivo=form.cleaned_data['motivo'],
            )
            messages.success(
                request,
                f'Stock de "{auditoria.id_producto.nombre_comun}" actualizado: '
                f'{auditoria.stock_anterior} → {auditoria.stock_nuevo} un.',
            )
        except ValidationError as exc:
            mensaje = exc.message if hasattr(exc, 'message') else str(exc)
            messages.error(request, mensaje)

        return self._redirect_destino(request)


@method_decorator(requiere_administradora, name='dispatch')
class MaestrosTemporadasView(View):
    """Gestión de temporadas comerciales y conmutación del ciclo activo."""

    template_name = 'inventario/maestros_temporadas.html'

    def _build_context(self, form=None):
        temporadas = Temporada.objects.annotate(
            total_productos=Count(
                'productos',
                filter=Q(productos__activo=True),
            )
        ).order_by('id_temporada')
        return {
            'temporadas': temporadas,
            'form': form or TemporadaForm(),
        }

    def get(self, request):
        return render(request, self.template_name, self._build_context())

    def post(self, request):
        accion = request.POST.get('action', '').strip()

        if accion == 'activar':
            temporada_id = request.POST.get('temporada_id')
            try:
                temporada = activar_temporada_comercial(int(temporada_id))
                messages.success(
                    request,
                    f'Ciclo activo cambiado a "{temporada.nombre}".',
                )
            except (TypeError, ValueError, ValidationError) as exc:
                mensaje = exc.message if hasattr(exc, 'message') else 'Temporada no válida.'
                messages.error(request, mensaje)
            return redirect('core:inventario_maestros')

        if accion == 'crear':
            form = TemporadaForm(request.POST)
            if form.is_valid():
                nueva = form.save()
                messages.success(
                    request,
                    f'Temporada "{nueva.nombre}" creada correctamente.',
                )
                return redirect('core:inventario_maestros')
            return render(request, self.template_name, self._build_context(form=form))

        messages.error(request, 'Acción no reconocida.')
        return redirect('core:inventario_maestros')


@method_decorator(requiere_administradora, name='dispatch')
class AuditoriaListView(ListView):
    """Bitácora paginada de solo lectura de movimientos de stock."""

    model = AuditoriaStock
    template_name = 'inventario/auditoria_list.html'
    context_object_name = 'auditorias'
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            AuditoriaStock.objects.select_related('id_producto', 'id_usuario')
            .annotate(
                diferencial=ExpressionWrapper(
                    F('stock_nuevo') - F('stock_anterior'),
                    output_field=IntegerField(),
                )
            )
            .order_by('-fecha_hora', '-id_auditoria')
        )

        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(id_producto__sku__icontains=query)
                | Q(id_producto__nombre_comun__icontains=query)
                | Q(id_usuario__username__icontains=query)
                | Q(motivo_ajuste__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '').strip()
        return context
