import io
from datetime import datetime
from zoneinfo import ZoneInfo

import openpyxl
from django.utils import timezone
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.models import Venta

TZ_SANTIAGO = ZoneInfo('America/Santiago')

NOMBRE_MESES = {
    1: 'Enero',
    2: 'Febrero',
    3: 'Marzo',
    4: 'Abril',
    5: 'Mayo',
    6: 'Junio',
    7: 'Julio',
    8: 'Agosto',
    9: 'Septiembre',
    10: 'Octubre',
    11: 'Noviembre',
    12: 'Diciembre',
}

FORMATO_MONEDA_CLP = '$#,##0'


def sanitizar_texto_excel(valor) -> str:
    """Convierte a texto limpio y elimina prefijos (=, +, -, @) contra Excel Formula Injection."""
    if valor is None:
        return ''
    return str(valor).strip().lstrip('=+-@').strip()


def obtener_rango_periodo_santiago(
    mes: int | None = None,
    anio: int | None = None,
) -> tuple[datetime | None, datetime | None, str, str]:
    """Calcula límites temporales en America/Santiago y etiquetas del período consultado."""
    if mes is not None:
        mes_int = int(mes)
        if not 1 <= mes_int <= 12:
            raise ValueError('El mes debe estar entre 1 y 12.')
        anio_int = (
            int(anio)
            if anio is not None
            else timezone.now().astimezone(TZ_SANTIAGO).year
        )
        inicio = datetime(anio_int, mes_int, 1, 0, 0, 0, tzinfo=TZ_SANTIAGO)
        if mes_int == 12:
            fin = datetime(anio_int + 1, 1, 1, 0, 0, 0, tzinfo=TZ_SANTIAGO)
        else:
            fin = datetime(anio_int, mes_int + 1, 1, 0, 0, 0, tzinfo=TZ_SANTIAGO)
        return (
            inicio,
            fin,
            f'{anio_int}_{mes_int:02d}',
            f'{NOMBRE_MESES[mes_int]} {anio_int}',
        )

    if anio is not None:
        anio_int = int(anio)
        inicio = datetime(anio_int, 1, 1, 0, 0, 0, tzinfo=TZ_SANTIAGO)
        fin = datetime(anio_int + 1, 1, 1, 0, 0, 0, tzinfo=TZ_SANTIAGO)
        return inicio, fin, f'{anio_int}', f'Año {anio_int}'

    return None, None, 'Historico', 'Consolidado Histórico'


def obtener_ventas_periodo_qs(mes: int | None = None, anio: int | None = None):
    """Retorna el queryset de ventas ordenado cronológicamente y filtrado por período."""
    queryset = Venta.objects.select_related('id_usuario').order_by(
        'fecha_hora',
        'id_venta',
    )
    inicio, fin, _, _ = obtener_rango_periodo_santiago(mes=mes, anio=anio)
    if inicio is not None and fin is not None:
        queryset = queryset.filter(fecha_hora__gte=inicio, fecha_hora__lt=fin)
    return queryset


def generar_reporte_ventas_xlsx(
    mes: int | None = None,
    anio: int | None = None,
) -> io.BytesIO:
    """Genera un libro Excel (.xlsx) en memoria con el desglose contable DL 825."""
    queryset = obtener_ventas_periodo_qs(mes=mes, anio=anio)
    _, _, _, etiqueta_periodo = obtener_rango_periodo_santiago(mes=mes, anio=anio)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Ventas Vivero'

    ws['A1'] = 'Vivero Leufucades — Reporte Contable de Ventas (DL N.º 825)'
    ws['A1'].font = Font(name='Calibri', size=14, bold=True, color='1B4332')
    ws.merge_cells('A1:G1')

    ws['A2'] = (
        f'Período: {etiqueta_periodo} | Comprobantes de Control Interno '
        '— Zona Horaria America/Santiago'
    )
    ws['A2'].font = Font(name='Calibri', size=10, italic=True, color='52606D')
    ws.merge_cells('A2:G2')

    borde_fino = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1'),
    )
    fill_cabecera = PatternFill(
        start_color='1B4332',
        end_color='1B4332',
        fill_type='solid',
    )
    font_cabecera = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    fill_totales = PatternFill(
        start_color='D8F3DC',
        end_color='D8F3DC',
        fill_type='solid',
    )
    font_totales = Font(name='Calibri', size=11, bold=True, color='1B4332')

    cabeceras = [
        'Folio',
        'Fecha y Hora',
        'Operador',
        'Método de Pago',
        'Total Bruto ($CLP)',
        'Base Neta ($CLP)',
        'IVA 19% ($CLP)',
    ]

    for col_idx, titulo in enumerate(cabeceras, start=1):
        celda = ws.cell(row=4, column=col_idx, value=titulo)
        celda.fill = fill_cabecera
        celda.font = font_cabecera
        celda.border = borde_fino
        celda.alignment = Alignment(
            horizontal='right' if col_idx >= 5 else 'left',
            vertical='center',
        )
    ws.row_dimensions[4].height = 24

    total_bruto_acum = 0
    total_neto_acum = 0
    monto_iva_acum = 0
    conteo_ventas = 0
    row_idx = 5

    for venta in queryset.iterator(chunk_size=500):
        fecha_local = timezone.localtime(venta.fecha_hora, TZ_SANTIAGO)
        operador_raw = venta.id_usuario.get_full_name() or venta.id_usuario.username
        bruto = int(venta.total_bruto)
        neto = int(venta.total_neto)
        iva = int(venta.monto_iva)

        fila = [
            f'#{venta.id_venta}',
            fecha_local.strftime('%d/%m/%Y %H:%M'),
            sanitizar_texto_excel(operador_raw),
            sanitizar_texto_excel(venta.metodo_pago),
            bruto,
            neto,
            iva,
        ]

        for col_idx, valor in enumerate(fila, start=1):
            celda = ws.cell(row=row_idx, column=col_idx, value=valor)
            celda.border = borde_fino
            if col_idx >= 5:
                celda.number_format = FORMATO_MONEDA_CLP
                celda.alignment = Alignment(horizontal='right', vertical='center')
            else:
                celda.alignment = Alignment(horizontal='left', vertical='center')

        total_bruto_acum += bruto
        total_neto_acum += neto
        monto_iva_acum += iva
        conteo_ventas += 1
        row_idx += 1

    fila_totales = [
        'TOTALES CONSOLIDADOS',
        '',
        '',
        f'{conteo_ventas} ventas',
        total_bruto_acum,
        total_neto_acum,
        monto_iva_acum,
    ]
    for col_idx, valor in enumerate(fila_totales, start=1):
        celda = ws.cell(row=row_idx, column=col_idx, value=valor)
        celda.fill = fill_totales
        celda.font = font_totales
        celda.border = borde_fino
        if col_idx >= 5:
            celda.number_format = FORMATO_MONEDA_CLP
            celda.alignment = Alignment(horizontal='right', vertical='center')
        else:
            celda.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[row_idx].height = 22

    for col_idx in range(1, 8):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for r in range(4, row_idx + 1):
            val = ws.cell(row=r, column=col_idx).value
            if val is None:
                continue
            if col_idx >= 5 and isinstance(val, int):
                longitud = len(f'${val:,}')
            else:
                longitud = len(str(val))
            if longitud > max_len:
                max_len = longitud
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    ws.freeze_panes = 'A5'

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
