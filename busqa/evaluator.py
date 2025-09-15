from typing import Dict, Any
from .models import LLMOutput

def ensure_full_criteria(result: dict, rubrics_cfg: dict) -> Dict[str, Dict[str, Any]]:
    full = {}
    criteria_from_result = result.get("criteria", {})
    
    for key in rubrics_cfg['criteria'].keys():
        if key in criteria_from_result and isinstance(criteria_from_result[key], dict):
            sc = float(criteria_from_result[key].get("score", 0) or 0)
            note = str(criteria_from_result[key].get("note", ""))
            full[key] = {"score": sc, "note": note}
        else:
            full[key] = {"score": 0.0, "note": "missing"}
    return full

def recompute_total(result: dict, rubrics_cfg: dict) -> float:
    total = 0.0
    criteria = result.get("criteria", {})
    for k, w in rubrics_cfg['criteria'].items():
        sc = float(criteria.get(k, {}).get("score", 0.0) or 0.0)
        total += sc * w
    return round(total, 2)

def label_from_score(score: float, rubrics_cfg: dict) -> str:
    labels = rubrics_cfg.get('labels', [])
    for label_info in labels:
        if score >= label_info['threshold']:
            return label_info['label']
    return "Kém"



def apply_policy_and_flow_penalties(result: dict, brand_policy, metrics: dict, rubrics_cfg: dict) -> dict:
    criteria = result.get("criteria", {})
    
    if metrics.get("policy_violations", 0) > 0:
        if "policy_compliance" in criteria:
            criteria["policy_compliance"]["score"] = min(30, criteria["policy_compliance"]["score"])
            criteria["policy_compliance"]["note"] += " [Policy violation detected]"
    
    if metrics.get("endcall_early_hint", 0) > 0:
        if "context_flow_closure" in criteria:
            criteria["context_flow_closure"]["score"] = max(0, criteria["context_flow_closure"]["score"] - 20)
            criteria["context_flow_closure"]["note"] += " [Early end call detected]"
    
    if metrics.get("long_option_lists", 0) > 0:
        if "no_redundant_questions" in criteria:
            criteria["no_redundant_questions"]["score"] = max(0, criteria["no_redundant_questions"]["score"] - 15)
            criteria["no_redundant_questions"]["note"] += " [Long option lists detected]"
    
    if metrics.get("context_resets", 0) > 0:
        if "context_flow_closure" in criteria:
            criteria["context_flow_closure"]["score"] = max(0, criteria["context_flow_closure"]["score"] - 25)
            criteria["context_flow_closure"]["note"] += " [Context resets detected]"
    
    if metrics.get("tts_money_reading_violation", 0) > 0:
        if "style_tts" in criteria:
            criteria["style_tts"]["score"] = max(0, criteria["style_tts"]["score"] - 20)
            criteria["style_tts"]["note"] += " [Money reading violation]"
    
    return result

def generate_auto_tags_risks(messages, transcript, metrics: dict) -> tuple:
    tags = set()
    risks = set()
    
    if metrics.get("repeated_questions", 0) > 0:
        tags.add("redundant_questions")
        risks.add("bot hỏi lại thông tin đã có")
    
    if metrics.get("endcall_early_hint", 0) > 0:
        tags.add("early_end")
        risks.add("bot kết thúc cuộc gọi khi khách còn câu hỏi")
    
    if metrics.get("context_resets", 0) > 0:
        tags.add("context_reset")
        risks.add("bot mất ngữ cảnh cuộc gọi")
    
    if metrics.get("long_option_lists", 0) > 0:
        tags.add("long_response")
        risks.add("bot liệt kê quá nhiều lựa chọn")
    
    if metrics.get("policy_violations", 0) > 0:
        tags.add("policy_violation")
        risks.add("bot vi phạm chính sách công ty")
    
    if metrics.get("tts_money_reading_violation", 0) > 0:
        tags.add("tts_money_reading_violation")
        risks.add("bot đọc số tiền không đúng cách")
    
    if "không hiểu" in transcript.lower() or "ý bạn là" in transcript.lower():
        tags.add("misunderstanding")
        risks.add("bot hiểu sai ý khách")
    
    return list(tags), list(risks)

def coerce_llm_json_unified(llm_json: Any, rubrics_cfg: dict, brand_policy=None, messages=None, transcript=None, metrics=None, diagnostics_cfg=None, diagnostics_hits=None):
    detected_flow = str(llm_json.get("detected_flow", "")).strip()
    crit_full = ensure_full_criteria(llm_json, rubrics_cfg)
    total = float(llm_json.get("total_score", 0.0) or 0.0)
    recalculated = recompute_total({"criteria": crit_full}, rubrics_cfg)
    
    if abs(recalculated - total) > 0.1:
        total = recalculated
    
    label = llm_json.get("label") or label_from_score(total, rubrics_cfg)

    normalized = {
        "version": str(llm_json.get("version", "v1.0")),
        "detected_flow": detected_flow,
        "confidence": float(llm_json.get("confidence", 0.0) or 0.0),
        "criteria": crit_full,
        "total_score": total,
        "label": label,
        "final_comment": str(llm_json.get("final_comment", "")),
        "tags": llm_json.get("tags", []) or [],
        "risks": llm_json.get("risks", []) or [],
        "suggestions": llm_json.get("suggestions", []) or [],
    }
    
    if brand_policy and metrics:
        normalized = apply_policy_and_flow_penalties(normalized, brand_policy, metrics, rubrics_cfg)
    
    if diagnostics_cfg and diagnostics_hits:
        normalized = apply_diagnostics_penalties(normalized, diagnostics_cfg, diagnostics_hits)
        
        all_hits = []
        all_hits.extend(diagnostics_hits.get("operational_readiness", []))
        all_hits.extend(diagnostics_hits.get("risk_compliance", []))
        
        diag_tags = set(normalized.get("tags", []))
        diag_risks = set(normalized.get("risks", []))
        
        for hit in all_hits:
            hit_key = hit["key"]
            
            if hit_key in ["fare_math_inconsistent", "double_room_rule_violation"]:
                diag_tags.add("knowledge_violation")
            
            if hit_key in ["forbidden_phone_collect", "promise_hold_seat", "payment_policy_violation", "pdpa_consent_missing"]:
                diag_tags.add("policy_violation")
            
            diag_tags.add(f"diag_{hit_key}")
            
            if hit_key == "forbidden_phone_collect":
                diag_risks.add("thu thập SĐT trái chính sách")
            elif hit_key == "child_policy_miss":
                diag_risks.add("không áp dụng chính sách trẻ em")
            elif hit_key == "handover_sla_missing":
                diag_risks.add("thiếu cam kết SLA khi kết thúc")
            elif hit_key == "fare_math_inconsistent":
                diag_risks.add("thông tin giá vé mâu thuẫn")
            elif hit_key == "promise_hold_seat":
                diag_risks.add("hứa giữ chỗ trái thẩm quyền")
        
        normalized["tags"] = list(diag_tags)
        normalized["risks"] = list(diag_risks)
    
    if brand_policy and metrics or (diagnostics_cfg and diagnostics_hits):
        normalized["total_score"] = recompute_total(normalized, rubrics_cfg)
        normalized["label"] = label_from_score(normalized["total_score"], rubrics_cfg)
    
    if messages is not None and transcript is not None and metrics is not None:
        auto_tags, auto_risks = generate_auto_tags_risks(messages, transcript, metrics)
        normalized["tags"] = list(set(normalized.get("tags", [])) | set(auto_tags))
        normalized["risks"] = list(set(normalized.get("risks", [])) | set(auto_risks))
    
    return LLMOutput(**normalized)

def apply_diagnostics_penalties(result: dict, diagnostics_cfg: dict, diagnostics_hits: dict) -> dict:
    criteria = result.get("criteria", {})
    
    all_hits = []
    all_hits.extend(diagnostics_hits.get("operational_readiness", []))
    all_hits.extend(diagnostics_hits.get("risk_compliance", []))
    
    for hit in all_hits:
        hit_key = hit["key"]
        hit_evidence = hit["evidence"]
        
        penalty_config = None
        
        for item in diagnostics_cfg.get("operational_readiness", []):
            if item["key"] == hit_key:
                penalty_config = item["penalty"]
                break
        
        if not penalty_config:
            for item in diagnostics_cfg.get("risk_compliance", []):
                if item["key"] == hit_key:
                    penalty_config = item["penalty"]
                    break
        
        if not penalty_config:
            continue
        
        for criterion, penalty_rules in penalty_config.items():
            if criterion not in criteria:
                continue
            
            current_score = float(criteria[criterion]["score"])
            current_note = criteria[criterion]["note"]
            
            if "delta" in penalty_rules:
                delta = penalty_rules["delta"]
                new_score = max(0, min(100, current_score + delta))
                criteria[criterion]["score"] = new_score
            
            if "clamp_max" in penalty_rules:
                clamp_max = penalty_rules["clamp_max"]
                if current_score > clamp_max:
                    criteria[criterion]["score"] = float(clamp_max)
            
            evidence_summary = "; ".join(hit_evidence[:2])
            diag_note = f"Diag: {hit_key} — evidence: {evidence_summary}"
            
            if current_note and current_note != "missing":
                criteria[criterion]["note"] = f"{current_note}. {diag_note}"
            else:
                criteria[criterion]["note"] = diag_note
    
    return result