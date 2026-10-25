import os
import threading
import base64
import json
import urllib.request
import urllib.error
import socket
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email import policy
from email.parser import BytesParser

def get_email_api_config():
    """Obtiene la configuración del proveedor de correo mediante API HTTPS."""
    api_key = os.environ.get("EMAIL_API_KEY", "").strip() or os.environ.get("RESEND_API_KEY", "").strip()
    from_email = os.environ.get("EMAIL_FROM", "").strip() or os.environ.get("SMTP_USER", "contacto@creditob2b.cl").strip()
    from_name = os.environ.get("EMAIL_FROM_NAME", "").strip() or os.environ.get("SMTP_FROM_NAME", "CréditoB2B Chile").strip()
    api_url = os.environ.get("EMAIL_API_URL", "https://api.resend.com/emails").strip()
    return {
        "is_configured": bool(api_key and from_email),
        "api_key": api_key,
        "from_email": from_email,
        "from_name": from_name,
        "api_url": api_url,
    }

def get_smtp_config():
    """Obtiene y normaliza la configuración SMTP del entorno."""
    host = os.environ.get('SMTP_HOST', '').strip()
    port_str = os.environ.get('SMTP_PORT', '587').strip()
    user = os.environ.get('SMTP_USER', '').strip()
    password = os.environ.get('SMTP_PASSWORD', '').strip()
    from_name = os.environ.get('SMTP_FROM_NAME', 'CréditoB2B Chile').strip()
    
    try:
        port = int(port_str)
    except ValueError:
        port = 587
        
    is_configured = bool(host and user and password)
    return {
        'is_configured': is_configured,
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'from_name': from_name
    }

class EmailApiClient:
    """Cliente para enviar mensajes MIME mediante una API HTTPS compatible con Resend / Hostinger."""
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key

    def sendmail(self, from_addr, recipients, raw_message):
        import email.utils
        import unicodedata
        message = BytesParser(policy=policy.default).parsebytes(raw_message.encode("utf-8") if isinstance(raw_message, str) else raw_message)
        
        # Extraer y normalizar 'from' a formato estándar estricto aceptado por la API de Resend
        header_from = message.get("From") or from_addr
        real_name, email_addr = email.utils.parseaddr(header_from)
        if not email_addr and '@' in from_addr:
            email_addr = from_addr.strip()
        
        # Quitar acentos o caracteres especiales del nombre para evitar rechazo en el encabezado HTTP
        if real_name:
            norm_name = unicodedata.normalize('NFKD', real_name).encode('ascii', 'ignore').decode('ascii').strip()
            clean_from = f"{norm_name} <{email_addr}>" if norm_name else email_addr
        else:
            clean_from = email_addr

        payload = {
            "from": clean_from,
            "to": recipients,
            "subject": message.get("Subject", ""),
        }
        attachments = []
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = part.get_content_disposition()
            filename = part.get_filename()
            content_type = part.get_content_type()
            if disposition == "attachment" or filename:
                data = part.get_payload(decode=True) or b""
                attachments.append({
                    "filename": filename or "adjunto.pdf",
                    "content": base64.b64encode(data).decode("ascii"),
                })
            elif content_type == "text/html":
                payload["html"] = part.get_content()
            elif content_type == "text/plain":
                payload["text"] = part.get_content()

        if attachments:
            payload["attachments"] = attachments

        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CreditoB2B-email-api/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"API de correo respondió HTTP {response.status}: {response_body}")
                return response_body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API de correo respondió HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"No se pudo conectar con la API de correo por HTTPS: {exc.reason}") from exc

def _connect_smtp_robust(host, port, user, password, log_callback=None):
    """Fallback SMTP forzando resolución IPv4 en caso de usar SMTP en lugar de API."""
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(f"[SMTP Connection] {msg}")

    resolved_ip = host
    try:
        addr_infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if addr_infos:
            resolved_ip = addr_infos[0][4][0]
            _log(f"Resolución IPv4 para {host}: {resolved_ip}")
    except Exception as dns_err:
        _log(f"Advertencia en resolución IPv4 ({host}): {dns_err}, usando hostname directo.")
        resolved_ip = host

    ports_to_try = [port]
    for alt in [587, 465, 2525]:
        if alt not in ports_to_try:
            ports_to_try.append(alt)

    last_error = None
    for target_port in ports_to_try:
        server = None
        try:
            _log(f"Intentando conexión con {resolved_ip}:{target_port} (SNI: {host})...")
            if target_port == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(resolved_ip, target_port, timeout=4, context=context)
                server.ehlo(host)
            else:
                server = smtplib.SMTP(resolved_ip, target_port, timeout=4)
                server.ehlo(host)
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo(host)

            _log(f"Autenticando usuario {user}...")
            server.login(user, password)
            _log(f"¡Autenticación SMTP exitosa en puerto {target_port}!")
            return server
        except Exception as conn_err:
            last_error = conn_err
            _log(f"Fallo en puerto {target_port}: {conn_err}")
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    raise last_error or Exception(f"No fue posible conectar a {host} en los puertos {ports_to_try}")

def send_purchase_confirmation_email(order_record, pdf_bytes=None):
    """
    Despacha en un hilo secundario:
    1. Notificación al cliente comprador con su clave y comprobante PDF adjunto.
    2. Notificación interna a la administración (contacto@creditob2b.cl) avisando nueva compra.
    Prioriza API HTTPS (EMAIL_API_KEY) sobre SMTP tradicional para evitar bloqueos de firewall en Railway.
    """
    api_cfg = get_email_api_config()
    smtp_cfg = get_smtp_config()

    if not api_cfg["is_configured"] and not smtp_cfg["is_configured"]:
        print("[Email Service Info] Ni EMAIL_API_KEY ni SMTP configurados. Se omite envío de correo.")
        return False

    billing = order_record.get('billing_data', {}) or {}
    recipient_email = billing.get('email') or billing.get('correo') or ''
    recipient_email = recipient_email.strip()
    
    admin_email = os.environ.get('ADMIN_NOTIFICATION_EMAIL', 'contacto@creditob2b.cl').strip()

    def _worker():
        order_id = order_record.get('order_id', '')
        token_acceso = order_record.get('token_acceso', '')
        plan_tipo = order_record.get('plan_tipo', 'pack_3')
        creditos_totales = order_record.get('creditos_totales', 1)
        monto = int(order_record.get('monto', 0))
        monto_fmt = f"${monto:,}".replace(',', '.')
        receptor_nombre = billing.get('razon_social') or billing.get('nombre') or 'Cliente'
        receptor_rut = billing.get('rut') or 'N/A'
        receptor_giro = billing.get('giro') or 'No especificado'
        receptor_direccion = billing.get('direccion') or 'No especificada'
        base_url = os.environ.get('BASE_PUBLIC_URL', 'https://creditob2b-production.up.railway.app').rstrip('/')
        app_access_url = f"{base_url}/app?credit_token={token_acceso}" if token_acceso else f"{base_url}/app"

        use_api = api_cfg["is_configured"]
        dispatcher = None
        from_email_addr = api_cfg["from_email"] if use_api else smtp_cfg["user"]
        from_name_str = api_cfg["from_name"] if use_api else smtp_cfg["from_name"]

        try:
            if use_api:
                dispatcher = EmailApiClient(api_cfg["api_url"], api_cfg["api_key"])
                print(f"[Email Service] Utilizando API HTTPS ({api_cfg['api_url']})")
            else:
                dispatcher = _connect_smtp_robust(smtp_cfg['host'], smtp_cfg['port'], smtp_cfg['user'], smtp_cfg['password'])
                print(f"[Email Service] Utilizando conexión SMTP directa a {smtp_cfg['host']}")

            # 1. Enviar correo a los clientes/usuarios (soporta múltiples separados por coma)
            client_list = [e.strip() for e in recipient_email.split(',') if e.strip() and '@' in e]
            for c_mail in client_list:
                try:
                    msg_user = MIMEMultipart('mixed')
                    msg_user['Subject'] = f"Confirmación de Compra y Clave de Acceso - Orden {order_id}"
                    msg_user['From'] = f"{from_name_str} <{from_email_addr}>"
                    msg_user['To'] = c_mail

                    html_user = f"""
                    <!DOCTYPE html>
                    <html lang="es">
                    <head>
                      <meta charset="utf-8">
                      <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
                        .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 14px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.06); }}
                        .header {{ background: linear-gradient(135deg, #0a2540 0%, #0284c7 100%); color: #ffffff; padding: 24px 28px; text-align: left; }}
                        .header h1 {{ margin: 0; font-size: 20px; font-weight: 800; }}
                        .header p {{ margin: 4px 0 0; font-size: 13px; color: #bae6fd; }}
                        .content {{ padding: 28px; line-height: 1.6; font-size: 14px; }}
                        .token-box {{ background: #f0fdf4; border: 1px solid #86efac; border-radius: 10px; padding: 18px; margin: 20px 0; text-align: center; }}
                        .token-title {{ font-size: 12px; font-weight: 700; text-transform: uppercase; color: #166534; letter-spacing: 0.05em; }}
                        .token-code {{ font-family: monospace, Courier; font-size: 16px; font-weight: 800; color: #0f172a; background: #ffffff; padding: 8px 14px; border-radius: 6px; border: 1px dashed #22c55e; display: inline-block; margin-top: 6px; word-break: break-all; }}
                        .btn {{ display: inline-block; background: #0066cc; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 700; font-size: 14px; margin-top: 14px; text-align: center; }}
                        .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 28px; font-size: 11px; color: #64748b; text-align: center; }}
                        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
                        td {{ padding: 6px 0; border-bottom: 1px solid #f1f5f9; }}
                        td.label {{ color: #64748b; font-weight: 600; width: 40%; }}
                        td.val {{ color: #0f172a; font-weight: 700; text-align: right; }}
                      </style>
                    </head>
                    <body>
                      <div class="card">
                        <div class="header">
                          <h1>CréditoB2B Chile</h1>
                          <p>Evaluación de Capacidad & Riesgo Comercial · Ley 19.983</p>
                        </div>
                        <div class="content">
                          <p>Estimado(a) <strong>{receptor_nombre}</strong>,</p>
                          <p>Confirmamos la recepción exitosa de tu pago por el servicio de evaluación crediticia comercial. Tu cuenta cuenta con <strong>{creditos_totales} crédito(s)</strong> disponibles.</p>
                          
                          <table>
                            <tr>
                              <td class="label">N° de Orden:</td>
                              <td class="val">{order_id}</td>
                            </tr>
                            <tr>
                              <td class="label">Paquete Contratado:</td>
                              <td class="val">{plan_tipo.upper()} ({creditos_totales} Informes)</td>
                            </tr>
                            <tr>
                              <td class="label">Total Pagado:</td>
                              <td class="val">{monto_fmt} CLP</td>
                            </tr>
                          </table>

                          <div class="token-box">
                            <div class="token-title">Tu Clave Secreta de Acceso</div>
                            <div class="token-code">{token_acceso}</div>
                            <p style="font-size: 11px; color: #15803d; margin: 8px 0 0;">Guarda esta clave para ingresar a la plataforma o consultar tus créditos.</p>
                          </div>

                          <div style="text-align: center;">
                            <a href="{app_access_url}" class="btn">🚀 Ingresar directamente a la Plataforma</a>
                          </div>

                          <p style="margin-top: 24px; font-size: 12.5px; color: #64748b;">
                            Se adjunta a este correo tu <strong>Comprobante de Compra y Pago Comercial en formato PDF</strong>. Si requieres factura formal con DTE del SII, nuestro equipo emitirá el documento con los datos tributarios informados.
                          </p>
                        </div>
                        <div class="footer">
                          © 2026 CréditoB2B Chile. Plataforma técnica de apoyo a la gestión de riesgo.<br/>
                          Soporte comercial: contacto@creditob2b.cl | WhatsApp: +56 9 8341 4730
                        </div>
                      </div>
                    </body>
                    </html>
                    """
                    msg_user.attach(MIMEText(html_user, 'html', 'utf-8'))

                    if pdf_bytes:
                        part = MIMEApplication(pdf_bytes, _subtype="pdf")
                        part.add_header('Content-Disposition', 'attachment', filename=f"Comprobante_Pago_{order_id}.pdf")
                        msg_user.attach(part)

                    dispatcher.sendmail(from_email_addr, [c_mail], msg_user.as_string())
                    print(f"[Email Success] Notificación enviada al cliente {c_mail} para orden {order_id}")
                except Exception as client_err:
                    print(f"[Email Error] Falló envío a cliente {c_mail}: {str(client_err)}")

            # 2. Notificación a Administración (contacto@creditob2b.cl)
            admin_list = [a.strip() for a in admin_email.split(',') if a.strip() and '@' in a]
            for a_mail in admin_list:
                try:
                    msg_admin = MIMEMultipart('mixed')
                    msg_admin['Subject'] = f"🔔 [Nueva Suscripción/Compra] {receptor_nombre} - Orden {order_id}"
                    msg_admin['From'] = f"{from_name_str} <{from_email_addr}>"
                    msg_admin['To'] = a_mail

                    html_admin = f"""
                    <!DOCTYPE html>
                    <html lang="es">
                    <head><meta charset="utf-8">
                    <style>
                      body {{ font-family: sans-serif; background: #f1f5f9; padding: 20px; }}
                      .box {{ background: #ffffff; max-width: 550px; margin: 0 auto; border-radius: 10px; border: 1px solid #cbd5e1; padding: 24px; }}
                      h2 {{ color: #0f172a; margin-top: 0; }}
                      table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
                      td {{ padding: 8px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }}
                      td.label {{ font-weight: bold; color: #475569; width: 40%; }}
                    </style>
                    </head>
                    <body>
                      <div class="box">
                        <h2>🎉 Nueva Compra Realizada en CréditoB2B</h2>
                        <p>Se ha registrado y confirmado un nuevo pago mediante pasarela bancaria:</p>
                        <table>
                          <tr><td class="label">N° de Orden:</td><td><strong>{order_id}</strong></td></tr>
                          <tr><td class="label">Razón Social / Nombre:</td><td>{receptor_nombre}</td></tr>
                          <tr><td class="label">RUT:</td><td>{receptor_rut}</td></tr>
                          <tr><td class="label">Giro:</td><td>{receptor_giro}</td></tr>
                          <tr><td class="label">Dirección:</td><td>{receptor_direccion}</td></tr>
                          <tr><td class="label">Correo Comprador:</td><td>{recipient_email}</td></tr>
                          <tr><td class="label">Plan:</td><td>{plan_tipo.upper()} ({creditos_totales} Informes)</td></tr>
                          <tr><td class="label">Monto Pagado:</td><td><strong>{monto_fmt} CLP</strong></td></tr>
                          <tr><td class="label">Token Asignado:</td><td><code>{token_acceso}</code></td></tr>
                        </table>
                        <p style="font-size: 12px; color: #64748b; margin-top: 20px;">
                          Se adjunta el comprobante de compra emitido al cliente para el respaldo contable y emisión de factura SII correspondiente.
                        </p>
                      </div>
                    </body>
                    </html>
                    """
                    msg_admin.attach(MIMEText(html_admin, 'html', 'utf-8'))

                    if pdf_bytes:
                        part_admin = MIMEApplication(pdf_bytes, _subtype="pdf")
                        part_admin.add_header('Content-Disposition', 'attachment', filename=f"Comprobante_Pago_{order_id}.pdf")
                        msg_admin.attach(part_admin)

                    dispatcher.sendmail(from_email_addr, [a_mail], msg_admin.as_string())
                    print(f"[Email Success] Notificación administrativa enviada a {a_mail} para orden {order_id}")
                except Exception as admin_err:
                    print(f"[Email Error] Falló envío a administración {a_mail}: {str(admin_err)}")

        except Exception as e:
            print(f"[Email Error] Falló conexión/despacho con servicio de correo: {str(e)}")
        finally:
            if dispatcher and not use_api:
                try:
                    dispatcher.quit()
                except Exception:
                    pass

    threading.Thread(target=_worker, daemon=True).start()
    return True

def send_purchase_confirmation_sync(order_record, pdf_bytes=None):
    """Ejecución síncrona que retorna logs detallados y errores explícitos para diagnóstico."""
    api_cfg = get_email_api_config()
    smtp_cfg = get_smtp_config()
    logs = []

    use_api = api_cfg["is_configured"]
    if not use_api and not smtp_cfg["is_configured"]:
        return {'success': False, 'error': 'Ni EMAIL_API_KEY ni configuración SMTP presentes en entorno.'}

    billing = order_record.get('billing_data', {}) or {}
    recipient_email = billing.get('email') or billing.get('correo') or ''
    admin_email = os.environ.get('ADMIN_NOTIFICATION_EMAIL', 'contacto@creditob2b.cl').strip()

    order_id = order_record.get('order_id', '')
    token_acceso = order_record.get('token_acceso', '')
    plan_tipo = order_record.get('plan_tipo', 'pack_3')
    creditos_totales = order_record.get('creditos_totales', 1)
    monto = int(order_record.get('monto', 0))
    monto_fmt = f"${monto:,}".replace(',', '.')
    receptor_nombre = billing.get('razon_social') or billing.get('nombre') or 'Cliente'
    base_url = os.environ.get('BASE_PUBLIC_URL', 'https://creditob2b-production.up.railway.app').rstrip('/')
    app_access_url = f"{base_url}/app?credit_token={token_acceso}" if token_acceso else f"{base_url}/app"

    dispatcher = None
    from_email_addr = api_cfg["from_email"] if use_api else smtp_cfg["user"]
    from_name_str = api_cfg["from_name"] if use_api else smtp_cfg["from_name"]

    try:
        if use_api:
            logs.append(f"Iniciando despacho mediante API HTTPS ({api_cfg['api_url']})...")
            dispatcher = EmailApiClient(api_cfg["api_url"], api_cfg["api_key"])
            logs.append("Cliente API HTTPS inicializado correctamente.")
        else:
            def log_cb(m):
                logs.append(m)
            dispatcher = _connect_smtp_robust(smtp_cfg['host'], smtp_cfg['port'], smtp_cfg['user'], smtp_cfg['password'], log_callback=log_cb)

        # Enviar a clientes
        client_list = [e.strip() for e in recipient_email.split(',') if e.strip() and '@' in e]
        for c_mail in client_list:
            msg_user = MIMEMultipart('mixed')
            msg_user['Subject'] = f"Confirmación de Compra y Clave de Acceso - Orden {order_id}"
            msg_user['From'] = f"{from_name_str} <{from_email_addr}>"
            msg_user['To'] = c_mail
            msg_user.attach(MIMEText(f"<p>Hola {receptor_nombre}, tu clave es <b>{token_acceso}</b></p><p><a href='{app_access_url}'>Ingresar</a></p>", 'html', 'utf-8'))
            if pdf_bytes:
                part = MIMEApplication(pdf_bytes, _subtype="pdf")
                part.add_header('Content-Disposition', 'attachment', filename=f"Comprobante_Pago_{order_id}.pdf")
                msg_user.attach(part)
            dispatcher.sendmail(from_email_addr, [c_mail], msg_user.as_string())
            logs.append(f"Despachado a cliente: {c_mail}")

        # Enviar a admin
        admin_list = [a.strip() for a in admin_email.split(',') if a.strip() and '@' in a]
        for a_mail in admin_list:
            msg_admin = MIMEMultipart('mixed')
            msg_admin['Subject'] = f"🔔 [Nueva Suscripción] {receptor_nombre} - Orden {order_id}"
            msg_admin['From'] = f"{from_name_str} <{from_email_addr}>"
            msg_admin['To'] = a_mail
            msg_admin.attach(MIMEText(f"<p>Nueva orden {order_id} por {monto_fmt} CLP para {receptor_nombre}</p>", 'html', 'utf-8'))
            dispatcher.sendmail(from_email_addr, [a_mail], msg_admin.as_string())
            logs.append(f"Despachado a admin: {a_mail}")

        return {'success': True, 'logs': logs, 'mode': 'API_HTTPS' if use_api else 'SMTP'}
    except Exception as e:
        logs.append(f"Excepción en envío de correo: {str(e)}")
        return {'success': False, 'logs': logs, 'error': str(e)}
    finally:
        if dispatcher and not use_api:
            try:
                dispatcher.quit()
            except Exception:
                pass
