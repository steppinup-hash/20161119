import unittest
import os
import sys
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.storage import (
    init_db, create_subscription, get_subscription, list_subscriptions,
    save_ai_report, get_ai_report, list_ai_reports, update_ai_report
)
from backend.rebalancer import (
    calculate_cpu,
    calculate_zombie_score,
    find_benchmark_alternative,
    generate_student_metaphor,
    analyze_and_rebalance_subscriptions
)
from backend.notion_client import sync_ai_report_to_notion

class TestPRDStep2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_cost_per_use_cpu_formula(self):
        """2. 핵심 계산 수식: CPU = 월 결제 금액 / max(최근 30일 이용 횟수, 1)"""
        # Case 1: 0 uses (denominator is max(0, 1) = 1)
        cpu_0 = calculate_cpu(17000, 0)
        self.assertEqual(cpu_0, 17000.0)
        
        # Case 2: 1 use
        cpu_1 = calculate_cpu(17000, 1)
        self.assertEqual(cpu_1, 17000.0)
        
        # Case 3: 4 uses
        cpu_4 = calculate_cpu(17000, 4)
        self.assertEqual(cpu_4, 4250.0)
        
        # Case 4: 20 uses
        cpu_20 = calculate_cpu(14900, 20)
        self.assertEqual(cpu_20, 745.0)

    def test_02_zombie_score_thresholds(self):
        """
        2. 좀비 구독 지수 스코어링 (0~100점):
           - 80점 이상: 즉시 해지 권고 (Kill List)
           - 50~79점: 요금제 변경 / 파티원 전환 (Swap List)
           - 50점 미만: 유지 (Keep)
        """
        # High Zombie: Netflix 17,000 KRW used only 0 or 1 time
        score_kill = calculate_zombie_score(17000, 1, "OTT")
        self.assertGreaterEqual(score_kill, 80)
        
        # High Zombie: ChatGPT Plus 29,000 KRW used 0 times
        score_kill_ai = calculate_zombie_score(29000, 0, "생산성/AI")
        self.assertGreaterEqual(score_kill_ai, 85)
        
        # Moderate Zombie: YouTube 14,900 KRW used 4 times (swap candidate)
        score_swap = calculate_zombie_score(14900, 4, "음원")
        self.assertTrue(50 <= score_swap < 80, f"Expected 50-79, got {score_swap}")
        
        # Healthy Keep: Coupang Wow used 8 times (e-commerce target is 4)
        score_keep = calculate_zombie_score(7890, 8, "쇼핑/멤버십")
        self.assertLess(score_keep, 50, f"Expected <50, got {score_keep}")
        
        # Healthy Keep: YouTube used 25 times
        score_keep_yt = calculate_zombie_score(14900, 25, "음원")
        self.assertLess(score_keep_yt, 50, f"Expected <50, got {score_keep_yt}")

    def test_03_benchmark_alternative_lookup(self):
        """3. 유사 서비스 요금제 비교 벤치마크 예시 매칭"""
        # OTT benchmark: Netflix -> PicklePlus/Buts 1/N
        netflix_bench = find_benchmark_alternative("넷플릭스 프리미엄")
        self.assertIsNotNone(netflix_bench)
        self.assertIn("피클플러스", netflix_bench["recommendation"])
        self.assertEqual(netflix_bench["monthly_savings"], 12750)
        
        # Music benchmark: YouTube -> T우주패스
        yt_bench = find_benchmark_alternative("유튜브 프리미엄 (YouTube Premium)")
        self.assertIsNotNone(yt_bench)
        self.assertIn("T우주패스", yt_bench["recommendation"])
        self.assertEqual(yt_bench["monthly_savings"], 7000)
        
        # AI benchmark: ChatGPT Plus -> GitHub Student Developer Pack
        chatgpt_bench = find_benchmark_alternative("ChatGPT Plus")
        self.assertIsNotNone(chatgpt_bench)
        self.assertIn("GitHub Student", chatgpt_bench["recommendation"])
        self.assertEqual(chatgpt_bench["monthly_savings"], 29000)

    def test_04_student_financial_metaphor(self):
        """4. 학식 / 치킨 환산 정량적 재무 비유 텍스트 생성"""
        metaphor = generate_student_metaphor(29000)
        self.assertIn("학식", metaphor)
        self.assertIn("치킨", metaphor)
        self.assertIn("348,000", metaphor)  # 29,000 * 12 = 348,000 KRW

    def test_05_rebalancing_report_generation_and_kpis(self):
        """
        1.2 & 4: AI 분석 보고서 생성 및 KPI 검증
        - 월평균 예상 절감액: 15,000원 ~ 35,000원 이상
        - 응답 시간: 8초 이내
        - 출력 폼: Kill List Top 3, Swap List, 학식/치킨 환산 비유
        """
        test_subs = [
            {"id": 1, "service_name": "넷플릭스 프리미엄", "category": "OTT", "amount": 17000, "usage_count": 1},
            {"id": 2, "service_name": "유튜브 프리미엄", "category": "음원", "amount": 14900, "usage_count": 4},
            {"id": 3, "service_name": "ChatGPT Plus", "category": "생산성/AI", "amount": 29000, "usage_count": 1},
            {"id": 4, "service_name": "쿠팡 와우멤버십", "category": "쇼핑/멤버십", "amount": 7890, "usage_count": 8}
        ]
        
        report = analyze_and_rebalance_subscriptions(test_subs)
        
        # Verify KPI 1: Speed <= 8.0s
        self.assertTrue(report["kpi_speed_met"])
        self.assertLessEqual(report["elapsed_seconds"], 8.0)
        
        # Verify KPI 2: Savings >= 15,000 KRW
        self.assertTrue(report["kpi_savings_met"])
        self.assertGreaterEqual(report["total_monthly_savings"], 15000)
        
        # Verify Kill List Top 3
        self.assertIn("kill_list", report)
        self.assertTrue(len(report["kill_list"]) > 0)
        self.assertTrue(any(k["service_name"] == "ChatGPT Plus" or k["service_name"] == "넷플릭스 프리미엄" for k in report["kill_list"]))
        
        # Verify Swap List
        self.assertIn("swap_list", report)
        self.assertTrue(len(report["swap_list"]) > 0)
        
        # Verify Metaphor
        self.assertIn("student_metaphor", report)
        self.assertIn("학식", report["student_metaphor"])

    def test_06_notion_ai_reports_sync(self):
        """Notion [AI Reports] DB 동기화 규격: Report Title, Monthly Savings, Annual Savings"""
        mock_report = {
            "report_title": "2026 대학생 구독 다이어트 리포트",
            "total_monthly_savings": 35000,
            "total_annual_savings": 420000
        }
        res = sync_ai_report_to_notion(mock_report)
        self.assertTrue(res["success"])
        self.assertTrue(res["simulated"])
        self.assertTrue(res["notion_page_id"].startswith("simulated-report"))

    def test_07_adoption_rate_tracking(self):
        """KPI: AI 리밸런싱 권고안 채택률 35% 이상 트래킹"""
        # Save a test report
        rep_id = save_ai_report({
            "report_title": "채택률 테스트 리포트",
            "monthly_savings": 25000,
            "annual_savings": 300000,
            "total_recommendations": 4
        })
        
        # Adopt 2 out of 4 recommendations -> 50% adoption rate (>= 35% KPI satisfied!)
        adopted_count = 2
        total_recs = 4
        adoption_rate = round((adopted_count / total_recs) * 100, 1)
        self.assertEqual(adoption_rate, 50.0)
        self.assertGreaterEqual(adoption_rate, 35.0)
        
        update_ai_report(rep_id, {
            "adopted_count": adopted_count,
            "adoption_rate": adoption_rate
        })
        
        saved = get_ai_report(rep_id)
        self.assertEqual(saved["adopted_count"], 2)
        self.assertEqual(saved["adoption_rate"], 50.0)

if __name__ == "__main__":
    unittest.main()
