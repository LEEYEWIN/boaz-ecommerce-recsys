import pickle, numpy as np, os
from collections import Counter

BASE_DIR = os.path.dirname(__file__)

with open(os.path.join(BASE_DIR, "data/user_sequences.pkl"), "rb") as f:
    user_sequences = pickle.load(f)

seq_lengths = [len(data["sequence"]) for data in user_sequences.values()]
personas    = [data["persona_type"] for data in user_sequences.values()]

print("=== 시퀀스 길이 분포 ===")
print(f"평균: {np.mean(seq_lengths):.0f}")
print(f"최소: {np.min(seq_lengths)}")
print(f"최대: {np.max(seq_lengths)}")
print(f"중간값: {np.median(seq_lengths):.0f}")

print("\n=== 페르소나 분포 ===")
for persona, cnt in Counter(personas).most_common():
    print(f"  {persona}: {cnt}명")

print("\n=== 시퀀스 길이 구간 ===")
lengths = np.array(seq_lengths)
print(f"  100개 미만: {(lengths < 100).sum()}명")
print(f"  100~500개: {((lengths >= 100) & (lengths < 500)).sum()}명")
print(f"  500~1000개: {((lengths >= 500) & (lengths < 1000)).sum()}명")
print(f"  1000개 이상: {(lengths >= 1000).sum()}명")