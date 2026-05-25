from google.cloud import bigquery
import pandas as pd
import numpy as np
import random
import uuid
from datetime import datetime, timedelta, date

PROJECT   = "boaz-ecommerce-rec"
DATASET   = "ecommerce_logs"
TABLE_ID  = f"{PROJECT}.{DATASET}.session_log"
START_DATE = date(2024, 7, 1)
END_DATE   = date(2024, 12, 31)
BATCH_SIZE = 5000

PERSONA_CONFIGS = {
    "minimalist_office_woman": {
        "activity": (5, 15),
        "category_weight": 0.75,
        "dwell_range": (30, 60),
        "patterns": {"Payday_Spender": 0.5, "Loyal_Repeat_Buyer": 0.3, "Window_Shopper": 0.1, "Weekend_Hunter": 0.1},
    },
    "trendy_young_woman": {
        "activity": (15, 30),
        "category_weight": 0.70,
        "dwell_range": (10, 30),
        "patterns": {"Sale_Chaser": 0.4, "Window_Shopper": 0.35, "Weekend_Hunter": 0.15, "Payday_Spender": 0.10},
    },
    "sporty_active": {
        "activity": (15, 30),
        "category_weight": 0.80,
        "dwell_range": (15, 40),
        "patterns": {"Weekend_Hunter": 0.45, "Loyal_Repeat_Buyer": 0.35, "Payday_Spender": 0.20},
    },
    "classic_man": {
        "activity": (1, 5),
        "category_weight": 0.80,
        "dwell_range": (60, 120),
        "patterns": {"Payday_Spender": 0.5, "Loyal_Repeat_Buyer": 0.3, "Weekend_Hunter": 0.2},
    },
    "home_beauty": {
        "activity": (5, 15),
        "category_weight": 0.75,
        "dwell_range": (20, 50),
        "patterns": {"Loyal_Repeat_Buyer": 0.5, "Payday_Spender": 0.3, "Window_Shopper": 0.2},
    },
    "maternity_woman": {
        "activity": (1, 5),
        "category_weight": 0.85,
        "dwell_range": (45, 90),
        "patterns": {"Loyal_Repeat_Buyer": 0.6, "Payday_Spender": 0.25, "Weekend_Hunter": 0.15},
    },
    "casual_hood_man": {
        "activity": (15, 30),
        "category_weight": 0.75,
        "dwell_range": (10, 25),
        "patterns": {"Sale_Chaser": 0.4, "Weekend_Hunter": 0.35, "Window_Shopper": 0.15, "Payday_Spender": 0.10},
    },
    "lingerie_woman": {
        "activity": (5, 15),
        "category_weight": 0.85,
        "dwell_range": (30, 60),
        "patterns": {"Loyal_Repeat_Buyer": 0.55, "Payday_Spender": 0.3, "Window_Shopper": 0.15},
    },
}

PATTERN_PROBS = {
    "Loyal_Repeat_Buyer": {"click_to_cart": 0.20, "cart_to_purchase": 0.60},
    "Payday_Spender":     {"click_to_cart": 0.15, "cart_to_purchase": 0.50},
    "Window_Shopper":     {"click_to_cart": 0.05, "cart_to_purchase": 0.20},
    "Weekend_Hunter":     {"click_to_cart": 0.10, "cart_to_purchase": 0.30},
    "Sale_Chaser":        {"click_to_cart": 0.10, "cart_to_purchase": 0.25},
}

BQ_SCHEMA = [
    bigquery.SchemaField("session_id",       "STRING"),
    bigquery.SchemaField("user_id",          "STRING"),
    bigquery.SchemaField("article_id",       "STRING"),
    bigquery.SchemaField("event_type",       "STRING"),
    bigquery.SchemaField("persona_type",     "STRING"),
    bigquery.SchemaField("shopping_pattern", "STRING"),
    bigquery.SchemaField("ab_group",         "STRING"),
    bigquery.SchemaField("dwell_time",       "INTEGER"),
    bigquery.SchemaField("timestamp",        "TIMESTAMP"),
]


def sample_dwell_time(lo: int, hi: int) -> int:
    mu    = (np.log(lo) + np.log(hi)) / 2
    sigma = 0.35
    val   = np.random.lognormal(mu, sigma)
    return int(np.clip(val, lo, hi))


def get_multipliers(current_date: date, shopping_pattern: str):
    weekday      = current_date.weekday()   # 5=Sat, 6=Sun
    month        = current_date.month
    dom          = current_date.day

    act_mult  = 1.0
    prob_mult = 1.0

    if weekday >= 5 and shopping_pattern == "Weekend_Hunter":
        act_mult *= 2.0

    if 22 <= dom <= 28 and shopping_pattern == "Payday_Spender":
        act_mult  *= 2.0
        prob_mult *= 1.5

    if month == 11 and shopping_pattern == "Sale_Chaser":
        act_mult  *= 2.0
        prob_mult *= 2.0

    return act_mult, prob_mult


def generate_user_day_events(user: dict, current_date: date,
                              persona_articles: dict, all_article_ids: list) -> list:
    user_id          = user["user_id"]
    persona          = user["persona_type"]
    shopping_pattern = user["shopping_pattern"]
    ab_group         = user["ab_group"]

    cfg = PERSONA_CONFIGS.get(persona)
    if not cfg:
        return []

    articles = persona_articles.get(persona, [])
    if not articles:
        return []

    act_mult, prob_mult = get_multipliers(current_date, shopping_pattern)
    probs = PATTERN_PROBS[shopping_pattern]

    act_min, act_max = cfg["activity"]
    n_clicks = int(random.randint(act_min, act_max) * act_mult)

    events = []
    session_id    = str(uuid.uuid4())
    session_start = datetime.combine(current_date, datetime.min.time()).replace(
        hour=random.randint(8, 21), minute=random.randint(0, 59)
    )
    current_time = session_start

    for _ in range(n_clicks):
        # 30분 초과 시 새 세션
        if (current_time - session_start).total_seconds() > 1800:
            session_start = current_time
            session_id    = str(uuid.uuid4())

        # 상품 선택 (카테고리 가중치 vs 노이즈)
        if random.random() < cfg["category_weight"]:
            article_id = str(random.choice(articles[:50]))
        else:
            article_id = str(random.choice(all_article_ids))

        dwell = sample_dwell_time(*cfg["dwell_range"])

        events.append({
            "session_id":       session_id,
            "user_id":          user_id,
            "article_id":       article_id,
            "event_type":       "click",
            "persona_type":     persona,
            "shopping_pattern": shopping_pattern,
            "ab_group":         ab_group,
            "dwell_time":       dwell,
            "timestamp":        current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        })
        current_time += timedelta(seconds=dwell + random.randint(5, 30))

        # click → add_to_cart
        if random.random() < probs["click_to_cart"] * prob_mult:
            events.append({
                "session_id":       session_id,
                "user_id":          user_id,
                "article_id":       article_id,
                "event_type":       "add_to_cart",
                "persona_type":     persona,
                "shopping_pattern": shopping_pattern,
                "ab_group":         ab_group,
                "dwell_time":       0,
                "timestamp":        current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            })
            current_time += timedelta(seconds=random.randint(2, 10))

            # add_to_cart → purchase
            if random.random() < probs["cart_to_purchase"] * prob_mult:
                events.append({
                    "session_id":       session_id,
                    "user_id":          user_id,
                    "article_id":       article_id,
                    "event_type":       "purchase",
                    "persona_type":     persona,
                    "shopping_pattern": shopping_pattern,
                    "ab_group":         ab_group,
                    "dwell_time":       0,
                    "timestamp":        current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                })
                current_time += timedelta(seconds=random.randint(2, 10))

    return events


def bulk_insert(client: bigquery.Client, rows: list):
    if not rows:
        return
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    job_config = bigquery.LoadJobConfig(
        schema=BQ_SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    job = client.load_table_from_dataframe(df, TABLE_ID, job_config=job_config)
    job.result()


def main():
    client = bigquery.Client(project=PROJECT)

    print("유저 정보 로드 중...")
    df_users = client.query("""
        SELECT user_id, persona_type, shopping_pattern, ab_group
        FROM `boaz-ecommerce-rec.ecommerce_logs.user_info`
    """).to_dataframe()
    users = df_users.to_dict(orient="records")
    print(f"총 {len(users)}명 로드 완료")

    print("페르소나별 인기 상품 로드 중...")
    df_articles = client.query("""
        SELECT persona_type, article_id, COUNT(*) as cnt
        FROM `boaz-ecommerce-rec.ecommerce_logs.user_log`
        WHERE event_type = 'click'
        GROUP BY persona_type, article_id
        ORDER BY persona_type, cnt DESC
    """).to_dataframe()

    persona_articles = {}
    all_article_ids  = df_articles["article_id"].unique().tolist()
    for persona, group in df_articles.groupby("persona_type"):
        persona_articles[persona] = group["article_id"].tolist()[:100]
    print(f"상품 로드 완료 (총 {len(all_article_ids)}개)")

    total_days = (END_DATE - START_DATE).days + 1
    buffer     = []
    total_rows = 0

    print(f"\n{START_DATE} ~ {END_DATE} ({total_days}일) 로그 생성 시작\n")

    current_date = START_DATE
    day_num      = 0

    while current_date <= END_DATE:
        day_num += 1
        day_rows = 0

        for user in users:
            events = generate_user_day_events(
                user, current_date, persona_articles, all_article_ids
            )
            buffer.extend(events)
            day_rows += len(events)

        total_rows += day_rows

        # 배치 단위로 BigQuery insert
        if len(buffer) >= BATCH_SIZE:
            bulk_insert(client, buffer)
            buffer = []

        print(f"[{day_num:3d}/{total_days}] {current_date}  "
              f"이벤트 {day_rows:5d}건  누적 {total_rows:,}건")

        current_date += timedelta(days=1)

    # 남은 버퍼 flush
    if buffer:
        bulk_insert(client, buffer)

    print(f"\n완료! 총 {total_rows:,}건 → {TABLE_ID}")


if __name__ == "__main__":
    main()
