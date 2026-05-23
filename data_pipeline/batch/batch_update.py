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

print("\n유저별 추천 저장 중...")
query_users = """
SELECT user_id, persona_type
FROM `boaz-ecommerce-rec.ecommerce_logs.user_info`
"""
df_users = client.query(query_users).to_dataframe()
print(f"총 유저 수: {len(df_users)}")

for _, row in df_users.iterrows():
    user_id  = row["user_id"]
    persona  = row["persona_type"]
    articles = persona_top.get(persona, [])
    key      = f"{user_id}_main"
    r.setex(key, 86400, json.dumps(articles))

print(f"완료! {len(df_users)}명 유저 Redis 저장 완료")
print("\n=== 저장된 페르소나 목록 ===")
for persona, articles in persona_top.items():
    print(f"  {persona}: {articles[:3]}... 외 {len(articles)-3}개")