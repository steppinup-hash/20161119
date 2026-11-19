import unittest
import os
import sys
import json
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.storage import (
    init_db,
    get_or_create_profile, update_profile,
    create_savings_history, list_savings_history,
    record_d3_action, get_d3_defense_stats,
    create_subscription, list_subscriptions
)
from backend.notion_client import (
    sync_profile_to_notion,
    sync_subscription_to_notion,
    sync_ai_report_to_notion,
    sync_savings_history_to_notion
)
from backend.d3_guard import (
    check_d3_alerts,
    get_cancellation_guide,
    compute_savings_tracker_data
)

class TestPRDStep3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_notion_4_databases_schema_sync(self):
        """2. 노션 4대 데이터베이스 스키마 명세 검증 (Profiles, Subscriptions, AI Reports, Savings History)"""
        # 1) Profiles: Student Name (Title), Income (Number), Budget (Number)
        prof_res = sync_profile_to_notion({
            "student_name": "홍길동",
            "income": 900000,
            "budget": 35000
        })
        self.assertTrue(prof_res["success"])
        self.assertTrue(prof_res["simulated"])
        self.assertTrue(prof_res["notion_page_id"].startswith("simulated-profile"))

        # 2) Subscriptions: Service Name (Title), Monthly Cost (Number), Billing Day (Number), Status (Status)
        sub_res = sync_subscription_to_notion({
            "service_name": "넷플릭스 프리미엄",
            "amount": 17000,
            "billing_date": 15,
            "status": "Active"
        })
        self.assertTrue(sub_res["success"])
        self.assertTrue(sub_res["notion_page_id"].startswith("simulated-notion"))

        # 3) AI Reports: Report Title (Title), Monthly Savings (Number), Annual Savings (Number)
        rep_res = sync_ai_report_to_notion({
            "report_title": "11월 정기 리밸런싱",
            "monthly_savings": 35000,
            "annual_savings": 420000
        })
        self.assertTrue(rep_res["success"])
        self.assertTrue(rep_res["notion_page_id"].startswith("simulated-report"))

        # 4) Savings History: Log Title (Title), Saved Amount (Number), Saved Date (Date)
        sav_res = sync_savings_history_to_notion({
            "log_title": "ChatGPT Plus -> Copilot 전환 절감",
            "saved_amount": 29000,
            "saved_date": "2026-11-19"
        })
        self.assertTrue(sav_res["success"])
        self.assertTrue(sav_res["notion_page_id"].startswith("simulated-savings"))

    def test_02_d3_detection_condition_and_guides(self):
        """3. D-3 자동 감지 스펙: (Billing Day - Today == 3) 조건 감지 및 30초 초간단 해지 가이드 딥링크 출력"""
        test_subs = [
            {"id": 1, "service_name": "넷플릭스", "amount": 17000, "billing_date": 15},
            {"id": 2, "service_name": "유튜브 프리미엄", "amount": 14900, "billing_date": 28},
            {"id": 3, "service_name": "ChatGPT Plus", "amount": 29000, "billing_date": 5}
        ]
        
        # Test case: Today is 12th -> Billing Day 15 - 12 == 3 -> Netflix should be detected
        alerts_day_12 = check_d3_alerts(test_subs, current_day=12)
        netflix_alerts = [a for a in alerts_day_12 if a["service_name"] == "넷플릭스" and a["days_left"] == 3]
        self.assertTrue(len(netflix_alerts) > 0)
        self.assertIn("netflix.com", netflix_alerts[0]["deep_link"])
        self.assertTrue(len(netflix_alerts[0]["steps"]) >= 3)
        self.assertLessEqual(netflix_alerts[0]["estimated_seconds"], 35)

    def test_03_d3_defense_rate_kpi(self):
        """1.2 핵심 성공 지표: D-3 알림 후 자동 갱신 방어율 40% 이상 트래킹"""
        # Record 3 actions: 2 defended (cancelled), 1 ignored
        record_d3_action(1, "넷플릭스", 15, True)
        record_d3_action(2, "유튜브", 28, False)
        record_d3_action(3, "ChatGPT Plus", 5, True)
        
        stats = get_d3_defense_stats()
        self.assertGreaterEqual(stats["defense_rate"], 40.0)
        self.assertTrue(stats["kpi_defense_met"])

    def test_04_student_lifecycle_and_budget_achievement_kpi(self):
        """1.2 & 3: 대학생 라이프사이클(시험기간, 방학) 및 목표 고정비 예산 달성률 80% 이상"""
        profile = get_or_create_profile()
        self.assertIsNotNone(profile)
        
        # Update lifecycle to '시험기간' and budget to 35,000 KRW
        updated = update_profile({
            "student_name": "이대학",
            "income": 800000,
            "budget": 35000,
            "lifecycle_mode": "시험기간"
        })
        self.assertEqual(updated["lifecycle_mode"], "시험기간")
        self.assertEqual(updated["budget"], 35000)
        
        # Subscriptions within or close to budget
        subs = [
            {"service_name": "유튜브 프리미엄 파티원", "category": "음원", "amount": 7900},
            {"service_name": "쿠팡 와우", "category": "쇼핑/멤버십", "amount": 7890}
        ] # Total: 15,790 <= budget (35,000) -> 100% achievement rate
        
        tracker_data = compute_savings_tracker_data(updated, subs, [])
        self.assertEqual(tracker_data["achievement_rate"], 100.0)
        self.assertTrue(tracker_data["kpi_budget_met"])

    def test_05_savings_tracker_visualizations_data(self):
        """3. Savings Tracker 시각화 데이터 명세: 목표 예산 게이지, 최근 6개월 Area Chart, 도넛 차트"""
        profile = {"budget": 35000, "income": 850000}
        subs = [
            {"service_name": "넷플릭스", "category": "OTT", "amount": 17000},
            {"service_name": "유튜브", "category": "음원", "amount": 14900},
            {"service_name": "ChatGPT", "category": "생산성/AI", "amount": 29000}
        ]
        history = [
            {"log_title": "넷플릭스 파티원 전환", "saved_amount": 12750, "saved_date": "2026-11-01"}
        ]
        
        data = compute_savings_tracker_data(profile, subs, history)
        
        # Donut Chart
        self.assertIn("OTT", data["donut_chart"]["labels"])
        self.assertIn("음원", data["donut_chart"]["labels"])
        self.assertEqual(len(data["donut_chart"]["labels"]), len(data["donut_chart"]["values"]))
        
        # Area Chart (6 Months)
        self.assertEqual(len(data["area_chart"]), 6)
        self.assertGreater(data["cumulative_savings_total"], 0)

    def test_06_notion_crud_sync_success_rate_kpi(self):
        """1.2 KPI: 노션 데이터베이스 실시간 CRUD 동기화 성공률 99.5% 이상"""
        operations = [
            sync_profile_to_notion({"student_name": "테스트", "income": 500000, "budget": 30000}),
            sync_subscription_to_notion({"service_name": "테스트 구독", "amount": 10000, "billing_date": 1}),
            sync_ai_report_to_notion({"report_title": "테스트 보고서", "monthly_savings": 20000, "annual_savings": 240000}),
            sync_savings_history_to_notion({"log_title": "테스트 절감", "saved_amount": 15000, "saved_date": "2026-11-19"})
        ]
        success_count = sum(1 for op in operations if op["success"])
        success_rate = (success_count / len(operations)) * 100.0
        self.assertEqual(success_rate, 100.0)
        self.assertGreaterEqual(success_rate, 99.5)

if __name__ == "__main__":
    unittest.main()
