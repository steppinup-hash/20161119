import sqlite3
import os
import json
import time
from typing import Dict, List, Optional, Any

if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/subscriptions.db"
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "subscriptions.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Subscriptions table matching PRD Step 1 and Step 3 specs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_name TEXT NOT NULL,
        category TEXT NOT NULL,
        amount INTEGER NOT NULL,
        billing_cycle TEXT NOT NULL DEFAULT '월간',
        billing_date INTEGER NOT NULL,
        confidence_score REAL NOT NULL DEFAULT 1.0,
        usage_count INTEGER DEFAULT 3,
        raw_input TEXT,
        input_type TEXT DEFAULT 'text',
        notion_page_id TEXT,
        notion_synced_at TEXT,
        status TEXT NOT NULL DEFAULT 'Active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Check if usage_count column exists in existing DB
    cursor.execute("PRAGMA table_info(subscriptions)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "usage_count" not in columns:
        cursor.execute("ALTER TABLE subscriptions ADD COLUMN usage_count INTEGER DEFAULT 3")
        
    # 2. AI Reports table for PRD Step 2 & Step 3
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_title TEXT NOT NULL,
        monthly_savings INTEGER NOT NULL,
        annual_savings INTEGER NOT NULL,
        kill_list_json TEXT,
        swap_list_json TEXT,
        student_metaphor TEXT,
        raw_response TEXT,
        notion_page_id TEXT,
        notion_synced_at TEXT,
        adopted_count INTEGER DEFAULT 0,
        total_recommendations INTEGER DEFAULT 0,
        adoption_rate REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 3. Profiles table for PRD Step 3
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL DEFAULT '김대학',
        income INTEGER NOT NULL DEFAULT 850000,
        budget INTEGER NOT NULL DEFAULT 35000,
        lifecycle_mode TEXT NOT NULL DEFAULT '일반학기',
        notion_page_id TEXT,
        notion_synced_at TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Ensure default profile exists
    cursor.execute("SELECT COUNT(*) as cnt FROM profiles")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("""
        INSERT INTO profiles (student_name, income, budget, lifecycle_mode)
        VALUES ('김대학', 850000, 35000, '일반학기')
        """)

    # 4. Savings History table for PRD Step 3
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS savings_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_title TEXT NOT NULL,
        saved_amount INTEGER NOT NULL,
        saved_date TEXT NOT NULL,
        service_name TEXT,
        action_type TEXT DEFAULT 'cancel',
        notion_page_id TEXT,
        notion_synced_at TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. D-3 Alert Actions table for Tracking Auto-renewal Defense Rate KPI
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS d3_alert_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER,
        service_name TEXT,
        billing_day INTEGER,
        alert_date TEXT,
        defended INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 6. Settings table for API keys and configuration
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Seed default benchmark subscriptions if empty (for Vercel serverless /tmp persistence)
    cursor.execute("SELECT COUNT(*) as cnt FROM subscriptions")
    if cursor.fetchone()["cnt"] == 0:
        samples = [
            ("넷플릭스 프리미엄 (Netflix)", "OTT", 17000, "월간", 15, 0.98, 1, "[KB국민카드] 11/15 넷플릭스 17,000원 결제완료", "sms", "Active"),
            ("유튜브 프리미엄 (YouTube Premium)", "음원", 14900, "월간", 28, 0.96, 5, "[신한카드] 10/28 YouTube 14,900원 승인", "sms", "Active"),
            ("ChatGPT Plus (OpenAI)", "생산성/AI", 29000, "월간", 5, 0.95, 1, "OpenAI ChatGPT Plus USD 20.00 (약 29,000원)", "receipt_ocr", "Active"),
            ("쿠팡 와우멤버십", "쇼핑/멤버십", 7890, "월간", 1, 0.99, 8, "[카카오페이] 11/01 쿠팡 와우 7,890원 자동결제", "sms", "Active")
        ]
        cursor.executemany("""
        INSERT INTO subscriptions (service_name, category, amount, billing_cycle, billing_date, confidence_score, usage_count, raw_input, input_type, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, samples)

    # Seed sample savings history if empty
    cursor.execute("SELECT COUNT(*) as cnt FROM savings_history")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("""
        INSERT INTO savings_history (log_title, saved_amount, saved_date, service_name, action_type)
        VALUES ('왓챠 프리미엄 1/N 파티원 전환', 9000, '2026-10-15', '왓챠', 'swap')
        """)
        cursor.execute("""
        INSERT INTO savings_history (log_title, saved_amount, saved_date, service_name, action_type)
        VALUES ('미사용 피트니스 앱 즉시 해지', 19000, '2026-11-01', '운동 멤버십', 'cancel')
        """)
    
    conn.commit()
    conn.close()

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["value"]
    return os.environ.get(key, default)

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    result = {row["key"]: row["value"] for row in rows}
    for env_key in [
        "OPENROUTER_API_KEY", "NOTION_API_KEY",
        "NOTION_PROFILES_DB_ID", "NOTION_SUBSCRIPTIONS_DB_ID",
        "NOTION_AI_REPORTS_DB_ID", "NOTION_SAVINGS_HISTORY_DB_ID"
    ]:
        if env_key not in result and os.environ.get(env_key):
            result[env_key] = os.environ.get(env_key)
    return result

# Subscriptions Functions
def list_subscriptions() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_subscription(sub_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_subscription(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO subscriptions (
        service_name, category, amount, billing_cycle, billing_date,
        confidence_score, usage_count, raw_input, input_type, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("service_name", "미지정 서비스"),
        data.get("category", "기타"),
        int(data.get("amount", 0)),
        data.get("billing_cycle", "월간"),
        int(data.get("billing_date", 1)),
        float(data.get("confidence_score", 1.0)),
        int(data.get("usage_count", 3)),
        data.get("raw_input", ""),
        data.get("input_type", "text"),
        data.get("status", "Active")
    ))
    sub_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sub_id

def update_subscription(sub_id: int, data: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    
    for key in ["service_name", "category", "amount", "billing_cycle", "billing_date", "confidence_score", "usage_count", "status", "notion_page_id", "notion_synced_at"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
            
    if not fields:
        conn.close()
        return False
        
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(sub_id)
    
    query = f"UPDATE subscriptions SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, tuple(values))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def delete_subscription(sub_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

# AI Reports Functions
def save_ai_report(report_data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO ai_reports (
        report_title, monthly_savings, annual_savings,
        kill_list_json, swap_list_json, student_metaphor,
        raw_response, total_recommendations, notion_page_id, notion_synced_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report_data.get("report_title", "AI 구독 리밸런싱 보고서"),
        int(report_data.get("monthly_savings", 0)),
        int(report_data.get("annual_savings", 0)),
        json.dumps(report_data.get("kill_list", []), ensure_ascii=False),
        json.dumps(report_data.get("swap_list", []), ensure_ascii=False),
        report_data.get("student_metaphor", ""),
        report_data.get("raw_response", ""),
        int(report_data.get("total_recommendations", 0)),
        report_data.get("notion_page_id"),
        report_data.get("notion_synced_at")
    ))
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id

def get_ai_report(report_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["kill_list"] = json.loads(data["kill_list_json"]) if data["kill_list_json"] else []
    data["swap_list"] = json.loads(data["swap_list_json"]) if data["swap_list_json"] else []
    return data

def list_ai_reports() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_reports ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["kill_list"] = json.loads(d["kill_list_json"]) if d["kill_list_json"] else []
        d["swap_list"] = json.loads(d["swap_list_json"]) if d["swap_list_json"] else []
        result.append(d)
    return result

def update_ai_report(report_id: int, updates: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    for k, v in updates.items():
        fields.append(f"{k} = ?")
        values.append(v)
    if not fields:
        conn.close()
        return False
    values.append(report_id)
    cursor.execute(f"UPDATE ai_reports SET {', '.join(fields)} WHERE id = ?", tuple(values))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

# PRD Step 3: Profiles Management
def get_or_create_profile() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
        INSERT INTO profiles (student_name, income, budget, lifecycle_mode)
        VALUES ('김대학', 850000, 35000, '일반학기')
        """)
        conn.commit()
        cursor.execute("SELECT * FROM profiles ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    return dict(row)

def update_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    for k in ["student_name", "income", "budget", "lifecycle_mode", "notion_page_id", "notion_synced_at"]:
        if k in data and data[k] is not None:
            fields.append(f"{k} = ?")
            values.append(data[k])
    if fields:
        fields.append("updated_at = CURRENT_TIMESTAMP")
        cursor.execute(f"UPDATE profiles SET {', '.join(fields)} WHERE id = 1", tuple(values))
        conn.commit()
    conn.close()
    return get_or_create_profile()

# PRD Step 3: Savings History Management
def create_savings_history(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO savings_history (
        log_title, saved_amount, saved_date, service_name, action_type,
        notion_page_id, notion_synced_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("log_title", "구독 다이어트 절감"),
        int(data.get("saved_amount", 0)),
        data.get("saved_date", time.strftime("%Y-%m-%d")),
        data.get("service_name", ""),
        data.get("action_type", "cancel"),
        data.get("notion_page_id"),
        data.get("notion_synced_at")
    ))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id

def list_savings_history() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM savings_history ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# PRD Step 3: D-3 Alert Actions & Defense Rate KPI Tracking
def record_d3_action(sub_id: int, service_name: str, billing_day: int, defended: bool) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO d3_alert_actions (subscription_id, service_name, billing_day, alert_date, defended)
    VALUES (?, ?, ?, ?, ?)
    """, (
        sub_id,
        service_name,
        billing_day,
        time.strftime("%Y-%m-%d"),
        1 if defended else 0
    ))
    action_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return action_id

def get_d3_defense_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total, SUM(defended) as defended FROM d3_alert_actions")
    row = cursor.fetchone()
    conn.close()
    total = row["total"] or 0
    defended = row["defended"] or 0
    rate = round((defended / total * 100.0), 1) if total > 0 else 50.0  # Default to healthy sample rate
    return {
        "total_actions": total,
        "defended_count": defended,
        "defense_rate": rate,
        "kpi_defense_met": rate >= 40.0  # KPI: D-3 알림 후 자동 갱신 방어율 40% 이상
    }
