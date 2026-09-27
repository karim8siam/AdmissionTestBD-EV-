import http.server
import json
import os
import sys
import re
import uuid
import decimal
import urllib.parse
import hashlib
import hmac
from datetime import datetime, date

# Neon PostgreSQL connection URL
NEON_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_okZQmgr0e1fv@ep-frosty-grass-b5eq2vv9-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

# 4-Step Security Credentials for Admin Panel
ADMIN_MASTER_PASSWORD_1 = os.environ.get("ADMIN_MASTER_PASSWORD_1", "4990OrpU4990!HelloWorld123")
ADMIN_SECONDARY_PASSWORD_2 = os.environ.get("ADMIN_SECONDARY_PASSWORD_2", "alonbiysA1")
ADMIN_SECURITY_PIN = os.environ.get("ADMIN_SECURITY_PIN", "499011")
ADMIN_SECURITY_WORD = os.environ.get("ADMIN_SECURITY_WORD", "barca")

# Secure Admin Session Token
ADMIN_TOKEN = hashlib.sha256(
    f"{ADMIN_MASTER_PASSWORD_1}:{ADMIN_SECONDARY_PASSWORD_2}:{ADMIN_SECURITY_PIN}:{ADMIN_SECURITY_WORD}".encode('utf-8')
).hexdigest()

# Root directory of the repository
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lazy schema check
_SCHEMA_ENSURED = False

def get_db_connection():
    """Connects to Neon PostgreSQL pooler."""
    import psycopg2
    conn = psycopg2.connect(NEON_URL, connect_timeout=10)
    return conn

def hash_password(password: str) -> str:
    salt = "admission_test_bd_secure_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def verify_password(password: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), stored_hash)

def ensure_database_schema(conn):
    """Ensures that all needed tables and indexes exist on the database."""
    global _SCHEMA_ENSURED
    if _SCHEMA_ENSURED:
        return
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                student_id VARCHAR(64) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS students (
                student_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                roll_number VARCHAR(64),
                target_college VARCHAR(255),
                session VARCHAR(32),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS exam_submissions (
                id SERIAL PRIMARY KEY,
                submission_code VARCHAR(64) UNIQUE NOT NULL,
                student_id VARCHAR(64) NOT NULL,
                student_name VARCHAR(255) NOT NULL,
                target_college VARCHAR(255),
                session VARCHAR(32) NOT NULL,
                test_id INTEGER NOT NULL,
                test_code VARCHAR(64) NOT NULL,
                subject_mode VARCHAR(64) NOT NULL,
                total_questions INTEGER NOT NULL,
                correct_count INTEGER NOT NULL,
                wrong_count INTEGER NOT NULL,
                unanswered_count INTEGER NOT NULL,
                score NUMERIC(6, 2) NOT NULL,
                percentage NUMERIC(6, 2) NOT NULL,
                time_taken_seconds INTEGER NOT NULL,
                submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_submissions_rank ON exam_submissions (test_id, subject_mode, session, score DESC, time_taken_seconds ASC);
            CREATE INDEX IF NOT EXISTS idx_submissions_alltime ON exam_submissions (test_id, subject_mode, score DESC, time_taken_seconds ASC);
            CREATE TABLE IF NOT EXISTS received_sms_logs (
                id SERIAL PRIMARY KEY,
                sender VARCHAR(32) NOT NULL,
                raw_message TEXT NOT NULL,
                parsed_amount NUMERIC(10, 2),
                parsed_sender VARCHAR(32),
                parsed_trx_id VARCHAR(64) UNIQUE,
                is_claimed BOOLEAN DEFAULT FALSE,
                claimed_by_student_id VARCHAR(64),
                received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS student_enrollments (
                id SERIAL PRIMARY KEY,
                student_id VARCHAR(64) NOT NULL,
                student_name VARCHAR(255),
                student_email VARCHAR(255),
                package_type VARCHAR(32) NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                sender_number VARCHAR(32) NOT NULL,
                trx_id VARCHAR(64) UNIQUE NOT NULL,
                status VARCHAR(32) DEFAULT 'verified',
                enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE student_enrollments ADD COLUMN IF NOT EXISTS package_type VARCHAR(32) DEFAULT 'medical';
            ALTER TABLE student_enrollments ADD COLUMN IF NOT EXISTS student_email VARCHAR(255);
            ALTER TABLE student_enrollments ADD COLUMN IF NOT EXISTS sender_number VARCHAR(32);
            ALTER TABLE student_enrollments ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'verified';
            ALTER TABLE received_sms_logs ADD COLUMN IF NOT EXISTS is_claimed BOOLEAN DEFAULT FALSE;
            ALTER TABLE received_sms_logs ADD COLUMN IF NOT EXISTS claimed_by_student_id VARCHAR(64);
        """)
        conn.commit()
        _SCHEMA_ENSURED = True
    except Exception as e:
        print(f"[WARN] Failed to ensure schema: {e}")

def parse_bkash_sms(text):
    """
    Parses official bKash incoming SMS for payment verification.
    Supports English & Bengali SMS, variations in TrxID / TxnID / Trx ID,
    +88 phone numbers, and flexible amount placements.
    """
    if not text:
        return None

    clean_text = ' '.join(str(text).split())

    # 1. TrxID extraction (TrxID, Trx ID, TxnID, TxID, Transaction ID, ট্রানজেকশন আইডি)
    trx_id = None
    trx_match = re.search(
        r'(?:Trx\s*ID|Txn\s*ID|TxID|Transaction\s*ID|ট্রানজেকশন\s*আইডি)[:\s]+([A-Za-z0-9]{6,20})',
        clean_text,
        re.IGNORECASE
    )
    if trx_match:
        trx_id = trx_match.group(1).strip().strip('.!,:;').upper()

    # 2. Amount extraction
    amount = None
    amt_patterns = [
        r'(?:received|recharge|পেয়েছেন|পাওয়া\s*গেছে)\s+(?:tk\.?|bdt|টাকা|৳)?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
        r'(?:tk\.?|bdt|টাকা|৳)\s*([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:received|recharge|পেয়েছেন)?',
        r'([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:tk\.?|bdt|টাকা|৳)\s*(?:received|recharge|পেয়েছেন)?'
    ]
    for pat in amt_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1).replace(',', ''))
                if val > 0:
                    amount = val
                    break
            except ValueError:
                pass

    # 3. Sender mobile number extraction
    sender = None
    sender_patterns = [
        r'(?:from|থেকে)\s*(?:\+?88)?\s*(01[3-9]\d{8})',
        r'(?:\+?88)?\s*(01[3-9]\d{8})\s*(?:থেকে|from)',
        r'(?:\+?88)?(01[3-9]\d{8})'
    ]
    for pat in sender_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            sender = m.group(1)
            break

    if trx_id:
        return {
            "amount": amount or 0.0,
            "sender": sender or "unknown",
            "trx_id": trx_id,
            "raw": clean_text
        }
    return None



class handler(http.server.BaseHTTPRequestHandler):
    """Vercel Serverless Function & Full-Stack Handler."""

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, HEAD')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def get_route_path(self):
        """Extracts the actual route path from incoming request URL, supporting Vercel __route rewrite parameter."""
        parsed = urllib.parse.urlparse(self.path or '/')
        query = urllib.parse.parse_qs(parsed.query)

        if '__route' in query:
            route = query['__route'][0]
            clean_route = urllib.parse.urlparse(route).path.rstrip('/') or '/'
            clean_query = {k: v for k, v in query.items() if k != '__route'}
            return clean_route, clean_query

        raw_path = self.headers.get('x-forwarded-uri') or parsed.path or '/'
        path = urllib.parse.urlparse(raw_path).path.rstrip('/') or '/'
        return path, query

    def check_admin_auth(self, query):
        """Validates admin token/password from Authorization header or query parameter."""
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ', 1)[1].strip()
            if token in (ADMIN_TOKEN, ADMIN_MASTER_PASSWORD_1):
                return True
        if query.get('admin_token', [''])[0] in (ADMIN_TOKEN, ADMIN_MASTER_PASSWORD_1):
            return True
        return False

    def serve_static_file(self, file_path, content_type):
        """Streams a static file (HTML, JSON, Images) with correct caching and headers."""
        try:
            if not os.path.isfile(file_path):
                self.send_json_response({"status": "error", "message": f"File not found: {file_path}"}, status=404)
                return
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            if content_type.startswith('text/html'):
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
            else:
                self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_json_response({"status": "error", "message": str(e)}, status=500)

    def do_GET(self):
        path, query = self.get_route_path()

        # 1. Root & HTML Page
        if path in ('', '/', '/index', '/index.html'):
            html_path = os.path.join(BASE_DIR, 'index.html')
            self.serve_static_file(html_path, 'text/html; charset=utf-8')
            return

        # 2. Static Assets & Images (Support both /web/assets/ and /assets/)
        if path.startswith('/web/assets/') or path.startswith('/assets/'):
            clean_rel = path.lstrip('/')
            file_path = os.path.join(BASE_DIR, clean_rel)
            if not os.path.isfile(file_path):
                if path.startswith('/assets/'):
                    file_path = os.path.join(BASE_DIR, 'web', clean_rel)
                elif path.startswith('/web/assets/'):
                    file_path = os.path.join(BASE_DIR, clean_rel.replace('web/', ''))
            if os.path.isfile(file_path):
                ctype = 'image/jpeg' if file_path.lower().endswith(('.jpg', '.jpeg')) else ('image/png' if file_path.lower().endswith('.png') else 'application/octet-stream')
                self.serve_static_file(file_path, ctype)
                return
            else:
                self.send_json_response({"status": "error", "message": f"Asset not found: {file_path}"}, status=404)
                return

        # 3. Data Stores (JSON test banks)
        if path.startswith('/data/'):
            clean_rel = path.lstrip('/')
            file_path = os.path.join(BASE_DIR, clean_rel)
            self.serve_static_file(file_path, 'application/json; charset=utf-8')
            return

        # 4. API Endpoints
        if path in ('/api', '/api/health', '/api/index'):
            self.send_json_response({
                "status": "healthy",
                "service": "Admission Test BD Cloud API",
                "database": "Neon PostgreSQL",
                "timestamp": datetime.now().isoformat()
            })
            return

        if path == '/api/payment/sms-webhook':
            # Check if this GET request contains SMS parameters (e.g. from SMS forwarder apps)
            has_sms_param = any(k.lower() in ('message', 'text', 'body', 'msg', 'content', 'sms', 'm', 'raw', 'data') for k in query.keys())
            if has_sms_param or ('sender' in query or 'from' in query or 's' in query or 'phone' in query or 'address' in query):
                flattened_query = {k: (v[0] if isinstance(v, list) and v else v) for k, v in query.items()}
                self.handle_sms_webhook(flattened_query)
                return

            self.send_json_response({
                "error_code": 0,
                "status": "active",
                "message": "bKash SMS Webhook endpoint is active and listening for POST & GET requests.",
                "webhook_target": "/api/payment/sms-webhook"
            })
            return


        if path == '/api/payment/status':
            self.handle_payment_status(query)
            return

        if path == '/api/leaderboard':
            self.handle_get_leaderboard(query)
            return

        if path == '/api/stats':
            self.handle_get_stats()
            return

        # Admin: Get All Payments & Logs
        if path == '/api/admin/payments':
            if not self.check_admin_auth(query):
                self.send_json_response({"status": "error", "message": "Unauthorized admin access"}, status=401)
                return
            self.handle_admin_get_payments()
            return

        # Fallback for unknown web routes to index.html (SPA routing)
        if not path.startswith('/api/'):
            html_path = os.path.join(BASE_DIR, 'index.html')
            if os.path.exists(html_path):
                self.serve_static_file(html_path, 'text/html; charset=utf-8')
                return

        self.send_json_response({"status": "error", "message": f"Endpoint not found: {path}"}, status=404)

    def do_POST(self):
        path, query = self.get_route_path()

        content_length = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""

        try:
            try:
                data = json.loads(post_body) if post_body else {}
            except Exception:
                parsed_form = urllib.parse.parse_qs(post_body)
                data = {k: v[0] for k, v in parsed_form.items()}
        except Exception as e:
            self.send_json_response({"status": "error", "message": f"Invalid request body: {str(e)}"}, status=400)
            return

        # Auth Routes
        if path == '/api/auth/signup':
            self.handle_auth_signup(data)
            return

        if path == '/api/auth/login':
            self.handle_auth_login(data)
            return

        # Admin Routes
        if path == '/api/admin/login':
            self.handle_admin_login(data)
            return

        if path == '/api/admin/approve-payment':
            if not self.check_admin_auth(query) and data.get('admin_token') not in (ADMIN_TOKEN, ADMIN_MASTER_PASSWORD_1):
                self.send_json_response({"status": "error", "message": "Unauthorized admin access"}, status=401)
                return
            self.handle_admin_approve_payment(data)
            return

        if path == '/api/admin/reject-payment':
            if not self.check_admin_auth(query) and data.get('admin_token') not in (ADMIN_TOKEN, ADMIN_MASTER_PASSWORD_1):
                self.send_json_response({"status": "error", "message": "Unauthorized admin access"}, status=401)
                return
            self.handle_admin_reject_payment(data)
            return

        if path == '/api/admin/manual-enroll':
            if not self.check_admin_auth(query) and data.get('admin_token') not in (ADMIN_TOKEN, ADMIN_MASTER_PASSWORD_1):
                self.send_json_response({"status": "error", "message": "Unauthorized admin access"}, status=401)
                return
            self.handle_admin_manual_enroll(data)
            return

        # Payment & Exam Routes
        if path == '/api/payment/sms-webhook':
            webhook_data = {}
            if isinstance(data, dict):
                webhook_data = dict(data)
            has_known_key = any(k.lower() in ('message', 'text', 'msg', 'body', 'content', 'sms', 'm', 'sender', 'from', 's', 'phone', 'address') for k in webhook_data.keys())
            if not has_known_key and post_body:
                webhook_data['message'] = post_body.strip()
            if query:
                for qk, qv in query.items():
                    val = qv[0] if isinstance(qv, list) and qv else qv
                    if qk not in webhook_data or not webhook_data[qk]:
                        webhook_data[qk] = val
            self.handle_sms_webhook(webhook_data)
            return


        if path == '/api/payment/verify-trx':
            self.handle_verify_trx(data)
            return

        if path == '/api/submit-exam':
            self.handle_submit_exam(data)
            return

        self.send_json_response({"status": "error", "message": f"POST endpoint not found: {path}"}, status=404)

    def send_json_response(self, data, status=200):
        def default_serializer(o):
            if hasattr(o, 'isoformat'):
                return o.isoformat()
            if isinstance(o, decimal.Decimal):
                return float(o)
            return str(o)

        response_bytes = json.dumps(data, ensure_ascii=False, default=default_serializer).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.end_headers()
        self.wfile.write(response_bytes)

    # ================= AUTH HANDLERS =================
    def handle_auth_signup(self, data):
        email = (data.get('email') or '').strip().lower()
        password = (data.get('password') or '').strip()
        name = (data.get('name') or 'Student').strip() or 'Student'

        if not email or '@' not in email or '.' not in email:
            self.send_json_response({"success": False, "message": "Please enter a valid email address."}, status=400)
            return
        if len(password) < 4:
            self.send_json_response({"success": False, "message": "Password must be at least 4 characters long."}, status=400)
            return

        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            import psycopg2.extras
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Check existing email
            c.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if c.fetchone():
                self.send_json_response({"success": False, "message": "An account already exists with this email. Please log in."}, status=400)
                return

            student_id = f"STU-{uuid.uuid4().hex[:8].upper()}"
            pass_hash = hash_password(password)

            c.execute("""
                INSERT INTO users (student_id, email, password_hash, name)
                VALUES (%s, %s, %s, %s);
            """, (student_id, email, pass_hash, name))

            c.execute("""
                INSERT INTO students (student_id, name, target_college, session)
                VALUES (%s, %s, 'National Merit Leaderboard', '2025-26')
                ON CONFLICT (student_id) DO NOTHING;
            """, (student_id, name))

            conn.commit()
        except Exception as e:
            self.send_json_response({"success": False, "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        self.send_json_response({
            "success": True,
            "student_id": student_id,
            "email": email,
            "name": name,
            "medical_enrolled": False,
            "versity_enrolled": False,
            "combo_enrolled": False,
            "enrollments": [],
            "message": "🎉 Account created successfully!"
        })

    def handle_auth_login(self, data):
        email = (data.get('email') or '').strip().lower()
        password = (data.get('password') or '').strip()

        if not email or not password:
            self.send_json_response({"success": False, "message": "Please provide both email and password."}, status=400)
            return

        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            import psycopg2.extras
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            c.execute("SELECT student_id, email, password_hash, name FROM users WHERE email = %s;", (email,))
            user = c.fetchone()
            if not user or not verify_password(password, user['password_hash']):
                self.send_json_response({"success": False, "message": "Incorrect email or password! Please try again."}, status=401)
                return

            # Fetch student's verified enrollments
            c.execute("""
                SELECT package_type, amount, sender_number, trx_id, status, enrolled_at
                FROM student_enrollments
                WHERE (student_id = %s OR student_email = %s) AND status = 'verified';
            """, (user['student_id'], email))
            rows = [dict(r) for r in c.fetchall()]

            packages = [r['package_type'].lower() for r in rows]
            combo = 'combo' in packages
            med = combo or ('medical' in packages)
            var = combo or ('versity' in packages)

        except Exception as e:
            self.send_json_response({"success": False, "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        self.send_json_response({
            "success": True,
            "student_id": user['student_id'],
            "email": user['email'],
            "name": user['name'] or 'Student',
            "medical_enrolled": med,
            "versity_enrolled": var,
            "combo_enrolled": combo,
            "enrollments": rows,
            "message": "Login successful! Profile and enrollments synchronized."
        })

    # ================= ADMIN HANDLERS =================
    def handle_admin_login(self, data):
        p1 = (data.get('master_password_1') or data.get('master_password') or data.get('password') or '').strip()
        p2 = (data.get('secondary_password_2') or data.get('secondary_password') or '').strip()
        pin = (data.get('security_pin') or '').strip()
        word = (data.get('security_word') or '').strip().lower()

        # Step 1: Master Password 1
        if not hmac.compare_digest(p1, ADMIN_MASTER_PASSWORD_1):
            self.send_json_response({"success": False, "step": 1, "message": "Step 1 Failed: Master Password 1 is incorrect!"}, status=401)
            return

        # Step 2: Secondary Password 2
        if not hmac.compare_digest(p2, ADMIN_SECONDARY_PASSWORD_2):
            self.send_json_response({"success": False, "step": 2, "message": "Step 2 Failed: Secondary Password 2 is incorrect!"}, status=401)
            return

        # Step 3: Security PIN
        if not hmac.compare_digest(pin, ADMIN_SECURITY_PIN):
            self.send_json_response({"success": False, "step": 3, "message": "Step 3 Failed: Security PIN is incorrect!"}, status=401)
            return

        # Step 4: Security Secret Word
        if not hmac.compare_digest(word, ADMIN_SECURITY_WORD.lower()):
            self.send_json_response({"success": False, "step": 4, "message": "Step 4 Failed: Security Secret Word is incorrect!"}, status=401)
            return

        # All 4 Steps Successfully Verified
        self.send_json_response({
            "success": True,
            "token": ADMIN_TOKEN,
            "message": "4-Step Security Verification Passed! Welcome to the Admin Control Panel."
        })

    def handle_admin_get_payments(self):
        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            import psycopg2.extras
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # 1. Enrollments list
            c.execute("""
                SELECT id, student_id, student_name, student_email,
                       package_type, package_type AS package,
                       amount, sender_number, trx_id, status,
                       enrolled_at, enrolled_at AS created_at
                FROM student_enrollments
                ORDER BY enrolled_at DESC
                LIMIT 100;
            """)
            enrollments = [dict(r) for r in c.fetchall()]

            # 2. Raw SMS logs
            c.execute("""
                SELECT id, sender,
                       raw_message, raw_message AS raw_sms,
                       parsed_amount, parsed_amount AS amount,
                       parsed_sender,
                       parsed_trx_id, parsed_trx_id AS trx_id,
                       is_claimed, claimed_by_student_id, claimed_by_student_id AS matched_claim_id,
                       received_at
                FROM received_sms_logs
                ORDER BY received_at DESC
                LIMIT 100;
            """)
            sms_logs = [dict(r) for r in c.fetchall()]


            # 3. Metrics
            c.execute("SELECT COALESCE(SUM(amount), 0) FROM student_enrollments WHERE status = 'verified';")
            total_rev = c.fetchone()['coalesce']
            c.execute("SELECT COUNT(*) FROM student_enrollments WHERE status = 'verified';")
            verified_cnt = c.fetchone()['count']
            c.execute("SELECT COUNT(*) FROM student_enrollments WHERE status = 'pending';")
            pending_cnt = c.fetchone()['count']
            c.execute("SELECT COUNT(*) FROM exam_submissions;")
            total_exams = c.fetchone()['count']

        except Exception as e:
            self.send_json_response({"status": "error", "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        self.send_json_response({
            "success": True,
            "metrics": {
                "total_revenue": float(total_rev),
                "verified_students": verified_cnt,
                "pending_claims": pending_cnt,
                "total_exams": total_exams
            },
            "enrollments": enrollments,
            "claims": enrollments,
            "sms_logs": sms_logs
        })

    def handle_admin_approve_payment(self, data):
        trx_id = (data.get('trx_id') or '').strip().upper()
        enrollment_id = data.get('enrollment_id') or data.get('claim_id')
        package_override = (data.get('package') or data.get('package_type') or '').strip().lower()

        if not trx_id and not enrollment_id:
            self.send_json_response({"success": False, "message": "TrxID or ID is required."}, status=400)
            return

        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            import psycopg2.extras
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            if enrollment_id:
                if package_override in ('medical', 'versity', 'combo'):
                    c.execute("""
                        UPDATE student_enrollments 
                        SET status = 'verified', package_type = %s 
                        WHERE id = %s 
                        RETURNING trx_id, student_id, package_type;
                    """, (package_override, enrollment_id))
                else:
                    c.execute("""
                        UPDATE student_enrollments 
                        SET status = 'verified' 
                        WHERE id = %s 
                        RETURNING trx_id, student_id, package_type;
                    """, (enrollment_id,))
            else:
                if package_override in ('medical', 'versity', 'combo'):
                    c.execute("""
                        UPDATE student_enrollments 
                        SET status = 'verified', package_type = %s 
                        WHERE trx_id = %s 
                        RETURNING trx_id, student_id, package_type;
                    """, (package_override, trx_id))
                else:
                    c.execute("""
                        UPDATE student_enrollments 
                        SET status = 'verified' 
                        WHERE trx_id = %s 
                        RETURNING trx_id, student_id, package_type;
                    """, (trx_id,))
            row = c.fetchone()
            if not row:
                self.send_json_response({"success": False, "message": "Payment record not found."}, status=404)
                return

            # Mark matching SMS as claimed
            actual_trx = row['trx_id']
            c.execute("""
                UPDATE received_sms_logs
                SET is_claimed = TRUE, claimed_by_student_id = %s
                WHERE parsed_trx_id = %s;
            """, (row['student_id'], actual_trx))

            conn.commit()
        except Exception as e:
            self.send_json_response({"success": False, "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        pkg_label = "Combo (All Tests)" if row['package_type'] == 'combo' else ("Medical (95 Tests)" if row['package_type'] == 'medical' else "Varsity (95 Tests)")
        self.send_json_response({
            "success": True,
            "package": row['package_type'],
            "message": f"🎉 TrxID: {actual_trx} approved successfully! The student's '{pkg_label}' subscription has been unlocked."
        })

    def handle_admin_manual_enroll(self, data):
        identifier = (data.get('identifier') or data.get('student_id') or data.get('email') or '').strip()
        package = (data.get('package') or data.get('package_type') or 'combo').strip().lower()
        if package not in ('medical', 'versity', 'combo'):
            package = 'combo'
        trx_id = (data.get('trx_id') or f"MANUAL-{uuid.uuid4().hex[:8].upper()}").strip().upper()
        sender_number = (data.get('sender_number') or '01644265766').strip()
        student_name = (data.get('student_name') or 'Enrolled Student').strip()

        if not identifier:
            self.send_json_response({"success": False, "message": "Please provide student email, ID, or bKash mobile number."}, status=400)
            return

        is_email = '@' in identifier
        student_id = identifier if not is_email else f"stu_{uuid.uuid4().hex[:8]}"
        student_email = identifier if is_email else None
        amount = 799.0 if package == 'combo' else 499.0

        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            c = conn.cursor()
            c.execute("""
                INSERT INTO student_enrollments (student_id, student_name, student_email, package_type, amount, sender_number, trx_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'verified')
                ON CONFLICT (trx_id) DO UPDATE SET
                    status = 'verified',
                    package_type = EXCLUDED.package_type,
                    student_email = COALESCE(EXCLUDED.student_email, student_enrollments.student_email);
            """, (student_id, student_name, student_email, package, amount, sender_number, trx_id))
            conn.commit()
        except Exception as e:
            self.send_json_response({"success": False, "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        pkg_label = "Combo (All Tests)" if package == 'combo' else ("Medical (95 Tests)" if package == 'medical' else "Varsity (95 Tests)")
        self.send_json_response({
            "success": True,
            "message": f"🎉 Student '{identifier}' has been directly granted '{pkg_label}' subscription successfully!"
        })

    def handle_admin_reject_payment(self, data):
        trx_id = (data.get('trx_id') or '').strip().upper()
        enrollment_id = data.get('enrollment_id')

        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            c = conn.cursor()
            if enrollment_id:
                c.execute("UPDATE student_enrollments SET status = 'rejected' WHERE id = %s;", (enrollment_id,))
            else:
                c.execute("UPDATE student_enrollments SET status = 'rejected' WHERE trx_id = %s;", (trx_id,))
            conn.commit()
        except Exception as e:
            self.send_json_response({"success": False, "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        self.send_json_response({"success": True, "message": "Payment request has been rejected."})

    # ================= PAYMENT & EXAM HANDLERS =================
    def handle_payment_status(self, query):
        student_id = query.get('student_id', [''])[0].strip()
        email = query.get('email', [''])[0].strip().lower()

        if not student_id and not email:
            self.send_json_response({
                "student_id": "",
                "medical_enrolled": False,
                "versity_enrolled": False,
                "combo_enrolled": False,
                "has_pending": False,
                "enrollments": []
            })
            return

        where_clauses = []
        params = []
        if student_id:
            where_clauses.append("student_id = %s")
            params.append(student_id)
        if email:
            where_clauses.append("(student_email IS NOT NULL AND student_email != '' AND student_email = %s)")
            params.append(email)

        if not where_clauses:
            self.send_json_response({
                "student_id": "",
                "medical_enrolled": False,
                "versity_enrolled": False,
                "combo_enrolled": False,
                "has_pending": False,
                "pending_packages": [],
                "enrollments": []
            })
            return

        import psycopg2.extras
        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = f"""
                SELECT package_type, amount, sender_number, trx_id, status, enrolled_at
                FROM student_enrollments
                WHERE ({' OR '.join(where_clauses)});
            """
            c.execute(sql, tuple(params))
            rows = [dict(r) for r in c.fetchall()]
        except Exception as e:
            self.send_json_response({"status": "error", "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        verified_rows = [r for r in rows if r['status'] == 'verified']
        pending_rows = [r for r in rows if r['status'] == 'pending']

        packages = [r['package_type'].lower() for r in verified_rows]
        combo = 'combo' in packages
        med = combo or ('medical' in packages)
        var = combo or ('versity' in packages)

        self.send_json_response({
            "student_id": student_id,
            "medical_enrolled": med,
            "versity_enrolled": var,
            "combo_enrolled": combo,
            "has_pending": len(pending_rows) > 0,
            "pending_packages": [r['package_type'] for r in pending_rows],
            "enrollments": rows
        })

    def handle_sms_webhook(self, data):
        if not isinstance(data, dict):
            if isinstance(data, str):
                data = {"message": data}
            else:
                data = {}

        # Case-insensitive key lookup
        norm_data = {str(k).lower(): v for k, v in data.items()}

        sender = (
            norm_data.get('sender') or 
            norm_data.get('from') or 
            norm_data.get('phone') or 
            norm_data.get('address') or 
            norm_data.get('s') or 
            norm_data.get('c') or 
            norm_data.get('from_number') or 
            norm_data.get('mobile') or 
            'bKash'
        )
        if isinstance(sender, list) and sender:
            sender = sender[0]
        sender = str(sender).strip()

        raw_message = (
            norm_data.get('message') or 
            norm_data.get('text') or 
            norm_data.get('body') or 
            norm_data.get('msg') or 
            norm_data.get('content') or 
            norm_data.get('sms') or 
            norm_data.get('m') or 
            norm_data.get('payload') or 
            norm_data.get('raw') or 
            ''
        )
        if isinstance(raw_message, list) and raw_message:
            raw_message = raw_message[0]
        raw_message = str(raw_message).strip()

        # If still empty, check inside any nested dictionary or find text containing TrxID/received
        if not raw_message:
            for val in data.values():
                if isinstance(val, dict):
                    nested_msg = val.get('message') or val.get('text') or val.get('body') or val.get('msg')
                    if nested_msg:
                        raw_message = str(nested_msg).strip()
                        break
                elif isinstance(val, str) and any(keyword in val.lower() for keyword in ('trxid', 'trx id', 'received', 'bkash', 'bdt', 'tk')):
                    raw_message = val.strip()
                    break

        if not raw_message and data:
            raw_message = json.dumps(data, ensure_ascii=False)

        parsed = parse_bkash_sms(raw_message)

        matched_student = None
        auto_verified = False

        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            import psycopg2.extras
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            if parsed and parsed.get('trx_id'):
                trx_id = parsed['trx_id']
                amount = parsed.get('amount') or 0.0
                sender_mobile = parsed.get('sender') or sender

                # 1. Check if a student already submitted a pending claim for this TrxID
                c.execute("""
                    SELECT id, student_id, student_name, student_email, package_type, status
                    FROM student_enrollments
                    WHERE UPPER(trx_id) = %s;
                """, (trx_id,))
                existing_enrollment = c.fetchone()

                if existing_enrollment:
                    c.execute("""
                        UPDATE student_enrollments
                        SET status = 'verified'
                        WHERE id = %s;
                    """, (existing_enrollment['id'],))
                    matched_student = existing_enrollment['student_id']
                    auto_verified = True

                # 2. Insert into received_sms_logs
                c.execute("""
                    INSERT INTO received_sms_logs (sender, raw_message, parsed_amount, parsed_sender, parsed_trx_id, is_claimed, claimed_by_student_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (parsed_trx_id) DO UPDATE SET
                        raw_message = EXCLUDED.raw_message,
                        parsed_amount = EXCLUDED.parsed_amount,
                        parsed_sender = EXCLUDED.parsed_sender,
                        is_claimed = COALESCE(received_sms_logs.is_claimed, EXCLUDED.is_claimed),
                        claimed_by_student_id = COALESCE(received_sms_logs.claimed_by_student_id, EXCLUDED.claimed_by_student_id);
                """, (
                    sender, 
                    raw_message, 
                    amount, 
                    sender_mobile, 
                    trx_id, 
                    bool(matched_student), 
                    matched_student
                ))
            else:
                # Log raw message even if regex didn't extract a TrxID (for complete audit logging)
                c.execute("""
                    INSERT INTO received_sms_logs (sender, raw_message, parsed_amount, parsed_sender, parsed_trx_id, is_claimed)
                    VALUES (%s, %s, NULL, %s, NULL, FALSE);
                """, (sender, raw_message or "Unknown SMS content", sender))

            conn.commit()
        except Exception as e:
            print(f"[ERROR] sms-webhook error: {e}")
            self.send_json_response({
                "error_code": 1,
                "status": "error",
                "message": str(e)
            }, status=500)
            return
        finally:
            conn.close()

        # Returns error_code: 0 and status: "success" so Android SMS Forwarders record delivery as success
        self.send_json_response({
            "error_code": 0,
            "status": "success",
            "message": "bKash SMS successfully recorded and logged.",
            "auto_verified": auto_verified,
            "matched_student": matched_student,
            "parsed": parsed or {"raw": raw_message}
        })


    def handle_verify_trx(self, data):
        student_id = data.get('student_id', '').strip()
        student_name = data.get('student_name', 'Student').strip() or 'Student'
        student_email = (data.get('email') or data.get('student_email') or '').strip().lower()
        package = (data.get('package') or data.get('package_type') or 'medical').strip().lower()
        sender_number = data.get('sender_number', '').strip()
        trx_id = data.get('trx_id', '').strip().upper()

        if not student_id or not sender_number or not trx_id:
            self.send_json_response({
                "success": False,
                "message": "Please provide your bKash mobile number and TrxID accurately."
            }, status=400)
            return

        clean_num = re.sub(r'[\s\-+]', '', sender_number)
        if clean_num.startswith('880'):
            clean_num = clean_num[2:]
        if not re.match(r'^01[3-9]\d{8}$', clean_num):
            self.send_json_response({
                "success": False,
                "message": "Please enter a valid 11-digit bKash mobile number (e.g. 017xxxxxxxx)."
            }, status=400)
            return
        sender_number = clean_num

        if len(trx_id) < 6:
            self.send_json_response({
                "success": False,
                "message": "Please provide a valid Transaction ID (TrxID)."
            }, status=400)
            return

        pricing = {
            'medical': 499.0,
            'versity': 499.0,
            'combo': 799.0
        }
        required_price = pricing.get(package, 499.0)

        import psycopg2.extras
        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # 1. Check if student already enrolled (only match valid non-empty email)
            valid_email = student_email if (student_email and '@' in student_email and '.' in student_email) else None
            if valid_email:
                c.execute("""
                    SELECT package_type, status FROM student_enrollments
                    WHERE (student_id = %s OR student_email = %s)
                      AND (package_type = %s OR package_type = 'combo') AND status = 'verified';
                """, (student_id, valid_email, package))
            else:
                c.execute("""
                    SELECT package_type, status FROM student_enrollments
                    WHERE student_id = %s
                      AND (package_type = %s OR package_type = 'combo') AND status = 'verified';
                """, (student_id, package))
            already = c.fetchone()
            if already:
                self.send_json_response({
                    "success": True,
                    "verified": True,
                    "status": "verified",
                    "already_enrolled": True,
                    "package": already['package_type'],
                    "message": "You are already successfully enrolled in this package!"
                })
                return

            # 2. Check if TrxID was claimed by another student
            c.execute("SELECT student_id, student_email, status FROM student_enrollments WHERE trx_id = %s;", (trx_id,))
            claimed_other = c.fetchone()
            if claimed_other:
                is_same_student = (claimed_other['student_id'] == student_id) or (valid_email and claimed_other.get('student_email') == valid_email)
                if not is_same_student:
                    self.send_json_response({
                        "success": False,
                        "verified": False,
                        "message": "This TrxID was already submitted by another student account."
                    }, status=400)
                    return
                elif claimed_other['status'] == 'verified':
                    self.send_json_response({
                        "success": True,
                        "verified": True,
                        "status": "verified",
                        "package": package,
                        "message": "This TrxID payment has already been verified and approved."
                    })
                    return

            # 3. Check received SMS logs for matching bKash SMS
            c.execute("SELECT * FROM received_sms_logs WHERE UPPER(parsed_trx_id) = %s;", (trx_id,))
            sms_log = c.fetchone()

            is_auto_verified = False
            if sms_log:
                if sms_log['is_claimed'] and sms_log['claimed_by_student_id'] and sms_log['claimed_by_student_id'] != student_id:
                    self.send_json_response({
                        "success": False,
                        "verified": False,
                        "message": "This TrxID was already claimed by another account."
                    }, status=400)
                    return
                if sms_log['parsed_amount'] is not None and float(sms_log['parsed_amount']) > 0 and float(sms_log['parsed_amount']) < required_price:
                    self.send_json_response({
                        "success": False,
                        "verified": False,
                        "message": f"Insufficient payment! This package requires Tk {int(required_price)}, but TrxID recorded Tk {float(sms_log['parsed_amount'])}."
                    }, status=400)
                    return

                # Mark claimed in SMS logs
                c.execute("""
                    UPDATE received_sms_logs
                    SET is_claimed = TRUE, claimed_by_student_id = %s
                    WHERE UPPER(parsed_trx_id) = %s;
                """, (student_id, trx_id))
                is_auto_verified = True

            # 4. Insert or update student enrollment as verified (if SMS matched) or pending (if awaiting admin)
            status_val = 'verified' if is_auto_verified else 'pending'
            c.execute("""
                INSERT INTO student_enrollments (student_id, student_name, student_email, package_type, amount, sender_number, trx_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trx_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    student_email = COALESCE(EXCLUDED.student_email, student_enrollments.student_email),
                    package_type = EXCLUDED.package_type,
                    amount = EXCLUDED.amount;
            """, (student_id, student_name, valid_email, package, required_price, sender_number, trx_id, status_val))
            conn.commit()

        except Exception as e:
            self.send_json_response({"status": "error", "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        pkg_title = "Medical 100 Model Tests" if package == 'medical' else ("Varsity & GST Science 100 Model Tests" if package == 'versity' else "Medical + Varsity Mega Combo Pack")
        
        if is_auto_verified:
            self.send_json_response({
                "success": True,
                "verified": True,
                "status": "verified",
                "pending": False,
                "package": package,
                "message": f"🎉 Congratulations! Your bKash payment has been automatically verified. All 95 premium model tests for '{pkg_title}' have been unlocked!"
            })
        else:
            # STRICTLY NOT VERIFIED! PENDING ADMIN MANUAL APPROVAL OR SMS FORWARDER ARRIVAL
            self.send_json_response({
                "success": False,
                "verified": False,
                "status": "pending",
                "pending": True,
                "package": package,
                "message": f"✅ Your bKash payment request (TrxID: {trx_id}) has been submitted for verification. Tests will unlock automatically upon SMS matching or Admin approval."
            })

    def handle_submit_exam(self, data):
        student_name = data.get('student_name', 'Student').strip() or 'Student'
        student_id = data.get('student_id') or f"STU-{uuid.uuid4().hex[:8].upper()}"
        roll = data.get('roll_number', 'ROLL-2025')
        target = data.get('target_college', 'National Merit Leaderboard')
        session = data.get('session', '2025-26')
        try:
            test_id = int(data.get('test_id', 1))
        except (ValueError, TypeError):
            test_id = 1
        test_code = data.get('test_code', f"MT-FULL-{test_id:03d}")
        subject_mode = data.get('subject_mode', 'FullExam')
        try:
            total_questions = max(1, int(data.get('total_questions', 100)))
        except (ValueError, TypeError):
            total_questions = 100
        try:
            correct_count = max(0, int(data.get('correct_count', 0)))
        except (ValueError, TypeError):
            correct_count = 0
        try:
            wrong_count = max(0, int(data.get('wrong_count', 0)))
        except (ValueError, TypeError):
            wrong_count = 0
        try:
            unanswered_count = max(0, int(data.get('unanswered_count', 0)))
        except (ValueError, TypeError):
            unanswered_count = 0
        try:
            score = float(data.get('score', 0.0))
            if str(score) == 'nan' or score != score:
                score = 0.0
        except (ValueError, TypeError):
            score = 0.0
        percentage = round((score / total_questions) * 100, 2) if total_questions > 0 else 0.0
        try:
            raw_time = data.get('time_taken_seconds')
            time_taken_seconds = int(float(raw_time)) if (raw_time is not None and str(raw_time) != 'nan') else 60
            if time_taken_seconds <= 0:
                time_taken_seconds = 1
        except (ValueError, TypeError):
            time_taken_seconds = 60
        submission_code = f"SUB-{uuid.uuid4().hex[:10].upper()}"

        import psycopg2.extras
        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            c.execute("""
                INSERT INTO students (student_id, name, roll_number, target_college, session)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(student_id) DO UPDATE SET
                    name=EXCLUDED.name,
                    roll_number=EXCLUDED.roll_number,
                    target_college=EXCLUDED.target_college,
                    session=EXCLUDED.session;
            """, (student_id, student_name, roll, target, session))

            c.execute("""
                INSERT INTO exam_submissions
                (submission_code, student_id, student_name, target_college, session, test_id, test_code, subject_mode,
                 total_questions, correct_count, wrong_count, unanswered_count, score, percentage, time_taken_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (submission_code, student_id, student_name, target, session, test_id, test_code, subject_mode,
                  total_questions, correct_count, wrong_count, unanswered_count, score, percentage, time_taken_seconds))
            conn.commit()

            c.execute("""
                SELECT COUNT(*) + 1 AS rank FROM exam_submissions
                WHERE test_id = %s AND subject_mode = %s AND session = %s
                  AND (score > %s OR (score = %s AND time_taken_seconds < %s));
            """, (test_id, subject_mode, session, score, score, time_taken_seconds))
            session_rank = c.fetchone()['rank']

            c.execute("SELECT COUNT(*) AS total FROM exam_submissions WHERE test_id = %s AND subject_mode = %s AND session = %s;",
                      (test_id, subject_mode, session))
            session_total = c.fetchone()['total']
            session_percentile = round(((session_total - session_rank) / session_total) * 100, 2) if session_total > 0 else 100.0

            c.execute("""
                SELECT COUNT(*) + 1 AS rank FROM exam_submissions
                WHERE test_id = %s AND subject_mode = %s
                  AND (score > %s OR (score = %s AND time_taken_seconds < %s));
            """, (test_id, subject_mode, score, score, time_taken_seconds))
            all_time_rank = c.fetchone()['rank']

            c.execute("SELECT COUNT(*) AS total FROM exam_submissions WHERE test_id = %s AND subject_mode = %s;",
                      (test_id, subject_mode))
            all_time_total = c.fetchone()['total']
            all_time_percentile = round(((all_time_total - all_time_rank) / all_time_total) * 100, 2) if all_time_total > 0 else 100.0

            c.execute("""
                SELECT student_id, student_name, target_college, session, score, percentage, time_taken_seconds, submitted_at
                FROM exam_submissions
                WHERE test_id = %s AND subject_mode = %s AND session = %s
                ORDER BY score DESC, time_taken_seconds ASC
                LIMIT 10;
            """, (test_id, subject_mode, session))
            session_leaderboard = [dict(r) for r in c.fetchall()]

            c.execute("""
                SELECT student_id, student_name, target_college, session, score, percentage, time_taken_seconds, submitted_at
                FROM exam_submissions
                WHERE test_id = %s AND subject_mode = %s
                ORDER BY score DESC, time_taken_seconds ASC
                LIMIT 10;
            """, (test_id, subject_mode))
            all_time_leaderboard = [dict(r) for r in c.fetchall()]

        except Exception as e:
            self.send_json_response({"status": "error", "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        result = {
            "status": "success",
            "database": "postgres",
            "student_id": student_id,
            "submission_code": submission_code,
            "exam_details": {
                "test_id": test_id,
                "test_code": test_code,
                "subject_mode": subject_mode,
                "score": score,
                "percentage": percentage,
                "time_taken_seconds": time_taken_seconds,
                "session": session
            },
            "rankings": {
                "session": session,
                "session_rank": session_rank,
                "session_total": session_total,
                "session_percentile": session_percentile,
                "all_time_rank": all_time_rank,
                "all_time_total": all_time_total,
                "all_time_percentile": all_time_percentile
            },
            "leaderboards": {
                "session": session_leaderboard,
                "all_time": all_time_leaderboard
            }
        }
        self.send_json_response(result)

    def handle_get_leaderboard(self, query):
        test_id = int(query.get('test_id', [1])[0])
        subject_mode = query.get('subject_mode', ['FullExam'])[0]
        session = query.get('session', ['all'])[0]

        import psycopg2.extras
        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if session == 'all':
                c.execute("""
                    SELECT student_id, student_name, target_college, session, score, percentage, time_taken_seconds, submitted_at
                    FROM exam_submissions
                    WHERE test_id = %s AND subject_mode = %s
                    ORDER BY score DESC, time_taken_seconds ASC
                    LIMIT 20;
                """, (test_id, subject_mode))
            else:
                c.execute("""
                    SELECT student_id, student_name, target_college, session, score, percentage, time_taken_seconds, submitted_at
                    FROM exam_submissions
                    WHERE test_id = %s AND subject_mode = %s AND session = %s
                    ORDER BY score DESC, time_taken_seconds ASC
                    LIMIT 20;
                """, (test_id, subject_mode, session))
            rows = [dict(r) for r in c.fetchall()]
        except Exception as e:
            self.send_json_response({"status": "error", "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        self.send_json_response({
            "test_id": test_id,
            "subject_mode": subject_mode,
            "session": session,
            "database": "postgres",
            "leaderboard": rows
        })

    def handle_get_stats(self):
        conn = get_db_connection()
        try:
            ensure_database_schema(conn)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM students;")
            s_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM exam_submissions;")
            sub_count = c.fetchone()[0]
            c.execute("SELECT session, COUNT(*) FROM exam_submissions GROUP BY session ORDER BY session;")
            sess_rows = c.fetchall()
        except Exception as e:
            self.send_json_response({"status": "error", "message": str(e)}, status=500)
            return
        finally:
            conn.close()

        self.send_json_response({
            "database": "postgres",
            "total_students": s_count,
            "total_submissions": sub_count,
            "sessions": {s: cnt for s, cnt in sess_rows}
        })


if __name__ == '__main__':
    import socketserver
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 8089), handler)
    print("Test Vercel API Handler running at http://127.0.0.1:8089")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
