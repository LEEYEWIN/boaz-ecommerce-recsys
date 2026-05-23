from kafka import KafkaProducer
from google.cloud import bigquery
import json, time, random, uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

bq_client = bigquery.Client(project="boaz-ecommerce-rec")

# 유저 정보 가져오기
print("유저 정보 로드 중...")
df_users = bq_client.query("""
    SELECT user_id, persona_type, shopping_pattern
    FROM `boaz-ecommerce-rec.ecommerce_logs.user_info`
""").to_dataframe()
print(f"총 {len(df_users)}명 로드 완료")

# 페르소나별 인기 article_id 가져오기
print("페르소나별 인기 상품 로드 중...")
df_articles = bq_client.query("""
    SELECT persona_type, article_id, COUNT(*) as cnt
    FROM `boaz-ecommerce-rec.ecommerce_logs.user_log`
    WHERE event_type = 'click'
    GROUP BY persona_type, article_id
    ORDER BY persona_type, cnt DESC
""").to_dataframe()

persona_articles = {}
for persona, group in df_articles.groupby("persona_type"):
    persona_articles[persona] = group["article_id"].tolist()[:100]
print("상품 로드 완료")

# 100명 랜덤 샘플링
sample_users = df_users.sample(100).to_dict(orient="records")
print(f"\n시뮬레이션 시작! {len(sample_users)}명 유저")

def simulate_user(user):
    user_id    = user["user_id"]
    persona    = user["persona_type"]
    pattern    = user["shopping_pattern"]
    session_id = str(uuid.uuid4())
    articles   = persona_articles.get(persona, [])

    if not articles:
        return

    n_clicks = random.randint(5, 15)
    print(f"[{persona}] {user_id[:8]}... → {n_clicks}개 클릭")

    for i in range(n_clicks):
        article_id = random.choice(articles)
        event_type = "click"

        if pattern == "Loyal_Repeat_Buyer" and random.random() < 0.2:
            event_type = "add_to_cart"
        elif pattern == "Payday_Spender" and random.random() < 0.15:
            event_type = "add_to_cart"
        elif pattern == "Window_Shopper" and random.random() < 0.05:
            event_type = "add_to_cart"
        elif pattern == "Sale_Chaser" and random.random() < 0.1:
            event_type = "add_to_cart"

        log = {
            "user_id":      user_id,
            "session_id":   session_id,
            "event_type":   event_type,
            "article_id":   str(article_id),
            "persona_type": persona,
            "timestamp":    datetime.now().isoformat()
        }
        producer.send("user-log", value=log)
        time.sleep(random.uniform(0.1, 0.5))

    print(f"  완료: {user_id[:8]}...")

# 10명씩 병렬 처리
with ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(simulate_user, sample_users)

producer.flush()
print("\n전체 시뮬레이션 완료!")