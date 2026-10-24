import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime

def format_clp(val):
    if val is None or val == "": return "$0"
    try:
        n = int(round(float(val)))
        return f"${n:,}".replace(",", ".")
    except Exception:
        return str(val)

def generate_credit_report(input_data, result_data):
    """Genera un dictamen formal en PDF listo para comités de crédito."""
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
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748b')
    )
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#0f172a')
    )
    alert_style = ParagraphStyle(
        'Alert',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#991b1b')
    )

    story = []
    
    # 1. ENCABEZADO
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    header_data = [
        [
            Paragraph("<b>DICTAMEN DE EVALUACIÓN DE CRÉDITO COMERCIAL</b>", title_style),
            Paragraph(f"<b>Fecha:</b> {now_str}<br/><b>Analista:</b> {input_data.get('analista') or 'No informado'}", subtitle_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[400, 140])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_header)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceBefore=8, spaceAfter=14))

    # 2. IDENTIFICACIÓN DE LA EMPRESA
    story.append(Paragraph("1. Identificación y Antecedentes Societarios", section_title))
    empresa_data = [
        [
            Paragraph("<b>Razón Social:</b>", body_style), Paragraph(str(input_data.get('razonSocial', '—')), body_bold),
            Paragraph("<b>RUT:</b>", body_style), Paragraph(str(input_data.get('rut', '—')), body_bold)
        ],
        [
            Paragraph("<b>Sector / Industria:</b>", body_style), Paragraph(str(input_data.get('sector', '—')), body_style),
            Paragraph("<b>Antigüedad:</b>", body_style), Paragraph(f"{input_data.get('antiguedad', '—')} años", body_style)
        ],
        [
            Paragraph("<b>Ventas 12 Meses:</b>", body_style), Paragraph(format_clp(input_data.get('ventas12m')), body_bold),
            Paragraph("<b>Solicitante:</b>", body_style), Paragraph(str(input_data.get('rutSolicitante', '—')), body_style)
        ]
    ]
    t_empresa = Table(empresa_data, colWidths=[110, 170, 90, 170])
    t_empresa.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_empresa)
    story.append(Spacer(1, 14))

    # 3. DICTAMEN Y CONDICIONES RECOMENDADAS
    story.append(Paragraph("2. Dictamen del Comité y Límites de Riesgo", section_title))
    status_label = result_data.get('status', {}).get('label', 'En Revisión')
    score_val = result_data.get('score', 0)
    lim_aprobado = result_data.get('limits', {}).get('approved', 0)
    plazo_aprobado = result_data.get('term', {}).get('approved', 0)
    clasif = result_data.get('classification', {}).get('label', '—')

    dec_bg = colors.HexColor('#dcfce7') if 'Aprob' in status_label else (colors.HexColor('#fee2e2') if 'Rechaz' in status_label else colors.HexColor('#fef3c7'))
    dec_color = colors.HexColor('#166534') if 'Aprob' in status_label else (colors.HexColor('#991b1b') if 'Rechaz' in status_label else colors.HexColor('#92400e'))
    
    dictamen_data = [
        [
            Paragraph(f"<b>DECISIÓN FINAL:</b> <font color='{dec_color}'><b>{status_label.upper()}</b></font>", body_bold),
            Paragraph(f"<b>Scoring de Riesgo:</b> <b>{score_val:.1f} / 100</b> ({clasif})", body_bold)
        ],
        [
            Paragraph(f"<b>Límite Aprobado:</b> <font size='11'><b>{format_clp(lim_aprobado)}</b></font>", body_bold),
            Paragraph(f"<b>Plazo Máximo Autorizado:</b> <font size='11'><b>{plazo_aprobado} días</b></font>", body_bold)
        ],
        [
            Paragraph(f"<b>Monto Solicitado:</b> {format_clp(input_data.get('montoSolicitado'))}", body_style),
            Paragraph(f"<b>Plazo Solicitado:</b> {input_data.get('plazo')} días", body_style)
        ],
        [
            Paragraph(f"<b>Exposición Actual:</b> {format_clp(input_data.get('exposicionActual'))}", body_style),
            Paragraph(f"<b>Límite Disponible Adicional:</b> {format_clp(result_data.get('limits', {}).get('available'))}", body_style)
        ]
    ]
    t_dictamen = Table(dictamen_data, colWidths=[270, 270])
    t_dictamen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), dec_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_dictamen)
    story.append(Spacer(1, 14))

    # 4. RATIOS Y KPIS FINANCIEROS CLAVE
    story.append(Paragraph("3. Indicadores Financieros y KPIs del Core Crediticio", section_title))
    ratios = result_data.get('ratios', {})
    
    rc = ratios.get('razonCorriente')
    rc_str = f"{rc:.2f}x" if rc is not None else "—"
    rc_diag = "Saludable (≥1.3x)" if (rc and rc >= 1.3) else ("Ajustado (1.0 - 1.29x)" if (rc and rc >= 1.0) else "Riesgo de liquidez")
    
    nde = ratios.get('deudaNetaEbitda')
    nde_str = "Caja Neta" if nde == -1 else (f"{nde:.2f}x" if nde is not None else "—")
    nde_diag = "Óptimo (≤2.5x)" if (nde == -1 or (nde and nde <= 2.5)) else ("Moderado (2.5 - 3.5x)" if (nde and nde <= 3.5) else "Endeudamiento elevado")

    m_ebitda = ratios.get('margenEbitda')
    m_ebitda_str = f"{m_ebitda * 100:.1f}%" if m_ebitda is not None else "—"
    m_ebitda_diag = "Sólido (≥12%)" if (m_ebitda and m_ebitda >= 0.12) else ("Marginal (5% - 11.9%)" if (m_ebitda and m_ebitda >= 0.05) else "Crítico")

    dso = ratios.get('dso')
    dso_str = f"{round(dso)} días" if dso is not None else "—"
    dso_diag = "Cobro ágil (≤45 días)" if (dso and dso <= 45) else ("Plazo ordinario (46 - 75 días)" if (dso and dso <= 75) else "Cartera rezagada")

    dp = ratios.get('deudaPatrimonio')
    dp_str = f"{dp:.2f}x" if dp is not None else "—"
    dp_diag = "Bajo apalancamiento (≤1.5x)" if (dp and dp <= 1.5) else ("Moderado (1.5 - 2.5x)" if (dp and dp <= 2.5) else "Alto apalancamiento")

    fl = ratios.get('flujoLibre')
    fl_str = format_clp(fl) if fl is not None else "—"
    fl_diag = "Superávit de caja" if (fl and fl > 0) else "Déficit / Dependiente"

    kpi_rows = [
        [Paragraph("<b>KPI / Ratio Financiero</b>", body_bold), Paragraph("<b>Valor Calculado</b>", body_bold), Paragraph("<b>Benchmark / Estándar</b>", body_bold), Paragraph("<b>Evaluación de Riesgo</b>", body_bold)],
        [Paragraph("Razón Corriente (Liquidez)", body_style), Paragraph(rc_str, body_bold), Paragraph("≥ 1.30x", body_style), Paragraph(rc_diag, body_style)],
        [Paragraph("Deuda Neta / EBITDA", body_style), Paragraph(nde_str, body_bold), Paragraph("≤ 2.50x", body_style), Paragraph(nde_diag, body_style)],
        [Paragraph("Margen EBITDA (Rentabilidad)", body_style), Paragraph(m_ebitda_str, body_bold), Paragraph("≥ 12.0%", body_style), Paragraph(m_ebitda_diag, body_style)],
        [Paragraph("DSO (Rotación de Cartera)", body_style), Paragraph(dso_str, body_bold), Paragraph("≤ 45 días (Ley 19.983)", body_style), Paragraph(dso_diag, body_style)],
        [Paragraph("Pasivo / Patrimonio (Solvencia)", body_style), Paragraph(dp_str, body_bold), Paragraph("≤ 1.50x", body_style), Paragraph(dp_diag, body_style)],
        [Paragraph("Flujo Libre Operacional", body_style), Paragraph(fl_str, body_bold), Paragraph("> $0 CLP", body_style), Paragraph(fl_diag, body_style)],
    ]
    t_kpis = Table(kpi_rows, colWidths=[160, 100, 120, 160])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    for col_idx in range(4):
        t_kpis.setStyle(TableStyle([('TEXTCOLOR', (col_idx,0), (col_idx,0), colors.white)]))
    story.append(t_kpis)
    story.append(Spacer(1, 14))

    # 5. DIMENSIONES EVALUADAS
    story.append(Paragraph("4. Desglose de Dimensiones del Scoring", section_title))
    dim_rows = [[Paragraph("<b>Dimensión</b>", body_bold), Paragraph("<b>Puntaje</b>", body_bold), Paragraph("<b>Peso</b>", body_bold), Paragraph("<b>Diagnóstico</b>", body_bold)]]
    for d in result_data.get('dimensions', []):
        diag = "Favorable" if d.get('note', 0) >= 70 else ("Aceptable" if d.get('note', 0) >= 50 else "Crítico")
        dim_rows.append([
            Paragraph(d.get('label', ''), body_style),
            Paragraph(f"{d.get('note', 0):.0f} / 100", body_bold),
            Paragraph(f"{d.get('weight', 0)}%", body_style),
            Paragraph(diag, body_style)
        ])
    t_dims = Table(dim_rows, colWidths=[180, 80, 80, 200])
    t_dims.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_dims)
    story.append(Spacer(1, 14))

    # 4. ALERTAS Y BLOQUEOS DEL EXPEDIENTE
    hard_blockers = result_data.get('hardBlockers', [])
    pending_items = result_data.get('pendingItems', [])
    warnings = result_data.get('warnings', [])
    
    if hard_blockers or pending_items or warnings:
        story.append(Paragraph("4. Bloqueos, Antecedentes Pendientes y Alertas", section_title))
        issues_rows = []
        if hard_blockers:
            for hb in hard_blockers:
                txt = hb.get('text') if isinstance(hb, dict) else str(hb)
                issues_rows.append([
                    Paragraph("<font color='#991b1b'><b>BLOQUEO CRÍTICO</b></font>", body_bold),
                    Paragraph(f"<font color='#991b1b'>{txt}</font>", body_style)
                ])
        if pending_items:
            for pi in pending_items:
                txt = pi.get('text') if isinstance(pi, dict) else str(pi)
                issues_rows.append([
                    Paragraph("<font color='#0284c7'><b>PENDIENTE</b></font>", body_bold),
                    Paragraph(txt, body_style)
                ])
        if warnings:
            for w in warnings[:6]: # Limitar para no desbordar página
                txt = w.get('text') if isinstance(w, dict) else str(w)
                issues_rows.append([
                    Paragraph("<font color='#b45309'>ALERTA</font>", body_bold),
                    Paragraph(txt, body_style)
                ])
        
        t_issues = Table(issues_rows, colWidths=[130, 410])
        t_issues.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_issues)
        story.append(Spacer(1, 14))

    # 5. OBSERVACIONES Y FIRMAS
    story.append(Paragraph("4. Dictamen del Analista y Trazabilidad", section_title))
    obs_text = input_data.get('observaciones') or "Evaluación realizada mediante el modelo cuantitativo de scoring B2B con extracción de fuentes tributarias oficiales SII y bancarias CMF."
    story.append(Paragraph(f"<b>Observaciones:</b> {obs_text}", body_style))
    story.append(Spacer(1, 30))

    firmas_data = [
        [
            Paragraph("____________________________<br/><b>Analista de Riesgo Comercial</b><br/>Firma y Timbre", body_style),
            Paragraph("____________________________<br/><b>Gerencia de Finanzas / Crédito</b><br/>Aprobación Comité", body_style)
        ]
    ]
    t_firmas = Table(firmas_data, colWidths=[270, 270])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_firmas)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
