from kafka import KafkaConsumer
from google.cloud import bigquery
import json, time, requests, threading
from collections import defaultdict

KAFKA_BROKER    = "localhost:9092"
FASTAPI_URL     = "http://localhost:8000/predict"
SESSION_TIMEOUT = 10  # 30분 (테스트시 10으로 변경)

consumer = KafkaConsumer(
    "user-log",
    bootstrap_servers=KAFKA_BROKER,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    auto_offset_reset="latest",
    group_id="session-consumer",
    consumer_timeout_ms=1000
)

bq_client = bigquery.Client(project="boaz-ecommerce-rec")

sessions      = defaultdict(list)
session_times = {}
lock          = threading.Lock()

def save_to_bigquery(session_id, seq, persona_type):
    rows = [{
        "session_id":   session_id,
        "user_id":      seq[0].get("user_id", "unknown"),
        "persona_type": persona_type,
        "sequence":     json.dumps([
            {"article_id": s["article_id"], "event": s["event_type"]}
            for s in seq
        ]),
        "timestamp":    seq[-1].get("timestamp", "")
    }]
    try:
        errors = bq_client.insert_rows_json(
            "boaz-ecommerce-rec.ecommerce_logs.session_log", rows
        )
        if errors:
            print(f"[BigQuery 오류] {errors}")
        else:
            print(f"[BigQuery 저장] {session_id[:8]}... → {len(seq)}건")
    except Exception as e:
        print(f"[BigQuery 실패] {e}")

def flush_session(session_id):
    with lock:
        seq = sessions.pop(session_id, [])
        session_times.pop(session_id, None)
    if not seq:
        return

    persona_type = seq[0].get("persona_type", "unknown")
    payload = {
        "session_id":   session_id,
        "persona_type": persona_type,
        "sequence":     [{"article_id": s["article_id"], "event": s["event_type"]} for s in seq]
    }
    try:
        res = requests.post(FASTAPI_URL, json=payload, timeout=5)
        print(f"[세션 종료] {session_id[:8]}... → {len(seq)}건 → 추론 완료: {res.status_code}")
    except Exception as e:
        print(f"[추론 실패] {e}")

    save_to_bigquery(session_id, seq, persona_type)

def flush_expired():
    while True:
        time.sleep(2)
        now = time.time()
        with lock:
            expired = [sid for sid, t in session_times.items() if now - t > SESSION_TIMEOUT]
        for sid in expired:
            flush_session(sid)

t = threading.Thread(target=flush_expired, daemon=True)
t.start()

print("Kafka Consumer 시작. 로그 기다리는 중...")

while True:
    for msg in consumer:
        log = msg.value
        session_id = log.get("session_id")
        if not session_id:
            continue
        with lock:
            sessions[session_id].append(log)
            session_times[session_id] = time.time()
        print(f"[로그 수신] {log.get('event_type')} | {log.get('article_id')} | session: {session_id[:8]}...")