from django import forms
from django.core.exceptions import ValidationError

from core.models import Producto, Temporada
from services.inventario import TIPO_MOVIMIENTO_INGRESO, TIPO_MOVIMIENTO_MERMA

INPUT_CSS = (
    'w-full min-h-[44px] px-3.5 rounded-lg border border-[#E2E8E4] bg-white '
    'text-[#1F2933] text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] '
    'focus:border-[#2D6A4F]'
)


class ProductoForm(forms.ModelForm):
    """Formulario de creación/edición de especies con validación de precios, stock y estacionalidad."""

    class Meta:
        model = Producto
        fields = [
            'sku',
            'nombre_comun',
            'nombre_cientifico',
            'id_temporada',
            'es_fijo',
            'precio_unitario',
            'stock_actual',
            'stock_minimo',
            'descripcion_cuidados',
            'url_imagen',
        ]
        labels = {
            'sku': 'SKU',
            'nombre_comun': 'Nombre Común',
            'nombre_cientifico': 'Nombre Científico',
            'id_temporada': 'Temporada Comercial',
            'es_fijo': 'Producto Permanente (todo el año)',
            'precio_unitario': 'Precio Unitario Bruto ($CLP)',
            'stock_actual': 'Stock Actual (un.)',
            'stock_minimo': 'Stock Mínimo Crítico (un.)',
            'descripcion_cuidados': 'Descripción y Cuidados',
            'url_imagen': 'Fotografía de la Especie (se convertirá a WebP)',
        }
        widgets = {
            'sku': forms.TextInput(attrs={'class': INPUT_CSS, 'placeholder': 'Ej: VIV-001'}),
            'nombre_comun': forms.TextInput(
                attrs={'class': INPUT_CSS, 'placeholder': 'Ej: Copihue Rojo'}
            ),
            'nombre_cientifico': forms.TextInput(
                attrs={'class': INPUT_CSS, 'placeholder': 'Ej: Lapageria rosea'}
            ),
            'id_temporada': forms.Select(attrs={'class': INPUT_CSS}),
            'es_fijo': forms.CheckboxInput(
                attrs={
                    'class': (
                        'h-5 w-5 rounded border-[#E2E8E4] text-[#1B4332] '
                        'focus:ring-2 focus:ring-[#2D6A4F]'
                    )
                }
            ),
            'precio_unitario': forms.NumberInput(
                attrs={'class': INPUT_CSS, 'min': '0', 'step': '1', 'placeholder': '8900'}
            ),
            'stock_actual': forms.NumberInput(
                attrs={'class': INPUT_CSS, 'min': '0', 'step': '1', 'placeholder': '10'}
            ),
            'stock_minimo': forms.NumberInput(
                attrs={'class': INPUT_CSS, 'min': '0', 'step': '1', 'placeholder': '5'}
            ),
            'descripcion_cuidados': forms.Textarea(
                attrs={
                    'class': (
                        'w-full px-3.5 py-2.5 rounded-lg border border-[#E2E8E4] bg-white '
                        'text-[#1F2933] text-sm focus:outline-none focus:ring-2 '
                        'focus:ring-[#2D6A4F] focus:border-[#2D6A4F]'
                    ),
                    'rows': 3,
                    'placeholder': 'Riego, exposición solar, tipo de suelo...',
                }
            ),
            'url_imagen': forms.ClearableFileInput(
                attrs={
                    'class': (
                        'w-full text-sm text-[#52606D] file:mr-4 file:min-h-[44px] '
                        'file:px-4 file:rounded-lg file:border-0 file:text-sm '
                        'file:font-medium file:bg-[#D8F3DC] file:text-[#1B4332] '
                        'hover:file:bg-[#2D6A4F] hover:file:text-white'
                    ),
                    'accept': 'image/*',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_temporada'].empty_label = '--------- (Sin temporada / Permanente)'

    def clean_precio_unitario(self):
        precio = self.cleaned_data.get('precio_unitario')
        if precio is None or precio < 0:
            raise ValidationError('El precio unitario debe ser mayor o igual a $0 CLP.')
        return precio

    def clean_stock_actual(self):
        stock = self.cleaned_data.get('stock_actual')
        if stock is None or stock < 0:
            raise ValidationError('El stock actual no puede ser negativo.')
        return stock

    def clean_stock_minimo(self):
        minimo = self.cleaned_data.get('stock_minimo')
        if minimo is None or minimo < 0:
            raise ValidationError('El stock mínimo no puede ser negativo.')
        return minimo

    def clean(self):
        cleaned_data = super().clean()
        es_fijo = cleaned_data.get('es_fijo')
        id_temporada = cleaned_data.get('id_temporada')

        if not es_fijo and id_temporada is None:
            self.add_error(
                'id_temporada',
                'Los productos estacionales deben asociarse a una temporada comercial, '
                'o bien marcarse como Producto Permanente.',
            )
        elif es_fijo and id_temporada is not None:
            self.add_error(
                'id_temporada',
                'Un producto permanente no debe asociarse a una temporada específica.',
            )

        return cleaned_data


class AjusteStockForm(forms.Form):
    """Formulario para ingresos de cosecha o mermas/ajustes de stock con motivo obligatorio."""

    TIPO_CHOICES = [
        (TIPO_MOVIMIENTO_INGRESO, 'Ingreso de Cosecha (+)'),
        (TIPO_MOVIMIENTO_MERMA, 'Merma / Ajuste (-)'),
    ]

    tipo_movimiento = forms.ChoiceField(
        choices=TIPO_CHOICES,
        label='Tipo de Movimiento',
        widget=forms.Select(attrs={'class': INPUT_CSS}),
    )
    cantidad = forms.IntegerField(
        min_value=1,
        label='Cantidad (unidades)',
        widget=forms.NumberInput(
            attrs={'class': INPUT_CSS, 'min': '1', 'step': '1', 'placeholder': 'Ej: 5'}
        ),
    )
    motivo = forms.CharField(
        max_length=220,
        required=True,
        label='Motivo del Ajuste',
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CSS,
                'placeholder': 'Ej: Reposición de invernadero / Daño por helada',
            }
        ),
    )

    def clean_motivo(self):
        motivo = (self.cleaned_data.get('motivo') or '').strip()
        if not motivo:
            raise ValidationError('El motivo del ajuste es obligatorio.')
        return motivo


class TemporadaForm(forms.ModelForm):
    """Formulario para registrar una nueva temporada comercial."""

    class Meta:
        model = Temporada
        fields = ['nombre']
        labels = {'nombre': 'Nombre de la Temporada'}
        widgets = {
            'nombre': forms.TextInput(
                attrs={'class': INPUT_CSS, 'placeholder': 'Ej: Primavera - Verano'}
            )
        }

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise ValidationError('Ingresa un nombre válido para la temporada.')
        if Temporada.objects.filter(nombre__iexact=nombre).exists():
            raise ValidationError('Ya existe una temporada con ese nombre.')
        return nombre
