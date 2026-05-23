from fastapi import APIRouter
from services.kafka_producer import send_log_to_kafka

router = APIRouter()

@router.post("/event")
def collect_event(log: dict):
    topic = "impression-log" if log.get("event_type") == "impression" else "user-log"
    send_log_to_kafka(topic, log)

    return {
        "status": "ok",
        "topic": topic,
        "data": log
    }