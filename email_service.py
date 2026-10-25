import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

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

import socket
import ssl

def _connect_smtp_robust(host, port, user, password, log_callback=None):
    """
    Establece conexión SMTP forzando resolución IPv4 (evita 'Errno 101 Network is unreachable' en Railway/Cloud)
    y con fallback automático entre SSL (465) y STARTTLS (587).
    """
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(f"[SMTP Connection] {msg}")

    # Forzar resolución IPv4
    resolved_ip = host
    try:
        addr_infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if addr_infos:
            resolved_ip = addr_infos[0][4][0]
            _log(f"Resolución IPv4 para {host}: {resolved_ip}")
    except Exception as dns_err:
        _log(f"Advertencia en resolución IPv4 ({host}): {dns_err}, usando hostname directo.")
        resolved_ip = host

    # Estrategia de puertos a probar (2525 es el puerto alternativo estándar no bloqueado)
    ports_to_try = [port]
    for alt in [2525, 587, 465]:
        if alt not in ports_to_try:
            ports_to_try.append(alt)

    last_error = None
    for target_port in ports_to_try:
        server = None
        try:
            _log(f"Intentando conexión con {resolved_ip}:{target_port} (SNI: {host})...")
            if target_port == 465:
                # SSL Directo
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(resolved_ip, target_port, timeout=12, context=context)
                # Enviar EHLO con el hostname original
                server.ehlo(host)
            else:
                # STARTTLS (puerto 587 o similar)
                server = smtplib.SMTP(resolved_ip, target_port, timeout=12)
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
    1. Notificación al cliente comprador con su clave y comprobante PDF.
    2. Notificación interna al equipo/administrador (contacto@creditob2b.cl) avisando nueva suscripción/compra.
    """
    cfg = get_smtp_config()
    if not cfg['is_configured']:
        print("[SMTP Info] SMTP no configurado en variables de entorno. Se omite envío de correo.")
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

        # Conexión SMTP compartida para ambos envíos
        server = None
        try:
            server = _connect_smtp_robust(cfg['host'], cfg['port'], cfg['user'], cfg['password'])

            # 1. Enviar correo a los clientes/usuarios (soporta múltiples separados por coma)
            client_list = [e.strip() for e in recipient_email.split(',') if e.strip() and '@' in e]
            for c_mail in client_list:
                try:
                    msg_user = MIMEMultipart('mixed')
                    msg_user['Subject'] = f"Confirmación de Compra y Clave de Acceso - Orden {order_id}"
                    msg_user['From'] = f"{cfg['from_name']} <{cfg['user']}>"
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

                    server.sendmail(cfg['user'], [c_mail], msg_user.as_string())
                    print(f"[SMTP Success] Notificación enviada al cliente {c_mail} para orden {order_id}")
                except Exception as user_err:
                    print(f"[SMTP Error] Falló envío al cliente {c_mail}: {str(user_err)}")

            # 2. Enviar notificación interna a administración (soporta múltiples separados por coma)
            admin_list = [a.strip() for a in admin_email.split(',') if a.strip() and '@' in a]
            for a_mail in admin_list:
                try:
                    msg_admin = MIMEMultipart('mixed')
                    msg_admin['Subject'] = f"🔔 [Nueva Suscripción/Compra] {receptor_nombre} - Orden {order_id} ({monto_fmt} CLP)"
                    msg_admin['From'] = f"{cfg['from_name']} <{cfg['user']}>"
                    msg_admin['To'] = a_mail

                    html_admin = f"""
                    <!DOCTYPE html>
                    <html lang="es">
                    <head>
                      <meta charset="utf-8">
                      <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; color: #0f172a; padding: 20px; }}
                        .box {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #cbd5e1; padding: 24px; }}
                        h2 {{ margin-top: 0; color: #0b3d91; font-size: 18px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }}
                        td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
                        td.lbl {{ font-weight: 700; color: #475569; width: 35%; }}
                        td.txt {{ color: #0f172a; }}
                      </style>
                    </head>
                    <body>
                      <div class="box">
                        <h2>🎉 Nueva Compra Aprobada en CréditoB2B</h2>
                        <p style="font-size: 13px; color: #334155;">Se ha registrado y validado una nueva suscripción/compra de paquetes de informes:</p>
                        <table>
                          <tr><td class="lbl">N° Orden</td><td class="txt"><strong>{order_id}</strong></td></tr>
                          <tr><td class="lbl">Plan</td><td class="txt">{plan_tipo.upper()} ({creditos_totales} informes)</td></tr>
                          <tr><td class="lbl">Monto Pagado</td><td class="txt"><strong>{monto_fmt} CLP</strong></td></tr>
                          <tr><td class="lbl">Cliente / Razón Social</td><td class="txt"><strong>{receptor_nombre}</strong></td></tr>
                          <tr><td class="lbl">RUT Comprador</td><td class="txt">{receptor_rut}</td></tr>
                          <tr><td class="lbl">Giro</td><td class="txt">{receptor_giro}</td></tr>
                          <tr><td class="lbl">Dirección</td><td class="txt">{receptor_direccion}</td></tr>
                          <tr><td class="lbl">Email Comprador</td><td class="txt">{recipient_email}</td></tr>
                          <tr><td class="lbl">Token Asignado</td><td class="txt"><code>{token_acceso}</code></td></tr>
                        </table>
                        <p style="font-size: 12px; color: #64748b; margin-top: 18px;">
                          Se adjunta el Comprobante Comercial PDF para respaldo administrativo.
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

                    server.sendmail(cfg['user'], [a_mail], msg_admin.as_string())
                    print(f"[SMTP Success] Notificación administrativa enviada a {a_mail} para orden {order_id}")
                except Exception as admin_err:
                    print(f"[SMTP Error] Falló envío a administración {a_mail}: {str(admin_err)}")

        except Exception as e:
            print(f"[SMTP Error] Falló conexión con servidor SMTP: {str(e)}")
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    # Ejecutar en segundo plano
    threading.Thread(target=_worker, daemon=True).start()
    return True

def send_purchase_confirmation_sync(order_record, pdf_bytes=None):
    """Ejecución síncrona que retorna logs detallados y errores explícitos para diagnóstico."""
    cfg = get_smtp_config()
    logs = []
    if not cfg['is_configured']:
        return {'success': False, 'error': 'SMTP_HOST, SMTP_USER o SMTP_PASSWORD no configurados en entorno.'}

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

    server = None
    try:
        def log_cb(m):
            logs.append(m)
        server = _connect_smtp_robust(cfg['host'], cfg['port'], cfg['user'], cfg['password'], log_callback=log_cb)

        # Enviar a clientes
        client_list = [e.strip() for e in recipient_email.split(',') if e.strip() and '@' in e]
        for c_mail in client_list:
            msg_user = MIMEMultipart('mixed')
            msg_user['Subject'] = f"Confirmación de Compra y Clave de Acceso - Orden {order_id}"
            msg_user['From'] = f"{cfg['from_name']} <{cfg['user']}>"
            msg_user['To'] = c_mail
            msg_user.attach(MIMEText(f"<p>Hola {receptor_nombre}, tu clave es <b>{token_acceso}</b></p><p><a href='{app_access_url}'>Ingresar</a></p>", 'html', 'utf-8'))
            if pdf_bytes:
                part = MIMEApplication(pdf_bytes, _subtype="pdf")
                part.add_header('Content-Disposition', 'attachment', filename=f"Comprobante_Pago_{order_id}.pdf")
                msg_user.attach(part)
            server.sendmail(cfg['user'], [c_mail], msg_user.as_string())
            logs.append(f"Despachado a cliente: {c_mail}")

        # Enviar a admin
        admin_list = [a.strip() for a in admin_email.split(',') if a.strip() and '@' in a]
        for a_mail in admin_list:
            msg_admin = MIMEMultipart('mixed')
            msg_admin['Subject'] = f"🔔 [Nueva Suscripción] {receptor_nombre} - Orden {order_id}"
            msg_admin['From'] = f"{cfg['from_name']} <{cfg['user']}>"
            msg_admin['To'] = a_mail
            msg_admin.attach(MIMEText(f"<p>Nueva orden {order_id} por {monto_fmt} CLP para {receptor_nombre}</p>", 'html', 'utf-8'))
            server.sendmail(cfg['user'], [a_mail], msg_admin.as_string())
            logs.append(f"Despachado a admin: {a_mail}")

        return {'success': True, 'logs': logs}
    except Exception as e:
        logs.append(f"Excepción SMTP: {str(e)}")
        return {'success': False, 'logs': logs, 'error': str(e)}
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


