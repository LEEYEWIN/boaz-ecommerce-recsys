from kafka import KafkaProducer
import json, time, random, uuid
from datetime import datetime

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

# 테스트용 유저/상품 목록
USER_ID     = "45c20056-944b-40ce-84c5-62897512f922"
PERSONA     = "minimalist_office_woman"
SESSION_ID  = str(uuid.uuid4())
ARTICLES    = ["860395001", "863775001", "721287004", "855531007", "826197001"]
EVENT_TYPES = ["click", "click", "click", "add_to_cart"]

print(f"더미 로그 발생 시작 | session_id: {SESSION_ID[:8]}...")

for i in range(10):
    log = {
        "user_id":      USER_ID,
        "session_id":   SESSION_ID,
        "event_type":   random.choice(EVENT_TYPES),
        "article_id":   random.choice(ARTICLES),
        "persona_type": PERSONA,
        "timestamp":    datetime.now().isoformat()
    }
    producer.send("user-log", value=log)
    print(f"[전송] {log['event_type']} | {log['article_id']}")
    time.sleep(1)

producer.flush()
print("더미 로그 전송 완료!")