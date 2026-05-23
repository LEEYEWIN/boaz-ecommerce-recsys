import sys, os
sys.path.append(os.path.dirname(__file__))

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import pickle, random, numpy as np
from bert4rec import BERT4Rec

MAX_SEQ_LEN = 50
BATCH_SIZE  = 128
NEG_SAMPLES = 99
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"
BASE_DIR    = os.path.dirname(__file__)

with open(os.path.join(BASE_DIR, "data/user_sequences.pkl"), "rb") as f:
    user_sequences = pickle.load(f)
with open(os.path.join(BASE_DIR, "data/article_maps.pkl"), "rb") as f:
    maps = pickle.load(f)

VOCAB_SIZE   = len(maps["article2idx"]) + 2
all_item_ids = list(maps["idx2article"].keys())

def split_sequence(seq):
    if len(seq) < 3:
        return None, None, None
    return seq[:-2], seq[-2], seq[-1]

class TestDataset(Dataset):
    def __init__(self):
        self.samples = []
        for uid, data in user_sequences.items():
            seq = data["sequence"]
            train_seq, valid_item, test_item = split_sequence(seq)
            if train_seq is None:
                continue
            self.samples.append((train_seq + [valid_item], test_item))

    def pad(self, seq):
        seq = seq[-MAX_SEQ_LEN:]
        return [0] * (MAX_SEQ_LEN - len(seq)) + seq

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        seq, target = self.samples[idx]
        padded = self.pad(seq + [1])
        return (torch.tensor(padded, dtype=torch.long),
                torch.tensor(target, dtype=torch.long))

model = BERT4Rec(VOCAB_SIZE, MAX_SEQ_LEN).to(DEVICE)
model.load_state_dict(torch.load(
    os.path.join(BASE_DIR, "weights/best_model.pt"), map_location=DEVICE))
model.eval()

test_ds     = TestDataset()
test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE)

hits, ndcgs = [], []
with torch.no_grad():
    for input_ids, targets in test_loader:
        input_ids = input_ids.to(DEVICE)
        logits    = model(input_ids)[:, -1, :]

        for i, target in enumerate(targets.tolist()):
            neg = random.sample(
                [x for x in all_item_ids if x != target], NEG_SAMPLES)
            candidates      = [target] + neg
            candidate_scores = logits[i][candidates]
            _, top_k_local  = torch.topk(candidate_scores, 10)
            top_k_local     = top_k_local.tolist()

            if 0 in top_k_local:
                hits.append(1)
                ndcgs.append(1 / np.log2(top_k_local.index(0) + 2))
            else:
                hits.append(0)
                ndcgs.append(0)

print(f"최종 Test HR@10:   {np.mean(hits):.4f}")
print(f"최종 Test NDCG@10: {np.mean(ndcgs):.4f}")
print(f"(정답 1개 + 랜덤 네거티브 {NEG_SAMPLES}개, 총 100개 중 Top-10)")