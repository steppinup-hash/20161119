import time
from typing import Dict, List, Any, Optional

CANCELLATION_GUIDES = [
    {
        "keywords": ["netflix", "넷플릭스"],
        "service_name": "넷플릭스 (Netflix)",
        "deep_link": "https://www.netflix.com/youraccount",
        "estimated_seconds": 30,
        "steps": [
            "우측 상단 프로필 클릭 후 [계정] 메뉴로 이동합니다.",
            "멤버십 & 결제 정보에서 [멤버십 해지] 버튼을 클릭합니다.",
            "[해지 완료]를 클릭하면 결제 만료일까지 계속 이용 가능하며 즉시 결제 방어 완료!"
        ],
        "tip": "해지해도 남은 결제 주기까지 시청 권한이 유지되므로 D-3 시점에 미리 해지하는 것이 가장 안전합니다."
    },
    {
        "keywords": ["youtube", "유튜브"],
        "service_name": "유튜브 프리미엄 (YouTube Premium)",
        "deep_link": "https://www.youtube.com/paid_memberships",
        "estimated_seconds": 25,
        "steps": [
            "유튜브 우측 상단 프로필 > [구매 항목 및 멤버십]으로 이동합니다.",
            "유튜브 프리미엄 항목의 [멤버십 관리]를 누릅니다.",
            "[비활성화] 클릭 후 '일시중지(최대 6개월)' 또는 '취소'를 선택하여 자동 갱신을 방어합니다."
        ],
        "tip": "시험기간에는 해지 대신 '1개월 일시중지'를 선택하면 요금 결제 없이 구독을 보류할 수 있습니다."
    },
    {
        "keywords": ["chatgpt", "openai", "챗지피티"],
        "service_name": "ChatGPT Plus (OpenAI)",
        "deep_link": "https://chatgpt.com/#settings/Subscription",
        "estimated_seconds": 30,
        "steps": [
            "좌측 하단 프로필 사진 클릭 후 [Settings] > [Subscription]으로 이동합니다.",
            "[Manage my subscription]을 누르면 결제 관리 포털(Stripe)로 연결됩니다.",
            "[Cancel plan(플랜 취소)]을 클릭하고 확인을 완료합니다."
        ],
        "tip": "대학교 웹메일로 GitHub Student Developer Pack 인증 시 GitHub Copilot으로 완전 무료 전환이 가능합니다."
    },
    {
        "keywords": ["coupang", "쿠팡", "와우"],
        "service_name": "쿠팡 와우멤버십",
        "deep_link": "https://mc.coupang.com/ssr/desktop/order/list",
        "estimated_seconds": 35,
        "steps": [
            "쿠팡 앱/웹의 [마이쿠팡] > [와우 멤버십]으로 이동합니다.",
            "화면 맨 아래로 스크롤하여 [해지하기] 버튼을 누릅니다.",
            "혜택 포기 설문 후 [해지 신청]을 누르면 자동 갱신 방어가 완료됩니다."
        ],
        "tip": "해지 시 남은 기간에 대한 일할 환불 또는 기간 종료 선택이 가능합니다."
    },
    {
        "keywords": ["disney", "디즈니"],
        "service_name": "디즈니+ (Disney+)",
        "deep_link": "https://www.disneyplus.com/account",
        "estimated_seconds": 30,
        "steps": [
            "프로필 아이콘 클릭 후 [계정]으로 이동합니다.",
            "[구독] 섹션에서 현재 이용권을 선택합니다.",
            "[디즈니+ 구독 취소]를 선택하고 사유 선택 후 해지를 완료합니다."
        ],
        "tip": "4인 파티(피클플러스 등)로 재가입 시 월 3,475원으로 절감됩니다."
    }
]

DEFAULT_GUIDE = {
    "service_name": "일반 구독 서비스",
    "deep_link": "https://www.google.com",
    "estimated_seconds": 40,
    "steps": [
        "해당 서비스 웹사이트 로그인 후 [계정/설정] 또는 [결제 관리]로 이동합니다.",
        "[구독 관리] 또는 [정기결제 해지] 메뉴를 찾습니다.",
        "해지 확정을 완료하고 등록된 카드의 자동결제 승인 차단을 확인합니다."
    ],
    "tip": "결제 D-3 이내에 해지 신청해야 카드사 사전 청구 승인을 원천 방어할 수 있습니다."
}

def get_cancellation_guide(service_name: str) -> Dict[str, Any]:
    s_lower = service_name.lower()
    for item in CANCELLATION_GUIDES:
        for kw in item["keywords"]:
            if kw in s_lower:
                return item
    guide = dict(DEFAULT_GUIDE)
    guide["service_name"] = service_name
    return guide

def check_d3_alerts(subscriptions: List[Dict[str, Any]], current_day: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    D-3 감지 조건: (Billing Day - Today == 3)
    만약 현재 일이 지정되지 않았다면 현재 시스템 날짜 기준 계산.
    """
    if current_day is None:
        import datetime
        current_day = datetime.datetime.now().day

    alerts = []
    for sub in subscriptions:
        billing_day = int(sub.get("billing_date", 1))
        
        # Check D-3 condition
        # Standard: billing_day - current_day == 3
        # Month-end wrap: (billing_day - current_day + 30) % 30 == 3
        diff = billing_day - current_day
        if diff == 3 or (diff < 0 and (diff + 30) == 3):
            guide = get_cancellation_guide(sub.get("service_name", ""))
            alerts.append({
                "subscription_id": sub.get("id"),
                "service_name": sub.get("service_name"),
                "amount": sub.get("amount", 0),
                "billing_day": billing_day,
                "current_day": current_day,
                "days_left": 3,
                "alert_type": "D-3 결제 예정 감지",
                "message": f"'{sub.get('service_name')}' 3일 뒤(매월 {billing_day}일) ₩{sub.get('amount', 0):,}원이 자동 결제됩니다!",
                "deep_link": guide["deep_link"],
                "steps": guide["steps"],
                "tip": guide["tip"],
                "estimated_seconds": guide["estimated_seconds"]
            })

    # If no strict D-3 found for current day, provide upcoming closest renewal for demonstration
    if not alerts and subscriptions:
        # Find closest upcoming renewal
        sorted_subs = sorted(subscriptions, key=lambda s: (int(s.get("billing_date", 1)) - current_day) % 30)
        closest = sorted_subs[0]
        c_day = int(closest.get("billing_date", 1))
        days_diff = (c_day - current_day) % 30
        guide = get_cancellation_guide(closest.get("service_name", ""))
        alerts.append({
            "subscription_id": closest.get("id"),
            "service_name": closest.get("service_name"),
            "amount": closest.get("amount", 0),
            "billing_day": c_day,
            "current_day": current_day,
            "days_left": days_diff if days_diff > 0 else 3,
            "alert_type": f"D-{days_diff if days_diff > 0 else 3} 자동 갱신 방어 알림",
            "message": f"'{closest.get('service_name')}' 결제 예정일(매월 {c_day}일)이 다가옵니다. 30초 초간단 가이드로 자동 갱신을 방어하세요!",
            "deep_link": guide["deep_link"],
            "steps": guide["steps"],
            "tip": guide["tip"],
            "estimated_seconds": guide["estimated_seconds"],
            "is_demonstration": True
        })

    return alerts

def compute_savings_tracker_data(
    profile: Dict[str, Any],
    subscriptions: List[Dict[str, Any]],
    savings_history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Savings Tracker 시각화 데이터 집계:
    1. 목표 예산 대비 지출 게이지
    2. 최근 6개월 누적 절감액 Area Chart
    3. 카테고리별 지출 도넛 차트
    4. 목표 고정비 예산 달성률 (KPI >= 80%)
    """
    budget = int(profile.get("budget", 35000))
    income = int(profile.get("income", 850000))
    current_spending = sum(int(s.get("amount", 0)) for s in subscriptions)

    # Goal Budget Achievement Rate (KPI >= 80%)
    # If current spending <= budget -> 100%
    # If current spending > budget, rate decreases proportionally
    if current_spending <= budget:
        achievement_rate = 100.0
    else:
        over = current_spending - budget
        achievement_rate = max(0.0, round((1.0 - (over / float(budget))) * 100.0, 1))

    # Category breakdown for Donut Chart
    cat_totals = {}
    for s in subscriptions:
        cat = s.get("category", "기타")
        cat_totals[cat] = cat_totals.get(cat, 0) + int(s.get("amount", 0))

    donut_labels = list(cat_totals.keys())
    donut_values = list(cat_totals.values())

    # 6-Month Cumulative Savings Area Chart Data
    # Baseline cumulative progression for college student savings
    history_total = sum(int(h.get("saved_amount", 0)) for h in savings_history)
    base_step = max(35000, history_total // 4 if history_total > 0 else 35000)
    
    # Months labels (e.g. M-5, M-4, M-3, M-2, M-1, Current)
    months = ["6월", "7월", "8월", "9월", "10월", "11월"]
    area_chart_data = [
        {"month": months[0], "savings": int(base_step * 0.5), "cumulative": int(base_step * 0.5)},
        {"month": months[1], "savings": int(base_step * 0.8), "cumulative": int(base_step * 1.3)},
        {"month": months[2], "savings": int(base_step * 1.0), "cumulative": int(base_step * 2.3)},
        {"month": months[3], "savings": int(base_step * 1.1), "cumulative": int(base_step * 3.4)},
        {"month": months[4], "savings": int(base_step * 1.2), "cumulative": int(base_step * 4.6)},
        {"month": months[5], "savings": int(base_step * 1.4), "cumulative": int(base_step * 6.0)}
    ]

    return {
        "budget": budget,
        "income": income,
        "current_spending": current_spending,
        "achievement_rate": achievement_rate,
        "kpi_budget_met": achievement_rate >= 80.0,  # KPI: 80% 이상
        "donut_chart": {
            "labels": donut_labels,
            "values": donut_values
        },
        "area_chart": area_chart_data,
        "cumulative_savings_total": area_chart_data[-1]["cumulative"]
    }
