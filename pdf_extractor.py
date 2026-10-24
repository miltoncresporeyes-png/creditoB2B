import fitz
import re
from datetime import datetime

def parse_erut(pdf_bytes_or_path):
    """Extrae datos de un e-RUT chileno oficial."""
    doc = fitz.open(stream=pdf_bytes_or_path, filetype="pdf") if isinstance(pdf_bytes_or_path, (bytes, bytearray)) else fitz.open(pdf_bytes_or_path)
    text = '\n'.join([p.get_text() for p in doc])
    
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
    doc = fitz.open(stream=pdf_bytes_or_path, filetype="pdf") if isinstance(pdf_bytes_or_path, (bytes, bytearray)) else fitz.open(pdf_bytes_or_path)
    text = '\n'.join([p.get_text() for p in doc])
    
    m_rut = re.search(r'Rut:\s*([0-9\.\-kK]+)', text)
    rut = m_rut.group(1).strip() if m_rut else None
    
    # Deuda Total
    m_tot = re.search(r'Deuda total(?:\s*y estado de pago)?\s*\$([\d\.]+)', text)
    deuda_total = int(m_tot.group(1).replace('.', '')) if m_tot else 0
    
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
            'total': int(m_dir.group(1).replace('.', '')),
            'vigente': int(m_dir.group(2).replace('.', '')),
            'mora_30_59': int(m_dir.group(3).replace('.', '')),
            'mora_60_89': int(m_dir.group(4).replace('.', '')),
            'mora_90_mas': int(m_dir.group(5).replace('.', ''))
        }
    
    # Líneas disponibles
    m_disp = re.search(r'Líneas de crédito.*?Total\s*\$([\d\.]+)', text, re.DOTALL)
    lineas_disp = int(m_disp.group(1).replace('.', '')) if m_disp else 0

    return {
        'tipo': 'CMF_DEUDAS',
        'rut': rut,
        'deuda_total': deuda_total,
        'deuda_vigente': directa['vigente'],
        'mora_30_59': directa['mora_30_59'],
        'mora_60_89': directa['mora_60_89'],
        'mora_90_mas': directa['mora_90_mas'],
        'mora_total': directa['mora_30_59'] + directa['mora_60_89'] + directa['mora_90_mas'],
        'lineas_disponibles': lineas_disp
    }

def parse_carpeta_tributaria(pdf_bytes_or_path):
    """Extrae declaraciones mensuales F29 y datos del contribuyente de la Carpeta Tributaria SII."""
    doc = fitz.open(stream=pdf_bytes_or_path, filetype="pdf") if isinstance(pdf_bytes_or_path, (bytes, bytearray)) else fitz.open(pdf_bytes_or_path)
    
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
            # Ventas netas: Cod 563 (base gravada). Si es 0 o no está, estimar de Débitos Facturas/Boletas (Cod 502 + 111 / 0.19) o Cod 538 / 0.19
            v_netas = cods.get('563', 0)
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
                if l in ['122', '123', '843', '101', '102', '129', '1672', '1445', '1496']:
                    for nxt in lines[i+1:i+6]:
                        val = nxt.replace('.', '')
                        if re.match(r'^-?\d+$', val) and int(val) > 1000:
                            if l == '122' and 'total_activo' not in f22_data: f22_data['total_activo'] = int(val)
                            elif l == '123' and 'total_pasivo' not in f22_data: f22_data['total_pasivo'] = int(val)
                            elif l in ['843', '1496'] and 'patrimonio' not in f22_data: f22_data['patrimonio'] = int(val)
                            elif l == '101' and 'caja' not in f22_data: f22_data['caja'] = int(val)
                            elif l == '129' and 'inventarios' not in f22_data: f22_data['inventarios'] = int(val)
                            elif l in ['1672', '1445'] and 'resultado' not in f22_data: f22_data['resultado'] = int(val)
                            break
            if f22_data:
                break
            
    # Ordenar por periodo descendente
    f29_list.sort(key=lambda x: x['periodo'], reverse=True)
    
    ultimos_12 = f29_list[:12]
    ventas_12m = sum([x['ventas_netas'] for x in ultimos_12])
    promedio_mensual = int(ventas_12m / len(ultimos_12)) if ultimos_12 else 0

    return {
        'tipo': 'CARPETA_TRIBUTARIA',
        'rut': rut,
        'razon_social': razon_social,
        'fecha_inicio': fecha_inicio,
        'antiguedad_anios': antiguedad,
        'ventas_12m': ventas_12m,
        'promedio_mensual_ventas': promedio_mensual,
        'periodos_disponibles': len(f29_list),
        'historico_mensual': f29_list,
        'eeff_f22': f22_data
    }

def parse_estatutos(pdf_bytes_or_path):
    """Extrae representantes legales vigentes y datos societarios de escrituras/estatutos RES."""
    doc = fitz.open(stream=pdf_bytes_or_path, filetype="pdf") if isinstance(pdf_bytes_or_path, (bytes, bytearray)) else fitz.open(pdf_bytes_or_path)
    full = '\n'.join([p.get_text() for p in doc])
    
    ruts = set(re.findall(r'\b\d{1,2}\.\d{3}\.\d{3}-[\dkK]\b', full))
    # Quitar ruts tipicos de notarías o genéricos si es necesario
    facultades_financieras = any(term in full.lower() for term in ['endeudar', 'obligar', 'banco', 'mutuo', 'crédito', 'pagaré', 'cuenta corriente'])
    
    return {
        'tipo': 'ESTATUTOS_PODERES',
        'ruts_detectados': list(ruts),
        'facultades_financieras_detectadas': facultades_financieras,
        'es_res': 'Registro de Empresas y Sociedades' in full
    }
