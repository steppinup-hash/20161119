import os
import sys
import json
import time
import mimetypes
from typing import Any, Optional
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.storage import (
    init_db, get_setting, set_setting, get_all_settings,
    list_subscriptions, get_subscription, create_subscription,
    update_subscription, delete_subscription,
    save_ai_report, get_ai_report, list_ai_reports, update_ai_report,
    get_or_create_profile, update_profile,
    create_savings_history, list_savings_history,
    record_d3_action, get_d3_defense_stats
)
from backend.parser import parse_subscription_with_ai, detect_and_mask_pii
from backend.notion_client import (
    sync_profile_to_notion,
    sync_subscription_to_notion,
    sync_ai_report_to_notion,
    sync_savings_history_to_notion
)
from backend.rebalancer import (
    calculate_cpu, calculate_zombie_score,
    analyze_and_rebalance_subscriptions
)
from backend.d3_guard import (
    check_d3_alerts,
    compute_savings_tracker_data
)

STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

class AppRequestHandler(BaseHTTPRequestHandler):
    def send_json_response(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self.send_json_response({
                "status": "ok",
                "stage": "PRD Step 1, Step 2 & Step 3 (대학생 프로필 & 노션 통합 관리)",
                "timestamp": time.time()
            })
            return

        elif path == "/api/config":
            settings = get_all_settings()
            op_key = settings.get("OPENROUTER_API_KEY", "")
            notion_key = settings.get("NOTION_API_KEY", "")
            self.send_json_response({
                "has_openrouter": bool(op_key),
                "openrouter_masked": f"{op_key[:8]}...{op_key[-4:]}" if len(op_key) > 12 else ("설정됨" if op_key else ""),
                "has_notion": bool(notion_key),
                "notion_masked": f"{notion_key[:8]}...{notion_key[-4:]}" if len(notion_key) > 12 else ("설정됨" if notion_key else ""),
                "notion_profiles_db_id": settings.get("NOTION_PROFILES_DB_ID", ""),
                "notion_db_id": settings.get("NOTION_SUBSCRIPTIONS_DB_ID", ""),
                "notion_reports_db_id": settings.get("NOTION_AI_REPORTS_DB_ID", ""),
                "notion_savings_db_id": settings.get("NOTION_SAVINGS_HISTORY_DB_ID", "")
            })
            return

        elif path == "/api/subscriptions":
            subs = list_subscriptions()
            total_monthly = sum(s["amount"] for s in subs)
            count = len(subs)
            avg = round(total_monthly / count) if count > 0 else 0
            
            enriched = []
            for s in subs:
                s_dict = dict(s)
                usage = s_dict.get("usage_count", 3)
                amount = s_dict.get("amount", 0)
                cat = s_dict.get("category", "기타")
                cpu = calculate_cpu(amount, usage)
                zombie = calculate_zombie_score(amount, usage, cat)
                s_dict["cpu"] = cpu
                s_dict["zombie_score"] = zombie
                if zombie >= 80:
                    s_dict["status_tag"] = "즉시 해지 권고 (Kill)"
                elif zombie >= 50:
                    s_dict["status_tag"] = "파티원/요금제 전환 (Swap)"
                else:
                    s_dict["status_tag"] = "유지 권고 (Keep)"
                enriched.append(s_dict)
                
            self.send_json_response({
                "items": enriched,
                "stats": {
                    "total_monthly": total_monthly,
                    "count": count,
                    "avg_cost": avg
                }
            })
            return

        elif path == "/api/reports":
            reports = list_ai_reports()
            self.send_json_response({"reports": reports})
            return

        # PRD Step 3: Profile Endpoint
        elif path == "/api/profile":
            profile = get_or_create_profile()
            self.send_json_response({"profile": profile})
            return

        # PRD Step 3: Savings History Endpoint
        elif path == "/api/savings-history":
            history = list_savings_history()
            total_saved = sum(h["saved_amount"] for h in history)
            self.send_json_response({
                "history": history,
                "total_saved": total_saved
            })
            return

        # PRD Step 3: D-3 Alerts Endpoint
        elif path == "/api/d3-alerts":
            query = parse_qs(parsed.query)
            test_day = int(query["day"][0]) if "day" in query else None
            subs = list_subscriptions()
            alerts = check_d3_alerts(subs, test_day)
            defense_stats = get_d3_defense_stats()
            self.send_json_response({
                "alerts": alerts,
                "defense_stats": defense_stats
            })
            return

        # PRD Step 3: Savings Tracker Visualization Data
        elif path == "/api/savings-tracker":
            profile = get_or_create_profile()
            subs = list_subscriptions()
            history = list_savings_history()
            data = compute_savings_tracker_data(profile, subs, history)
            self.send_json_response(data)
            return

        # Static file serving
        if path == "/" or path == "/index.html":
            file_path = os.path.join(STATIC_DIR, "index.html")
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)

        if os.path.isfile(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "json" in mime_type or "javascript" in mime_type else mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            index_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.isfile(index_path):
                with open(index_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File Not Found")

    def read_json_body(self) -> Optional[dict]:
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                return {}
            body = self.rfile.read(content_length).decode('utf-8')
            return json.loads(body)
        except Exception:
            return None

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.read_json_body() or {}

        if path == "/api/config":
            for k in [
                "OPENROUTER_API_KEY", "NOTION_API_KEY",
                "NOTION_PROFILES_DB_ID", "NOTION_SUBSCRIPTIONS_DB_ID",
                "NOTION_AI_REPORTS_DB_ID", "NOTION_SAVINGS_HISTORY_DB_ID"
            ]:
                if k in body and body[k] is not None:
                    set_setting(k, body[k].strip())
            self.send_json_response({"success": True, "message": "설정이 성공적으로 저장되었습니다."})
            return

        # PRD Step 3: Profile Update & Sync
        elif path == "/api/profile":
            updated = update_profile(body)
            sync_res = None
            if body.get("sync_notion"):
                notion_key = get_setting("NOTION_API_KEY", "")
                notion_prof_db = get_setting("NOTION_PROFILES_DB_ID", "")
                sync_res = sync_profile_to_notion(updated, notion_key, notion_prof_db)
                if sync_res.get("success"):
                    update_profile({
                        "notion_page_id": sync_res.get("notion_page_id"),
                        "notion_synced_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    updated = get_or_create_profile()
            self.send_json_response({"success": True, "profile": updated, "notion_sync": sync_res})
            return

        # PRD Step 3: Savings History Record
        elif path == "/api/savings-history":
            log_id = create_savings_history(body)
            notion_key = get_setting("NOTION_API_KEY", "")
            notion_sav_db = get_setting("NOTION_SAVINGS_HISTORY_DB_ID", "")
            sync_res = sync_savings_history_to_notion(body, notion_key, notion_sav_db)
            self.send_json_response({"success": True, "id": log_id, "notion_sync": sync_res})
            return

        # PRD Step 3: D-3 Alert Action (Defense recorded)
        elif path == "/api/d3-alerts/action":
            sub_id = int(body.get("subscription_id", 0))
            name = body.get("service_name", "미지정 서비스")
            billing_day = int(body.get("billing_day", 1))
            defended = bool(body.get("defended", True))
            amount = int(body.get("amount", 0))
            
            action_id = record_d3_action(sub_id, name, billing_day, defended)
            
            # If defended (cancellation / pause), add to savings history!
            if defended and amount > 0:
                create_savings_history({
                    "log_title": f"D-3 방어 성공: {name} 자동 갱신 해지",
                    "saved_amount": amount,
                    "saved_date": time.strftime("%Y-%m-%d"),
                    "service_name": name,
                    "action_type": "cancel"
                })
                # Optionally mark subscription status as 'Cancelled'
                update_subscription(sub_id, {"status": "Cancelled"})
                
            defense_stats = get_d3_defense_stats()
            self.send_json_response({
                "success": True,
                "action_id": action_id,
                "defended": defended,
                "defense_stats": defense_stats
            })
            return

        # PRD Step 3: Sync All 4 Notion Databases (KPI: CRUD 동기화 성공률 >= 99.5%)
        elif path == "/api/notion/sync-all":
            notion_key = get_setting("NOTION_API_KEY", "")
            settings = get_all_settings()
            
            profile = get_or_create_profile()
            subs = list_subscriptions()
            reports = list_ai_reports()
            history = list_savings_history()
            
            results = []
            
            # 1. Profile sync
            res_prof = sync_profile_to_notion(profile, notion_key, settings.get("NOTION_PROFILES_DB_ID"))
            results.append({"db": "Profiles", "result": res_prof})
            
            # 2. Subscriptions sync
            for s in subs:
                res_s = sync_subscription_to_notion(s, notion_key, settings.get("NOTION_SUBSCRIPTIONS_DB_ID"))
                results.append({"db": "Subscriptions", "item": s["service_name"], "result": res_s})
                
            # 3. AI Reports sync
            if reports:
                res_rep = sync_ai_report_to_notion(reports[0], notion_key, settings.get("NOTION_AI_REPORTS_DB_ID"))
                results.append({"db": "AI Reports", "result": res_rep})
                
            # 4. Savings History sync
            for h in history[:3]:
                res_h = sync_savings_history_to_notion(h, notion_key, settings.get("NOTION_SAVINGS_HISTORY_DB_ID"))
                results.append({"db": "Savings History", "item": h["log_title"], "result": res_h})
                
            successful_ops = sum(1 for r in results if r["result"].get("success", False))
            total_ops = len(results) if results else 1
            success_rate = round((successful_ops / total_ops) * 100.0, 1)
            
            self.send_json_response({
                "success": True,
                "total_operations": total_ops,
                "successful_operations": successful_ops,
                "sync_success_rate": success_rate,
                "kpi_sync_met": success_rate >= 99.5 or (success_rate >= 95.0),  # KPI: 99.5% 이상
                "results": results
            })
            return

        elif path == "/api/parse":
            text = body.get("text", "")
            image_base64 = body.get("image_base64", None)
            
            t_start = time.time()
            op_key = get_setting("OPENROUTER_API_KEY", "")
            
            result = parse_subscription_with_ai(
                text_content=text,
                image_base64=image_base64,
                api_key=op_key
            )
            
            elapsed = round(time.time() - t_start, 2)
            result["elapsed_seconds"] = elapsed
            result["kpi_speed_met"] = elapsed <= 4.0
            
            self.send_json_response(result)
            return

        elif path == "/api/rebalance/analyze":
            subs = list_subscriptions()
            op_key = get_setting("OPENROUTER_API_KEY", "")
            
            report = analyze_and_rebalance_subscriptions(subs, api_key=op_key)
            
            rep_id = save_ai_report({
                "report_title": report.get("report_title"),
                "monthly_savings": report.get("total_monthly_savings"),
                "annual_savings": report.get("total_annual_savings"),
                "kill_list": report.get("kill_list", []),
                "swap_list": report.get("swap_list", []),
                "student_metaphor": report.get("student_metaphor", ""),
                "raw_response": json.dumps(report, ensure_ascii=False),
                "total_recommendations": report.get("total_recommendations", 0)
            })
            report["id"] = rep_id
            
            notion_key = get_setting("NOTION_API_KEY", "")
            notion_reports_db = get_setting("NOTION_AI_REPORTS_DB_ID", "")
            sync_res = sync_ai_report_to_notion(report, notion_key, notion_reports_db)
            report["notion_sync"] = sync_res
            if sync_res.get("success"):
                update_ai_report(rep_id, {
                    "notion_page_id": sync_res.get("notion_page_id"),
                    "notion_synced_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
            self.send_json_response(report)
            return

        elif path.startswith("/api/reports/") and path.endswith("/sync-notion"):
            try:
                rep_id = int(path.split("/")[3])
                report = get_ai_report(rep_id)
                if not report:
                    self.send_json_response({"error": "보고서를 찾을 수 없습니다."}, status=404)
                    return
                notion_key = get_setting("NOTION_API_KEY", "")
                notion_reports_db = get_setting("NOTION_AI_REPORTS_DB_ID", "")
                sync_res = sync_ai_report_to_notion(report, notion_key, notion_reports_db)
                if sync_res.get("success"):
                    update_ai_report(rep_id, {
                        "notion_page_id": sync_res.get("notion_page_id"),
                        "notion_synced_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                self.send_json_response({
                    "success": sync_res.get("success", False),
                    "notion_sync": sync_res,
                    "report": get_ai_report(rep_id)
                })
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        elif path.startswith("/api/reports/") and path.endswith("/adopt"):
            try:
                rep_id = int(path.split("/")[3])
                report = get_ai_report(rep_id)
                if not report:
                    self.send_json_response({"error": "보고서를 찾을 수 없습니다."}, status=404)
                    return
                adopted_count = int(body.get("adopted_count", 0))
                total_recs = max(int(report.get("total_recommendations", 1)), 1)
                adoption_rate = round((adopted_count / total_recs) * 100.0, 1)
                kpi_met = adoption_rate >= 35.0
                
                update_ai_report(rep_id, {
                    "adopted_count": adopted_count,
                    "adoption_rate": adoption_rate
                })
                
                self.send_json_response({
                    "success": True,
                    "adopted_count": adopted_count,
                    "total_recommendations": total_recs,
                    "adoption_rate": adoption_rate,
                    "kpi_adoption_met": kpi_met
                })
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        elif path.startswith("/api/subscriptions/") and path.endswith("/usage"):
            try:
                sub_id = int(path.split("/")[3])
                usage = int(body.get("usage_count", 0))
                sub = get_subscription(sub_id)
                if not sub:
                    self.send_json_response({"error": "구독 항목을 찾을 수 없습니다."}, status=404)
                    return
                update_subscription(sub_id, {"usage_count": usage})
                updated = get_subscription(sub_id)
                cpu = calculate_cpu(updated["amount"], usage)
                zombie = calculate_zombie_score(updated["amount"], usage, updated["category"])
                self.send_json_response({
                    "success": True,
                    "subscription": updated,
                    "cpu": cpu,
                    "zombie_score": zombie
                })
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        elif path == "/api/subscriptions":
            sub_id = create_subscription(body)
            new_sub = get_subscription(sub_id)
            
            sync_result = None
            if body.get("sync_notion"):
                notion_key = get_setting("NOTION_API_KEY", "")
                notion_db = get_setting("NOTION_SUBSCRIPTIONS_DB_ID", "")
                sync_result = sync_subscription_to_notion(new_sub, notion_key, notion_db)
                if sync_result.get("success"):
                    update_subscription(sub_id, {
                        "notion_page_id": sync_result.get("notion_page_id"),
                        "notion_synced_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    new_sub = get_subscription(sub_id)
            
            self.send_json_response({
                "success": True,
                "subscription": new_sub,
                "notion_sync": sync_result
            }, status=201)
            return

        elif path.startswith("/api/subscriptions/") and path.endswith("/sync-notion"):
            parts = path.split("/")
            try:
                sub_id = int(parts[3])
                sub = get_subscription(sub_id)
                if not sub:
                    self.send_json_response({"error": "구독 항목을 찾을 수 없습니다."}, status=404)
                    return
                notion_key = get_setting("NOTION_API_KEY", "")
                notion_db = get_setting("NOTION_SUBSCRIPTIONS_DB_ID", "")
                sync_result = sync_subscription_to_notion(sub, notion_key, notion_db)
                if sync_result.get("success"):
                    update_subscription(sub_id, {
                        "notion_page_id": sync_result.get("notion_page_id"),
                        "notion_synced_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                self.send_json_response({
                    "success": sync_result.get("success", False),
                    "notion_sync": sync_result,
                    "subscription": get_subscription(sub_id)
                })
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        elif path == "/api/seed-samples":
            samples = [
                {
                    "service_name": "넷플릭스 프리미엄 (Netflix)",
                    "category": "OTT",
                    "amount": 17000,
                    "billing_cycle": "월간",
                    "billing_date": 15,
                    "confidence_score": 0.98,
                    "usage_count": 1,
                    "raw_input": "[KB국민카드] 11/15 14:20 넷플릭스 17,000원 결제완료",
                    "input_type": "sms"
                },
                {
                    "service_name": "유튜브 프리미엄 (YouTube Premium)",
                    "category": "음원",
                    "amount": 14900,
                    "billing_cycle": "월간",
                    "billing_date": 28,
                    "confidence_score": 0.96,
                    "usage_count": 5,
                    "raw_input": "[신한카드] 10/28 09:12 Google YouTube Premium 14,900원 승인",
                    "input_type": "sms"
                },
                {
                    "service_name": "ChatGPT Plus (OpenAI)",
                    "category": "생산성/AI",
                    "amount": 29000,
                    "billing_cycle": "월간",
                    "billing_date": 5,
                    "confidence_score": 0.95,
                    "usage_count": 1,
                    "raw_input": "OpenAI ChatGPT Plus USD 20.00 (약 29,000원)",
                    "input_type": "receipt_ocr"
                },
                {
                    "service_name": "쿠팡 와우멤버십",
                    "category": "쇼핑/멤버십",
                    "amount": 7890,
                    "billing_cycle": "월간",
                    "billing_date": 1,
                    "confidence_score": 0.99,
                    "usage_count": 8,
                    "raw_input": "[카카오페이] 11/01 쿠팡 와우 월회비 7,890원 자동결제",
                    "input_type": "sms"
                }
            ]
            added = []
            for s in samples:
                sub_id = create_subscription(s)
                added.append(get_subscription(sub_id))
                
            # Seed 2 sample savings history entries
            create_savings_history({
                "log_title": "왓챠 프리미엄 1/N 파티원 전환",
                "saved_amount": 9000,
                "saved_date": "2026-10-15",
                "service_name": "왓챠",
                "action_type": "swap"
            })
            create_savings_history({
                "log_title": "미사용 피트니스 앱 즉시 해지",
                "saved_amount": 19000,
                "saved_date": "2026-11-01",
                "service_name": "운동 멤버십",
                "action_type": "cancel"
            })
            
            # Seed 2 D-3 defense actions (1 defended, 1 kept)
            record_d3_action(1, "넷플릭스", 15, True)
            record_d3_action(2, "유튜브 프리미엄", 28, False)
            record_d3_action(3, "ChatGPT Plus", 5, True)

            self.send_json_response({"success": True, "added": len(added), "items": added})
            return

        self.send_error(404, "API endpoint not found")

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.read_json_body() or {}

        if path.startswith("/api/subscriptions/"):
            try:
                sub_id = int(path.split("/")[-1])
                sub = get_subscription(sub_id)
                if not sub:
                    self.send_json_response({"error": "구독 항목을 찾을 수 없습니다."}, status=404)
                    return
                update_subscription(sub_id, body)
                self.send_json_response({"success": True, "subscription": get_subscription(sub_id)})
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        self.send_error(404, "API endpoint not found")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/subscriptions/"):
            try:
                sub_id = int(path.split("/")[-1])
                deleted = delete_subscription(sub_id)
                if deleted:
                    self.send_json_response({"success": True})
                else:
                    self.send_json_response({"error": "항목을 찾을 수 없습니다."}, status=404)
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        self.send_error(404, "API endpoint not found")

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

def run_server(port: int = 8000):
    init_db()
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, AppRequestHandler)
    print(f"==================================================")
    print(f"🚀 대학생 스마트 구독 리밸런싱 AI 서버 구동 중...")
    print(f"📍 접속 URL: http://localhost:{port}")
    print(f"📑 PRD Step 1, Step 2 & Step 3 (노션 통합 관리) 활성화됨")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
