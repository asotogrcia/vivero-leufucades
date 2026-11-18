from django.db.models import Q
from django.views.generic import ListView

from core.models import Producto, Temporada


class CatalogoListView(ListView):
    """Catálogo comercial público de Vivero Leufucades (100% anónimo, sin login)."""

    model = Producto
    template_name = 'catalogo/catalogo.html'
    context_object_name = 'productos'

    def _resolver_temporada_param(self) -> str:
        raw = self.request.GET.get('temporada', '').strip()
        if not raw or raw == 'actual':
            return 'actual'
        if raw in ('fijos', 'todas') or raw.isdigit():
            return raw
        return 'actual'

    def get_queryset(self):
        queryset = (
            Producto.objects.select_related('id_temporada')
            .only(
                'id_producto', 'sku', 'nombre_comun', 'nombre_cientifico',
                'precio_unitario', 'stock_actual', 'es_fijo',
                'descripcion_cuidados', 'url_imagen', 'id_temporada__nombre',
            )
            .filter(activo=True)
        )

        temporada_param = self._resolver_temporada_param()
        if temporada_param == 'actual':
            queryset = queryset.filter(
                Q(id_temporada__es_activa=True) | Q(es_fijo=True)
            )
        elif temporada_param == 'fijos':
            queryset = queryset.filter(es_fijo=True)
        elif temporada_param.isdigit():
            queryset = queryset.filter(id_temporada_id=int(temporada_param))
        # Si temporada_param == 'todas', se mantienen todos los productos activos.

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
        temporadas = list(Temporada.objects.all())
        temporada_activa = next((t for t in temporadas if t.es_activa), None)
        temporada_seleccionada = self._resolver_temporada_param()

        context.update(
            {
                'temporadas': temporadas,
                'temporada_activa': temporada_activa,
                'temporada_seleccionada': temporada_seleccionada,
                'temporada_seleccionada_obj': next(
                    (
                        t
                        for t in temporadas
                        if str(t.id_temporada) == temporada_seleccionada
                    ),
                    None,
                ),
                'query': self.request.GET.get('q', '').strip(),
            }
        )
        return context
