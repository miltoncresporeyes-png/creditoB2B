import os, re, time, threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from flask_cors import CORS

ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT, '.env'))

app = Flask(__name__, static_folder='assets', static_url_path='/assets')
CORS(app, resources={r"/api/*": {"origins": "*"}})
CACHE = {}
LOCK = threading.Lock()

def fetch_sii(rut):
    rut = rut.strip()
    with LOCK:
        if rut in CACHE:
            return CACHE[rut]
    body, dv = (rut.split('-') + [''])[:2]
    driver = None
    text = ""
    try:
        opts = webdriver.EdgeOptions()
        opts.add_argument('--headless=new')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Edge(options=opts)
        driver.set_page_load_timeout(15)
        driver.get('https://www2.sii.cl/stc/noauthz')
        time.sleep(4)
        inp = driver.find_element(By.CSS_SELECTOR, 'input.rut-form')
        inp.clear()
        inp.send_keys(rut)
        time.sleep(1)
        btn = driver.find_element(By.NAME, 'Consultar')
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(5)
        
        # Desplegar secciones colapsables (Actividades Económicas y Documentos Autorizados)
        try:
            acc_headers = driver.find_elements(By.XPATH, "//*[contains(text(), 'VER ')]")
            for h in acc_headers:
                driver.execute_script("arguments[0].click();", h)
            time.sleep(2)
        except Exception:
            pass

        text = driver.find_element(By.TAG_NAME, 'body').text
    except Exception as scrape_err:
        # Fallback resiliente: si el navegador headless no está instalado en el servidor o el portal SII no responde
        print(f"[SII Parser Warning] No fue posible consultar automáticamente vía navegador ({str(scrape_err)}). Activando respuesta estructurada de contingencia.")
        data = {
            'rut': rut,
            'nombre': None,
            'rutContribuyente': rut,
            'inicioActividades': 'Verificar manualmente o adjuntar Carpeta Tributaria F29',
            'fechaInicioActividades': None,
            'antiguedad': None,
            'monedaExtranjera': 'No',
            'empresaMenorTamano': 'No especificado',
            'actividad': 'Información disponible en Carpeta Tributaria F29/F22',
            'codActividad': None,
            'afectaIva': 'Si',
            'anioTimbraje': str(datetime.now().year),
            'documentosTimbrados': [{'documento': 'Factura Electrónica', 'anio': str(datetime.now().year)}],
            'fallback': True,
            'nota': 'Consulta automática al portal SII temporalmente no disponible desde este entorno. Por favor verifica los datos o adjunta la Carpeta Tributaria oficial.'
        }
        with LOCK:
            CACHE[rut] = data
        return data
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
    data = parse_sii(text, rut)
    with LOCK:
        CACHE[rut] = data
    return data

def parse_sii(text, rut):
    # Limpiar y normalizar para evitar fallas por tildes o codificación
    def grab_flexible(pattern):
        m = re.search(pattern + r'\s*:\s*(.+)', text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    nombre = grab_flexible(r'Nombre\s+o\s+Raz[oó\?]n\s+Social')
    rutc = grab_flexible(r'RUT\s+Contribuyente')
    inicio = grab_flexible(r'Contribuyente\s+presenta\s+Inicio\s+de\s+Actividades')
    fecha_inicio = grab_flexible(r'Fecha\s+de\s+Inicio\s+de\s+Actividades')
    extranjera = grab_flexible(r'Contribuyente\s+autorizado\s+para\s+declarar\s+y\s+pagar\s+sus\s+impuestos\s+en\s+moneda\s+extranjera')
    pyme = grab_flexible(r'Contribuyente\s+es\s+Empresa\s+de\s+Menor\s+Tama[nñ\?]o')
    antiguedad = None
    if fecha_inicio:
        try:
            from datetime import datetime
            d = datetime.strptime(fecha_inicio, '%d-%m-%Y')
            antiguedad = round((datetime.now() - d).days / 365.25, 1)
        except Exception:
            pass

    # Extraer Actividad Económica principal
    actividad = None
    cod_actividad = None
    afecta_iva = None
    m_act = re.search(r'Actividades\s+Econ[oó\?]micas\s+vigentes.*?Fecha\s*\n\s*1\s*\n\s*([^\n]+)\s*\n\s*(\d{4,6})\s*\n\s*([^\n]+)\s*\n\s*([^\n]+)', text, re.DOTALL | re.IGNORECASE)
    if m_act:
        actividad = m_act.group(1).strip()
        cod_actividad = m_act.group(2).strip()
        afecta_iva = m_act.group(4).strip()
    else:
        # Fallback genérico si viene en otra disposición
        m_act2 = re.search(r'1\s*\n\s*([A-ZÁÉÍÓÚÑ0-9\s,\.\-]{10,80})\s*\n\s*(\d{5,6})\s*\n\s*Primera\s*\n\s*(Si|No)', text, re.IGNORECASE)
        if m_act2:
            actividad = m_act2.group(1).strip()
            cod_actividad = m_act2.group(2).strip()
            afecta_iva = m_act2.group(3).strip()

    # Extraer última autorización / timbraje electrónico
    m_timbraje = re.search(r'Factura\s+Electr[oó\?]nica\s*\n\s*(\d{4})', text, re.IGNORECASE)
    anio_timbraje = m_timbraje.group(1).strip() if m_timbraje else None

    # Extraer lista completa de documentos autorizados y año de timbraje
    documentos_timbrados = []
    # Buscar patrones de documentos y años (Factura, Boleta, Guía, etc.)
    doc_matches = re.findall(r'(Factura[^\n\d]*|Boleta[^\n\d]*|Gu[ií]a[^\n\d]*|Liquidaci[oó]n[^\n\d]*)\s*(\d{4})', text, re.IGNORECASE)
    seen_docs = set()
    for dm in doc_matches:
        d_name = re.sub(r'^\d+\s*', '', dm[0]).strip()
        d_year = dm[1].strip()
        if d_name and int(d_year) >= 2000 and d_name.lower() not in seen_docs:
            seen_docs.add(d_name.lower())
            documentos_timbrados.append({'documento': d_name, 'anio': d_year})
            if 'factura' in d_name.lower() and ('electr' in d_name.lower() or not anio_timbraje):
                anio_timbraje = d_year

    return {
        'rut': rut,
        'nombre': nombre,
        'rutContribuyente': rutc,
        'inicioActividades': inicio,
        'fechaInicioActividades': fecha_inicio,
        'antiguedad': antiguedad,
        'monedaExtranjera': extranjera,
        'empresaMenorTamano': pyme,
        'actividad': actividad,
        'codActividad': cod_actividad,
        'afectaIva': afecta_iva,
        'anioTimbraje': anio_timbraje,
        'documentosTimbrados': documentos_timbrados,
        'rawSnippet': text[:1500]
    }

@app.route('/')
def landing():
    return send_file(ROOT + '/landing.html')

@app.route('/app')
def app_view():
    return send_file(ROOT + '/index.html')

@app.route('/favicon.ico')
def favicon():
    return ('', 204)

@app.route('/assets/<path:path>')
def assets(path):
    return send_from_directory(ROOT + '/assets', path)

@app.route('/api/sii')
def api_sii():
    rut = request.args.get('rut', '').strip()
    if not rut:
        return jsonify({'error': 'RUT requerido'}), 400
    try:
        data = fetch_sii(rut)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

import pdf_extractor

@app.route('/api/extract-pdf', methods=['POST'])
def extract_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No se adjuntó ningún archivo'}), 400
    
    file = request.files['file']
    doc_type = request.form.get('type', 'auto')
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'El archivo debe ser un PDF'}), 400
    
    try:
        content = file.read()
        if doc_type == 'erut':
            data = pdf_extractor.parse_erut(content)
        elif doc_type == 'cmf':
            data = pdf_extractor.parse_cmf_deudas(content)
        elif doc_type == 'carpeta_tributaria':
            data = pdf_extractor.parse_carpeta_tributaria(content)
        elif doc_type == 'estatutos':
            data = pdf_extractor.parse_estatutos(content)
        else:
            # Deteccion automatica segun contenido
            # Probar erut, cmf, carpeta tributaria
            try:
                ct = pdf_extractor.parse_carpeta_tributaria(content)
                if ct['periodos_disponibles'] > 0:
                    data = ct
                else:
                    cmf = pdf_extractor.parse_cmf_deudas(content)
                    if cmf['deuda_total'] > 0 or cmf['rut']:
                        data = cmf
                    else:
                        data = pdf_extractor.parse_erut(content)
            except Exception:
                data = pdf_extractor.parse_erut(content)
                
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'error': f'Error al procesar el PDF: {str(e)}'}), 500

import db
import report_generator
import invoice_generator
import email_service
from flask import Response

@app.route('/api/evaluations', methods=['POST'])
def handle_evaluations():
    """Registra de forma segura un expediente de evaluación evaluado localmente."""
    body = request.get_json() or {}
    input_data = body.get('input', {})
    result_data = body.get('result', {})
    if not input_data:
        return jsonify({'error': 'Faltan datos de evaluación'}), 400
    try:
        eval_id = db.save_evaluation(input_data, result_data)
        return jsonify({'success': True, 'id': eval_id})
    except Exception as e:
        return jsonify({'error': 'Error al guardar el expediente'}), 500

@app.route('/api/evaluations', methods=['GET'])
def list_evaluations_restricted():
    """El listado público de expedientes confidenciales está bloqueado por seguridad."""
    return jsonify({
        'error': 'Acceso no autorizado. El listado masivo de expedientes confidenciales está restringido.'
    }), 403

@app.route('/api/evaluations/<int:eval_id>', methods=['GET'])
def get_single_evaluation(eval_id):
    """Consulta segura de expediente que requiere token de acceso válido."""
    token = request.args.get('token', '').strip()
    if not token:
        return jsonify({'error': 'Token de autorización requerido para consultar el expediente'}), 401
    
    # Validar que el token corresponda a una transacción autorizada
    tx = db.check_payment_access(token)
    if not tx or tx.get('evaluacion_id') != eval_id:
        return jsonify({'error': 'Acceso denegado al expediente solicitado'}), 403

    eval_record = db.get_evaluation(eval_id)
    if not eval_record:
        return jsonify({'error': 'Evaluación no encontrada'}), 404
    return jsonify({'success': True, 'evaluation': eval_record})

@app.route('/api/report-pdf', methods=['POST'])
def export_report_pdf():
    body = request.get_json() or {}
    input_data = body.get('input', {})
    result_data = body.get('result', {})
    mode = body.get('mode', 'manual') # 'manual' (gratuita) o 'automated' (documental de pago)
    token = body.get('token') or request.args.get('token')
    eval_id = body.get('eval_id')
    
    if not input_data or not result_data:
        return jsonify({'error': 'Faltan datos para generar el dictamen'}), 400
        
    # Si solicita informe oficial sin marcas de agua, requiere validar crédito mediante token secreto
    is_preliminary = True
    credito_valido = False
    
    if token:
        order = db.get_order_by_token(token)
        if order and order.get('estado') == 'APPROVED':
            # Verificar o consumir crédito atómicamente
            ok, msg = db.consume_credit(token, eval_id=eval_id)
            if ok:
                credito_valido = True
                is_preliminary = False

    try:
        pdf_bytes = report_generator.generate_credit_report(input_data, result_data, is_preliminary=is_preliminary)
        prefix = "Dictamen_Credito_Oficial_" if not is_preliminary else "Dictamen_Preliminar_"
        filename = f"{prefix}{input_data.get('rut', 'Comercial')}.pdf"
        resp = Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        resp.headers['X-Report-Type'] = 'official' if not is_preliminary else 'preliminary'
        return resp
    except Exception as e:
        return jsonify({'error': f'Error al generar dictamen PDF: {str(e)}'}), 500

# Configuración centralizada de precios conforme a la política comercial de CreditoB2B
PRICES_CONFIG = {
    'individual': {'monto': 9990.0, 'informes': 1, 'nombre': 'Informe Individual'},
    'pack_3': {'monto': 24990.0, 'informes': 3, 'nombre': 'Pack 3 Informes'},
    'pack_10': {'monto': 69900.0, 'informes': 10, 'nombre': 'Pack 10 Informes'}
}

@app.route('/api/sample-report', methods=['GET'])
def get_sample_report():
    """Genera y descarga un informe de demostración con datos ficticios claramente identificados."""
    sample_input = {
        'rut': '76.999.888-K',
        'razonSocial': 'DISTRIBUIDORA EJEMPLO DEMO SpA',
        'sector': 'Comercio mayorista y distribución',
        'analista': 'Comité de Riesgo Comercial',
        'montoSolicitado': 45000000,
        'plazo': 30,
        'antiguedad': 8.5,
        'inicioActividades': 'SI',
        'afectaIva': 'SI',
        'timbrajeReciente': 'SI',
        'giro': 'VENTA AL POR MAYOR DE MAQUINARIA Y EQUIPO',
        'ebitda': 185000000,
        'ventas12m': 980000000,
        'patrimonio': 340000000,
        'deudaFinanciera': 95000000,
        'deudaCmfTotal': 45000000,
        'deudaCmfMora': 0,
        'deudaCastigada': 0,
        'diasMoraComercial': 0,
        'quiebraReorganizacion': 'NO',
        'acuerdoLey19983': 'SI',
        'poderesVigentes': 'SI',
        'esDemo': True
    }
    sample_result = {
        'score': 88.5,
        'status': {
            'key': 'approved',
            'label': 'APROBADO',
            'message': 'EMPRESA CON SÓLIDA CAPACIDAD DE PAGO Y GENERACIÓN OPERATIVA PARA LA LÍNEA SOLICITADA.',
            'tone': 'ok'
        },
        'limits': {
            'approved': 45000000,
            'commercial': 80547945,
            'financial': 55500000,
            'risk': 100000000,
            'gross': 55500000,
            'exposure': 0,
            'available': 55500000,
            'requested': 45000000
        },
        'term': {
            'approved': 30,
            'requested': 30,
            'notes': ['Plazo estándar comercial de 30 días conforme a Ley 19.983.']
        },
        'dimensions': [
            {'name': 'Capacidad de pago (FCO y EBITDA)', 'score': 28.5, 'max': 30, 'weight': 30},
            {'name': 'Solvencia y apalancamiento', 'score': 22.0, 'max': 25, 'weight': 25},
            {'name': 'Comportamiento comercial y CMF', 'score': 19.0, 'max': 20, 'weight': 20},
            {'name': 'Cumplimiento tributario SII', 'score': 10.0, 'max': 10, 'weight': 10},
            {'name': 'Formalidad legal y personería', 'score': 9.0, 'max': 15, 'weight': 15}
        ],
        'issues': []
    }
    try:
        pdf_bytes = report_generator.generate_credit_report(sample_input, sample_result)
        filename = "Informe_Ejemplo_Demostracion_CreditoB2B.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return jsonify({'error': f'Error al generar dictamen demo: {str(e)}'}), 500

import uuid, secrets

@app.route('/api/payments/create', methods=['POST'])
def create_payment():
    data = request.get_json() or {}
    plan = data.get('plan', 'pack_3')
    eval_id = data.get('eval_id')
    
    plan_info = PRICES_CONFIG.get(plan, PRICES_CONFIG['pack_3'])
    monto = plan_info['monto']
    informes = plan_info['informes']
    order_id = f"ORD-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
    try:
        db.create_payment_order(order_id, plan, monto, eval_id, creditos=informes)
        return jsonify({
            'success': True,
            'order_id': order_id,
            'plan': plan,
            'plan_nombre': plan_info['nombre'],
            'informes': plan_info['informes'],
            'monto': monto,
            'moneda': 'CLP'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Variables Mercado Pago exclusivamente desde entorno (.env)
MP_ACCESS_TOKEN = os.environ.get('MERCADO_PAGO_ACCESS_TOKEN')
MP_PUBLIC_KEY = os.environ.get('MERCADO_PAGO_PUBLIC_KEY')
MP_WEBHOOK_SECRET = os.environ.get('MERCADO_PAGO_WEBHOOK_SECRET')

def verify_mp_webhook_signature(x_signature, x_request_id, data_id):
    """Valida la firma HMAC-SHA256 enviada por Mercado Pago en el header x-signature."""
    if not x_signature:
        if not MP_WEBHOOK_SECRET:
            return True, "No secret configured"
        return False, "Cabecera x-signature requerida"

    if not x_request_id:
        return False, "Cabecera x-request-id requerida"
        
    ts = None
    v1 = None
    for part in x_signature.split(','):
        if '=' in part:
            k, v = part.strip().split('=', 1)
            if k == 'ts': ts = v
            elif k == 'v1': v1 = v
            
    if not ts or not v1:
        return False, "Formato de x-signature inválido"
        
    secret_key = MP_WEBHOOK_SECRET or 'creditob2b_default_webhook_secret'
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    import hmac, hashlib
    expected_hash = hmac.new(
        secret_key.encode('utf-8'),
        manifest.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_hash, v1):
        return False, "Firma digital de webhook inválida"
        
    return True, "Firma verificada"

@app.route('/api/payments/mp-preference', methods=['POST'])
def create_mp_preference():
    """Genera preferencia de pago oficial en Mercado Pago Sandbox/Producción."""
    import requests as req
    
    # Validar que existan credenciales configuradas
    if not MP_ACCESS_TOKEN or not MP_PUBLIC_KEY:
        return jsonify({'error': 'La pasarela de pago no está configurada en el servidor (faltan credenciales en el entorno).'}), 503

    data = request.get_json() or {}
    plan = data.get('plan', 'pack_3')
    eval_id = data.get('eval_id')
    billing_data = data.get('billing_data', {})
    
    plan_info = PRICES_CONFIG.get(plan, PRICES_CONFIG['pack_3'])
    monto = int(plan_info['monto'])
    informes = plan_info['informes']
    order_id = f"MP-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
    
    try:
        # Registrar orden en BD local con datos de facturación y cantidad de créditos
        db.create_payment_order(order_id, plan, monto, eval_id, billing_data, creditos=informes)
        
        # Crear preferencia en API de Mercado Pago
        headers = {
            'Authorization': f'Bearer {MP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        host = request.host_url.rstrip('/')
        # Mercado Pago requiere URLs https válidas para habilitar auto_return
        if not host.startswith('https://'):
            base_url = os.environ.get('BASE_PUBLIC_URL', 'https://creditob2b.cl')
        else:
            base_url = host
            
        preference_payload = {
            'items': [
                {
                    'id': plan,
                    'title': f"CreditoB2B - {plan_info['nombre']}",
                    'description': f"Evaluación de Capacidad de Crédito B2B ({plan_info['informes']} informe(s))",
                    'quantity': 1,
                    'currency_id': 'CLP',
                    'unit_price': monto
                }
            ],
            'external_reference': order_id,
            'back_urls': {
                'success': f"{base_url}/pago/exito?order_id={order_id}",
                'failure': f"{base_url}/pago/fallo?order_id={order_id}",
                'pending': f"{base_url}/pago/pendiente?order_id={order_id}"
            },
            'auto_return': 'approved',
            'statement_descriptor': 'CREDITOB2B'
        }
        mp_res = req.post('https://api.mercadopago.com/checkout/preferences', json=preference_payload, headers=headers, timeout=10)
        if mp_res.status_code in [200, 201]:
            pref_data = mp_res.json()
            return jsonify({
                'success': True,
                'order_id': order_id,
                'preference_id': pref_data.get('id'),
                'init_point': pref_data.get('init_point'),
                'sandbox_init_point': pref_data.get('sandbox_init_point'),
                'public_key': MP_PUBLIC_KEY
            })
        else:
            return jsonify({'error': 'Error de comunicación con la pasarela de pago.'}), 502
    except Exception as e:
        return jsonify({'error': 'Error al procesar la solicitud de pago.'}), 500

@app.route('/api/payments/mp-webhook', methods=['POST'])
def mp_webhook():
    """Webhook oficial de Mercado Pago: valida firma criptográfica y confirma transacciones consultando el estado real."""
    import requests as req
    data = request.get_json() or {}
    topic = data.get('type') or request.args.get('topic') or data.get('topic')
    
    payment_id = None
    if topic == 'payment':
        payment_id = data.get('data', {}).get('id') or request.args.get('id')
    
    if not payment_id:
        return jsonify({'status': 'ignored', 'reason': 'not a payment event'}), 200

    # 1. Validación estricta de la firma oficial de Mercado Pago si está presente o configurada
    x_signature = request.headers.get('x-signature')
    x_request_id = request.headers.get('x-request-id')
    
    if MP_WEBHOOK_SECRET or x_signature:
        sig_ok, sig_msg = verify_mp_webhook_signature(x_signature, x_request_id, payment_id)
        if not sig_ok:
            return jsonify({'error': 'Firma de webhook rechazada', 'detail': sig_msg}), 401

    if payment_id and MP_ACCESS_TOKEN:
        try:
            # 2. Consultar estado real a la API de Mercado Pago (control server-to-server definitivo)
            headers = {'Authorization': f'Bearer {MP_ACCESS_TOKEN}'}
            chk_res = req.get(f'https://api.mercadopago.com/v1/payments/{payment_id}', headers=headers, timeout=10)
            if chk_res.status_code == 200:
                payment_info = chk_res.json()
                status = payment_info.get('status')
                order_id = payment_info.get('external_reference')
                paid_amount = payment_info.get('transaction_amount')
                currency = payment_info.get('currency_id')
                
                # Validar existencia de orden en la BD
                order_record = db.get_payment_order(order_id) if order_id else None
                if not order_record:
                    return jsonify({'error': 'Orden no encontrada'}), 404
                
                # Validar integridad: estado aprobado, moneda CLP y monto coincidente
                expected_amount = float(order_record.get('monto', 0))
                if status == 'approved' and currency == 'CLP' and float(paid_amount) >= expected_amount:
                    access_token = f"tok_{secrets.token_urlsafe(24)}"
                    updated_order, status_msg = db.verify_and_complete_payment(order_id, access_token)
                    if updated_order and status_msg != "Pago previamente confirmado":
                        try:
                            # Generar comprobante comercial PDF para adjuntarlo al correo
                            invoice_pdf = invoice_generator.generate_invoice_pdf(updated_order, updated_order.get('billing_data', {}))
                            email_service.send_purchase_confirmation_email(updated_order, invoice_pdf)
                        except Exception as em_err:
                            print(f"[Email Dispatch Error] {str(em_err)}")
                    return jsonify({'status': 'approved_and_verified', 'order_id': order_id}), 200
                else:
                    return jsonify({'status': 'payment_not_approved_or_amount_mismatch', 'payment_status': status}), 200
        except Exception as e:
            return jsonify({'error': 'Error procesando notificación'}), 500

    return jsonify({'status': 'received'}), 200

@app.route('/pago/exito')
def pago_exito():
    """Página informativa de retorno tras el checkout de Mercado Pago."""
    import requests as req
    order_id = request.args.get('order_id', '').strip()
    collection_id = request.args.get('collection_id', '').strip()
    payment_id = request.args.get('payment_id', '').strip() or collection_id

    order_record = db.get_payment_order(order_id)
    if not order_record:
        return f"""
        <!DOCTYPE html>
        <html lang="es"><head><meta charset="UTF-8"><title>Orden no encontrada</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
          <h2>Orden de compra no encontrada</h2>
          <p>La referencia de orden proporcionada no existe en el sistema.</p>
          <a href="/">Volver al Inicio</a>
        </body></html>
        """, 404

    # Verificación segura server-to-server con API de Mercado Pago si no está ya aprobada
    if order_record['estado'] != 'APPROVED' and payment_id and MP_ACCESS_TOKEN:
        try:
            headers = {'Authorization': f'Bearer {MP_ACCESS_TOKEN}'}
            chk_res = req.get(f'https://api.mercadopago.com/v1/payments/{payment_id}', headers=headers, timeout=10)
            if chk_res.status_code == 200:
                payment_info = chk_res.json()
                mp_status = payment_info.get('status')
                mp_order_id = payment_info.get('external_reference')
                paid_amount = payment_info.get('transaction_amount')
                currency = payment_info.get('currency_id')
                expected_amount = float(order_record.get('monto', 0))

                if mp_status == 'approved' and mp_order_id == order_id and currency == 'CLP' and float(paid_amount) >= expected_amount:
                    access_token = f"tok_{secrets.token_urlsafe(24)}"
                    updated_order, status_msg = db.verify_and_complete_payment(order_id, access_token)
                    if updated_order:
                        order_record = updated_order
                        if status_msg != "Pago previamente confirmado":
                            try:
                                invoice_pdf = invoice_generator.generate_invoice_pdf(order_record, order_record.get('billing_data', {}))
                                email_service.send_purchase_confirmation_email(order_record, invoice_pdf)
                            except Exception as em_err:
                                print(f"[Email Dispatch Error] {str(em_err)}")
        except Exception:
            pass

    is_approved = order_record.get('estado') == 'APPROVED'
    billing = order_record.get('billing_data', {})
    receptor_nombre = billing.get('razon_social') or billing.get('nombre') or 'Cliente Registrado'
    receptor_rut = billing.get('rut') or 'N/A'
    plan_nombre = PRICES_CONFIG.get(order_record.get('plan_tipo'), {}).get('nombre', 'Evaluación de Crédito')
    monto_fmt = f"${int(order_record.get('monto', 0)):,}".replace(',', '.')

    status_badge_text = "Pago Confirmado" if is_approved else "Verificando Transacción"
    status_msg = "Tu pago ha sido confirmado. Puedes descargar de inmediato tu comprobante comercial y acceder a la plataforma." if is_approved else "Estamos validando la confirmación de la pasarela bancaria. Si el pago fue completado, tu acceso se habilitará en breve."

    download_button = f"""
    <a href="/api/invoice-pdf?order_id={order_id}" class="btn btn-invoice" target="_blank" download>
      📄 Descargar Comprobante de Compra (PDF)
    </a>
    """ if is_approved else """
    <p style="color: #f59e0b; font-size: 13px;">⏳ La descarga se habilitará una vez recibido el comprobante bancario.</p>
    """

    tok = order_record.get('token_acceso', '') if is_approved else ''
    app_url = f"/app?credit_token={tok}" if tok else "/app"
    token_display = f"""
    <div class="order-row" style="background: rgba(37,99,235,0.1); padding: 8px; border-radius: 8px; margin-top: 8px;">
      <span class="order-label" style="color: #60a5fa;">Token Secreto de Acceso:</span>
      <span class="order-value" style="font-family: monospace; font-size: 13px; color: #93c5fd;">{tok}</span>
    </div>
    """ if tok else ""

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <meta name="referrer" content="no-referrer">
      <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
      <title>Confirmación de Compra - CréditoB2B</title>
      <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
      <style>
        :root {{
          --bg-dark: #070d1e;
          --card-bg: #111a33;
          --card-border: #1e294b;
          --accent-blue: #2563eb;
          --accent-green: #10b981;
          --text-main: #f8fafc;
          --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
          background: var(--bg-dark);
          color: var(--text-main);
          min-height: 100vh;
          margin: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px 16px;
        }}
        .container {{
          background: var(--card-bg);
          border: 1px solid var(--card-border);
          border-radius: 20px;
          max-width: 580px;
          width: 100%;
          padding: 40px 32px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
          text-align: center;
        }}
        .success-badge {{
          width: 72px;
          height: 72px;
          border-radius: 50%;
          background: rgba(16, 185, 129, 0.15);
          color: var(--accent-green);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 38px;
          font-weight: 800;
          margin-bottom: 20px;
          border: 2px solid rgba(16, 185, 129, 0.3);
        }}
        h1 {{
          font-size: 24px;
          font-weight: 800;
          margin: 0 0 10px;
          color: #ffffff;
          letter-spacing: -0.02em;
        }}
        .lead {{
          color: var(--text-muted);
          font-size: 14.5px;
          margin: 0 0 24px;
          line-height: 1.5;
        }}
        .order-box {{
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid var(--card-border);
          border-radius: 14px;
          padding: 20px;
          text-align: left;
          margin-bottom: 24px;
        }}
        .order-row {{
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          font-size: 13.5px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .order-row:last-child {{ border-bottom: none; }}
        .order-label {{ color: var(--text-muted); }}
        .order-value {{ font-weight: 600; color: #ffffff; text-align: right; }}
        .actions {{
          display: flex;
          flex-direction: column;
          gap: 12px;
        }}
        .btn {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 13px 24px;
          border-radius: 10px;
          font-size: 14.5px;
          font-weight: 700;
          text-decoration: none;
          cursor: pointer;
          transition: all 0.2s ease;
          border: none;
        }}
        .btn-invoice {{
          background: #1e3a8a;
          color: #ffffff;
          border: 1px solid #3b82f6;
        }}
        .btn-invoice:hover {{
          background: #1d4ed8;
          transform: translateY(-1px);
        }}
        .btn-app {{
          background: var(--accent-blue);
          color: #ffffff;
        }}
        .btn-app:hover {{
          background: #1d4ed8;
          transform: translateY(-1px);
        }}
        .btn-home {{
          background: transparent;
          color: var(--text-muted);
          border: 1px solid var(--card-border);
        }}
        .btn-home:hover {{
          color: #ffffff;
          border-color: #475569;
        }}
        .tax-note {{
          font-size: 11.5px;
          color: #64748b;
          margin-top: 18px;
          line-height: 1.4;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="success-badge">{'✓' if is_approved else '⏳'}</div>
        <h1>{status_badge_text}</h1>
        <p class="lead">{status_msg}</p>

        <div class="order-box">
          <div class="order-row">
            <span class="order-label">N° de Orden:</span>
            <span class="order-value">{order_id}</span>
          </div>
          <div class="order-row">
            <span class="order-label">Plan / Servicio:</span>
            <span class="order-value">{plan_nombre}</span>
          </div>
          <div class="order-row">
            <span class="order-label">Total Pagado:</span>
            <span class="order-value" style="color: #34d399;">{monto_fmt} CLP</span>
          </div>
          <div class="order-row">
            <span class="order-label">Comprador:</span>
            <span class="order-value">{receptor_nombre}</span>
          </div>
          <div class="order-row">
            <span class="order-label">RUT Comprador:</span>
            <span class="order-value">{receptor_rut}</span>
          </div>
          <div class="order-row">
            <span class="order-label">Estado Orden:</span>
            <span class="order-value" style="color: {'#34d399' if is_approved else '#f59e0b'};">{'Aprobada' if is_approved else 'En Verificación'}</span>
          </div>
          {token_display}
        </div>

        <div class="actions">
          {download_button}
          <a href="{app_url}" class="btn btn-app">
            🚀 Comenzar a Evaluar en la Plataforma
          </a>
          <a href="/" class="btn btn-home">
            Volver a la Portada
          </a>
        </div>

        <p class="tax-note">
          Comprobante digital de servicio comercial.<br/>
          Para solicitar factura formal con DTE del SII contacte a facturacion@creditob2b.cl.
        </p>
      </div>
    </body>
    </html>
    """, 200

@app.route('/pago/fallo')
def pago_fallo():
    order_id = request.args.get('order_id', '')
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <title>Pago Fallido - CréditoB2B</title>
      <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
      <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #0b132b; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
        .card {{ background: #1c2541; padding: 40px; border-radius: 16px; text-align: center; max-width: 480px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #3a506b; }}
        .icon {{ font-size: 56px; margin-bottom: 16px; color: #ef4444; }}
        h1 {{ font-size: 26px; margin: 0 0 12px; }}
        p {{ color: #94a3b8; font-size: 15px; line-height: 1.5; }}
        .btn {{ display: inline-block; margin-top: 24px; padding: 12px 28px; background: #3b82f6; color: #fff; text-decoration: none; border-radius: 8px; font-weight: 700; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="icon">✗</div>
        <h1>El pago no pudo procesarse</h1>
        <p>La transacción no fue autorizada o fue cancelada por la entidad financiera.</p>
        <p style="font-size: 13px; color: #64748b;">Orden: <strong>{order_id}</strong></p>
        <a href="/" class="btn">Volver al Inicio</a>
      </div>
    </body>
    </html>
    """, 200

@app.route('/pago/pendiente')
def pago_pendiente():
    order_id = request.args.get('order_id', '')
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <title>Pago Pendiente - CréditoB2B</title>
      <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
      <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #0b132b; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
        .card {{ background: #1c2541; padding: 40px; border-radius: 16px; text-align: center; max-width: 480px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #3a506b; }}
        .icon {{ font-size: 56px; margin-bottom: 16px; color: #f59e0b; }}
        h1 {{ font-size: 26px; margin: 0 0 12px; }}
        p {{ color: #94a3b8; font-size: 15px; line-height: 1.5; }}
        .btn {{ display: inline-block; margin-top: 24px; padding: 12px 28px; background: #3b82f6; color: #fff; text-decoration: none; border-radius: 8px; font-weight: 700; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="icon">⏳</div>
        <h1>Pago en Proceso</h1>
        <p>Tu pago está pendiente de confirmación bancaria.</p>
        <p style="font-size: 13px; color: #64748b;">Orden: <strong>{order_id}</strong></p>
        <a href="/" class="btn">Volver al Inicio</a>
      </div>
    </body>
    </html>
    """, 200

@app.route('/api/invoice-pdf', methods=['GET'])
def download_invoice_pdf():
    order_id = request.args.get('order_id', '').strip()
    if not order_id:
        return jsonify({'error': 'order_id requerido'}), 400
    order_record = db.get_payment_order(order_id)
    if not order_record:
        return jsonify({'error': 'Orden no encontrada'}), 404
    
    billing_data = order_record.get('billing_data') or {}
    try:
        pdf_bytes = invoice_generator.generate_invoice_pdf(order_record, billing_data)
        rut_clean = re.sub(r'[^a-zA-Z0-9]', '', billing_data.get('rut', 'cliente'))
        filename = f"Factura_Electronica_{order_id}_{rut_clean}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return jsonify({'error': f'Error al generar factura PDF: {str(e)}'}), 500

@app.route('/api/payments/verify', methods=['POST'])
def verify_payment():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    if not order_id:
        return jsonify({'error': 'order_id requerido'}), 400
    access_token = f"tok_{secrets.token_urlsafe(24)}"
    try:
        tx, err = db.verify_and_complete_payment(order_id, access_token)
        if err and not tx:
            return jsonify({'error': err}), 400
        return jsonify({
            'success': True,
            'transaction': tx,
            'access_token': access_token,
            'download_url': f"/api/report-pdf-paid?token={access_token}",
            'invoice_url': f"/api/invoice-pdf?order_id={order_id}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/payments/credit-status', methods=['GET'])
def get_credit_status():
    """Consulta el saldo de créditos disponible exclusivamente mediante token de acceso secreto."""
    token = request.args.get('token', '').strip() or request.args.get('identifier', '').strip()
    if not token:
        return jsonify({'error': 'Token de acceso requerido'}), 400
        
    # Rechazar explícitamente si se intenta usar un número de orden público en lugar de un token secreto
    if token.startswith('ORD-') or token.startswith('MP-') or token.startswith('TEST-'):
        return jsonify({'valid': False, 'message': 'Acceso no autorizado: la consulta de saldo requiere el token secreto de acceso asignado al pagar.'}), 403

    # Si coincide con un order_id registrado en la base de datos, rechazar con 403
    order_by_id = db.get_payment_order(token)
    if order_by_id:
        return jsonify({'valid': False, 'message': 'Acceso no autorizado: la consulta de saldo requiere el token secreto de acceso, no el identificador de orden.'}), 403

    order = db.get_order_by_token(token)
    if not order:
        return jsonify({'valid': False, 'message': 'Token no encontrado o compra no aprobada'}), 404
    
    plan_info = PRICES_CONFIG.get(order.get('plan_tipo'), {})
    order_id = order.get('order_id', '')
    masked_order = order_id[:8] + '...' + order_id[-4:] if len(order_id) > 12 else order_id
    paid_at = order.get('paid_at') or order.get('created_at')

    # No exponer token secreto en la respuesta
    return jsonify({
        'valid': True,
        'plan_tipo': order.get('plan_tipo'),
        'plan_nombre': plan_info.get('nombre', 'Paquete de Informes'),
        'creditos_totales': order.get('creditos_totales', 1),
        'creditos_restantes': order.get('creditos_restantes', 0),
        'creditos_usados': max(0, order.get('creditos_totales', 1) - order.get('creditos_restantes', 0)),
        'order_id_masked': masked_order,
        'paid_at': paid_at,
        'evaluacion_id': order.get('evaluacion_id'),
        'invoice_url': f"/api/invoice-pdf?order_id={order_id}" if order_id else None
    })

@app.route('/api/report-pdf-paid', methods=['GET'])
def export_paid_report():
    token = request.args.get('token', '').strip()
    if not token:
        return jsonify({'error': 'Token de acceso requerido'}), 401
    tx = db.get_order_by_token_or_order_id(token)
    if not tx:
        return jsonify({'error': 'Token de pago inválido o transacción no aprobada'}), 403
    eval_id = tx.get('evaluacion_id')
    if not eval_id:
        return jsonify({'error': 'No hay expediente asociado a este pago'}), 404
    eval_record = db.get_evaluation(eval_id)
    if not eval_record:
        return jsonify({'error': 'Expediente no encontrado'}), 404
    try:
        pdf_bytes = report_generator.generate_credit_report(
            eval_record['input_data'], 
            eval_record['result_data'],
            is_preliminary=False
        )
        rut = eval_record['input_data'].get('rut', 'Comercial')
        filename = f"Dictamen_Credito_Oficial_{rut}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return jsonify({'error': f'Error al generar dictamen PDF: {str(e)}'}), 500

@app.route('/api/test-email', methods=['GET', 'POST'])
def trigger_test_email():
    """Endpoint de diagnóstico para emitir correos de prueba reales hacia cliente y administración."""
    client_email = request.args.get('client_email', 'pedropablomeromero@gmail.com').strip()
    admin_email = request.args.get('admin_email', 'contacto@creditob2b.cl').strip()

    fake_order = {
        'order_id': f'TEST-{int(time.time())}',
        'plan_tipo': 'pack_3',
        'monto': 24990,
        'creditos_totales': 3,
        'creditos_restantes': 3,
        'token_acceso': f'tok_test_{secrets.token_urlsafe(16)}',
        'billing_data': {
            'nombre': 'Pedro Pablo Romero',
            'razon_social': 'Comercializadora Pedro Romero SpA',
            'rut': '76.123.456-7',
            'giro': 'Distribución & Servicios Comerciales',
            'direccion': 'Santiago, Chile',
            'email': client_email
        }
    }

    # Temporalmente configurar ADMIN_NOTIFICATION_EMAIL si se especifica
    if admin_email:
        os.environ['ADMIN_NOTIFICATION_EMAIL'] = admin_email

    try:
        # Generar comprobante PDF de prueba para adjuntarlo
        sample_pdf = invoice_generator.generate_invoice_pdf(fake_order, fake_order['billing_data'])
        ok = email_service.send_purchase_confirmation_email(fake_order, sample_pdf)
        cfg = email_service.get_smtp_config()
        return jsonify({
            'success': True,
            'message': 'Prueba de correo iniciada en segundo plano.',
            'smtp_configured': cfg['is_configured'],
            'smtp_host': cfg['host'],
            'smtp_user': cfg['user'],
            'enviado_a_cliente': client_email,
            'enviado_a_admin': admin_email,
            'nota': 'Si las variables SMTP no están configuradas en .env o Railway, el servicio registrará la simulación sin error.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)