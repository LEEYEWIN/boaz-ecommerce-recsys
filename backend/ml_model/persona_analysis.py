import sys, os
sys.path.append(os.path.dirname(__file__))

import torch
import torch.nn.functional as F
import pickle, random, numpy as np
from collections import defaultdict
from bert4rec import BERT4Rec
from bert4rec_phase1 import BERT4Rec as BERT4Rec_Phase1

DEVICE   = "mps" if torch.backends.mps.is_available() else "cpu"
BASE_DIR = os.path.dirname(__file__)

with open(os.path.join(BASE_DIR, "data/user_sequences.pkl"), "rb") as f:
    user_sequences = pickle.load(f)
with open(os.path.join(BASE_DIR, "data/article_maps.pkl"), "rb") as f:
    maps = pickle.load(f)

VOCAB_SIZE   = len(maps["article2idx"]) + 2
all_item_ids = list(maps["idx2article"].keys())

def pad(seq, max_len, pad_val=0):
    seq = seq[-max_len:]
    return [pad_val] * (max_len - len(seq)) + seq

def evaluate_by_persona(model, max_seq_len, model_name, use_time=False):
    model.eval()
    persona_hits  = defaultdict(list)
    persona_ndcgs = defaultdict(list)

    with torch.no_grad():
        for uid, data in user_sequences.items():
            seq          = data["sequence"]
            persona      = data["persona_type"]
            dwell_seq    = data.get("dwell_seq", [1] * len(seq))
            interval_seq = data.get("interval_seq", [1] * len(seq))

            if len(seq) < 3:
                continue

            train_seq = seq[:-2] + [seq[-2]]
            target    = seq[-1]

            padded    = pad(train_seq + [1], max_seq_len)
            dwell_pad = pad(dwell_seq[:-1] + [0], max_seq_len, 0)
            inter_pad = pad(interval_seq[:-1] + [0], max_seq_len, 0)

            inp      = torch.tensor([padded],    dtype=torch.long).to(DEVICE)
            dwell    = torch.tensor([dwell_pad], dtype=torch.long).to(DEVICE)
            interval = torch.tensor([inter_pad], dtype=torch.long).to(DEVICE)

            if use_time:
                logits = model(inp, dwell, interval)[0, -1, :]
            else:
                logits = model(inp)[0, -1, :]

            neg        = random.sample([x for x in all_item_ids if x != target], 99)
            candidates = [target] + neg
            scores     = logits[candidates]
            _, top_k   = torch.topk(scores, 10)
            top_k      = top_k.tolist()

            if 0 in top_k:
                persona_hits[persona].append(1)
                persona_ndcgs[persona].append(1 / np.log2(top_k.index(0) + 2))
            else:
                persona_hits[persona].append(0)
                persona_ndcgs[persona].append(0)

    print(f"\n=== {model_name} 페르소나별 성능 ===")
    print(f"{'페르소나':<30} {'HR@10':>8} {'NDCG@10':>10}")
    print("-" * 52)
    for persona in sorted(persona_hits.keys()):
        hr   = np.mean(persona_hits[persona])
        ndcg = np.mean(persona_ndcgs[persona])
        print(f"{persona:<30} {hr:>8.4f} {ndcg:>10.4f}")

    return persona_hits, persona_ndcgs

# Phase 1 모델 로드 (MAX_SEQ_LEN=50, dwell 없음)
print("Phase 1 모델 로드 중...")
model1 = BERT4Rec_Phase1(VOCAB_SIZE, max_seq_len=50).to(DEVICE)
model1.load_state_dict(torch.load(
    os.path.join(BASE_DIR, "weights/best_model_phase1.pt"), map_location=DEVICE))
hits1, ndcgs1 = evaluate_by_persona(model1, 50, "Phase 1 (Standard)", use_time=False)

# Phase 2 모델 로드 (MAX_SEQ_LEN=30, dwell 있음)
print("Phase 2 모델 로드 중...")
model2 = BERT4Rec(VOCAB_SIZE, max_seq_len=50).to(DEVICE)
model2.load_state_dict(torch.load(
    os.path.join(BASE_DIR, "weights/best_model.pt"), map_location=DEVICE))
hits2, ndcgs2 = evaluate_by_persona(model2, 50, "Phase 2 (Time-aware)", use_time=True)

# 비교
print("\n=== Phase 1 vs Phase 2 NDCG@10 변화 ===")
print(f"{'페르소나':<30} {'Phase1':>8} {'Phase2':>8} {'변화':>8}")
print("-" * 60)
for persona in sorted(hits1.keys()):
    n1   = np.mean(ndcgs1[persona])
    n2   = np.mean(ndcgs2[persona])
    diff = n2 - n1
    arrow = "↑" if diff > 0 else "↓"
    print(f"{persona:<30} {n1:>8.4f} {n2:>8.4f} {arrow}{abs(diff):>6.4f}")

# ── shopping_pattern별 분석 추가 ──────────────────────────
def evaluate_by_pattern(model, max_seq_len, model_name, use_time=False):
    model.eval()
    pattern_hits  = defaultdict(list)
    pattern_ndcgs = defaultdict(list)

    with torch.no_grad():
        for uid, data in user_sequences.items():
            seq          = data["sequence"]
            pattern      = data.get("shopping_pattern", "unknown")
            dwell_seq    = data.get("dwell_seq", [1] * len(seq))
            interval_seq = data.get("interval_seq", [1] * len(seq))

            if len(seq) < 3:
                continue

            train_seq = seq[:-2] + [seq[-2]]
            target    = seq[-1]

            padded    = pad(train_seq + [1], max_seq_len)
            dwell_pad = pad(dwell_seq[:-1] + [0], max_seq_len, 0)
            inter_pad = pad(interval_seq[:-1] + [0], max_seq_len, 0)

            inp      = torch.tensor([padded],    dtype=torch.long).to(DEVICE)
            dwell    = torch.tensor([dwell_pad], dtype=torch.long).to(DEVICE)
            interval = torch.tensor([inter_pad], dtype=torch.long).to(DEVICE)

            if use_time:
                logits = model(inp, dwell, interval)[0, -1, :]
            else:
                logits = model(inp)[0, -1, :]

            neg        = random.sample([x for x in all_item_ids if x != target], 99)
            candidates = [target] + neg
            scores     = logits[candidates]
            _, top_k   = torch.topk(scores, 10)
            top_k      = top_k.tolist()

            if 0 in top_k:
                pattern_hits[pattern].append(1)
                pattern_ndcgs[pattern].append(1 / np.log2(top_k.index(0) + 2))
            else:
                pattern_hits[pattern].append(0)
                pattern_ndcgs[pattern].append(0)

    print(f"\n=== {model_name} shopping_pattern별 성능 ===")
    print(f"{'패턴':<25} {'HR@10':>8} {'NDCG@10':>10} {'유저수':>6}")
    print("-" * 55)
    for pattern in sorted(pattern_hits.keys()):
        hr   = np.mean(pattern_hits[pattern])
        ndcg = np.mean(pattern_ndcgs[pattern])
        cnt  = len(pattern_hits[pattern])
        print(f"{pattern:<25} {hr:>8.4f} {ndcg:>10.4f} {cnt:>6}")

    return pattern_hits, pattern_ndcgs

# Phase 1 shopping_pattern 분석
phits1, pndcgs1 = evaluate_by_pattern(model1, 50, "Phase 1 (Standard)", use_time=False)

# Phase 2 shopping_pattern 분석
phits2, pndcgs2 = evaluate_by_pattern(model2, 50, "Phase 2 (Time-aware)", use_time=True)

# 비교
print("\n=== Phase 1 vs Phase 2 shopping_pattern NDCG@10 변화 ===")
print(f"{'패턴':<25} {'Phase1':>8} {'Phase2':>8} {'변화':>8}")
print("-" * 55)
for pattern in sorted(phits1.keys()):
    n1   = np.mean(pndcgs1[pattern])
    n2   = np.mean(pndcgs2[pattern])
    diff = n2 - n1
    arrow = "↑" if diff > 0 else "↓"
    print(f"{pattern:<25} {n1:>8.4f} {n2:>8.4f} {arrow}{abs(diff):>6.4f}")