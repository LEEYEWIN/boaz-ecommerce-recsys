from google.cloud import bigquery
import redis, json

client = bigquery.Client(project="boaz-ecommerce-rec")
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

TOP_K = 20

print("BigQuery에서 페르소나별 인기상품 추출 중...")
query = """
SELECT
    persona_type,
    article_id,
    COUNT(*) as click_count
FROM `boaz-ecommerce-rec.ecommerce_logs.user_log`
WHERE event_type = 'click'
GROUP BY persona_type, article_id
ORDER BY persona_type, click_count DESC
"""
df = client.query(query).to_dataframe()
print(f"완료! 총 {len(df)}행")

persona_top = {}
for persona, group in df.groupby("persona_type"):
    top_articles = group.head(TOP_K)["article_id"].tolist()
    persona_top[persona] = top_articles
    print(f"  {persona}: {len(top_articles)}개 추출")

print("\nRedis에 저장 중...")
for persona, articles in persona_top.items():
    key = f"persona_{persona}_main"
    r.setex(key, 86400, json.dumps(articles))
    print(f"  저장 완료: {key}")

# ★ 추가: 전체 인기상품 집계 (A그룹용)
print("\n전체 인기상품 집계 중...")
global_query = """
SELECT article_id, COUNT(*) as score
FROM `boaz-ecommerce-rec.ecommerce_logs.user_log`
WHERE event_type IN ('purchase', 'add_to_cart')
GROUP BY article_id
ORDER BY score DESC
LIMIT 20
"""
global_df = client.query(global_query).to_dataframe()
global_popular = global_df["article_id"].tolist()
r.setex("global_popular", 86400, json.dumps(global_popular))
print(f"전체 인기상품 저장 완료: {global_popular[:3]}...")

print("\n유저별 추천 저장 중...")
query_users = """
SELECT user_id, persona_type, ab_group
FROM `boaz-ecommerce-rec.ecommerce_logs.user_info`
"""
df_users = client.query(query_users).to_dataframe()
print(f"총 유저 수: {len(df_users)}")

for _, row in df_users.iterrows():
    user_id = row["user_id"]
    persona = row["persona_type"]
    ab_group = row["ab_group"]
    articles = persona_top.get(persona, [])

    # ★ 추가: ab_group Redis 저장
    r.set(f"{user_id}_ab_group", ab_group)

    # B그룹만 개인화 추천 저장
    if ab_group == "B":
        key = f"{user_id}_main"
        r.setex(key, 86400, json.dumps(articles))

print(f"완료! {len(df_users)}명 유저 Redis 저장 완료")
print("\n=== 저장된 페르소나 목록 ===")
for persona, articles in persona_top.items():
    print(f"  {persona}: {articles[:3]}... 외 {len(articles)-3}개")
