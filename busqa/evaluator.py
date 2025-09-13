from typing import Dict, Any
from .rubrics import RUBRICS, LABEL_THRESHOLDS
from .models import LLMOutput

def ensure_full_criteria(intent: str, criteria: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Đảm bảo mọi tiêu chí trong rubric đều có mặt; thiếu thì điền score=0, note='(thiếu)'."""
    full = {}
    for key in RUBRICS[intent].keys():
        if key in criteria and isinstance(criteria[key], dict):
            # normalize
            sc = float(criteria[key].get("score", 0) or 0)
            note = str(criteria[key].get("note", ""))
            full[key] = {"score": sc, "note": note}
        else:
            full[key] = {"score": 0.0, "note": "(thiếu bằng chứng trong transcript)"}
    return full

def recompute_total(intent: str, criteria: Dict[str, Dict[str, Any]]) -> float:
    total = 0.0
    for k, w in RUBRICS[intent].items():
        sc = float(criteria.get(k, {}).get("score", 0.0) or 0.0)
        total += sc * w
    return round(total, 2)

def label_from_score(score: float) -> str:
    for thr, lbl in LABEL_THRESHOLDS:
        if score >= thr:
            return lbl
    return "Kém"

def coerce_llm_json(obj: Dict[str, Any]) -> LLMOutput:
    intent = str(obj.get("detected_intent", "")).strip()
    crit = obj.get("criteria", {}) or {}
    crit_full = ensure_full_criteria(intent, crit)
    total = float(obj.get("total_score", 0.0) or 0.0)
    recalculated = recompute_total(intent, crit_full)
    # Nếu LLM tính khác thì dùng lại điểm chuẩn
    if abs(recalculated - total) > 0.1:
        total = recalculated
    label = obj.get("label") or label_from_score(total)

    normalized = {
        "version": str(obj.get("version", "v1.0")),
        "detected_intent": intent,
        "confidence": float(obj.get("confidence", 0.0) or 0.0),
        "criteria": crit_full,
        "total_score": total,
        "label": label,
        "final_comment": str(obj.get("final_comment", "")),
        "tags": obj.get("tags", []) or [],
        "risks": obj.get("risks", []) or [],
        "suggestions": obj.get("suggestions", []) or [],
    }
    return LLMOutput(**normalized)