from kafka import KafkaProducer
from google.cloud import bigquery
import json, time, random, uuid, numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

bq_client = bigquery.Client(project="boaz-ecommerce-rec")

# 페르소나 설정
PERSONAS = {
    "minimalist_office_woman": {
        "activity_level": "mid",
        "category_weight": 0.75,
        "noise_ratio": 0.15,
        "dwell_lognormal": (3.5, 0.5),
    },
    "trendy_young_woman": {
        "activity_level": "high",
        "category_weight": 0.70,
        "noise_ratio": 0.25,
        "dwell_lognormal": (2.8, 0.5),
    },
    "sporty_active": {
        "activity_level": "high",
        "category_weight": 0.80,
        "noise_ratio": 0.20,
        "dwell_lognormal": (3.0, 0.5),
    },
    "classic_man": {
        "activity_level": "low",
        "category_weight": 0.80,
        "noise_ratio": 0.10,
        "dwell_lognormal": (4.2, 0.5),
    },
    "home_beauty": {
        "activity_level": "mid",
        "category_weight": 0.75,
        "noise_ratio": 0.15,
        "dwell_lognormal": (3.2, 0.5),
    },
    "maternity_woman": {
        "activity_level": "low",
        "category_weight": 0.85,
        "noise_ratio": 0.10,
        "dwell_lognormal": (3.8, 0.5),
    },
    "casual_hood_man": {
        "activity_level": "high",
        "category_weight": 0.75,
        "noise_ratio": 0.20,
        "dwell_lognormal": (2.5, 0.5),
    },
    "lingerie_woman": {
        "activity_level": "mid",
        "category_weight": 0.85,
        "noise_ratio": 0.10,
        "dwell_lognormal": (3.5, 0.5),
    },
}

ACTIVITY_CLICKS = {
    "high": (15, 30),
    "mid":  (5, 15),
    "low":  (1, 5),
}

PATTERN_CART_PROB = {
    "Loyal_Repeat_Buyer": 0.20,
    "Payday_Spender":     0.15,
    "Sale_Chaser":        0.10,
    "Window_Shopper":     0.05,
    "Weekend_Hunter":     0.10,
}

print("유저 정보 로드 중...")
df_users = bq_client.query("""
    SELECT user_id, persona_type, shopping_pattern
    FROM `boaz-ecommerce-rec.ecommerce_logs.user_info`
""").to_dataframe()
print(f"총 {len(df_users)}명 로드 완료")

print("페르소나별 인기 상품 로드 중...")
df_articles = bq_client.query("""
    SELECT persona_type, article_id, COUNT(*) as cnt
    FROM `boaz-ecommerce-rec.ecommerce_logs.user_log`
    WHERE event_type = 'click'
    GROUP BY persona_type, article_id
    ORDER BY persona_type, cnt DESC
""").to_dataframe()

# 전체 인기 상품 (noise용)
all_articles = df_articles["article_id"].tolist()

persona_articles = {}
for persona, group in df_articles.groupby("persona_type"):
    persona_articles[persona] = group["article_id"].tolist()[:100]
print("상품 로드 완료")

sample_users = df_users.sample(100).to_dict(orient="records")
print(f"\n시뮬레이션 시작! {len(sample_users)}명 유저")

def simulate_user(user):
    user_id    = user["user_id"]
    persona    = user["persona_type"]
    pattern    = user["shopping_pattern"]
    session_id = str(uuid.uuid4())

    config   = PERSONAS.get(persona, PERSONAS["minimalist_office_woman"])
    articles = persona_articles.get(persona, [])
    if not articles:
        return

    # activity_level에 따라 클릭 수 결정
    min_clicks, max_clicks = ACTIVITY_CLICKS[config["activity_level"]]
    n_clicks = random.randint(min_clicks, max_clicks)

    print(f"[{persona}] {user_id[:8]}... → {n_clicks}개 클릭")

    for i in range(n_clicks):
        # category_weight 기반으로 선호 카테고리 or 노이즈 선택
        if random.random() < config["category_weight"]:
            article_id = random.choice(articles)
        else:
            article_id = random.choice(all_articles)

        # dwell_time 로그정규분포로 생성
        mu, sigma = config["dwell_lognormal"]
        dwell_time = round(np.random.lognormal(mu, sigma), 1)
        if dwell_time < 3:
            continue  # 바운스 제외

        event_type = "click"

        # add_to_cart 확률
        cart_prob = PATTERN_CART_PROB.get(pattern, 0.10)
        if random.random() < cart_prob:
            event_type = "add_to_cart"

        # purchase 확률 (add_to_cart 후 5%)
        if event_type == "add_to_cart" and random.random() < 0.05:
            event_type = "purchase"

        log = {
            "user_id":      user_id,
            "session_id":   session_id,
            "event_type":   event_type,
            "article_id":   str(article_id),
            "persona_type": persona,
            "dwell_time":   dwell_time if event_type == "click" else None,
            "timestamp":    datetime.now().isoformat()
        }
        producer.send("user-log", value=log)
        time.sleep(random.uniform(0.1, 0.3))

    print(f"  완료: {user_id[:8]}...")

with ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(simulate_user, sample_users)

producer.flush()
print("\n전체 시뮬레이션 완료!")