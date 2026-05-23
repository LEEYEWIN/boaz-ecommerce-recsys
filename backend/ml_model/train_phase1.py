import sys, os
sys.path.append(os.path.dirname(__file__))

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import pickle, random, numpy as np
from tqdm import tqdm
from bert4rec import BERT4Rec

# ── 하이퍼파라미터 ──────────────────────────────────────────
MAX_SEQ_LEN = 50
MASK_PROB   = 0.2
BATCH_SIZE  = 128
EPOCHS      = 50
LR          = 1e-3
EMBED_SIZE  = 128
NUM_HEADS   = 4
NUM_LAYERS  = 2
DROPOUT     = 0.2
NEG_SAMPLES = 99   # 네거티브 샘플 수
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"

BASE_DIR = os.path.dirname(__file__)

# ── 데이터 로드 ────────────────────────────────────────────
print("데이터 로드 중...")
with open(os.path.join(BASE_DIR, "data/user_sequences.pkl"), "rb") as f:
    user_sequences = pickle.load(f)
with open(os.path.join(BASE_DIR, "data/article_maps.pkl"), "rb") as f:
    maps = pickle.load(f)

VOCAB_SIZE   = len(maps["article2idx"]) + 2
all_item_ids = list(maps["idx2article"].keys())  # 네거티브 샘플링용
print(f"VOCAB_SIZE: {VOCAB_SIZE} | DEVICE: {DEVICE}")

# ── Leave-One-Out 분할 ────────────────────────────────────
def split_sequence(seq):
    if len(seq) < 3:
        return None, None, None
    return seq[:-2], seq[-2], seq[-1]

# ── Dataset (슬라이딩 윈도우로 샘플 증폭) ─────────────────
class BERT4RecDataset(Dataset):
    def __init__(self, user_sequences, max_len, mask_prob, mode="train"):
        self.samples   = []
        self.max_len   = max_len
        self.mask_prob = mask_prob
        self.mode      = mode

        for uid, data in user_sequences.items():
            seq = data["sequence"]
            train_seq, valid_item, test_item = split_sequence(seq)
            if train_seq is None:
                continue

            if mode == "train":
                # 슬라이딩 윈도우로 샘플 수 증폭
                if len(train_seq) <= max_len:
                    self.samples.append(train_seq)
                else:
                    step = max_len // 2
                    for start in range(0, len(train_seq) - max_len + 1, step):
                        self.samples.append(train_seq[start:start + max_len])
                    self.samples.append(train_seq[-max_len:])
            elif mode == "valid":
                self.samples.append((train_seq, valid_item))
            elif mode == "test":
                self.samples.append((train_seq + [valid_item], test_item))

    def pad(self, seq):
        seq = seq[-self.max_len:]
        return [0] * (self.max_len - len(seq)) + seq

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        if self.mode == "train":
            seq       = self.samples[idx]
            padded    = self.pad(seq)
            input_ids = padded.copy()
            labels    = [0] * self.max_len

            for i, item in enumerate(padded):
                if item == 0:
                    continue
                if random.random() < self.mask_prob:
                    labels[i]    = item
                    input_ids[i] = 1
            return (torch.tensor(input_ids, dtype=torch.long),
                    torch.tensor(labels,    dtype=torch.long))
        else:
            seq, target = self.samples[idx]
            padded = self.pad(seq + [1])
            return (torch.tensor(padded, dtype=torch.long),
                    torch.tensor(target, dtype=torch.long))

# ── 네거티브 샘플링 평가 (HR@10, NDCG@10) ─────────────────
def evaluate(model, loader, k=10, neg_samples=NEG_SAMPLES):
    model.eval()
    hits, ndcgs = [], []

    with torch.no_grad():
        for input_ids, targets in loader:
            input_ids = input_ids.to(DEVICE)
            logits    = model(input_ids)[:, -1, :]  # (B, V)

            for i, target in enumerate(targets.tolist()):
                # 정답 1개 + 랜덤 네거티브 99개
                neg = random.sample(
                    [x for x in all_item_ids if x != target],
                    neg_samples
                )
                candidates = [target] + neg  # 총 100개
                candidate_scores = logits[i][candidates]  # (100,)

                # 100개 중 Top-K 추출
                _, top_k_local = torch.topk(candidate_scores, k)
                top_k_local = top_k_local.tolist()

                if 0 in top_k_local:  # 0번 인덱스 = 정답
                    hits.append(1)
                    rank = top_k_local.index(0) + 1
                    ndcgs.append(1 / np.log2(rank + 1))
                else:
                    hits.append(0)
                    ndcgs.append(0)

    return np.mean(hits), np.mean(ndcgs)

# ── 학습 실행 ──────────────────────────────────────────────
print("데이터셋 생성 중...")
train_ds = BERT4RecDataset(user_sequences, MAX_SEQ_LEN, MASK_PROB, "train")
valid_ds = BERT4RecDataset(user_sequences, MAX_SEQ_LEN, MASK_PROB, "valid")
test_ds  = BERT4RecDataset(user_sequences, MAX_SEQ_LEN, MASK_PROB, "test")

print(f"Train 샘플: {len(train_ds)} | Valid: {len(valid_ds)} | Test: {len(test_ds)}")

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
valid_loader = DataLoader(valid_ds, batch_size=BATCH_SIZE)
test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE)

model     = BERT4Rec(VOCAB_SIZE, MAX_SEQ_LEN, EMBED_SIZE, NUM_HEADS, NUM_LAYERS, DROPOUT).to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
criterion = nn.CrossEntropyLoss(ignore_index=0)

best_ndcg, patience_counter, PATIENCE = 0, 0, 7

print(f"\n학습 시작! | DEVICE: {DEVICE}")
for epoch in range(EPOCHS):
    model.train()
    total_loss = 0
    for input_ids, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS}"):
        input_ids, labels = input_ids.to(DEVICE), labels.to(DEVICE)
        loss = criterion(model(input_ids).view(-1, VOCAB_SIZE), labels.view(-1))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    hr, ndcg = evaluate(model, valid_loader)
    print(f"  Loss: {total_loss/len(train_loader):.4f} | "
          f"HR@10: {hr:.4f} | NDCG@10: {ndcg:.4f}")

    if ndcg > best_ndcg:
        best_ndcg = ndcg
        torch.save(model.state_dict(),
                   os.path.join(BASE_DIR, "weights/best_model.pt"))
        patience_counter = 0
        print("  → best_model.pt 저장!")
    else:
        patience_counter += 1
        if patience_counter >= PATIENCE:
            print("Early Stopping!")
            break

# 최종 테스트
model.load_state_dict(torch.load(os.path.join(BASE_DIR, "weights/best_model.pt"),
                                  map_location=DEVICE))
hr, ndcg = evaluate(model, test_loader)
print(f"\n최종 Test | HR@10: {hr:.4f} | NDCG@10: {ndcg:.4f}")
print(f"(평가 방식: 정답 1개 + 랜덤 네거티브 {NEG_SAMPLES}개, 총 100개 중 Top-10)")