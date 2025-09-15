from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

class Message(BaseModel):
    ts: Optional[datetime] = None
    sender_type: str = "unknown" 
    sender_name: Optional[str] = None
    text: str = ""

class LLMOutput(BaseModel):
    version: str
    detected_flow: str = ""  # thay đổi từ flow_id sang detected_flow
    confidence: float = 0.0
    criteria: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    total_score: float = 0.0
    label: str = ""
    final_comment: str = ""
    tags: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    
