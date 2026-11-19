import json
import urllib.request
import urllib.error
import time
from typing import Dict, Any, Optional

NOTION_VERSION = "2022-06-28"

def clean_database_id(raw_id: str) -> str:
    db_id = raw_id.strip()
    if "/" in db_id:
        db_id = db_id.split("/")[-1].split("?")[0]
    return db_id

# 1. Notion [Profiles] DB Sync
def sync_profile_to_notion(
    profile: Dict[str, Any],
    api_key: Optional[str] = None,
    database_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Syncs College Student Profile to Notion [Profiles] DB.
    Schema matching PRD Step 3:
      - Student Name: Title
      - Income: Number
      - Budget: Number
    """
    student_name = profile.get("student_name", "김대학")
    income = int(profile.get("income", 850000))
    budget = int(profile.get("budget", 35000))

    if not api_key or not database_id or api_key.strip() == "" or database_id.strip() == "":
        mock_id = f"simulated-profile-{int(time.time())}"
        return {
            "success": True,
            "simulated": True,
            "notion_page_id": mock_id,
            "url": f"https://www.notion.so/{mock_id.replace('-', '')}",
            "message": "노션 [Profiles] DB 동기화가 시뮬레이션 모드로 완료되었습니다."
        }

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    payload = {
        "parent": {"database_id": clean_database_id(database_id)},
        "properties": {
            "Student Name": {
                "title": [{"text": {"content": student_name}}]
            },
            "Income": {
                "number": income
            },
            "Budget": {
                "number": budget
            }
        }
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            page_id = resp_data.get("id", "")
            return {
                "success": True,
                "simulated": False,
                "notion_page_id": page_id,
                "url": resp_data.get("url", f"https://www.notion.so/{page_id.replace('-', '')}"),
                "message": "팀 노션 [Profiles] DB에 대학생 프로필이 정상 동기화되었습니다."
            }
    except Exception as e:
        return {"success": False, "error_code": "NOTION_SYNC_FAILED", "message": str(e)}

# 2. Notion [Subscriptions] DB Sync
def sync_subscription_to_notion(
    subscription: Dict[str, Any],
    api_key: Optional[str] = None,
    database_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Syncs subscription record to Notion [Subscriptions] DB.
    Schema matching PRD Step 3:
      - Service Name: Title
      - Monthly Cost: Number
      - Billing Day: Number
      - Status: Status (default 'Active')
    """
    service_name = subscription.get("service_name", "미지정 구독")
    amount = int(subscription.get("amount", 0))
    billing_day = int(subscription.get("billing_date", 1))
    status_name = subscription.get("status", "Active")
    
    if not api_key or not database_id or api_key.strip() == "" or database_id.strip() == "":
        mock_id = f"simulated-notion-{int(time.time())}-{subscription.get('id', 0)}"
        return {
            "success": True,
            "simulated": True,
            "notion_page_id": mock_id,
            "url": f"https://www.notion.so/{mock_id.replace('-', '')}",
            "message": "노션 [Subscriptions] DB 동기화가 시뮬레이션 모드로 완료되었습니다."
        }
        
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    
    payload = {
        "parent": {"database_id": clean_database_id(database_id)},
        "properties": {
            "Service Name": {
                "title": [{"text": {"content": service_name}}]
            },
            "Monthly Cost": {
                "number": amount
            },
            "Billing Day": {
                "number": billing_day
            },
            "Status": {
                "status": {"name": status_name}
            }
        }
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            page_id = resp_data.get("id", "")
            return {
                "success": True,
                "simulated": False,
                "notion_page_id": page_id,
                "url": resp_data.get("url", f"https://www.notion.so/{page_id.replace('-', '')}"),
                "message": "팀 노션 [Subscriptions] DB에 정상 동기화되었습니다."
            }
    except Exception as e:
        return {"success": False, "error_code": "NOTION_SYNC_FAILED", "message": str(e)}

# 3. Notion [AI Reports] DB Sync
def sync_ai_report_to_notion(
    report: Dict[str, Any],
    api_key: Optional[str] = None,
    database_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Syncs AI Rebalancing Report to Notion [AI Reports] DB.
    Schema matching PRD Step 3:
      - Report Title: Title
      - Monthly Savings: Number
      - Annual Savings: Number
    """
    report_title = report.get("report_title", "2026 대학생 스마트 구독 리밸런싱 AI 보고서")
    monthly_savings = int(report.get("monthly_savings", report.get("total_monthly_savings", 0)))
    annual_savings = int(report.get("annual_savings", report.get("total_annual_savings", monthly_savings * 12)))
    
    if not api_key or not database_id or api_key.strip() == "" or database_id.strip() == "":
        mock_id = f"simulated-report-{int(time.time())}"
        return {
            "success": True,
            "simulated": True,
            "notion_page_id": mock_id,
            "url": f"https://www.notion.so/{mock_id.replace('-', '')}",
            "message": "노션 [AI Reports] DB 연동이 시뮬레이션 모드로 완료되었습니다."
        }
        
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    
    payload = {
        "parent": {"database_id": clean_database_id(database_id)},
        "properties": {
            "Report Title": {
                "title": [{"text": {"content": report_title}}]
            },
            "Monthly Savings": {
                "number": monthly_savings
            },
            "Annual Savings": {
                "number": annual_savings
            }
        }
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            page_id = resp_data.get("id", "")
            return {
                "success": True,
                "simulated": False,
                "notion_page_id": page_id,
                "url": resp_data.get("url", f"https://www.notion.so/{page_id.replace('-', '')}"),
                "message": "팀 노션 [AI Reports] DB에 최적화 리밸런싱 보고서가 동기화되었습니다."
            }
    except Exception as e:
        return {"success": False, "error_code": "NOTION_SYNC_FAILED", "message": str(e)}

# 4. Notion [Savings History] DB Sync
def sync_savings_history_to_notion(
    log: Dict[str, Any],
    api_key: Optional[str] = None,
    database_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Syncs Savings History entry to Notion [Savings History] DB.
    Schema matching PRD Step 3:
      - Log Title: Title
      - Saved Amount: Number
      - Saved Date: Date
    """
    log_title = log.get("log_title", "구독 다이어트 절감 내역")
    saved_amount = int(log.get("saved_amount", 0))
    saved_date = log.get("saved_date", time.strftime("%Y-%m-%d"))

    if not api_key or not database_id or api_key.strip() == "" or database_id.strip() == "":
        mock_id = f"simulated-savings-{int(time.time())}"
        return {
            "success": True,
            "simulated": True,
            "notion_page_id": mock_id,
            "url": f"https://www.notion.so/{mock_id.replace('-', '')}",
            "message": "노션 [Savings History] DB 연동이 시뮬레이션 모드로 완료되었습니다."
        }

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    payload = {
        "parent": {"database_id": clean_database_id(database_id)},
        "properties": {
            "Log Title": {
                "title": [{"text": {"content": log_title}}]
            },
            "Saved Amount": {
                "number": saved_amount
            },
            "Saved Date": {
                "date": {"start": saved_date}
            }
        }
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            page_id = resp_data.get("id", "")
            return {
                "success": True,
                "simulated": False,
                "notion_page_id": page_id,
                "url": resp_data.get("url", f"https://www.notion.so/{page_id.replace('-', '')}"),
                "message": "팀 노션 [Savings History] DB에 절감 내역이 정상 동기화되었습니다."
            }
    except Exception as e:
        return {"success": False, "error_code": "NOTION_SYNC_FAILED", "message": str(e)}
