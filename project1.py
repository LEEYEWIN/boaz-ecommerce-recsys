from google.cloud import bigquery
import pandas as pd
import pickle, numpy as np
from collections import Counter

client = bigquery.Client(project="boaz-ecommerce-rec")

print("BigQuery 연결 중...")
query_log = """
SELECT user_id, session_id, article_id, event_type,
       timestamp, dwell_time, persona_type
FROM `boaz-ecommerce-rec.ecommerce_logs.user_log`
ORDER BY user_id, timestamp
"""
print("쿼리 전송 완료, 결과 기다리는 중...")
df_log = client.query(query_log).to_dataframe()
print(f"user_log 완료! 총 {len(df_log)}행")

# timestamp 변환
df_log["timestamp"] = pd.to_datetime(df_log["timestamp"])

# 바운스 제거
df_log = df_log[df_log["dwell_time"] >= 3].copy()
print(f"바운스 제거 후: {len(df_log)}행")

# user_info에서 shopping_pattern 가져오기
print("user_info 가져오는 중...")
query_info = """
SELECT user_id, persona_type, shopping_pattern
FROM `boaz-ecommerce-rec.ecommerce_logs.user_info`
"""
df_info = client.query(query_info).to_dataframe()
print(f"user_info 완료! 총 {len(df_info)}행")

# shopping_pattern 매핑
user_pattern_map = dict(zip(df_info["user_id"], df_info["shopping_pattern"]))

# article_id → 정수 인덱스 매핑
all_articles = df_log["article_id"].unique().tolist()
article2idx  = {a: i+2 for i, a in enumerate(all_articles)}
idx2article  = {i: a for a, i in article2idx.items()}

# dwell_time 버켓팅
df_log["dwell_log"] = np.log1p(df_log["dwell_time"])
dwell_min = df_log["dwell_log"].min()
dwell_max = df_log["dwell_log"].max()

def bucket_dwell(val, n_buckets=99):
    log_val = np.log1p(val)
    bucket  = int((log_val - dwell_min) / (dwell_max - dwell_min) * (n_buckets - 1))
    return min(max(bucket, 0), n_buckets - 1) + 1

# 유저별 시퀀스 생성
print("유저별 시퀀스 생성 중...")
user_sequences = {}

for user_id, group in df_log.groupby("user_id"):
    group = group.sort_values("timestamp").reset_index(drop=True)

    item_seq     = []
    dwell_seq    = []
    interval_seq = []
    prev_ts      = None

    for _, row in group.iterrows():
        item_idx     = article2idx.get(row["article_id"], 0)
        dwell_bucket = bucket_dwell(row["dwell_time"])

        if prev_ts is None:
            interval_bucket = 1
        else:
            try:
                diff_minutes = (row["timestamp"] - prev_ts).total_seconds() / 60
                if diff_minutes < 30:
                    interval_bucket = 1
                elif diff_minutes < 2880:    # 30분~2일
                    interval_bucket = 2
                elif diff_minutes < 5760:    # 2~4일
                    interval_bucket = 3
                elif diff_minutes < 10080:   # 4~7일
                    interval_bucket = 4
                elif diff_minutes < 20160:   # 7~14일
                    interval_bucket = 5
                elif diff_minutes < 44640:   # 14~31일
                    interval_bucket = 6
                else:
                    interval_bucket = 7
        item_seq.append(item_idx)
        dwell_seq.append(dwell_bucket)
        interval_seq.append(interval_bucket)
        prev_ts = row["timestamp"]

    persona          = group["persona_type"].iloc[-1]
    shopping_pattern = user_pattern_map.get(user_id, "unknown")

    user_sequences[user_id] = {
        "sequence":         item_seq,
        "dwell_seq":        dwell_seq,
        "interval_seq":     interval_seq,
        "persona_type":     persona,
        "shopping_pattern": shopping_pattern,
    }

print(f"완료! 총 유저 수: {len(user_sequences)}")

# shopping_pattern 분포 확인
patterns = [v["shopping_pattern"] for v in user_sequences.values()]
print("\n=== shopping_pattern 분포 ===")
for pattern, cnt in Counter(patterns).most_common():
    print(f"  {pattern}: {cnt}명")

# 저장
pd.DataFrame([
    {"article_id": a, "article_idx": i}
    for a, i in article2idx.items()
]).to_csv("backend/ml_model/data/valid_articles.csv", index=False)

with open("backend/ml_model/data/user_sequences.pkl", "wb") as f:
    pickle.dump(user_sequences, f)

with open("backend/ml_model/data/article_maps.pkl", "wb") as f:
    pickle.dump({"article2idx": article2idx, "idx2article": idx2article}, f)

print(f"\n총 아이템 수: {len(article2idx)}")
print("저장 완료!")

# interval_seq 버킷 분포 확인
all_intervals = []
for v in user_sequences.values():
    all_intervals.extend(v["interval_seq"])

labels = {
    1: "0~30분",
    2: "30분~1일",
    3: "1~3일",
    4: "3~7일",
    5: "7~14일",
    6: "14~31일",
    7: "31일+",
}

print("\n=== interval_seq 버킷 분포 ===")
for bucket, cnt in sorted(Counter(all_intervals).items()):
    label = labels.get(bucket, "기타")
    print(f"  Bucket {bucket} ({label}): {cnt:,}건")

    # project1.py 저장 완료 출력 이후에 추가
sample_user = list(user_sequences.keys())[0]
sample_seq = user_sequences[sample_user]
print(f"\n샘플 유저: {sample_user}")
print(f"시퀀스 길이: {len(sample_seq['sequence'])}")
print(f"interval_seq 앞 20개: {sample_seq['interval_seq'][:20]}")

# 실제 timestamp 간격 직접 확인
sample_group = df_log[df_log["user_id"] == sample_user].sort_values("timestamp").head(20)
print("\n실제 timestamp 앞 20개:")
print(sample_group[["timestamp", "article_id"]].to_string())
