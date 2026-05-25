from fastapi import APIRouter
from services.redis_client import get_realtime_recommendation, get_main_recommendation, get

router = APIRouter()

@router.get("/")
def get_recommendation(user_id: str, session_id: str):
    realtime_result = get_realtime_recommendation(session_id)

    if realtime_result:
        return {
            "source": "realtime",
            "ab_group": get(f"{user_id}_ab_group"),
            "data": realtime_result
        }

    # A/B 분기
    ab_group = get(f"{user_id}_ab_group")

    if ab_group == "A":
        import json
        raw = get("global_popular")
        main_result = json.loads(raw) if raw else []
        source = "popular"
    else:
        main_result = get_main_recommendation(user_id)
        source = "personalized"

    return {
        "source": source,
        "ab_group": ab_group,
        "data": main_result
    }
