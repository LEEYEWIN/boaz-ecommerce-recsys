import os, pickle, torch
import torch.nn.functional as F
from ml_model.bert4rec_phase1 import BERT4Rec

MAX_SEQ_LEN = 50
DEVICE      = "mps" if torch.backends.mps.is_available() else "cpu"
BASE_DIR    = os.path.dirname(__file__)

with open(os.path.join(BASE_DIR, "data/article_maps.pkl"), "rb") as f:
    maps = pickle.load(f)

article2idx = maps["article2idx"]
idx2article = maps["idx2article"]
VOCAB_SIZE  = len(article2idx) + 2

model = BERT4Rec(VOCAB_SIZE, MAX_SEQ_LEN).to(DEVICE)
model.load_state_dict(
    torch.load(os.path.join(BASE_DIR, "weights/best_model_phase1.pt"),
               map_location=DEVICE)
)
model.eval()
print(f"모델 로드 완료 | VOCAB_SIZE: {VOCAB_SIZE} | DEVICE: {DEVICE}")

def predict(sequence: list[dict], top_k: int = 10,
            dynamic_weights: dict = None) -> list[dict]:
    click_count = sum(1 for s in sequence if s["event"] == "click")
    if click_count < 3:
        return _cold_session(sequence, top_k)

    ids = [article2idx.get(s["article_id"], 0) for s in sequence]
    ids = ids[-(MAX_SEQ_LEN - 1):]
    ids = ids + [1]

    pad_len = MAX_SEQ_LEN - len(ids)
    ids     = [0] * pad_len + ids

    inp = torch.tensor([ids], dtype=torch.long).to(DEVICE)

    with torch.no_grad():
        logits = model(inp)
        probs  = F.softmax(logits[0, -1, :], dim=-1)

    if dynamic_weights:
        for art_id, w in dynamic_weights.items():
            idx = article2idx.get(art_id)
            if idx is not None:
                probs[idx] = probs[idx] * w

    top_probs, top_indices = torch.topk(probs, top_k)
    results = []
    for prob, idx in zip(top_probs.tolist(), top_indices.tolist()):
        art_id = idx2article.get(idx)
        if art_id:
            results.append({
                "article_id": str(art_id),
                "score": round(prob, 6)
            })
    return results

def _cold_session(sequence: list[dict], top_k: int) -> list[dict]:
    try:
        with open(os.path.join(BASE_DIR, "data/top_k_dict.pkl"), "rb") as f:
            top_k_dict = pickle.load(f)
        last       = sequence[-1]["article_id"] if sequence else None
        candidates = top_k_dict.get(last, [])[:top_k]
        return [{"article_id": str(a), "score": 1.0} for a in candidates]
    except Exception:
        return []
def build_dynamic_weights(sequence: list) -> dict:
    weights = {}
    for event in sequence:
        art_id = event["article_id"]
        evt    = event["event"]
        if evt == "add_to_cart":
            weights[art_id] = weights.get(art_id, 1.0) * 1.5
        elif evt == "click":
            weights[art_id] = weights.get(art_id, 1.0) * 1.1
    return weights
