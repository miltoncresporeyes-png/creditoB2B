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

def send_purchase_confirmation_email(order_record, pdf_bytes=None):
    """
    Despacha en un hilo secundario (sin bloquear la respuesta HTTP) el correo de
    confirmación con token/clave de acceso y comprobante PDF adjunto.
    """
    cfg = get_smtp_config()
    if not cfg['is_configured']:
        print("[SMTP Info] SMTP_HOST, SMTP_USER o SMTP_PASSWORD no configurados. Se omite envío de correo automático.")
        return False

    billing = order_record.get('billing_data', {}) or {}
    recipient_email = billing.get('email') or billing.get('correo') or ''
    recipient_email = recipient_email.strip()
    
    if not recipient_email or '@' not in recipient_email:
        print(f"[SMTP Warning] Orden {order_record.get('order_id')} no posee un correo electrónico válido para notificación.")
        return False

    def _worker():
        try:
            order_id = order_record.get('order_id', '')
            token_acceso = order_record.get('token_acceso', '')
            plan_tipo = order_record.get('plan_tipo', 'pack_3')
            creditos_totales = order_record.get('creditos_totales', 1)
            monto = int(order_record.get('monto', 0))
            monto_fmt = f"${monto:,}".replace(',', '.')
            receptor_nombre = billing.get('razon_social') or billing.get('nombre') or 'Cliente'
            base_url = os.environ.get('BASE_PUBLIC_URL', 'https://creditob2b-production.up.railway.app').rstrip('/')
            app_access_url = f"{base_url}/app?credit_token={token_acceso}" if token_acceso else f"{base_url}/app"

            msg = MIMEMultipart('mixed')
            msg['Subject'] = f"Confirmación de Compra y Clave de Acceso - Orden {order_id}"
            msg['From'] = f"{cfg['from_name']} <{cfg['user']}>"
            msg['To'] = recipient_email

            html_content = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
              <meta charset="utf-8">
              <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
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
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            # Adjuntar comprobante PDF si está disponible
            if pdf_bytes:
                part = MIMEApplication(pdf_bytes, _subtype="pdf")
                part.add_header('Content-Disposition', 'attachment', filename=f"Comprobante_Pago_{order_id}.pdf")
                msg.attach(part)

            # Conexión SMTP
            if cfg['port'] == 465:
                server = smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=15)
            else:
                server = smtplib.SMTP(cfg['host'], cfg['port'], timeout=15)
                server.starttls()

            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], [recipient_email], msg.as_string())
            server.quit()
            print(f"[SMTP Success] Correo de confirmación y comprobante enviado exitosamente a {recipient_email} para orden {order_id}")
        except Exception as e:
            print(f"[SMTP Error] Falló el despacho de correo para la orden {order_record.get('order_id')}: {str(e)}")

    # Ejecutar en segundo plano para no demorar el webhook ni el redirect de usuario
    threading.Thread(target=_worker, daemon=True).start()
    return True
