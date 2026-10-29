import fitz
import re
import unicodedata
from datetime import datetime

def parse_amount(val_str, fallback=0):
    """
    Función utilitaria unificada para parsear montos monetarios en formatos chilenos/hispanos:
    - Puntos como separador de miles: 10.218.331.980 -> 10218331980
    - Signos negativos: (1.500) o -1.500 -> -1500
    - Guiones contables: '-' -> 0 (celda vacía contable)
    - Decimales opcionales con coma: 1.500,50 -> 1501
    - No parseable -> fallback (usar fallback=None para detectar tokens inválidos)
    """
    if val_str is None:
        return fallback
    if isinstance(val_str, (int, float)):
        return int(round(val_str))
    s = str(val_str).strip().replace('$', '').replace('CLP', '').replace(' ', '')
    if s == '-':
        return 0
    if not s:
        return fallback
    negative = False
    if s.startswith('(') and s.endswith(')'):
        negative = True
        s = s[1:-1].strip()
    elif s.startswith('-'):
        negative = True
        s = s[1:].strip()
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif '.' in s and len(s.split('.')[-1]) == 3:
        s = s.replace('.', '')
    elif ',' in s and len(s.split(',')[-1]) == 3:
        s = s.replace(',', '')
    try:
        val = float(s)
        return int(round(-val if negative else val))
    except Exception:
        return fallback

def _pdf_text(pdf_bytes_or_path):
    """Abre un PDF con context manager (libera siempre los handles) y devuelve todo su texto."""
    doc = fitz.open(stream=pdf_bytes_or_path, filetype="pdf") if isinstance(pdf_bytes_or_path, (bytes, bytearray)) else fitz.open(pdf_bytes_or_path)
    try:
        return '\n'.join(p.get_text() for p in doc)
    finally:
        doc.close()

def _norm(text):
    """Minúsculas sin acentos/diacríticos para matching robusto (PRÉSTAMO == PRESTAMO)."""
    return ''.join(c for c in unicodedata.normalize('NFD', str(text).lower()) if unicodedata.category(c) != 'Mn')

_MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
          'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
          'noviembre': 11, 'diciembre': 12}
_MESES_CORTOS = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                 'jul': 7, 'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12}

def detect_period(text, filename=None):
    """
    Detecta el periodo contable del balance y retorna (clave_AAAAMM, texto_detectado) o (None, None).

    PRIORIDAD:
      1. Contexto en el contenido: "Acumulado mes/año | Diciembre/2024",
         "De el 01.01.2025 al 31.12.2025", "al 31 de diciembre de 2025", "Ejercicio 2025".
      2. Nombre del archivo: "Balance 202412.pdf", "sep2026", "2025".
    NUNCA usa la "Fecha :" de emisión del documento (fecha de impresión, no del periodo).
    """
    s = _norm(text or '')
    # 1a. Encabezado "Diciembre/2024" (Balance Tributario 8 columnas)
    m = re.search(r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s*/\s*(20\d{2})', s)
    if m:
        return int(m.group(2)) * 100 + _MESES[m.group(1)], m.group(0)
    # 1b. "De el 01.01.2025 al 31.12.2025" -> fecha final = cierre del periodo
    m = re.search(r'\bal\s+\d{1,2}[./-](\d{1,2})[./-](20\d{2})', s)
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(2)) * 100 + int(m.group(1)), m.group(0)
    # 1c. "al 31 de diciembre de 2025"
    m = re.search(r'al\s+\d{1,2}\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(20\d{2})', s)
    if m:
        return int(m.group(2)) * 100 + _MESES[m.group(1)], m.group(0)
    # 1d. "Ejercicio 2025" / "Ejercicio 2025-2026" (toma el primero)
    m = re.search(r'(?:ejercicio|cierre)\s*(?:del\s+|de\s+)?(20\d{2})(?:\s*[/-]\s*(\d{1,2}))?', s)
    if m:
        mo = int(m.group(2)) if m.group(2) and 1 <= int(m.group(2)) <= 12 else 12
        return int(m.group(1)) * 100 + mo, m.group(0)
    # 2. Nombre del archivo
    if filename:
        f = _norm(filename)
        ym = re.search(r'(20\d{2})', f)
        if ym:
            year = int(ym.group(1))
            rest = f[ym.end():ym.end() + 2]
            if re.fullmatch(r'(0[1-9]|1[0-2])', rest):
                return year * 100 + int(rest), filename
            win = f[max(0, ym.start() - 5):ym.end() + 5]
            for name, num in _MESES_CORTOS.items():
                if name in win:
                    return year * 100 + num, filename
            return year * 100 + 12, filename
    return None, None

def parse_erut(pdf_bytes_or_path):
    """Extrae datos de un e-RUT chileno oficial."""
    text = _pdf_text(pdf_bytes_or_path)
    if not text.strip():
        return {'tipo': 'e-RUT', 'error': 'PDF escaneado o sin capa de texto extraíble (requiere OCR)'}
    
    # Razon social
    m_razon = re.search(r'NOMBRE O RAZÓN SOCIAL\s*\n([^\n]+)', text, re.IGNORECASE)
    razon_social = m_razon.group(1).strip() if m_razon else None
    
    # RUT empresa
    m_rut = re.search(r'RUT\s*\n(\d{7,8}-[\dkK])', text)
    rut = m_rut.group(1).strip() if m_rut else None
    
    # Giro / Actividad
    m_giro = re.search(r'GLOSA DE ACTIVIDAD ECONÓMICA\s*\n([^\n]+(?:\n[^\n]+)?)', text, re.IGNORECASE)
    giro = ' '.join([line.strip() for line in m_giro.group(1).split('\n')]) if m_giro else None
    
    # Solicitante / Titular firma
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    rep_rut = None
    rep_nombre = None
    for i, line in enumerate(lines):
        if 'RUT USUARIO' in line.upper() and i + 1 < len(lines):
            # Buscar el primer valor con formato de rut en las lineas siguientes
            for sub in lines[i+1:i+4]:
                m_sub = re.search(r'([0-9\.\-kK]{8,12})', sub)
                if m_sub and '-' in m_sub.group(1):
                    rep_rut = m_sub.group(1).strip()
                    break
        if 'USUARIO' in line.upper() and 'RUT' not in line.upper() and i + 1 < len(lines):
            for sub in lines[i+1:i+4]:
                if sub and not re.match(r'^[0-9\.\-kK]+$', sub) and 'CÉDULA' not in sub and 'CEDULA' not in sub:
                    rep_nombre = sub.strip()
                    break

    return {
        'tipo': 'e-RUT',
        'rut': rut,
        'razon_social': razon_social,
        'giro': giro,
        'solicitante_rut': rep_rut,
        'solicitante_nombre': rep_nombre
    }

def parse_cmf_deudas(pdf_bytes_or_path):
    """Extrae deuda del informe CMF de la empresa."""
    text = _pdf_text(pdf_bytes_or_path)
    if not text.strip():
        return {'tipo': 'CMF_DEUDAS', 'error': 'PDF escaneado o sin capa de texto extraíble (requiere OCR)'}
    
    m_rut = re.search(r'Rut:\s*([0-9\.\-kK]+)', text)
    rut = m_rut.group(1).strip() if m_rut else None
    
    # Deuda Total
    m_tot = re.search(r'Deuda total(?:\s*y estado de pago)?\s*\$([\d\.]+)', text)
    deuda_total = parse_amount(m_tot.group(1)) if m_tot else 0
    
    # Detalle Deuda Directa
    m_dir = re.search(r'Deuda Directa.*?Total\s*\$([\d\.]+)\s*\$([\d\.]+)\s*\$([\d\.]+)\s*\$([\d\.]+)\s*\$([\d\.]+)', text, re.DOTALL)
    directa = {
        'total': deuda_total,
        'vigente': deuda_total,
        'mora_30_59': 0,
        'mora_60_89': 0,
        'mora_90_mas': 0
    }
    if m_dir:
        directa = {
            'total': parse_amount(m_dir.group(1)),
            'vigente': parse_amount(m_dir.group(2)),
            'mora_30_59': parse_amount(m_dir.group(3)),
            'mora_60_89': parse_amount(m_dir.group(4)),
            'mora_90_mas': parse_amount(m_dir.group(5))
        }
    
    # Líneas disponibles
    m_disp = re.search(r'Líneas de crédito.*?Total\s*\$([\d\.]+)', text, re.DOTALL)
    lineas_disp = parse_amount(m_disp.group(1)) if m_disp else 0

    # Conteo de instituciones bancarias distintas
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    instituciones = set()
    mora_30 = 0
    mora_60 = 0
    mora_90 = 0
    deuda_vigente_calc = 0

    for i, l in enumerate(lines):
        clean_upper = l.upper()
        if any(b in clean_upper for b in ['BANCO', 'SCOTIABANK', 'ITAU', 'BICE', 'SECURITY', 'TANNER']):
            clean_name = re.sub(r'\s*\(\d+\).*', '', l).strip()
            if len(clean_name) >= 5 and 'ESTADO DE PAGO' not in clean_name.upper():
                instituciones.add(clean_name)

        # Fila de crédito con fecha dd/mm/aaaa
        if re.match(r'^\d{2}/\d{2}/\d{4}$', l):
            amts = []
            row_valid = True
            for nxt in lines[i+1:i+6]:
                if nxt.startswith('$'):
                    v = parse_amount(nxt, fallback=None)
                    if v is None:
                        row_valid = False
                        break
                    amts.append(v)
            if row_valid and len(amts) == 5:
                deuda_vigente_calc += amts[1]
                mora_30 += amts[2]
                mora_60 += amts[3]
                mora_90 += amts[4]

    mora_30_final = directa['mora_30_59'] if directa['mora_30_59'] > 0 else mora_30
    mora_60_final = directa['mora_60_89'] if directa['mora_60_89'] > 0 else mora_60
    mora_90_final = directa['mora_90_mas'] if directa['mora_90_mas'] > 0 else mora_90
    mora_total = mora_30_final + mora_60_final + mora_90_final
    max_dias = 90 if mora_90_final > 0 else (60 if mora_60_final > 0 else (30 if mora_30_final > 0 else 0))

    return {
        'tipo': 'CMF_DEUDAS',
        'rut': rut,
        'deuda_total': deuda_total,
        'deuda_vigente': directa['vigente'] if directa['vigente'] > 0 else (deuda_vigente_calc if deuda_vigente_calc > 0 else deuda_total),
        'mora_30_59': mora_30_final,
        'mora_60_89': mora_60_final,
        'mora_90_mas': mora_90_final,
        'mora_total': mora_total,
        'lineas_disponibles': lineas_disp,
        'instituciones': len(instituciones) if instituciones else 1,
        'instituciones_lista': list(instituciones),
        'max_dias_mora': max_dias,
        'deuda_vencida': mora_total,
        # Mora 90+ NO es deuda castigada (write-off): la categoría 'castigada' no existe
        # en el estado de deuda directa del reporte CMF. Se reporta 0 para no disparar
        # el bloqueo por 'deuda castigada' del motor de scoring.
        'deuda_castigada': 0
    }

def parse_carpeta_tributaria(pdf_bytes_or_path):
    """Extrae declaraciones mensuales F29 y datos del contribuyente de la Carpeta Tributaria SII."""
    doc = fitz.open(stream=pdf_bytes_or_path, filetype="pdf") if isinstance(pdf_bytes_or_path, (bytes, bytearray)) else fitz.open(pdf_bytes_or_path)
    try:
        return _parse_carpeta_tributaria_doc(doc)
    finally:
        doc.close()

def _parse_carpeta_tributaria_doc(doc):
    if len(doc) == 0 or not any(p.get_text().strip() for p in doc):
        return {'tipo': 'CARPETA_TRIBUTARIA', 'error': 'PDF escaneado o sin capa de texto extraíble (requiere OCR)'}

    p1 = doc[0].get_text()
    m_rut = re.search(r'RUT del Emisor:\s*([0-9\.\-kK]+)', p1)
    rut = m_rut.group(1).strip() if m_rut else None
    m_name = re.search(r'Nombre del Emisor:\s*([^\n]+)', p1)
    razon_social = m_name.group(1).strip() if m_name else None
    m_ini = re.search(r'Fecha de Inicio de Actividades:\s*([0-9\/]+)', p1)
    fecha_inicio = m_ini.group(1).strip() if m_ini else None
    
    antiguedad = None
    if fecha_inicio:
        try:
            d = datetime.strptime(fecha_inicio, '%d/%m/%Y')
            antiguedad = round((datetime.now() - d).days / 365.25, 1)
        except Exception:
            pass

    f29_list = []
    
    for idx, page in enumerate(doc):
        text = page.get_text()
        if 'FORMULARIO 29' not in text:
            continue
        
        m_per = re.search(r'PERIODO\s*(?:\[15\])?\s*(\d{6})', text)
        periodo = m_per.group(1) if m_per else None
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        cods = {}
        for i, l in enumerate(lines):
            if re.match(r'^\d{2,4}$', l) and i + 2 < len(lines):
                val_str = lines[i+2].replace('.', '')
                if re.match(r'^-?\d+$', val_str):
                    cods[l] = int(val_str)

        if periodo:
            # Ventas netas / Base imponible: Cod 583 o Cod 563 (base imponible gravada F29).
            # Si no viene informado explícitamente, estimar de Débitos Facturas/Boletas (Cod 502 + 111 / 0.19) o Cod 538 / 0.19
            v_netas = cods.get('583', cods.get('563', 0))
            if v_netas == 0:
                debitos = cods.get('538', 0)
                if debitos > 0:
                    v_netas = int(round(debitos / 0.19))
            
            # Exportaciones cod 020
            v_netas += cods.get('020', 0)

            total_debitos = cods.get('538', 0)
            cred_iva = cods.get('511', cods.get('520', 0))
            
            f29_list.append({
                'periodo': periodo,
                'ventas_netas': v_netas,
                'base_imponible': cods.get('583', cods.get('563', 0)),
                'total_debitos': total_debitos,
                'cred_iva': cred_iva
            })

    # Extracción de F22 (Declaraciones de Renta / Balances oficiales)
    f22_data = {}
    for idx, page in enumerate(doc):
        text = page.get_text()
        if 'Declaraciones de Renta' in text or 'FORM. 22' in text:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for i, l in enumerate(lines):
                if l in ['122', '123', '843', '101', '784', '647', '102', '129', '1672', '1445', '1496']:
                    for nxt in lines[i+1:i+6]:
                        val = nxt.replace('.', '')
                        if re.match(r'^-?\d+$', val) and int(val) > 1000:
                            if l == '122' and 'total_activo' not in f22_data: f22_data['total_activo'] = int(val)
                            elif l == '123' and 'total_pasivo' not in f22_data: f22_data['total_pasivo'] = int(val)
                            elif l in ['843', '1496'] and 'patrimonio' not in f22_data: f22_data['patrimonio'] = int(val)
                            elif l == '101' and 'caja_efectivo' not in f22_data: f22_data['caja_efectivo'] = int(val)
                            elif l == '784' and 'caja_bancos' not in f22_data: f22_data['caja_bancos'] = int(val)
                            elif l == '647' and 'activo_inmovilizado' not in f22_data: f22_data['activo_inmovilizado'] = int(val)
                            elif l == '129' and 'inventarios' not in f22_data: f22_data['inventarios'] = int(val)
                            elif l in ['1672', '1445'] and 'resultado' not in f22_data: f22_data['resultado'] = int(val)
                            break
            # En F22 la caja total es dinero en efectivo (101) + saldos en cuenta corriente bancaria (784)
            caja_total = f22_data.get('caja_efectivo', 0) + f22_data.get('caja_bancos', 0)
            if caja_total > 0:
                f22_data['caja'] = caja_total
            if f22_data:
                break
            
    # Ordenar por periodo descendente
    f29_list.sort(key=lambda x: x['periodo'], reverse=True)
    
    ultimos_12 = f29_list[:12]
    ventas_12m = sum([x['ventas_netas'] for x in ultimos_12])
    promedio_mensual = int(ventas_12m / len(ultimos_12)) if ultimos_12 else 0

    # Determinar tendencia de ventas según la serie de los últimos 12 periodos
    tendencia_ventas = "estable"
    if len(ultimos_12) >= 6:
        ventas_cron = [x['ventas_netas'] for x in reversed(ultimos_12)]
        mid = len(ventas_cron) // 2
        primera_mitad = sum(ventas_cron[:mid]) / mid
        segunda_mitad = sum(ventas_cron[mid:]) / (len(ventas_cron) - mid)
        if primera_mitad > 0:
            var_pct = (segunda_mitad - primera_mitad) / primera_mitad * 100.0
            if var_pct >= 5.0:
                tendencia_ventas = "sube"
            elif var_pct <= -5.0:
                tendencia_ventas = "cae"
            else:
                tendencia_ventas = "estable"

    return {
        'tipo': 'CARPETA_TRIBUTARIA',
        'rut': rut,
        'razon_social': razon_social,
        'fecha_inicio': fecha_inicio,
        'antiguedad_anios': antiguedad,
        'ventas_12m': ventas_12m,
        'promedio_mensual_ventas': promedio_mensual,
        'tendencia_ventas': tendencia_ventas,
        'periodos_disponibles': len(f29_list),
        'historico_mensual': f29_list,
        'eeff_f22': f22_data
    }

def parse_estatutos(pdf_bytes_or_path):
    """Extrae representantes legales vigentes y datos societarios de escrituras/estatutos RES."""
    full = _pdf_text(pdf_bytes_or_path)
    if not full.strip():
        return {'tipo': 'ESTATUTOS_PODERES', 'error': 'PDF escaneado o sin capa de texto extraíble (requiere OCR)'}
    
    ruts = set(re.findall(r'\b\d{1,2}\.\d{3}\.\d{3}-[\dkK]\b', full))
    # Quitar ruts tipicos de notarías o genéricos si es necesario
    facultades_financieras = any(term in _norm(full) for term in ['endeudar', 'obligar', 'banco', 'mutuo', 'credito', 'pagare', 'cuenta corriente'])
    
    return {
        'tipo': 'ESTATUTOS_PODERES',
        'ruts_detectados': list(ruts),
        'facultades_financieras_detectadas': facultades_financieras,
        'es_res': 'Registro de Empresas y Sociedades' in full
    }

def _var_nota(key, base, actual):
    """Nota interpretativa de la variación de una partida entre año base y año actual."""
    flip_down = base > 0 and actual < 0
    flip_up = base < 0 and actual > 0
    up = actual > base
    if key == 'ing_op':
        if flip_down: return 'Ingresos netos pasaron a negativos.'
        if flip_up: return 'Recuperó ingresos netos positivos.'
        return 'Mayor actividad comercial.' if up else 'Contracción de los ingresos netos.'
    if key == 'ebitda':
        if base > 0 and actual <= 0: return 'EBITDA negativo: la operación no cubre sus costos fijos.'
        if base < 0 and actual >= 0: return 'Recuperó EBITDA positivo.'
        return 'Mejora de la rentabilidad operacional.' if up else 'Deterioro de la rentabilidad operacional.'
    if key == 'gastos_fin':
        return 'Mayor carga financiera por deuda o tasas.' if up else 'Alivio en los costos financieros.'
    if key == 'utilidad_ejercicio':
        if flip_down: return 'Pasó de ganancia a pérdida.'
        if flip_up: return 'Pasó de pérdida a ganancia.'
        return 'Mejora del resultado neto.' if up else 'Deterioro del resultado neto.'
    if key == 'caja':
        return 'Mayor colchón de caja.' if up else 'Menor liquidez disponible.'
    if key == 'cxc':
        return 'Más crédito comercial: inmoviliza caja.' if up else 'Cobro de cartera: libera caja.'
    if key == 'inv':
        return 'Acumulación de inventarios: consume caja.' if up else 'Rotación de inventarios: libera caja.'
    if key == 'cxp_op':
        return 'Mayor financiamiento con proveedores: libera caja.' if up else 'Pagos a proveedores: usa caja.'
    if key == 'pasivo_total':
        return 'Mayor apalancamiento con terceros.' if up else 'Reducción de deuda con terceros.'
    if key == 'deuda_financiera':
        return 'Incorporó deuda bancaria nueva.' if up else 'Amortizó deuda bancaria.'
    if key == 'patrimonio':
        return 'Generación de patrimonio o aporte de capital.' if up else 'Pérdidas o distribuciones reducen el patrimonio.'
    return 'Incremento.' if up else 'Disminución.'

def _build_variaciones(prev_b, curr_b):
    """Principales variaciones entre el año base (prev_b) y el año actual (curr_b)."""
    specs = [
        ('ing_op', 'Ingresos operacionales'),
        ('ebitda', 'EBITDA'),
        ('gastos_fin', 'Gastos financieros'),
        ('utilidad_ejercicio', 'Utilidad del ejercicio'),
        ('caja', 'Caja y equivalentes'),
        ('cxc', 'Cuentas por cobrar comerciales'),
        ('inv', 'Inventarios'),
        ('cxp_op', 'Cuentas por pagar operacionales'),
        ('pasivo_total', 'Pasivo total'),
        ('deuda_financiera', 'Deuda financiera bancaria'),
        ('patrimonio', 'Patrimonio neto'),
    ]
    items = []
    for key, glosa in specs:
        base = prev_b.get(key)
        actual = curr_b.get(key)
        if base is None or actual is None:
            continue
        delta = actual - base
        if delta == 0:
            continue
        pct = round(delta / abs(base) * 100, 1) if base != 0 else None
        flip = (base > 0 > actual) or (base < 0 < actual)
        material = flip or base == 0 or (pct is not None and abs(pct) >= 10)
        nota = _var_nota(key, base, actual)
        if not material:
            nota = 'Variación no material (<10% vs año base). ' + nota
        items.append({
            'campo': key,
            'glosa': glosa,
            'base': base,
            'actual': actual,
            'variacion': delta,
            'pct': pct,
            'material': material,
            'nota': nota
        })
    items.sort(key=lambda it: (not it['material'], -abs(it['variacion'])))
    return {
        'periodo_base': prev_b.get('period_label'),
        'periodo_actual': curr_b.get('period_label'),
        'items': items
    }

def parse_estados_financieros(pdf_bytes_or_path_or_list, filenames=None):
    """
    Analiza y extrae partidas contables estándar de balances (soporta uno o múltiples balances para análisis comparativo):
      1. Balances Tributarios / Tabulares de 8 Columnas (Débitos, Créditos, Deudor, Acreedor, Activo, Pasivo, Pérdida, Ganancia)
      2. Balances Clasificados IFRS / FECU / Formato Tradicional
    Aplica la técnica contable y de flujo de caja según principios financieros:
      - Activo Corriente (1-01 / C/P): Caja (1-01-01), Clientes/CxC (1-01-02), Inventarios/Mercaderías (1-01-03)
      - Activo No Corriente / Fijo (1-02 / L/P): Actividades de Inversión
      - Pasivo Corriente Operacional (2-01 / C/P): Proveedores (2-01-01/2-01-03) -> Flujo Operacional
      - Pasivo Financiero C/P y L/P (2-01-04, 2-02-03, préstamos bancarios/comex) -> Deuda Financiera & Flujo Financiamiento
      - Préstamos Socios / Relacionados (2-01-03-02) -> Se segregan de la deuda bancaria
      - Capital Social (3-01-01) -> Actividades de Financiamiento (Aumentos/Disminuciones de Capital)
    filenames: nombre(s) de archivo opcional(es) para detectar el periodo cuando el PDF no lo indica.
    """
    if isinstance(pdf_bytes_or_path_or_list, list):
        items = pdf_bytes_or_path_or_list
    else:
        items = [pdf_bytes_or_path_or_list]

    if filenames is None:
        fnames = [None] * len(items)
    elif isinstance(filenames, str):
        fnames = [filenames] + [None] * max(0, len(items) - 1)
    else:
        fnames = list(filenames) + [None] * max(0, len(items) - len(filenames))

    def extract_single_doc(pdf_input, filename=None):
        doc = fitz.open(stream=pdf_input, filetype="pdf") if isinstance(pdf_input, (bytes, bytearray)) else fitz.open(pdf_input)
        try:
            full_text = '\n'.join([p.get_text() for p in doc])
        finally:
            doc.close()
        if not full_text.strip():
            return {'lines': [], 'table_rows': [], 'period_label': '', 'period_key': None, 'full_text': '', 'scanned': True}
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]

        # Periodo contable real (contexto del contenido o filename), nunca la fecha de emisión
        period_key, period_label = detect_period(full_text, filename)

        table_rows = []
        for i, line in enumerate(lines):
            m = re.match(r'^([1-6]-\d{2}(?:-\d{2})?(?:-\d{2})?)\s*(.*)', line)
            if m:
                code = m.group(1)
                name = m.group(2).strip()
                collected_tokens = []
                for j in range(1, 10):
                    if i + j >= len(lines): break
                    nxt = lines[i + j]
                    # Detener si alcanzamos el inicio de otra cuenta contable
                    if re.match(r'^[1-6]-\d{2}', nxt): break
                    # Ignorar cabeceras repetidas en saltos de página (insensible a mayúsculas/acentos)
                    nxt_n = _norm(nxt)
                    if any(_norm(ign) in nxt_n for ign in ['Balance de 8 columnas', 'De el 01.01', 'Sumas', 'Saldos', 'Inventarios', 'Resultados', 'Cuenta', 'Descripci']):
                        continue
                    # Si no teníamos nombre de cuenta y la línea no contiene importes, es el nombre
                    if not name and not re.search(r'\d{3}', nxt):
                        name = nxt
                        continue
                    toks = [t for t in re.split(r'\s{2,}|\s(?=[-0-9])', nxt.strip()) if t]
                    collected_tokens.extend(toks)
                    if len(collected_tokens) >= 8:
                        break

                if len(collected_tokens) >= 8:
                    parsed = [parse_amount(t, fallback=None) for t in collected_tokens[:8]]
                    if all(p is not None for p in parsed):
                        table_rows.append({
                            'code': code, 'name': name,
                            'debitos': parsed[0], 'creditos': parsed[1],
                            'deudor': parsed[2], 'acreedor': parsed[3],
                            'activo': parsed[4], 'pasivo': parsed[5],
                            'perdida': parsed[6], 'ganancia': parsed[7]
                        })
                        continue

                # Formato estándar vertical de 8 números en líneas consecutivas (fallback)
                cols = []
                for j in range(1, 9):
                    if i + j < len(lines):
                        amt = parse_amount(lines[i + j], fallback=None)
                        if amt is not None:
                            cols.append(amt)
                if len(cols) == 8:
                    table_rows.append({
                        'code': code, 'name': name,
                        'debitos': cols[0], 'creditos': cols[1],
                        'deudor': cols[2], 'acreedor': cols[3],
                        'activo': cols[4], 'pasivo': cols[5],
                        'perdida': cols[6], 'ganancia': cols[7]
                    })

        return {
            'lines': lines,
            'table_rows': table_rows,
            'period_label': period_label,
            'period_key': period_key,
            'full_text': full_text
        }

    parsed_docs = [extract_single_doc(item, fn) for item, fn in zip(items, fnames)]
    all_scanned = bool(parsed_docs) and all(d.get('scanned') for d in parsed_docs)
    parsed_docs = [d for d in parsed_docs if len(d['table_rows']) >= 5 or len(d['lines']) > 0]
    if not parsed_docs:
        if all_scanned:
            return {'tipo': 'ESTADOS_FINANCIEROS', 'error': 'PDF escaneado o sin capa de texto extraíble (requiere OCR)'}
        return {'tipo': 'ESTADOS_FINANCIEROS', 'error': 'No se detectaron balances legibles'}

    # Orden cronológico SOLO si todos los balances tienen periodo detectado:
    # un orden por fechas erróneas es peor que conservar el orden de subida.
    # curr_b debe ser el balance más reciente para que los deltas del flujo
    # de caja comparativo no salgan invertidos.
    if all(d.get('period_key') is not None for d in parsed_docs):
        parsed_docs = [d for _, d in sorted(enumerate(parsed_docs),
                                            key=lambda t: (t[1]['period_key'], t[0]))]

    def process_balance_metrics(doc_info):
        table_rows = doc_info['table_rows']
        lines = doc_info['lines']

        if len(table_rows) >= 5:
            codes_present = {r['code'] for r in table_rows}

            def is_aggregate(r):
                # Fila subtotal/padre: excluir cuando existen hijos (evita doble conteo padre+hijos)
                return any(c.startswith(r['code'] + '-') for c in codes_present)

            def rows(prefix):
                return [r for r in table_rows if r['code'].startswith(prefix) and not is_aggregate(r)]

            def name_has(r, *words):
                n = _norm(r['name'])
                return any(w in n for w in words)

            # 1. Caja y equivalentes de efectivo (1-01-01)
            caja = sum(r['activo'] - r['pasivo'] for r in rows('1-01-01'))

            # 2. Cuentas por cobrar comerciales operacionales (1-01-02)
            cxc = sum(r['activo'] - r['pasivo'] for r in rows('1-01-02'))

            # 3. Inventarios / Mercaderías (1-01-03)
            inv = sum(r['activo'] - r['pasivo'] for r in rows('1-01-03'))

            # Otros activos corrientes operacionales (anticipos, impuestos por recuperar, etc.)
            otros_act_op = sum(r['activo'] - r['pasivo'] for r in rows('1-01')
                               if not (r['code'].startswith('1-01-01') or r['code'].startswith('1-01-02') or r['code'].startswith('1-01-03')))

            # 4. Activo corriente neto total (1-01)
            activo_cte = sum(r['activo'] - r['pasivo'] for r in rows('1-01'))

            # Activo no corriente / fijo (1-02)
            activo_no_cte = sum(r['activo'] - r['pasivo'] for r in rows('1-02'))

            # 5. Pasivo corriente total (2-01)
            pasivo_cte = sum(r['pasivo'] - r['activo'] for r in rows('2-01'))

            # Cuentas por pagar operacionales / comerciales (excluyendo deuda financiera bancaria y préstamos)
            cxp_op = sum(r['pasivo'] - r['activo'] for r in rows('2-01')
                         if not r['code'].startswith('2-01-04') and not name_has(r, 'prestamo', 'bancario', 'comex', 'leasing', 'linea de credito'))

            # 6. Pasivo no corriente (2-02) y Pasivo total
            pasivo_no_cte = sum(r['pasivo'] - r['activo'] for r in rows('2-02'))
            pasivo_total = pasivo_cte + pasivo_no_cte

            # 7. Patrimonio neto
            patrimonio = sum(r['pasivo'] - r['activo'] for r in rows('3-'))

            # Capital social estatutario (excluyendo reservas y resultados acumulados)
            capital_social = sum(r['pasivo'] - r['activo'] for r in table_rows
                                 if not is_aggregate(r) and (r['code'].startswith('3-01-01') or name_has(r, 'capital social', 'capital suscrito')))

            # 8. Gastos financieros (cuentas 5-02 o intereses dentro de gastos 5-xx)
            # Excluye Diferencia de Cambio (NIIF/NIC): puede ser gasto o ingreso, no es gasto financiero
            # asociado a préstamos ni comisiones bancarias.
            def is_exchange_diff(r):
                n = _norm(r['name'])
                return ('diferencia' in n and 'cambio' in n) or 'dif de cambio' in n or 'diferencia cambio' in n

            gastos_fin = sum(r['perdida'] for r in rows('5-')
                             if (r['code'].startswith('5-02') or name_has(r, 'interes'))
                             and not is_exchange_diff(r))

            # 8b. Diferencia de Cambio registrada por separado (NIIF/NIC):
            # neto = ganancia - pérdida (positivo = ingreso, negativo = gasto).
            dif_cambio_neto = sum(r['ganancia'] - r['perdida'] for r in table_rows if is_exchange_diff(r) and not is_aggregate(r))

            # 9. Deuda Financiera Bancaria / Institucional ESTRICTA:
            # Excluye explícitamente cuentas de SOCIOS, PARTES RELACIONADAS o EMPRESAS RELACIONADAS
            def is_strict_fin_debt(r):
                name_u = _norm(r['name'])
                if any(ign in name_u for ign in ['socio', 'partes relacionadas', 'empresas relacionadas', 'trabajador']):
                    return False
                code = r['code']
                if code.startswith('2-01-04') or code.startswith('2-02-03'):
                    return True
                if any(w in name_u for w in ['bancario', 'linea de credito', 'comex', 'leasing']) and (code.startswith('2-01') or code.startswith('2-02')):
                    return True
                if 'prestamo' in name_u and any(inst in name_u for inst in ['banco', 'bco', 'btg', 'santander', 'chile', 'bci', 'mercado pago', 'security', 'scotiabank', 'itau', 'estado', 'falabella']):
                    return True
                return False

            deuda_cp = sum(r['pasivo'] - r['activo'] for r in rows('2-01') if is_strict_fin_debt(r))
            deuda_lp = sum(r['pasivo'] - r['activo'] for r in rows('2-02') if is_strict_fin_debt(r))
            deuda_financiera = (deuda_cp + deuda_lp) if (deuda_cp + deuda_lp) > 0 else None

            # Préstamos de socios y partes relacionadas contabilizados por separado
            deuda_socios = sum(r['pasivo'] - r['activo'] for r in table_rows
                               if (name_has(r, 'socio', 'relacionad')) and (r['code'].startswith('2-01') or r['code'].startswith('2-02')) and not is_aggregate(r))

            # Servicio de deuda
            servicio_deuda = (deuda_cp + gastos_fin) if (deuda_cp + gastos_fin) > 0 else (gastos_fin if gastos_fin > 0 else None)

            # EBITDA y Resultados
            # Ingresos netos = columna Ganancia de 4-xx menos columna Pérdida de 4-xx (devoluciones/nc).
            # Costos directos = cuentas 6-xx (costo de ventas, transportes, comisiones marketplace, etc.).
            # EBITDA = Ingresos netos - Costos directos - Gastos operacionales (sin depreciación).
            ing_op = sum(r['ganancia'] - r['perdida'] for r in rows('4-'))
            costos_directos = sum(r['perdida'] - r['ganancia'] for r in rows('6-'))
            gastos_tot = sum(r['perdida'] - r['ganancia'] for r in table_rows
                             if (r['code'].startswith('5-') or r['code'].startswith('6-')) and not is_aggregate(r))
            gastos_op = sum(r['perdida'] for r in rows('5-01') if not name_has(r, 'deprec'))
            ebitda = (ing_op - costos_directos - gastos_op) if (ing_op - costos_directos - gastos_op) != 0 else None
            utilidad_neta = ing_op - gastos_tot
            depreciacion = sum(r['perdida'] for r in rows('5-') if name_has(r, 'deprec', 'amortiz'))
            # Utilidad/(Pérdida) del ejercicio: en balances tributarios de 8 columnas esta fila
            # ("Resultado del Ejercicio" / "Pérdidas / Ganancias") NO tiene código contable y no
            # entra en la suma 3-xx. Se obtiene por residuo de la ecuación contable.
            utilidad_ejercicio = (activo_cte + activo_no_cte) - pasivo_total - patrimonio

            return {
                'caja': caja,
                'cxc': cxc,
                'inv': inv,
                'otros_act_op': otros_act_op,
                'activo_cte': activo_cte,
                'activo_no_cte': activo_no_cte,
                'activo_total': activo_cte + activo_no_cte,
                'pasivo_cte': pasivo_cte,
                'cxp_op': cxp_op,
                'pasivo_no_cte': pasivo_no_cte,
                'pasivo_total': pasivo_total,
                'patrimonio': patrimonio,
                'capital_social': capital_social,
                'gastos_fin': gastos_fin,
                'dif_cambio': dif_cambio_neto,
                'deuda_cp': deuda_cp,
                'deuda_lp': deuda_lp,
                'deuda_financiera': deuda_financiera,
                'deuda_socios': deuda_socios,
                'servicio_deuda': servicio_deuda,
                'ing_op': ing_op,
                'costos_directos': costos_directos,
                'ebitda': ebitda,
                'utilidad_neta': utilidad_neta,
                'utilidad_ejercicio': utilidad_ejercicio,
                'depreciacion': depreciacion,
                'period_label': doc_info['period_label']
            }
        else:
            # Fallback para balances clasificados
            ext = {
                'caja': None, 'cxc': None, 'inv': None, 'otros_act_op': 0, 'activo_cte': None, 'activo_no_cte': 0,
                'activo_total': None, 'pasivo_cte': None, 'cxp_op': None, 'pasivo_no_cte': 0, 'pasivo_total': None, 'patrimonio': None,
                'capital_social': None, 'gastos_fin': None, 'dif_cambio': None, 'deuda_cp': None, 'deuda_lp': None,
                'deuda_financiera': None, 'deuda_socios': None, 'servicio_deuda': None,
                'ing_op': None, 'costos_directos': 0, 'ebitda': None, 'utilidad_neta': None,
                'utilidad_ejercicio': None, 'depreciacion': 0,
                'period_label': doc_info['period_label']
            }
            for i, line in enumerate(lines):
                line_u = line.upper()
                amt = None
                nums = re.findall(r'\(?-?\$?\s*\d{1,3}(?:[\.,]\d{3})+(?:[\.,]\d{2})?\)?', line)
                for n in nums:
                    parsed_n = parse_amount(n, fallback=None)
                    if parsed_n is not None and abs(parsed_n) >= 1000:
                        amt = parsed_n
                        break
                if amt is not None:
                    if ext['activo_cte'] is None and any(k in line_u for k in ['ACTIVO CORRIENTE', 'ACTIVO CIRCULANTE', 'TOTAL ACTIVOS CORRIENTES']):
                        ext['activo_cte'] = amt
                    elif ext['pasivo_cte'] is None and any(k in line_u for k in ['PASIVO CORRIENTE', 'PASIVO CIRCULANTE', 'TOTAL PASIVOS CORRIENTES']):
                        ext['pasivo_cte'] = amt
                    elif ext['cxc'] is None and any(k in line_u for k in ['DEUDORES COMERCIALES', 'CUENTAS POR COBRAR']):
                        ext['cxc'] = amt
                    elif ext['inv'] is None and any(k in line_u for k in ['EXISTENCIAS', 'INVENTARIOS', 'MERCADERIAS']):
                        ext['inv'] = amt
                    elif ext['caja'] is None and any(k in line_u for k in ['EFECTIVO Y EQUIVALENTES', 'DISPONIBLE', 'CAJA Y BANCOS']):
                        ext['caja'] = amt
                    elif ext['pasivo_total'] is None and any(k in line_u for k in ['TOTAL PASIVO', 'TOTAL PASIVOS']) and 'CORRIENTE' not in line_u:
                        ext['pasivo_total'] = amt
                    elif ext['patrimonio'] is None and any(k in line_u for k in ['PATRIMONIO NETO', 'TOTAL PATRIMONIO']):
                        ext['patrimonio'] = amt
                    elif ext['ebitda'] is None and any(k in line_u for k in ['EBITDA', 'RESULTADO OPERACIONAL', 'UTILIDAD OPERACIONAL']):
                        ext['ebitda'] = amt
                    elif ext['gastos_fin'] is None and any(k in line_u for k in ['GASTOS FINANCIEROS', 'COSTOS FINANCIEROS']):
                        ext['gastos_fin'] = amt
                    elif ext['dif_cambio'] is None and any(k in line_u for k in ['DIFERENCIA DE CAMBIO', 'DIFERENCIAS DE CAMBIO', 'DIF DE CAMBIO']):
                        ext['dif_cambio'] = -amt  # se asume pérdida; el signo real depende del PDF
                    elif ext['deuda_cp'] is None and any(k in line_u for k in ['OBLIGACIONES CON BANCOS C/P', 'DEUDA FINANCIERA CORRIENTE', 'PRESTAMOS BANCARIOS C/P']):
                        ext['deuda_cp'] = amt
            if ext['deuda_cp']:
                ext['deuda_financiera'] = ext['deuda_cp']
                ext['servicio_deuda'] = (ext['deuda_cp'] + (ext['gastos_fin'] or 0))
            return ext

    processed_list = [process_balance_metrics(d) for d in parsed_docs]

    # parsed_docs ya viene ordenado cronológicamente (parse_period_key):
    # curr_b = balance más reciente, prev_b = el anterior inmediato.
    curr_b = processed_list[-1]
    prev_b = processed_list[-2] if len(processed_list) >= 2 else None

    # Determinación del Flujo de Caja Operacional (Indirecto: EBITDA / Utilidad + Depreciación - Δ Capital de Trabajo)
    flujo_caja_op = None
    flujo_inversion = None
    flujo_financiamiento = None
    desglose_flujo = None

    if prev_b is not None:
        # Método del Estado de Flujos de Efectivo Comparativo
        delta_cxc = (curr_b['cxc'] or 0) - (prev_b['cxc'] or 0)
        delta_inv = (curr_b['inv'] or 0) - (prev_b['inv'] or 0)
        delta_otros_act = (curr_b['otros_act_op'] or 0) - (prev_b['otros_act_op'] or 0)
        delta_cxp = (curr_b['cxp_op'] or 0) - (prev_b['cxp_op'] or 0)

        # Resultado del PERÍODO COMPLETO comparado (no solo el balance actual).
        # Patrimonio 3-xx excluye la fila "Resultado del Ejercicio" (sin código contable en
        # balances tributarios), por lo que el patrimonio total real es patr + utilidad.
        # ΔPatrimonioTotal − ΔCapital Social da la ganancia retenida real del tramo completo
        # (asumiendo sin dividendos distribuidos).
        equity_curr = (curr_b['patrimonio'] or 0) + (curr_b.get('utilidad_ejercicio') or 0)
        equity_prev = (prev_b['patrimonio'] or 0) + (prev_b.get('utilidad_ejercicio') or 0)
        delta_patrimonio = equity_curr - equity_prev
        delta_capital = (curr_b['capital_social'] or 0) - (prev_b['capital_social'] or 0)
        ganancia_tramo = delta_patrimonio - delta_capital

        # Depreciación del tramo: solo la del balance ACTUAL.
        # El estado de resultados de prev_b cubre el período ANTERIOR al tramo (termina en
        # prev_b), por lo que sumarla duplicaría la depreciación. curr_b cubre (al menos)
        # el tramo que termina en curr_b.
        deprec = curr_b['depreciacion'] or 0

        flujo_caja_op = ganancia_tramo + deprec - delta_cxc - delta_inv - delta_otros_act + delta_cxp

        # Flujo de Inversión: Activos Fijos (Δ Activos no corrientes)
        delta_af = (curr_b['activo_no_cte'] or 0) - (prev_b['activo_no_cte'] or 0)
        flujo_inversion = - delta_af

        # Flujo de Financiamiento: Préstamos bancarios y aumentos/disminuciones de capital social
        delta_prestamos = ((curr_b['deuda_financiera'] or 0) + (curr_b['deuda_socios'] or 0)) - ((prev_b['deuda_financiera'] or 0) + (prev_b['deuda_socios'] or 0))
        flujo_financiamiento = delta_prestamos + delta_capital

        desglose_flujo = {
            'metodo': 'COMPARATIVO_DOS_PERIODOS',
            'ganancia_tramo_patrimonio': ganancia_tramo,
            'delta_patrimonio': delta_patrimonio,
            'delta_cxc': delta_cxc,
            'delta_inv': delta_inv,
            'delta_cxp': delta_cxp,
            'delta_otros_act_op': delta_otros_act,
            'delta_af_inversion': delta_af,
            'delta_prestamos_financiamiento': delta_prestamos,
            'delta_capital_social': delta_capital,
            'flujo_operacional': flujo_caja_op,
            'flujo_inversion': flujo_inversion,
            'flujo_financiamiento': flujo_financiamiento
        }
    else:
        # Estimación técnica para un solo período (sin balance anterior para comparar):
        # FCO = EBITDA − Gastos Financieros − Impuestos estimados
        # Impuestos: 25% sobre utilidad proxy (EBITDA − GF − Depreciación), solo si es positiva.
        # Depreciación se deduce del base imponible porque es gasto deducible (no cash).
        if curr_b['ebitda'] is not None:
            ebitda_v = curr_b['ebitda'] or 0
            gfin_v = curr_b['gastos_fin'] or 0
            deprec_v = curr_b['depreciacion'] or 0
            base_imponible = ebitda_v - gfin_v - deprec_v
            impuestos_est = max(0, base_imponible * 0.25)
            flujo_caja_op = int(round(ebitda_v - gfin_v - impuestos_est))

    # Principales variaciones entre año base y año actual (requiere dos balances)
    variaciones = _build_variaciones(prev_b, curr_b) if prev_b is not None else None

    return {
        'tipo': 'ESTADOS_FINANCIEROS',
        # Valores en crudo (raw): no se ocultan negativos ni ceros.
        # Un caja negativo (sobregiro), patrimonio 0 o gastos financieros netos son
        # información financiera válida que el motor de scoring debe poder evaluar.
        'activoCorriente': curr_b.get('activo_cte'),
        'pasivoCorriente': curr_b.get('pasivo_cte'),
        'cuentasPorCobrar': curr_b.get('cxc'),
        'inventarios': curr_b.get('inv'),
        'caja': curr_b.get('caja'),
        'pasivoTotal': curr_b.get('pasivo_total'),
        'patrimonio': curr_b.get('patrimonio'),
        'activoTotal': curr_b.get('activo_total'),
        'capitalSocial': curr_b.get('capital_social'),
        'utilidadEjercicio': curr_b.get('utilidad_ejercicio'),
        'ebitda': curr_b.get('ebitda'),
        'costosDirectos': curr_b.get('costos_directos'),
        'depreciacion': curr_b.get('depreciacion'),
        'flujoCajaOperacional': flujo_caja_op,
        'gastosFinancieros': curr_b.get('gastos_fin'),
        'diferenciaCambio': curr_b.get('dif_cambio'),
        'servicioDeuda': curr_b.get('servicio_deuda'),
        'deudaFinanciera': curr_b.get('deuda_financiera'),
        'deudaFinancieraCP': curr_b['deuda_cp'] if curr_b.get('deuda_cp') else None,
        'deudaSociosRelacionados': curr_b['deuda_socios'] if curr_b.get('deuda_socios') else None,
        'desglose_flujo': desglose_flujo,
        'variaciones': variaciones,
        'cuentas_detectadas': [
            {'campo': 'caja', 'glosa': 'Saldo neto 1-01-01 (Efectivo y Equivalentes)', 'monto': curr_b['caja']},
            {'campo': 'cuentasPorCobrar', 'glosa': 'Saldo neto 1-01-02 (Deudores Comerciales)', 'monto': curr_b['cxc']},
            {'campo': 'inventarios', 'glosa': 'Saldo neto 1-01-03 (Inventarios / Mercaderías)', 'monto': curr_b['inv']},
            {'campo': 'activoCorriente', 'glosa': 'Saldo neto grupo 1-01 (Activo Corriente)', 'monto': curr_b['activo_cte']},
            {'campo': 'activoTotal', 'glosa': 'Activo Total (1-01 + 1-02)', 'monto': curr_b.get('activo_total')},
            {'campo': 'pasivoCorriente', 'glosa': 'Saldo neto grupo 2-01 (Pasivo Corriente)', 'monto': curr_b['pasivo_cte']},
            {'campo': 'deudaFinancieraCP', 'glosa': 'Deuda Financiera Bancaria C/P (2-01-04 neto)', 'monto': curr_b['deuda_cp']},
            {'campo': 'deudaFinanciera', 'glosa': 'Deuda Financiera Total Bancaria (C/P + L/P)', 'monto': curr_b['deuda_financiera']},
            {'campo': 'deudaSociosRelacionados', 'glosa': 'Préstamos Socios y Relacionadas (2-01-03)', 'monto': curr_b['deuda_socios']},
            {'campo': 'capitalSocial', 'glosa': 'Capital Social Estatutario (3-01-01)', 'monto': curr_b.get('capital_social')},
            {'campo': 'utilidadEjercicio', 'glosa': 'Utilidad/(Pérdida) del Ejercicio (residuo ecuación contable)', 'monto': curr_b.get('utilidad_ejercicio')},
            {'campo': 'costosDirectos', 'glosa': 'Costos Directos (6-xx)', 'monto': curr_b.get('costos_directos')},
            {'campo': 'depreciacion', 'glosa': 'Depreciación y Amortización (5-xx)', 'monto': curr_b.get('depreciacion')},
            {'campo': 'flujoCajaOperacional', 'glosa': 'Flujo de Caja Operacional Calculado', 'monto': flujo_caja_op},
            {'campo': 'diferenciaCambio', 'glosa': 'Diferencia de Cambio neta (ingreso + / gasto -) — excluida de Gastos Financieros (NIIF/NIC)', 'monto': curr_b.get('dif_cambio')},
            {'campo': 'pasivoTotal', 'glosa': 'Pasivo Total (2-01 + 2-02)', 'monto': curr_b['pasivo_total']},
            {'campo': 'patrimonio', 'glosa': 'Patrimonio Neto (3-xx)', 'monto': curr_b['patrimonio']}
        ]
    }
