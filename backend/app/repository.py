from datetime import datetime


ISSUES = [
    {
        "id": 1,
        "title": "미국 기준금리 동결 가능성 확대, 글로벌 증시 변동성 증가",
        "source": "Reuters API",
        "category": "금융",
        "time": "3분 전",
        "report_status": "전송 완료",
        "summary": "미 연준 관련 발언과 물가 지표가 혼재되며 금리 동결 전망이 우세해졌고, 기술주 중심으로 단기 변동성이 확대되고 있습니다.",
        "channel": "Slack",
        "destination": "#exec-briefing",
        "preview_message": "*[긴급 이슈 브리핑]* 미국 기준금리 동결 가능성 확대, 글로벌 증시 변동성 증가\n요약: 미 연준 관련 발언과 물가 지표가 혼재되며 금리 동결 전망이 우세해졌고, 기술주 중심으로 단기 변동성이 확대되고 있습니다.",
    },
    {
        "id": 2,
        "title": "국내 반도체 수출 회복세, 공급망 리스크는 여전",
        "source": "NewsAPI",
        "category": "산업",
        "time": "12분 전",
        "report_status": "전송 대기",
        "summary": "반도체 수출이 회복 흐름을 보이고 있으나 원자재 가격과 특정 국가 규제 이슈가 동시에 부각되며 공급망 불확실성은 남아 있습니다.",
        "channel": "Slack",
        "destination": "#exec-briefing",
        "preview_message": "*[긴급 이슈 브리핑]* 국내 반도체 수출 회복세, 공급망 리스크는 여전\n요약: 반도체 수출이 회복 흐름을 보이고 있으나 원자재 가격과 특정 국가 규제 이슈가 동시에 부각되며 공급망 불확실성은 남아 있습니다.",
    },
    {
        "id": 3,
        "title": "유럽 AI 규제 후속안 발표 임박, 플랫폼 기업 대응 강화",
        "source": "SerpAPI",
        "category": "정책",
        "time": "25분 전",
        "report_status": "생성 완료",
        "summary": "유럽 규제기관의 후속 가이드라인 발표가 예고되면서 주요 플랫폼 기업들이 모델 투명성과 데이터 거버넌스 대응안을 조정하고 있습니다.",
        "channel": "Slack",
        "destination": "#exec-briefing",
        "preview_message": "*[긴급 이슈 브리핑]* 유럽 AI 규제 후속안 발표 임박, 플랫폼 기업 대응 강화\n요약: 유럽 규제기관의 후속 가이드라인 발표가 예고되면서 주요 플랫폼 기업들이 모델 투명성과 데이터 거버넌스 대응안을 조정하고 있습니다.",
    },
]

DELIVERY_LOGS = [
    {
        "id": 1,
        "issue_id": 1,
        "title": "미국 기준금리 동결 가능성 확대",
        "channel": "Slack",
        "time": "09:41",
        "status": "성공",
        "delivered_at": datetime(2026, 4, 16, 9, 41, 0),
    },
    {
        "id": 2,
        "issue_id": 2,
        "title": "국내 반도체 수출 회복세",
        "channel": "Slack",
        "time": "09:35",
        "status": "대기",
        "delivered_at": None,
    },
    {
        "id": 3,
        "issue_id": 3,
        "title": "유럽 AI 규제 후속안 발표 임박",
        "channel": "Slack",
        "time": "09:12",
        "status": "실패",
        "delivered_at": datetime(2026, 4, 16, 9, 12, 0),
    },
]


def list_issues() -> list[dict]:
    return [
        {
            "id": issue["id"],
            "title": issue["title"],
            "source": issue["source"],
            "category": issue["category"],
            "time": issue["time"],
            "report_status": issue["report_status"],
        }
        for issue in ISSUES
    ]


def get_issue_preview(issue_id: int) -> dict | None:
    for issue in ISSUES:
        if issue["id"] == issue_id:
            return {
                "issue_id": issue["id"],
                "title": issue["title"],
                "source": issue["source"],
                "channel": issue["channel"],
                "destination": issue["destination"],
                "summary": issue["summary"],
                "preview_message": issue["preview_message"],
            }
    return None


def list_delivery_logs() -> list[dict]:
    return DELIVERY_LOGS
