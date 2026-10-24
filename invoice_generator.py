import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime

def format_clp(val):
    if val is None or val == "":
        return "$0"
    try:
        n = int(round(float(val)))
        return f"${n:,}".replace(",", ".")
    except Exception:
        return str(val)

def generate_invoice_pdf(transaction_data, billing_info=None):
    """
    Genera un Comprobante Oficial de Compra y Pago Comercial en PDF
    con los datos de la transacción y del comprador.
    """
    if billing_info is None:
        billing_info = {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    header_title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0f172a')
    )

    header_sub_style = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )

    box_title = ParagraphStyle(
        'BoxTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1
    )

    box_num = ParagraphStyle(
        'BoxNum',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=4
    )

    cell_label = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )

    cell_val = ParagraphStyle(
        'CellVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0f172a')
    )

    cell_right_bold = ParagraphStyle(
        'CellRightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0f172a'),
        alignment=2
    )

    cell_right = ParagraphStyle(
        'CellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0f172a'),
        alignment=2
    )

    story = []

    # Datos emisor (CréditoB2B SpA)
    emisor_info = [
        Paragraph("<b>CREDITOB2B SpA</b>", header_title_style),
        Paragraph("Servicios Tecnológicos de Evaluación Financiera y Scoring Crediticio B2B", header_sub_style),
        Paragraph("R.U.T.: 77.492.831-5", header_sub_style),
        Paragraph("Giro: Actividades de consultoría de informática y servicios de información", header_sub_style),
        Paragraph("Casa Matriz: Av. Andrés Bello 2711, Las Condes, Santiago", header_sub_style),
        Paragraph("Contacto: facturacion@creditob2b.cl · www.creditob2b.cl", header_sub_style),
    ]

    # Folio / Recuadro de Comprobante Comercial
    order_id = transaction_data.get('order_id', 'ORD-0001')
    raw_num = "".join([c for c in order_id if c.isdigit()])[-6:] or "1042"
    folio = f"N° {raw_num}"
    
    fecha_emision = transaction_data.get('paid_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    receipt_box_content = [
        Paragraph("R.U.T.: 77.492.831-5", box_title),
        Spacer(1, 3),
        Paragraph("COMPROBANTE DE PAGO", box_title),
        Paragraph(folio, box_num),
        Spacer(1, 3),
        Paragraph("VENTA DE SERVICIOS DIGITALES", ParagraphStyle('SubB', parent=box_title, fontSize=7.5, textColor=colors.HexColor('#475569')))
    ]

    t_header = Table([
        [emisor_info, receipt_box_content]
    ], colWidths=[340, 200])

    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOX', (1,0), (1,0), 1.5, colors.HexColor('#1e3a8a')),
        ('TOPPADDING', (1,0), (1,0), 8),
        ('BOTTOMPADDING', (1,0), (1,0), 8),
        ('LEFTPADDING', (1,0), (1,0), 8),
        ('RIGHTPADDING', (1,0), (1,0), 8),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#f0f9ff')),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 14))

    # Identificación del Cliente / Receptor
    story.append(Paragraph("DATOS DEL RECEPTOR / CLIENTE", section_heading))
    
    razon_social = billing_info.get('razon_social') or billing_info.get('nombre') or 'Cliente Registrado'
    rut_receptor = billing_info.get('rut') or '66.888.999-K'
    giro = billing_info.get('giro') or 'Servicios Comerciales e Industriales'
    direccion = billing_info.get('direccion') or 'Santiago, Chile'
    comuna = billing_info.get('comuna') or 'Santiago'
    email = billing_info.get('email') or 'cliente@empresa.cl'
    forma_pago = billing_info.get('forma_pago') or 'Mercado Pago (Transferencia / Tarjeta de Débito o Crédito)'

    receptor_table_data = [
        [
            Paragraph("Señor(es):", cell_label), Paragraph(razon_social, cell_val),
            Paragraph("R.U.T.:", cell_label), Paragraph(rut_receptor, cell_val)
        ],
        [
            Paragraph("Giro:", cell_label), Paragraph(giro, cell_val),
            Paragraph("Fecha Emisión:", cell_label), Paragraph(str(fecha_emision)[:19], cell_val)
        ],
        [
            Paragraph("Dirección:", cell_label), Paragraph(f"{direccion}, {comuna}", cell_val),
            Paragraph("Contacto / Email:", cell_label), Paragraph(email, cell_val)
        ],
        [
            Paragraph("Forma de Pago:", cell_label), Paragraph(forma_pago, cell_val),
            Paragraph("Referencia Orden:", cell_label), Paragraph(order_id, cell_val)
        ],
    ]

    t_receptor = Table(receptor_table_data, colWidths=[80, 200, 90, 170])
    t_receptor.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_receptor)
    story.append(Spacer(1, 14))

    # Detalle de Items / Plan Contratado
    story.append(Paragraph("DETALLE DEL SERVICIO CONTRATADO", section_heading))
    
    plan_tipo = transaction_data.get('plan_tipo', 'individual')
    monto_total = float(transaction_data.get('monto', 9990))
    # Cálculo IVA (19% en Chile)
    # Si el precio incluye IVA o es Neto:
    # Mostramos desglose neto + IVA 19%
    monto_neto = round(monto_total / 1.19)
    monto_iva = monto_total - monto_neto

    plan_desc_map = {
        'individual': ('Evaluación de Capacidad de Crédito B2B - Informe Individual', '1 Dictamen formal en PDF con firmas y verificación SII'),
        'pack_3': ('Pack de 3 Evaluaciones de Crédito B2B', '3 Dictámenes formales en PDF con análisis de scoring y límites'),
        'pack_10': ('Pack de 10 Evaluaciones de Crédito B2B Corporativo', '10 Dictámenes formales en PDF descargables para comités')
    }
    desc_titulo, desc_detalle = plan_desc_map.get(plan_tipo, (f"Servicio Plan {plan_tipo}", "Evaluaciones de Crédito B2B"))

    items_data = [
        [
            Paragraph("Código", cell_label),
            Paragraph("Descripción", cell_label),
            Paragraph("Cant.", cell_label),
            Paragraph("Precio Unit.", cell_right_bold),
            Paragraph("Total Neto", cell_right_bold)
        ],
        [
            Paragraph(plan_tipo.upper(), cell_val),
            Paragraph(f"<b>{desc_titulo}</b><br/><font color='#64748b' size='7.5'>{desc_detalle}</font>", cell_val),
            Paragraph("1", cell_val),
            Paragraph(format_clp(monto_neto), cell_right),
            Paragraph(format_clp(monto_neto), cell_right)
        ]
    ]

    t_items = Table(items_data, colWidths=[65, 275, 40, 80, 80])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    # Pintar headers con letras blancas
    for i in range(5):
        t_items.setStyle(TableStyle([('TEXTCOLOR', (i,0), (i,0), colors.white)]))
    story.append(t_items)
    story.append(Spacer(1, 10))

    # Tabla de Totales e Impuestos (Neto, IVA 19%, Total)
    totales_data = [
        [Paragraph("Monto Neto:", cell_label), Paragraph(format_clp(monto_neto), cell_right_bold)],
        [Paragraph("I.V.A. (19%):", cell_label), Paragraph(format_clp(monto_iva), cell_right_bold)],
        [Paragraph("<b>TOTAL A PAGAR:</b>", ParagraphStyle('Tot', parent=cell_label, fontSize=10, textColor=colors.HexColor('#1e3a8a'))),
         Paragraph(f"<b>{format_clp(monto_total)} CLP</b>", ParagraphStyle('TotR', parent=cell_right_bold, fontSize=10, textColor=colors.HexColor('#1e3a8a')))]
    ]

    t_totales = Table(totales_data, colWidths=[120, 100])
    t_totales.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # Poner totales alineados a la derecha
    t_totales_container = Table([
        ["", t_totales]
    ], colWidths=[320, 220])
    t_totales_container.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_totales_container)
    story.append(Spacer(1, 20))

    # Constancia de Pago Comercial y Trazabilidad
    timbre_content = [
        Paragraph("<b>CONSTANCIA DE TRANSACCIÓN DIGITAL</b>", ParagraphStyle('TB', parent=cell_label, fontSize=8, alignment=1)),
        Paragraph("Comprobante de compra para efectos comerciales y de auditoría interna.", ParagraphStyle('TS', parent=cell_val, fontSize=7, alignment=1, textColor=colors.HexColor('#64748b'))),
        Spacer(1, 4),
        Paragraph(f"ID Orden: {order_id} | Token Autorización: {transaction_data.get('token_acceso', 'AUT-OK')[:20]}", ParagraphStyle('TH', parent=cell_val, fontSize=6.5, alignment=1, textColor=colors.HexColor('#94a3b8'))),
        Paragraph("Para solicitar la emisión de su Factura Electrónica formal con DTE del SII, escriba a facturacion@creditob2b.cl.", ParagraphStyle('TL', parent=cell_val, fontSize=6.5, alignment=1, textColor=colors.HexColor('#1e3a8a')))
    ]

    t_timbre = Table([[timbre_content]], colWidths=[380])
    t_timbre.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#1e3a8a')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))

    story.append(Table([["", t_timbre]], colWidths=[80, 380]))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
