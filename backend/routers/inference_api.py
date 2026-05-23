from fastapi import APIRouter
from ml_model.inference import predict, build_dynamic_weights
from services.redis_client import set_realtime_recommendation

router = APIRouter()

@router.post("/session")
def inference_session(payload: dict):
    session_id = payload["session_id"]
    user_id = payload["user_id"]
    persona_type = payload.get("persona_type")
    sequence = payload["sequence"]

    dynamic_weights = build_dynamic_weights(sequence)

    recommended_items = predict(
        sequence=sequence,
        top_k=10,
        dynamic_weights=dynamic_weights
    )

    result = {
        "user_id": user_id,
        "session_id": session_id,
        "persona_type": persona_type,
        "recommended_items": recommended_items
    }

    set_realtime_recommendation(session_id, result)

    return {
        "status": "ok",
        "saved_key": f"{session_id}_realtime",
        "result": result
    }