from dataclasses import dataclass
from typing import Dict, Any, Tuple
import yaml
import os

@dataclass
class BrandPolicy:
    forbid_phone_collect: bool = False
    require_fixed_greeting: bool = False
    ban_full_summary: bool = False
    max_prompted_openers: int = 3
    read_money_in_words: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrandPolicy':
        policies = data.get('policies', {})
        tts = data.get('tts', {})
        
        return cls(
            forbid_phone_collect=policies.get('forbid_phone_collect', False),
            require_fixed_greeting=policies.get('require_fixed_greeting', False),
            ban_full_summary=policies.get('ban_full_summary', False),
            max_prompted_openers=policies.get('max_prompted_openers', 3),
            read_money_in_words=tts.get('read_money_in_words', False)
        )

def load_brand_prompt(brand_path: str) -> Tuple[str, BrandPolicy]:
    with open(brand_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            front_matter = yaml.safe_load(parts[1])
            brand_prompt_text = parts[2].strip()
        else:
            front_matter = {}
            brand_prompt_text = content
    else:
        front_matter = {}
        brand_prompt_text = content
    
    brand_policy = BrandPolicy.from_dict(front_matter)
    
    return brand_prompt_text, brand_policy

def get_brand_prompt_path(brand_id: str, brands_dir: str = "brands") -> str | None:
    """Returns the full path to a brand's prompt file if it exists."""
    # Ensure brands_dir is an absolute path relative to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, brands_dir, brand_id, "prompt.md")
    
    if os.path.exists(path):
        return path
    return None

def get_available_brands(brands_dir: str = "brands") -> list[str]:
    """Returns a list of available brand IDs by scanning the brands directory."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_brands_dir = os.path.join(project_root, brands_dir)

    if not os.path.isdir(full_brands_dir):
        return []
    
    return [d for d in os.listdir(full_brands_dir) if os.path.isdir(os.path.join(full_brands_dir, d))]



def _safe_join_lines(lines: list[str]) -> str:
    try:
        return "\n".join([str(x) for x in lines if x is not None])
    except Exception:
        return ""

def build_brand_from_kb_json(kb: Dict[str, Any]) -> Tuple[str, BrandPolicy]:
    """
    Convert a structured KB JSON into (brand_prompt_text, BrandPolicy),
    preserving backward compatibility with existing prompt-based flow.

    The KB structure is flexible; missing parts degrade gracefully.
    """
    agent_name = str(kb.get("agent_name", "Unknown Agent")).strip()
    summary = str(kb.get("summary", "")).strip()

    # Build policy heuristics from KB
    # Defaults keep current behavior when absent
    policy_dict: Dict[str, Any] = {
        "policies": {},
        "tts": {}
    }

    # Heuristic examples: look into top-level or per-business limits/rules
    # If any business mentions collecting phone/PDPA restrictions in limits → forbid_phone_collect
    try:
        businesses = kb.get("businesses", []) or []
        text_limits = " ".join([str(b.get("limits", "")) for b in businesses])
        if any(key in text_limits.lower() for key in ["không thu thập số điện thoại", "không lấy sđt", "forbid phone", "pdpa"]):
            policy_dict.setdefault("policies", {})["forbid_phone_collect"] = True
    except Exception:
        pass

    # If routing or tie-break rules require fixed greeting pattern
    try:
        routing = kb.get("routing", {}) or {}
        tie_rules = _safe_join_lines(routing.get("tie_break_rules", []) or [])
        if any(key in tie_rules.lower() for key in ["chào hỏi theo mẫu", "fixed greeting"]):
            policy_dict.setdefault("policies", {})["require_fixed_greeting"] = True
    except Exception:
        pass

    # Example TTS rule
    try:
        if any(key in summary.lower() for key in ["đọc số tiền bằng chữ", "read money in words"]):
            policy_dict.setdefault("tts", {})["read_money_in_words"] = True
    except Exception:
        pass

    brand_policy = BrandPolicy.from_dict(policy_dict)

    # Build brand prompt text from KB sections
    sections: list[str] = []
    if agent_name:
        sections.append(f"Agent: {agent_name}")
    if summary:
        sections.append(f"Tóm tắt vai trò: {summary}")

    # Businesses
    try:
        if businesses:
            parts = ["\n## Danh mục Business/Intent"]
            for b in businesses:
                nm = str(b.get("name", "")).strip()
                alias = b.get("alias", []) or []
                scope = str(b.get("scope", "")).strip()
                limits = str(b.get("limits", "")).strip()
                triggers = b.get("triggers", []) or []
                regex_hint = str(b.get("regex_hint", "")).strip()
                kb_links = b.get("kb_links", []) or []
                examples = b.get("examples", []) or []
                confidence = b.get("confidence", None)

                parts.append(f"\n### {nm if nm else 'Business'}")
                if alias:
                    parts.append(f"Alias: {', '.join([str(a) for a in alias])}")
                if scope:
                    parts.append(f"Scope: {scope}")
                if limits:
                    parts.append(f"Limits: {limits}")
                if triggers:
                    parts.append(f"Triggers: {', '.join([str(t) for t in triggers])}")
                if regex_hint:
                    parts.append(f"Regex hint: {regex_hint}")
                if kb_links:
                    parts.append(f"KB Links: {', '.join([str(k) for k in kb_links])}")
                if confidence is not None:
                    parts.append(f"Confidence: {confidence}")
                if examples:
                    parts.append("Ví dụ:")
                    for ex in examples:
                        parts.append(f"- {str(ex)}")
            sections.append("\n".join(parts))
    except Exception:
        pass

    # Routing
    try:
        if routing:
            r_parts = ["\n## Routing"]
            prio = routing.get("priority_order", []) or []
            if prio:
                r_parts.append(f"Ưu tiên: {', '.join([str(p) for p in prio])}")
            tbr = routing.get("tie_break_rules", []) or []
            if tbr:
                r_parts.append("Tie-break rules:")
                for rule in tbr:
                    r_parts.append(f"- {str(rule)}")
            sections.append("\n".join(r_parts))
    except Exception:
        pass

    # Gaps
    try:
        gaps = kb.get("gaps", []) or []
        if gaps:
            g_parts = ["\n## Known Gaps/Notes"]
            for g in gaps:
                g_parts.append(f"- {str(g)}")
            sections.append("\n".join(g_parts))
    except Exception:
        pass

    brand_prompt_text = "\n\n".join([s for s in sections if s])
    return brand_prompt_text, brand_policy

