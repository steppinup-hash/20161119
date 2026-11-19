import unittest
import os
import sys
import json

# Setup project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.parser import (
    detect_and_mask_pii,
    extract_regex_amounts,
    guess_category,
    heuristic_parse_text,
    parse_subscription_with_ai
)
from backend.notion_client import sync_subscription_to_notion
from backend.storage import (
    init_db, create_subscription, get_subscription,
    update_subscription, delete_subscription, list_subscriptions
)

class TestPRDStep1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_pii_detection_and_masking(self):
        """Rule: WARN_PII_DETECTED - 카드번호/주민번호 마스킹(****) 처리 후 API 전송"""
        sample_sms = "[신한카드] 9410-1234-5678-9012 승인 홍길동님 넷플릭스 17,000원 결제 완료"
        masked, detected, pii_types = detect_and_mask_pii(sample_sms)
        
        self.assertTrue(detected)
        self.assertIn("카드번호 (Credit Card)", pii_types)
        self.assertNotIn("9410-1234-5678-9012", masked)
        self.assertIn("****-****-****-****", masked)
        
        # Test Korean Resident Registration Number
        sample_rrn = "신분확인: 991231-1234567 결제자정보"
        masked_rrn, detected_rrn, pii_types_rrn = detect_and_mask_pii(sample_rrn)
        self.assertTrue(detected_rrn)
        self.assertIn("주민등록번호 (RRN)", pii_types_rrn)
        self.assertNotIn("991231-1234567", masked_rrn)
        self.assertIn("******-*******", masked_rrn)

    def test_02_regex_amount_extraction(self):
        """Requirements 3.1: 정규식 기반 금액 패턴 감지"""
        text1 = "[KB국민카드] 11/15 14:20 넷플릭스 17,000원 결제완료"
        amounts1 = extract_regex_amounts(text1)
        self.assertEqual(amounts1, [17000])
        
        text2 = "[카카오페이] 유튜브 프리미엄 정기결제 ₩14,900 완료"
        amounts2 = extract_regex_amounts(text2)
        self.assertEqual(amounts2, [14900])
        
        text3 = "OpenAI ChatGPT Plus USD $20.00 또는 29000원 청구예정"
        amounts3 = extract_regex_amounts(text3)
        self.assertTrue(29000 in amounts3 or 20 in amounts3)

    def test_03_structured_data_parsing(self):
        """Requirements 3.2: 추출 객체 (service_name, category, amount, billing_cycle, billing_date, confidence_score)"""
        sample_sms = "[신한체크] 10/28 11:30 유튜브 프리미엄 14,900원 결제. 매월 28일 정기결제"
        result = heuristic_parse_text(sample_sms)
        
        self.assertIn("유튜브 프리미엄", result["service_name"])
        self.assertEqual(result["category"], "음원")
        self.assertEqual(result["amount"], 14900)
        self.assertEqual(result["billing_cycle"], "월간")
        self.assertEqual(result["billing_date"], 28)
        self.assertGreaterEqual(result["confidence_score"], 0.9)

    def test_04_low_confidence_exception(self):
        """Rule: ERR_VISION_LOW_CONFIDENCE - 저화질 식별 불가 안내 토스트 및 수동 모드"""
        unclear_text = "사진이 흐려서 아무것도 안 보임..."
        result = parse_subscription_with_ai(text_content=unclear_text, api_key=None)
        
        self.assertLess(result["confidence_score"], 0.6)
        self.assertEqual(result.get("error_code"), "ERR_VISION_LOW_CONFIDENCE")

    def test_05_notion_api_payload_and_sync(self):
        """Requirements: Notion [Subscriptions] DB 동기화 규격 (Service Name, Monthly Cost, Billing Day, Status)"""
        sub_data = {
            "id": 999,
            "service_name": "넷플릭스 프리미엄",
            "amount": 17000,
            "billing_date": 15,
            "status": "Active"
        }
        # In simulation mode (without credentials)
        sync_result = sync_subscription_to_notion(sub_data)
        self.assertTrue(sync_result["success"])
        self.assertTrue(sync_result["simulated"])
        self.assertTrue(sync_result["notion_page_id"].startswith("simulated-notion"))

    def test_06_storage_crud(self):
        """CRUD database operations check"""
        new_id = create_subscription({
            "service_name": "테스트 서비스",
            "category": "기타",
            "amount": 9900,
            "billing_cycle": "월간",
            "billing_date": 10,
            "confidence_score": 0.95
        })
        self.assertIsNotNone(new_id)
        
        fetched = get_subscription(new_id)
        self.assertEqual(fetched["service_name"], "테스트 서비스")
        self.assertEqual(fetched["amount"], 9900)
        
        # Update
        update_subscription(new_id, {"amount": 12000, "category": "생산성/AI"})
        updated = get_subscription(new_id)
        self.assertEqual(updated["amount"], 12000)
        self.assertEqual(updated["category"], "생산성/AI")
        
        # Delete
        deleted = delete_subscription(new_id)
        self.assertTrue(deleted)
        self.assertIsNone(get_subscription(new_id))

if __name__ == "__main__":
    unittest.main()
