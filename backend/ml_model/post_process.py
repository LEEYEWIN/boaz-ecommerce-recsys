def build_dynamic_weights(sequence: list[dict]) -> dict:
    """
    현재 세션 시퀀스 보고 동적 가중치 딕셔너리 생성
    click       → ×1.1
    add_to_cart → ×1.5
    """
    weights = {}
    for event in sequence:
        art_id = event["article_id"]
        evt    = event["event"]
        if evt == "add_to_cart":
            weights[art_id] = weights.get(art_id, 1.0) * 1.5
        elif evt == "click":
            weights[art_id] = weights.get(art_id, 1.0) * 1.1
    return weights