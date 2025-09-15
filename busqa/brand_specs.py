from dataclasses import dataclass
from typing import Dict, Any, Tuple
import yaml

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


