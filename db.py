import os
import json
import sqlite3
from datetime import datetime

# Conector con soporte dual PostgreSQL (DATABASE_URL) y fallback SQLite
DB_PATH = os.path.join(os.path.dirname(__file__), 'credit_evaluations.db')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if DATABASE_URL and (DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            # Adaptar prefijo antiguo de postgres:// a postgresql:// si es necesario
            pg_url = DATABASE_URL
            if pg_url.startswith('postgres://'):
                pg_url = pg_url.replace('postgres://', 'postgresql://', 1)
            conn = psycopg2.connect(pg_url, cursor_factory=RealDictCursor)
            conn.autocommit = False
            return conn
        except Exception:
            pass
    # Fallback SQLite local
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def is_postgres(conn):
    return hasattr(conn, 'pgconn') or 'psycopg2' in str(type(conn))

def init_db():
    conn = get_db()
    cur = conn.cursor()
    # Tabla de evaluaciones
    cur.execute('''
    CREATE TABLE IF NOT EXISTS evaluaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rut TEXT NOT NULL,
        razon_social TEXT,
        sector TEXT,
        analista TEXT,
        monto_solicitado REAL,
        plazo_solicitado INTEGER,
        score REAL,
        decision TEXT,
        limite_aprobado REAL,
        plazo_aprobado INTEGER,
        input_data TEXT NOT NULL,
        result_data TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_eval_rut ON evaluaciones(rut);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_eval_date ON evaluaciones(created_at);')

    # Tabla de transacciones de pago desacoplada de datos financieros
    cur.execute('''
    CREATE TABLE IF NOT EXISTS transacciones_pago (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE NOT NULL,
        plan_tipo TEXT NOT NULL,
        monto REAL NOT NULL,
        moneda TEXT DEFAULT 'CLP',
        estado TEXT NOT NULL DEFAULT 'PENDING',
        evaluacion_id INTEGER,
        token_acceso TEXT UNIQUE,
        proveedor TEXT DEFAULT 'SIMULATED_GATEWAY',
        billing_data TEXT,
        creditos_totales INTEGER DEFAULT 1,
        creditos_restantes INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paid_at TIMESTAMP,
        FOREIGN KEY (evaluacion_id) REFERENCES evaluaciones(id)
    );
    ''')
    # Migraciones livianas
    try:
        cur.execute("ALTER TABLE transacciones_pago ADD COLUMN billing_data TEXT;")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE transacciones_pago ADD COLUMN creditos_totales INTEGER DEFAULT 1;")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE transacciones_pago ADD COLUMN creditos_restantes INTEGER DEFAULT 1;")
    except Exception:
        pass

    cur.execute('CREATE INDEX IF NOT EXISTS idx_trans_order ON transacciones_pago(order_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_trans_token ON transacciones_pago(token_acceso);')
    conn.commit()
    conn.close()

def create_payment_order(order_id, plan_tipo, monto, evaluacion_id=None, billing_data=None, creditos=1):
    conn = get_db()
    cur = conn.cursor()
    b_json = json.dumps(billing_data or {}, ensure_ascii=False)
    cur.execute('''
    INSERT INTO transacciones_pago (order_id, plan_tipo, monto, estado, evaluacion_id, billing_data, creditos_totales, creditos_restantes)
    VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?)
    ''', (order_id, plan_tipo, monto, evaluacion_id, b_json, creditos, creditos))
    conn.commit()
    conn.close()
    return order_id

def get_payment_order(order_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM transacciones_pago WHERE order_id = ?', (order_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get('billing_data'):
        try:
            d['billing_data'] = json.loads(d['billing_data'])
        except Exception:
            d['billing_data'] = {}
    else:
        d['billing_data'] = {}
    return d

def update_payment_billing_data(order_id, billing_data):
    conn = get_db()
    cur = conn.cursor()
    b_json = json.dumps(billing_data or {}, ensure_ascii=False)
    cur.execute('UPDATE transacciones_pago SET billing_data = ? WHERE order_id = ?', (b_json, order_id))
    conn.commit()
    conn.close()

def verify_and_complete_payment(order_id, token_acceso):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM transacciones_pago WHERE order_id = ?', (order_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None, "Orden no encontrada"
    if row['estado'] == 'APPROVED':
        conn.close()
        d = dict(row)
        try:
            d['billing_data'] = json.loads(d.get('billing_data') or '{}')
        except Exception:
            d['billing_data'] = {}
        return d, "Pago previamente confirmado"
    
    cur.execute('''
    UPDATE transacciones_pago
    SET estado = 'APPROVED', token_acceso = ?, paid_at = CURRENT_TIMESTAMP
    WHERE order_id = ?
    ''', (token_acceso, order_id))
    conn.commit()
    cur.execute('SELECT * FROM transacciones_pago WHERE order_id = ?', (order_id,))
    updated_row = dict(cur.fetchone())
    conn.close()
    try:
        updated_row['billing_data'] = json.loads(updated_row.get('billing_data') or '{}')
    except Exception:
        updated_row['billing_data'] = {}
    return updated_row, None

def check_payment_access(token_acceso):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM transacciones_pago WHERE token_acceso = ? AND estado = "APPROVED"', (token_acceso,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_order_by_token(token):
    """Busca una orden aprobada exclusivamente mediante su token de acceso secreto."""
    if not token:
        return None
    tok = str(token).strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
    SELECT * FROM transacciones_pago 
    WHERE token_acceso = ? AND estado = "APPROVED"
    ''', (tok,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d['billing_data'] = json.loads(d.get('billing_data') or '{}')
    except Exception:
        d['billing_data'] = {}
    return d

def get_order_by_token_or_order_id(identifier):
    """Búsqueda compatible que solo admite token_acceso válido para autorizaciones."""
    return get_order_by_token(identifier)

def consume_credit(token, eval_id=None):
    """Consume 1 crédito de forma atómica e idempotente validando estrictamente el token_acceso.
    Si la orden ya fue vinculada a este eval_id, no vuelve a descontar créditos por recargas."""
    if not token:
        return False, "Token de acceso requerido"
    tok = str(token).strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
    SELECT * FROM transacciones_pago 
    WHERE token_acceso = ? AND estado = "APPROVED"
    ''', (tok,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Token de acceso inválido o transacción no aprobada"
    
    row_dict = dict(row)
    # Idempotencia: si ya evaluó este mismo eval_id, permitir acceso sin descontar crédito adicional
    if eval_id and row_dict.get('evaluacion_id') == eval_id:
        conn.close()
        return True, "Acceso autorizado para este expediente"
        
    creditos = row_dict.get('creditos_restantes', 0)
    if creditos <= 0:
        conn.close()
        return False, "No quedan créditos disponibles en este paquete"
        
    # Descontar crédito de forma atómica
    cur.execute('''
    UPDATE transacciones_pago
    SET creditos_restantes = creditos_restantes - 1,
        evaluacion_id = COALESCE(?, evaluacion_id)
    WHERE id = ? AND creditos_restantes > 0
    ''', (eval_id, row_dict['id']))
    conn.commit()
    conn.close()
    return True, "Crédito consumido exitosamente"

def save_evaluation(input_data, result_data):
    conn = get_db()
    cur = conn.cursor()
    rut = input_data.get('rut', '')
    razon = input_data.get('razonSocial', '')
    sector = input_data.get('sector', '')
    analista = input_data.get('analista', '')
    monto_sol = float(input_data.get('montoSolicitado', 0) or 0)
    plazo_sol = int(input_data.get('plazo', 30) or 30)
    score = float(result_data.get('score', 0) or 0)
    decision = result_data.get('status', {}).get('label', '')
    lim_aprobado = float(result_data.get('limits', {}).get('approved', 0) or 0)
    plazo_aprobado = int(result_data.get('term', {}).get('approved', 0) or 0)
    
    cur.execute('''
    INSERT INTO evaluaciones (
        rut, razon_social, sector, analista, monto_solicitado, plazo_solicitado,
        score, decision, limite_aprobado, plazo_aprobado, input_data, result_data
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        rut, razon, sector, analista, monto_sol, plazo_sol,
        score, decision, lim_aprobado, plazo_aprobado,
        json.dumps(input_data, ensure_ascii=False),
        json.dumps(result_data, ensure_ascii=False)
    ))
    eval_id = cur.lastrowid
    conn.commit()
    conn.close()
    return eval_id

def list_evaluations(limit=50):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
    SELECT id, rut, razon_social, analista, monto_solicitado, score, decision, limite_aprobado, plazo_aprobado, created_at
    FROM evaluaciones ORDER BY id DESC LIMIT ?
    ''', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_evaluation(eval_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM evaluaciones WHERE id = ?', (eval_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['input_data'] = json.loads(d['input_data'])
    d['result_data'] = json.loads(d['result_data'])
    return d

init_db()
