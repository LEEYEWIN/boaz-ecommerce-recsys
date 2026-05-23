from fastapi import APIRouter
from services.redis_client import get_realtime_recommendation, get_main_recommendation

router = APIRouter()

@router.get("/")
def get_recommendation(user_id: str, session_id: str):
    realtime_result = get_realtime_recommendation(session_id)

    if realtime_result:
        return {
            "source": "realtime",
            "data": realtime_result
        }

    main_result = get_main_recommendation(user_id)

    return {
        "source": "main",
        "data": main_result
    }