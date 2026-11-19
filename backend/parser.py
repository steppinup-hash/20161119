import re
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional

# Category mappings for Korean subscriptions
CATEGORY_KEYWORDS = {
    "OTT": ["넷플릭스", "netflix", "티빙", "tving", "디즈니", "disney", "웨이브", "wavve", "왓챠", "watcha", "쿠팡플레이", "coupang play", "라프텔", "laftel"],
    "음원": ["유튜브", "youtube", "스포티파이", "spotify", "멜론", "melon", "지니", "genie", "벅스", "bugs", "플로", "flo", "애플뮤직", "apple music"],
    "생산성/AI": ["chatgpt", "openai", "챗지피티", "claude", "클로드", "anthropic", "github", "copilot", "깃허브", "notion", "노션", "midjourney", "미드저니", "canva", "캔바", "figma", "피그마"],
    "클라우드/저장소": ["icloud", "아이클라우드", "google one", "구글 원", "구글 드라이브", "onedrive", "dropbox", "드롭박스"],
    "쇼핑/멤버십": ["쿠팡", "와우", "coupang", "네이버", "네이버플러스", "배민", "배달의민족", "클럽", "요기요", "요기패스", "컬리", "컬리패스", "신세계", "유니버스"],
    "도서/교육": ["밀리의 서재", "밀리", "리디", "ridi", "리디북스", "클래스101", "인프런", "패스트캠퍼스"],
    "통신/생활": ["통신요금", "알뜰폰", "skt", "kt", "lgu+", "u+", "정수기", "피트니스", "헬스장"]
}

DEFAULT_CATEGORIES = ["OTT", "음원", "생산성/AI", "클라우드/저장소", "쇼핑/멤버십", "도서/교육", "통신/생활", "기타"]

def detect_and_mask_pii(text: str) -> Tuple[str, bool, list]:
    """
    Detects and masks sensitive information (credit card numbers, resident registration numbers).
    Returns (masked_text, pii_detected_bool, detected_types_list).
    Rule: WARN_PII_DETECTED policy
    """
    pii_found = []
    masked = text
    
    # 1. Credit Card pattern (16 digits with - or space or continuous)
    # Examples: 1234-5678-9012-3456, 1234 5678 9012 3456, 1234567890123456
    card_pattern = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
    if card_pattern.search(masked):
        pii_found.append("카드번호 (Credit Card)")
        masked = card_pattern.sub("****-****-****-****", masked)
        
    # 2. Korean Resident Registration Number (RRN / 주민등록번호)
    # Example: 991231-1234567 or 991231 1234567
    rrn_pattern = re.compile(r'\b\d{6}[-\s]?[1-4]\d{6}\b')
    if rrn_pattern.search(masked):
        pii_found.append("주민등록번호 (RRN)")
        masked = rrn_pattern.sub("******-*******", masked)

    return masked, len(pii_found) > 0, pii_found


def extract_regex_amounts(text: str) -> list:
    """Extract potential monetary amounts from text."""
    # Pattern: 1,000원, 17,000 원, ₩17,000, 14900원, 29,000KRW, $20.00
    patterns = [
        r'(?:₩|￦|\$)\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]{1,2})?)',
        r'([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\s*(?:원|KRW|krw|달러)',
        r'(?:금액|승인|결제|청구)[\s:]*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)'
    ]
    amounts = []
    for pat in patterns:
        for match in re.finditer(pat, text):
            raw_val = match.group(1).replace(',', '')
            try:
                val = int(float(raw_val))
                if val > 0 and val not in amounts:
                    amounts.append(val)
            except ValueError:
                pass
    return amounts


def guess_category(service_name: str) -> str:
    """Guess category based on service name."""
    s_lower = service_name.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in s_lower:
                return cat
    return "기타"


def heuristic_parse_text(text: str) -> Dict[str, Any]:
    """
    High-accuracy rule-based & regex parser for payment SMS, push alerts, or text notes.
    Acts as a fast path or fallback when LLM is unavailable.
    """
    clean_text, pii_detected, pii_types = detect_and_mask_pii(text)
    
    # Extract amount
    amounts = extract_regex_amounts(clean_text)
    amount = amounts[0] if amounts else 0
    
    # Extract service name
    service_name = ""
    # Check known service keywords
    all_kws = []
    for cat, kws in CATEGORY_KEYWORDS.items():
        all_kws.extend(kws)
    
    found_services = []
    for kw in all_kws:
        idx = clean_text.lower().find(kw)
        if idx != -1:
            found_services.append((idx, kw))
            
    if found_services:
        found_services.sort(key=lambda x: x[0])
        # Find matching original capitalization/name
        raw_kw = found_services[0][1]
        # Match standard names
        name_map = {
            "넷플릭스": "넷플릭스 (Netflix)", "netflix": "넷플릭스 (Netflix)",
            "유튜브": "유튜브 프리미엄 (YouTube Premium)", "youtube": "유튜브 프리미엄 (YouTube Premium)",
            "chatgpt": "ChatGPT Plus", "챗지피티": "ChatGPT Plus",
            "쿠팡": "쿠팡 와우멤버십", "와우": "쿠팡 와우멤버십", "coupang": "쿠팡 와우멤버십",
            "스포티파이": "스포티파이 (Spotify)", "spotify": "스포티파이 (Spotify)",
            "티빙": "티빙 (TVING)", "tving": "티빙 (TVING)",
            "웨이브": "웨이브 (Wavve)", "wavve": "웨이브 (Wavve)",
            "디즈니": "디즈니+ (Disney+)", "disney": "디즈니+ (Disney+)",
            "왓챠": "왓챠 (Watcha)", "watcha": "왓챠 (Watcha)",
            "클로드": "Claude Pro", "claude": "Claude Pro",
            "github": "GitHub Copilot", "copilot": "GitHub Copilot", "깃허브": "GitHub Copilot",
            "notion": "노션 (Notion)", "노션": "노션 (Notion)",
            "네이버": "네이버 플러스 멤버십", "네이버플러스": "네이버 플러스 멤버십",
            "밀리의 서재": "밀리의 서재", "밀리": "밀리의 서재",
            "icloud": "iCloud+ (애플)", "아이클라우드": "iCloud+ (애플)"
        }
        service_name = name_map.get(raw_kw, raw_kw.title())
    else:
        # Fallback regex for common SMS format: [XX카드] MM/DD HH:MM <가맹점명> 금액
        sms_match = re.search(r'\]\s*(?:\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}\s+)?([가-힣A-Za-z0-9_\(\)]+)\s+[0-9,]+원', clean_text)
        if sms_match:
            service_name = sms_match.group(1).strip()
        else:
            first_line = clean_text.strip().split('\n')[0]
            service_name = first_line[:30].strip() if first_line else "미확인 서비스"
            
    # Extract billing date (day of month, 1-31)
    billing_date = 1
    has_explicit_date = False
    # Check "매월 N일"
    day_match = re.search(r'(?:매월|매달)?\s*([0-9]{1,2})\s*일', clean_text)
    if day_match:
        try:
            d = int(day_match.group(1))
            if 1 <= d <= 31:
                billing_date = d
                has_explicit_date = True
        except ValueError:
            pass
    else:
        # Check date format: MM/DD or YYYY-MM-DD
        date_match = re.search(r'(?:\d{4}[-./])?(\d{1,2})[-./](\d{1,2})', clean_text)
        if date_match:
            try:
                d = int(date_match.group(2))
                if 1 <= d <= 31:
                    billing_date = d
                    has_explicit_date = True
            except ValueError:
                pass
                
    category = guess_category(service_name)
    
    # Determine confidence score based on recognition quality
    # High confidence (>=0.9) requires both recognized merchant and valid monetary amount
    confidence = 0.2
    if found_services:
        confidence += 0.45
    elif service_name and service_name != "미확인 서비스":
        confidence += 0.15

    if amount > 0:
        confidence += 0.3
        
    if has_explicit_date:
        confidence += 0.05

    confidence = min(0.99, round(confidence, 2))
    
    return {
        "service_name": service_name,
        "category": category,
        "amount": amount,
        "billing_cycle": "월간",
        "billing_date": billing_date,
        "confidence_score": confidence,
        "pii_detected": pii_detected,
        "pii_types": pii_types,
        "clean_text": clean_text
    }


def call_openrouter_api(
    model: str,
    messages: list,
    api_key: str,
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Calls OpenRouter API with Exponential Backoff for HTTP 429.
    PRD Rule: ERR_OPENROUTER_429 -> Exponential Backoff retry then fallback.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "College Student Subscriptions Rebalancing AI"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    delay = 1.0
    for attempt in range(max_retries + 1):
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=12) as response:
                res_body = response.read().decode('utf-8')
                return json.loads(res_body)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2.0  # Exponential backoff
                    continue
                else:
                    raise Exception(f"ERR_OPENROUTER_429: Rate limit exceeded for {model} after {max_retries} retries.")
            else:
                err_msg = e.read().decode('utf-8', errors='ignore')
                raise Exception(f"OpenRouter HTTP {e.code}: {err_msg}")
        except Exception as e:
            if "ERR_OPENROUTER_429" in str(e):
                raise
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2.0
                continue
            raise e

    raise Exception("ERR_OPENROUTER_REQUEST_FAILED")


def parse_subscription_with_ai(
    text_content: Optional[str] = None,
    image_base64: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for PRD Step 1 Parsing.
    Supports:
    - Text / SMS / Multiline parsing
    - Image (Base64) OCR parsing
    - PII detection and masking
    - Model fallback: google/gemma-4-26b-a4b-it:free -> gemini-2.0-flash-exp:free
    - Schema: service_name, category, amount, billing_cycle, billing_date, confidence_score
    - Exception policies: ERR_VISION_LOW_CONFIDENCE, ERR_OPENROUTER_429, WARN_PII_DETECTED
    """
    pii_detected = False
    pii_types = []
    sanitized_text = ""
    
    if text_content:
        sanitized_text, pii_detected, pii_types = detect_and_mask_pii(text_content)
        
    system_prompt = """
You are a precise Korean subscription and payment extraction engine.
Extract the subscription details from the given receipt image, payment SMS, or payment screenshot.
You MUST output ONLY a valid JSON object with the following fields:
- service_name: (string) Service or merchant name (e.g., '넷플릭스', '유튜브 프리미엄', 'ChatGPT Plus', '쿠팡 와우')
- category: (string) One of ['OTT', '음원', '생산성/AI', '클라우드/저장소', '쇼핑/멤버십', '도서/교육', '통신/생활', '기타']
- amount: (integer) Monthly or payment amount in KRW (number only, e.g. 17000)
- billing_cycle: (string) '월간' or '연간' or '주간' (default '월간')
- billing_date: (integer) Day of the month for renewal/billing (1-31). If today or only payment date is known, use that day of the month.
- confidence_score: (float) Detection confidence from 0.0 to 1.0 (e.g. 0.95)

Rules:
1. If the image is blurry, unrecognizable, or missing payment details, set confidence_score <= 0.4.
2. Return ONLY clean JSON without markdown code blocks.
"""

    # If no API key is set, use local smart heuristic & OCR simulation
    if not api_key or api_key.strip() == "":
        res = heuristic_parse_text(sanitized_text if sanitized_text else "샘플 구독 결제")
        res["source"] = "heuristic_engine"
        res["model_used"] = "Local Smart Regex & OCR Engine"
        
        # Check low confidence rule
        if res.get("confidence_score", 0) < 0.6:
            res["error_code"] = "ERR_VISION_LOW_CONFIDENCE"
            res["error_message"] = "저화질 또는 정보 부족으로 정확한 파싱이 어렵습니다. 수동 입력을 권장합니다."
        return res

    # Build prompt messages
    user_content = []
    if sanitized_text:
        user_content.append({"type": "text", "text": f"입력 결제 텍스트:\n{sanitized_text}"})
        
    if image_base64:
        # Base64 can be data:image/png;base64,... or pure base64
        if not image_base64.startswith("data:"):
            img_url = f"data:image/jpeg;base64,{image_base64}"
        else:
            img_url = image_base64
        user_content.append({
            "type": "image_url",
            "image_url": {"url": img_url}
        })
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content if len(user_content) > 1 or image_base64 else (sanitized_text or "구독 결제 내역 분석")}
    ]

    primary_model = "google/gemma-4-26b-a4b-it:free"
    fallback_model = "gemini-2.0-flash-exp:free"
    
    last_error = None
    response_json = None
    model_used = primary_model

    # Try Primary Model
    try:
        raw_res = call_openrouter_api(primary_model, messages, api_key, max_retries=1)
        response_json = raw_res
    except Exception as e:
        last_error = e
        # If rate limit or other error, fallback to fallback_model
        try:
            model_used = fallback_model
            raw_res = call_openrouter_api(fallback_model, messages, api_key, max_retries=1)
            response_json = raw_res
        except Exception as e2:
            last_error = e2
            # Complete failure of external API -> fallback to local heuristic
            res = heuristic_parse_text(sanitized_text if sanitized_text else "")
            res["source"] = "heuristic_fallback"
            res["api_error"] = str(last_error)
            res["model_used"] = f"Fallback (API Error: {str(e2)[:40]})"
            if "ERR_OPENROUTER_429" in str(last_error) or "ERR_OPENROUTER_429" in str(e2):
                res["warning_code"] = "ERR_OPENROUTER_429"
                res["warning_message"] = "OpenRouter Rate Limit 발생으로 로컬 보조 파서로 전환되었습니다."
            return res

    # Parse response content
    try:
        content_str = response_json["choices"][0]["message"]["content"]
        # Remove potential markdown fences
        content_str = re.sub(r'^```(?:json)?\s*', '', content_str.strip())
        content_str = re.sub(r'\s*```$', '', content_str.strip())
        parsed = json.loads(content_str)
        
        parsed["source"] = "openrouter_api"
        parsed["model_used"] = model_used
        parsed["pii_detected"] = pii_detected
        parsed["pii_types"] = pii_types
        
        # Enforce types & defaults
        parsed["amount"] = int(parsed.get("amount", 0))
        parsed["billing_date"] = int(parsed.get("billing_date", 1))
        parsed["confidence_score"] = float(parsed.get("confidence_score", 0.9))
        parsed["service_name"] = str(parsed.get("service_name", "미확인 서비스"))
        parsed["category"] = str(parsed.get("category", "기타"))
        parsed["billing_cycle"] = str(parsed.get("billing_cycle", "월간"))
        
        # Check low confidence rule: ERR_VISION_LOW_CONFIDENCE
        if parsed["confidence_score"] < 0.6:
            parsed["error_code"] = "ERR_VISION_LOW_CONFIDENCE"
            parsed["error_message"] = "저화질 또는 정보 부족으로 정확한 파싱이 어렵습니다. 수동 입력을 권장합니다."
            
        return parsed
    except Exception as parse_err:
        # JSON parse failed from model response -> fallback to heuristic
        res = heuristic_parse_text(sanitized_text if sanitized_text else "")
        res["source"] = "heuristic_recovery"
        res["model_used"] = model_used
        return res
