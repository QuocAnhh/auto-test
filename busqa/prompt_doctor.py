"""
Prompt Doctor - LLM-based prompt analysis and improvement suggestions.
Analyzes evaluation summary to identify specific prompt issues and provide precise fixes.
"""

import json
import os
from typing import Dict, List, Any, Optional
from busqa.prompt_loader import load_unified_rubrics


class PromptDoctor:
    """
    LLM-based prompt analyzer that takes evaluation summary and provides
    specific suggestions for improving brand prompts.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize Prompt Doctor.
        
        Args:
            llm_client: Optional LLM client instance. If None, will create default.
        """
        self.llm_client = llm_client
        self.rubrics_cfg = load_unified_rubrics()
        
        # Initialize LLM client if not provided
        if not self.llm_client:
            try:
                from busqa.llm_client import LLMClient
                self.llm_client = LLMClient()
            except ImportError:
                print("Warning: LLMClient not available, using mock analysis")
                self.llm_client = None
    
    def build_analysis_prompt(self, evaluation_summary: Dict[str, Any], 
                            current_prompt: str, brand_policy: str) -> str:
        """
        Build the system prompt for LLM-based prompt analysis.
        
        Args:
            evaluation_summary: Summary from make_summary() function
            current_prompt: Current brand prompt text
            brand_policy: Brand policy text
            
        Returns:
            Formatted prompt string for LLM
        """
        criteria_descriptions = {
            "intent_routing": "Hiểu đúng ý định khách và định tuyến vào flow phù hợp",
            "slots_completeness": "Thu thập đầy đủ thông tin cần thiết theo flow",
            "no_redundant_questions": "Không hỏi lại thông tin đã có hoặc không cần thiết",
            "knowledge_accuracy": "Cung cấp thông tin chính xác về lịch trình, giá vé, chính sách",
            "context_flow_closure": "Duy trì ngữ cảnh và kết thúc cuộc gọi hợp lý",
            "style_tts": "Phong cách giao tiếp và đọc số liệu phù hợp",
            "policy_compliance": "Tuân thủ chính sách công ty và quy định",
            "empathy_experience": "Thể hiện sự đồng cảm và tạo trải nghiệm tích cực"
        }
        
        return f"""
Bạn là một chuyên gia phân tích và tối ưu hóa prompt cho chatbot. Nhiệm vụ của bạn là:

1. PHÂN TÍCH summary kết quả đánh giá để tìm ra patterns và trends
2. TÌM RA vấn đề cụ thể trong prompt gây ra các vấn đề này
3. CHỈ RA chính xác đoạn nào trong prompt cần sửa
4. ĐỀ XUẤT cách sửa cụ thể với code/text thay thế

## TIÊU CHÍ ĐÁNH GIÁ (8 TIÊU CHÍ CHUNG)
{json.dumps(criteria_descriptions, ensure_ascii=False, indent=2)}

## INPUT DATA:
- Evaluation Summary: {json.dumps(evaluation_summary, ensure_ascii=False, indent=2)}
- Current Brand Prompt: 
```
{current_prompt}
```

- Brand Policy: 
```
{brand_policy}
```

## OUTPUT FORMAT (JSON):
{{
  "analysis": {{
    "overall_patterns": ["patterns tổng quan từ summary"],
    "critical_issues": ["vấn đề nghiêm trọng nhất"],
    "trends": ["xu hướng điểm thấp theo criteria"]
  }},
  "specific_fixes": [
    {{
      "criterion": "tên tiêu chí có vấn đề",
      "avg_score": "điểm trung bình hiện tại",
      "target_score": "điểm mục tiêu",
      "problem_pattern": "pattern vấn đề từ summary",
      "prompt_section": "phần prompt có vấn đề",
      "line_range": [start_line, end_line],
      "current_code": "code hiện tại có vấn đề",
      "suggested_code": "code đề xuất sửa",
      "reasoning": "lý do dựa trên patterns trong summary",
      "priority": "high/medium/low",
      "expected_improvement": "cải thiện dự kiến"
    }}
  ],
  "summary": "tóm tắt các thay đổi cần thiết dựa trên patterns"
}}

## QUY TẮC QUAN TRỌNG:
- Phân tích dựa trên patterns trong evaluation summary, không phải từng conversation riêng lẻ
- Chỉ ra chính xác dòng/đoạn nào trong prompt cần sửa
- Đưa ra code/text thay thế cụ thể, không chỉ gợi ý chung chung
- Ưu tiên các vấn đề có tác động lớn nhất đến điểm số
- Đảm bảo suggestions thực tế và có thể implement được
"""
    
    async def analyze_prompt_issues(self, evaluation_summary: Dict[str, Any], 
                                  current_prompt: str, brand_policy: str = "") -> Dict[str, Any]:
        """
        Analyze prompt issues based on evaluation summary.
        
        Args:
            evaluation_summary: Summary from make_summary() function
            current_prompt: Current brand prompt text
            brand_policy: Brand policy text (optional)
            
        Returns:
            Dictionary containing analysis results and suggestions
        """
        try:
            # Build analysis prompt
            analysis_prompt = self.build_analysis_prompt(evaluation_summary, current_prompt, brand_policy)
            
            # Call LLM for analysis
            if self.llm_client:
                # Use default model from environment or fallback
                model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                
                llm_response = await self.llm_client.call_async(
                    model=model,
                    system_prompt=analysis_prompt,
                    user_prompt="Phân tích prompt và đưa ra gợi ý cải thiện dựa trên evaluation summary."
                )
                
                # LLM response is already parsed JSON, just validate and return
                if self.validate_analysis_result(llm_response):
                    return llm_response
                else:
                    return {
                        "error": "Invalid LLM response format",
                        "analysis": {"overall_patterns": [], "critical_issues": [], "trends": []},
                        "specific_fixes": [],
                        "summary": "LLM response format is invalid"
                    }
            else:
                # Fallback to mock analysis if no LLM client
                return self._generate_mock_analysis(evaluation_summary, current_prompt, brand_policy)
                
        except Exception as e:
            return {
                "error": f"Analysis failed: {str(e)}",
                "analysis": {"overall_patterns": [], "critical_issues": [], "trends": []},
                "specific_fixes": [],
                "summary": f"Analysis failed due to error: {str(e)}"
            }
    
    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM response and extract analysis results.
        
        Args:
            llm_response: Raw response from LLM
            
        Returns:
            Parsed analysis results
        """
        try:
            import json
            import re
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # Validate result structure
                if self.validate_analysis_result(result):
                    return result
            
            # If JSON parsing fails, return error
            return {
                "error": "Failed to parse LLM response",
                "analysis": {"overall_patterns": [], "critical_issues": [], "trends": []},
                "specific_fixes": [],
                "summary": "LLM response could not be parsed"
            }
            
        except Exception as e:
            return {
                "error": f"Error parsing LLM response: {str(e)}",
                "analysis": {"overall_patterns": [], "critical_issues": [], "trends": []},
                "specific_fixes": [],
                "summary": "Error occurred while parsing LLM response"
            }

    def _generate_mock_analysis(self, evaluation_summary: Dict[str, Any], 
                               current_prompt: str, brand_policy: str) -> Dict[str, Any]:
        """
        Generate mock analysis for testing purposes.
        """
        criteria_avg = evaluation_summary.get("criteria_avg", {})
        avg_total_score = evaluation_summary.get("avg_total_score", 0)
        
        # Find the lowest scoring criteria
        lowest_criterion = None
        lowest_score = 100
        for criterion, score in criteria_avg.items():
            if score < lowest_score:
                lowest_score = score
                lowest_criterion = criterion
        
        # Generate mock suggestions based on the lowest scoring criterion
        specific_fixes = []
        if lowest_criterion and lowest_score < 80:
            if lowest_criterion == "slots_completeness":
                specific_fixes.append({
                    "criterion": "slots_completeness",
                    "avg_score": lowest_score,
                    "target_score": 85,
                    "problem_pattern": f"Slots completeness thấp ({lowest_score}/100) - agent không thu thập đủ thông tin",
                    "prompt_section": "flow_definitions",
                    "line_range": [1, 4],
                    "current_code": "1. Hỏi điểm đi\n2. Hỏi điểm đến\n3. Hỏi ngày đi\n4. Hỏi số khách",
                    "suggested_code": "1. Hỏi điểm đi\n2. Hỏi điểm đến\n3. Hỏi ngày đi\n4. Hỏi giờ đi (sáng/chiều/tối)\n5. Hỏi số khách\n6. Hỏi loại xe (ghế ngồi/giường nằm)",
                    "reasoning": f"Dựa trên evaluation summary: slots_completeness chỉ đạt {lowest_score}/100. Cần bổ sung thêm giờ đi và loại xe để thu thập đầy đủ thông tin.",
                    "priority": "high" if lowest_score < 60 else "medium",
                    "expected_improvement": f"+{85 - lowest_score} điểm slots_completeness"
                })
            elif lowest_criterion == "knowledge_accuracy":
                specific_fixes.append({
                    "criterion": "knowledge_accuracy",
                    "avg_score": lowest_score,
                    "target_score": 85,
                    "problem_pattern": f"Knowledge accuracy thấp ({lowest_score}/100) - thông tin không chính xác",
                    "prompt_section": "knowledge_base",
                    "line_range": [6, 6],
                    "current_code": "Giá vé từ 100k-200k tùy tuyến",
                    "suggested_code": "## BẢNG GIÁ VÉ CHI TIẾT\n- Hà Nội - Hải Phòng: 120k (ghế ngồi), 180k (giường nằm)\n- Hà Nội - Đà Nẵng: 450k (ghế ngồi), 650k (giường nằm)\n- Hà Nội - TP.HCM: 800k (ghế ngồi), 1200k (giường nằm)",
                    "reasoning": f"Dựa trên evaluation summary: knowledge_accuracy chỉ đạt {lowest_score}/100. Cần cung cấp thông tin giá vé cụ thể và chính xác.",
                    "priority": "high" if lowest_score < 60 else "medium",
                    "expected_improvement": f"+{85 - lowest_score} điểm knowledge_accuracy"
                })
            elif lowest_criterion == "empathy_experience":
                specific_fixes.append({
                    "criterion": "empathy_experience",
                    "avg_score": lowest_score,
                    "target_score": 85,
                    "problem_pattern": f"Empathy experience thấp ({lowest_score}/100) - thiếu sự đồng cảm và trải nghiệm tích cực",
                    "prompt_section": "conversation_style",
                    "line_range": [1, 3],
                    "current_code": "## PHONG CÁCH GIAO TIẾP\n- Lịch sự, chuyên nghiệp\n- Trả lời ngắn gọn",
                    "suggested_code": "## PHONG CÁCH GIAO TIẾP\n- Lịch sự, chuyên nghiệp, thân thiện\n- Thể hiện sự đồng cảm với khách hàng\n- Sử dụng ngôn ngữ tích cực và hỗ trợ\n- Hỏi thêm về nhu cầu và mong muốn của khách\n- Đưa ra lời khuyên hữu ích",
                    "reasoning": f"Dựa trên evaluation summary: empathy_experience chỉ đạt {lowest_score}/100. Cần cải thiện phong cách giao tiếp để tạo trải nghiệm tích cực hơn cho khách hàng.",
                    "priority": "high" if lowest_score < 60 else "medium",
                    "expected_improvement": f"+{85 - lowest_score} điểm empathy_experience"
                })
            elif lowest_criterion == "style_tts":
                specific_fixes.append({
                    "criterion": "style_tts",
                    "avg_score": lowest_score,
                    "target_score": 85,
                    "problem_pattern": f"Style TTS thấp ({lowest_score}/100) - phong cách giao tiếp và đọc số liệu chưa phù hợp",
                    "prompt_section": "tts_guidelines",
                    "line_range": [1, 2],
                    "current_code": "## HƯỚNG DẪN TTS\n- Đọc số rõ ràng",
                    "suggested_code": "## HƯỚNG DẪN TTS\n- Đọc số rõ ràng, chậm rãi\n- Sử dụng ngữ điệu thân thiện\n- Nhấn mạnh thông tin quan trọng\n- Tạm dừng sau mỗi thông tin chính",
                    "reasoning": f"Dựa trên evaluation summary: style_tts chỉ đạt {lowest_score}/100. Cần cải thiện hướng dẫn TTS để giao tiếp tự nhiên hơn.",
                    "priority": "high" if lowest_score < 60 else "medium",
                    "expected_improvement": f"+{85 - lowest_score} điểm style_tts"
                })
            else:
                # Generic fix for other criteria
                specific_fixes.append({
                    "criterion": lowest_criterion,
                    "avg_score": lowest_score,
                    "target_score": 85,
                    "problem_pattern": f"{lowest_criterion} thấp ({lowest_score}/100) - cần cải thiện",
                    "prompt_section": "general_improvements",
                    "line_range": [1, 1],
                    "current_code": "Cần cải thiện phần này",
                    "suggested_code": f"Cải thiện {lowest_criterion} để tăng điểm từ {lowest_score} lên 85+",
                    "reasoning": f"Dựa trên evaluation summary: {lowest_criterion} chỉ đạt {lowest_score}/100. Cần cải thiện để tăng điểm tổng thể.",
                    "priority": "high" if lowest_score < 60 else "medium",
                    "expected_improvement": f"+{85 - lowest_score} điểm {lowest_criterion}"
                })
        
        # Generate overall patterns
        overall_patterns = []
        if avg_total_score < 70:
            overall_patterns.append(f"Điểm tổng thể thấp ({avg_total_score:.1f}/100) - cần cải thiện toàn diện")
        if lowest_criterion:
            overall_patterns.append(f"Tiêu chí yếu nhất: {lowest_criterion} ({lowest_score}/100)")
        
        critical_issues = []
        if lowest_score < 60:
            critical_issues.append(f"{lowest_criterion} có điểm rất thấp ({lowest_score}/100)")
        
        trends = []
        if avg_total_score < 70:
            trends.append(f"Điểm trung bình: {avg_total_score:.1f}/100 - dưới ngưỡng chấp nhận được")
        
        return {
            "analysis": {
                "overall_patterns": overall_patterns,
                "critical_issues": critical_issues,
                "trends": trends
            },
            "specific_fixes": specific_fixes,
            "summary": f"Phân tích dựa trên {evaluation_summary.get('successful_count', 0)} conversations. Cần cải thiện {lowest_criterion} để tăng điểm tổng thể từ {avg_total_score:.1f} lên 80+."
        }
    
    def get_criteria_priority(self, criterion: str, avg_score: float) -> str:
        """
        Determine priority level based on criterion and score.
        
        Args:
            criterion: Name of the criterion
            avg_score: Average score for this criterion
            
        Returns:
            Priority level: "high", "medium", or "low"
        """
        # Get weight from rubrics config
        weight = self.rubrics_cfg.get("criteria", {}).get(criterion, 0.1)
        
        # High priority if low score and high weight
        if avg_score < 60 and weight > 0.15:
            return "high"
        elif avg_score < 70 and weight > 0.1:
            return "medium"
        else:
            return "low"
    
    def validate_analysis_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean up analysis result.
        
        Args:
            result: Raw analysis result from LLM
            
        Returns:
            Validated and cleaned result
        """
        # Ensure required fields exist
        if "analysis" not in result:
            result["analysis"] = {"overall_patterns": [], "critical_issues": [], "trends": []}
        
        if "specific_fixes" not in result:
            result["specific_fixes"] = []
        
        if "summary" not in result:
            result["summary"] = "No summary available"
        
        # Validate specific_fixes structure
        validated_fixes = []
        for fix in result.get("specific_fixes", []):
            if isinstance(fix, dict):
                # Ensure required fields
                validated_fix = {
                    "criterion": fix.get("criterion", "unknown"),
                    "avg_score": fix.get("avg_score", 0),
                    "target_score": fix.get("target_score", 80),
                    "problem_pattern": fix.get("problem_pattern", "No pattern identified"),
                    "prompt_section": fix.get("prompt_section", "unknown"),
                    "line_range": fix.get("line_range", [0, 0]),
                    "current_code": fix.get("current_code", ""),
                    "suggested_code": fix.get("suggested_code", ""),
                    "reasoning": fix.get("reasoning", "No reasoning provided"),
                    "priority": fix.get("priority", "low"),
                    "expected_improvement": fix.get("expected_improvement", "Unknown improvement")
                }
                validated_fixes.append(validated_fix)
        
        result["specific_fixes"] = validated_fixes
        return result


# Convenience function for easy usage
async def analyze_prompt_suggestions(evaluation_summary: Dict[str, Any], 
                                   current_prompt: str, 
                                   brand_policy: str = "",
                                   llm_client=None) -> Dict[str, Any]:
    """
    Convenience function to analyze prompt suggestions.
    
    Args:
        evaluation_summary: Summary from make_summary() function
        current_prompt: Current brand prompt text
        brand_policy: Brand policy text (optional)
        llm_client: Optional LLM client instance
        
    Returns:
        Dictionary containing analysis results and suggestions
    """
    doctor = PromptDoctor(llm_client)
    result = await doctor.analyze_prompt_issues(evaluation_summary, current_prompt, brand_policy)
    return doctor.validate_analysis_result(result)
