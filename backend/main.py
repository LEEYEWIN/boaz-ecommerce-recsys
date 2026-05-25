import os
import sys
import json
import uuid
import time
import redis
import pandas as pd

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import bigquery

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "ml_model"))
sys.path.insert(0, BASE_DIR)

from services.kafka_producer import send_log
from inference import predict
from post_process import build_dynamic_weights

load_dotenv(os.path.join(BASE_DIR, ".env"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

print("articles 데이터 로드 중...")
bq_client = bigquery.Client(project="boaz-ecommerce-rec")
articles_df = bq_client.query("""
    SELECT article_id, prod_name, product_type_name,
           graphical_appearance_name, colour_group_name, detail_desc
    FROM `boaz-ecommerce-rec.ecommerce_logs.articles`
""").to_dataframe()

articles_df = articles_df.drop_duplicates(subset="article_id")
articles_dict = articles_df.set_index("article_id").to_dict(orient="index")
print(f"articles 로드 완료: {len(articles_dict)}개")


class SequenceItem(BaseModel):
    article_id: str
    event: str


class PredictRequest(BaseModel):
    session_id: str
    persona_type: str
    sequence: list[SequenceItem]


SESSION_TIMEOUT = 30 * 60  # 30분 (초 단위)

class LogEvent(BaseModel):
    user_id: str
    session_id: str
    event_type: str
    article_id: str
    timestamp: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/articles/{article_id}")
async def get_article(article_id: str):
    info = articles_dict.get(int(article_id)) or articles_dict.get(article_id)
    if not info:
        return {"article_id": article_id, "prod_name": article_id, "image_url": ""}

    aid = str(article_id).zfill(10)
    image_url = f"https://image.hm.com/assets/hm/{aid[1:3]}/{aid[3:5]}/{aid}.jpg"

    return {
        "article_id":                article_id,
        "prod_name":                 info.get("prod_name", ""),
        "product_type_name":         info.get("product_type_name", ""),
        "graphical_appearance_name": info.get("graphical_appearance_name", ""),
        "colour_group_name":         info.get("colour_group_name", ""),
        "detail_desc":               info.get("detail_desc", ""),
        "image_url":                 image_url
    }


@app.post("/predict")
async def predict_endpoint(req: PredictRequest):
    seq_dicts = [s.dict() for s in req.sequence]
    weights = build_dynamic_weights(seq_dicts)
    results = predict(seq_dicts, top_k=10, dynamic_weights=weights)
    redis_key = f"{req.session_id}_realtime"
    r.setex(redis_key, 3600, json.dumps({"recommended_items": results}))
    return {
        "session_id": req.session_id,
        "recommended_items": results,
        "source": "model"
    }


def check_and_refresh_session(user_id: str, current_session_id: str) -> str:
    last_event_key = f"{user_id}_last_event_time"
    now = time.time()
    last_event_time = r.get(last_event_key)

    if last_event_time and (now - float(last_event_time)) > SESSION_TIMEOUT:
        new_session_id = str(uuid.uuid4())
        r.setex(last_event_key, SESSION_TIMEOUT * 2, str(now))
        return new_session_id

    r.setex(last_event_key, SESSION_TIMEOUT * 2, str(now))
    return current_session_id


def update_impression_clicked(session_id: str, article_id: str):
    query = f"""
        UPDATE `boaz-ecommerce-rec.ecommerce_logs.impression_log`
        SET is_clicked = TRUE
        WHERE session_id = '{session_id}' AND article_id = '{article_id}'
    """
    bq_client.query(query)


@app.post("/api/log/event")
async def log_event(event: LogEvent):
    session_id = check_and_refresh_session(event.user_id, event.session_id)

    if event.event_type == "click":
        update_impression_clicked(session_id, event.article_id)

    log_data = {
        "user_id":    event.user_id,
        "session_id": session_id,
        "event_type": event.event_type,
        "article_id": event.article_id,
        "timestamp":  event.timestamp,
    }
    send_log("user-log", log_data)
    print(f"Kafka 전송 완료: {event.article_id}")
    return {"status": "ok", "session_id": session_id}


@app.get("/api/recommend/main")
async def get_main_recommend(user_id: str):
    ab_group = r.get(f"{user_id}_ab_group") or "B"

    if ab_group == "A":
        raw = r.get("global_popular")
        recommendations = json.loads(raw) if raw else []
        source = "popular"
    else:
        raw = r.get(f"{user_id}_main")
        recommendations = json.loads(raw) if raw else []
        source = "personalized"

    return {
        "user_id":        user_id,
        "ab_group":       ab_group,
        "recommendations": recommendations,
        "source":         source
    }


@app.get("/api/recommend/realtime")
async def get_realtime_recommend(session_id: str):
    redis_key = f"{session_id}_realtime"
    cached = r.get(redis_key)
    if cached:
        data = json.loads(cached)
        if isinstance(data, dict) and "recommended_items" in data:
            recommendations = data["recommended_items"]
        else:
            recommendations = data
        return {
            "session_id": session_id,
            "recommendations": recommendations,
            "source": "redis"
        }
    return {
        "session_id": session_id,
        "recommendations": [],
        "message": "세션 캐시 없음"
    }


@app.get("/api/recommend/{session_id}")
async def get_recommendation_by_path(session_id: str):
    redis_key = f"{session_id}_realtime"
    cached = r.get(redis_key)
    if cached:
        data = json.loads(cached)
        if isinstance(data, dict) and "recommended_items" in data:
            recommendations = data["recommended_items"]
        else:
            recommendations = data
        return {
            "session_id": session_id,
            "recommended_items": recommendations,
            "source": "redis"
        }
    return {
        "session_id": session_id,
        "recommended_items": [],
        "message": "세션 캐시 없음"
    }