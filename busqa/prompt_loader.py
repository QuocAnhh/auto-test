import os
import yaml
from typing import Dict, Any, Tuple

def load_unified_rubrics(path: str = "config/rubrics_unified.yaml") -> Dict[str, Any]:
    """Load unified rubrics configuration and validate weights."""
    if not os.path.isabs(path):
        # Make relative to project root
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, path)
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Validate weights sum to approximately 1.0
    criteria = data.get('criteria', {})
    total_weight = sum(criteria.values())
    
    if abs(total_weight - 1.0) > 0.01:  # Allow small floating point differences
        print(f"Warning: Total weights sum to {total_weight}, normalizing to 1.0")
        # Normalize weights
        for key in criteria:
            criteria[key] = criteria[key] / total_weight
        data['criteria'] = criteria
    
    return data

def get_criteria_descriptions() -> Dict[str, str]:
    """Get descriptions for each unified criteria."""
    return {
        "intent_routing": "Hiểu đúng ý định khách và định tuyến vào flow phù hợp",
        "slots_completeness": "Thu thập đầy đủ thông tin cần thiết theo flow",
        "no_redundant_questions": "Không hỏi lại thông tin đã có hoặc không cần thiết", 
        "knowledge_accuracy": "Cung cấp thông tin chính xác về lịch trình, giá vé, chính sách",
        "context_flow_closure": "Duy trì ngữ cảnh và kết thúc cuộc gọi hợp lý",
        "style_tts": "Phong cách giao tiếp và đọc số liệu phù hợp",
        "policy_compliance": "Tuân thủ chính sách công ty và quy định",
        "empathy_experience": "Thể hiện sự đồng cảm và tạo trải nghiệm tích cực"
    }

def load_diagnostics_config(path: str = "config/diagnostics.yaml") -> Dict[str, Any]:
    """Load diagnostics configuration and validate schema."""
    if not os.path.isabs(path):
        # Make relative to project root
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, path)
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Validate required sections
    if 'operational_readiness' not in data:
        raise ValueError("Missing 'operational_readiness' section in diagnostics config")
    if 'risk_compliance' not in data:
        raise ValueError("Missing 'risk_compliance' section in diagnostics config")
    
    # Validate each diagnostic item has required fields
    for section_name in ['operational_readiness', 'risk_compliance']:
        for item in data[section_name]:
            if 'key' not in item:
                raise ValueError(f"Missing 'key' in {section_name} item: {item}")
            if 'penalty' not in item:
                raise ValueError(f"Missing 'penalty' in {section_name} item: {item}")
            
            # Validate penalty structure
            penalty = item['penalty']
            for criterion, penalty_rules in penalty.items():
                if not isinstance(penalty_rules, dict):
                    raise ValueError(f"Invalid penalty format for {item['key']}.{criterion}")
                
                # Check for valid penalty types
                valid_penalty_types = {'delta', 'clamp_max'}
                if not any(pt in penalty_rules for pt in valid_penalty_types):
                    raise ValueError(f"No valid penalty type in {item['key']}.{criterion}. Use 'delta' or 'clamp_max'")
    
    return data
