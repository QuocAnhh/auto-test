"""
Aggregation and insights module for batch evaluation results.
"""
import statistics
from typing import Dict, List, Any
from collections import Counter

def make_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create summary statistics from batch evaluation results.
    
    Args:
        results: List of evaluation result dictionaries (each follows per-conversation format)
        
    Returns:
        Dictionary containing aggregated statistics and insights
    """
    if not results:
        return {
            "count": 0,
            "errors": [],
            "avg_total_score": 0,
            "median_total_score": 0,
            "std_total_score": 0,
            "criteria_avg": {},
            "diagnostics_top": [],
            "flow_distribution": {},
            "policy_violation_rate": 0,
            "metrics_overview": {},
            "latency_stats": {}
        }
    
    # Separate successful results from errors
    successful_results = []
    errors = []
    
    for result in results:
        if "error" in result:
            errors.append(result)
        else:
            successful_results.append(result)
    
    if not successful_results:
        return {
            "count": len(results),
            "errors": errors,
            "avg_total_score": 0,
            "median_total_score": 0,
            "std_total_score": 0,
            "criteria_avg": {},
            "diagnostics_top": [],
            "flow_distribution": {},
            "policy_violation_rate": 0,
            "metrics_overview": {},
            "latency_stats": {}
        }
    
    # Extract scores and basic stats
    total_scores = [r["result"]["total_score"] for r in successful_results]
    avg_total_score = statistics.mean(total_scores)
    median_total_score = statistics.median(total_scores)
    std_total_score = statistics.stdev(total_scores) if len(total_scores) > 1 else 0
    
    # Criteria averages (8 unified criteria)
    criteria_scores = {}
    for result in successful_results:
        for criterion, details in result["result"]["criteria"].items():
            if criterion not in criteria_scores:
                criteria_scores[criterion] = []
            criteria_scores[criterion].append(details["score"])
    
    criteria_avg = {
        criterion: statistics.mean(scores) 
        for criterion, scores in criteria_scores.items()
    }
    
    # Flow distribution
    flows = [r["result"]["detected_flow"] for r in successful_results]
    flow_distribution = dict(Counter(flows))
    
    # Policy violation rate
    policy_violations = [
        r["metrics"].get("policy_violations", 0) 
        for r in successful_results
    ]
    policy_violation_rate = len([pv for pv in policy_violations if pv > 0]) / len(successful_results)
    
    # Diagnostics frequency (top diagnostic rules)
    diagnostics_counter = Counter()
    for result in successful_results:
        diagnostics = result["metrics"].get("diagnostics", {})
        for category in ["operational_readiness", "risk_compliance"]:
            for hit in diagnostics.get(category, []):
                diagnostics_counter[hit["key"]] += 1
    
    diagnostics_top = diagnostics_counter.most_common(5)
    
    # Metrics overview
    metric_keys = [
        "repeated_questions", "agent_user_ratio", "context_resets", 
        "long_option_lists", "tts_money_reading_violation"
    ]
    
    metrics_overview = {}
    for key in metric_keys:
        values = [r["metrics"].get(key) for r in successful_results if r["metrics"].get(key) is not None]
        if values:
            metrics_overview[key] = statistics.mean(values)
    
    # Latency stats
    latency_keys = ["first_response_latency_seconds", "avg_agent_response_latency_seconds"]
    latency_stats = {}
    for key in latency_keys:
        values = [r["metrics"].get(key) for r in successful_results if r["metrics"].get(key) is not None]
        if values:
            latency_stats[f"avg_{key}"] = statistics.mean(values)
            latency_stats[f"median_{key}"] = statistics.median(values)
    
    return {
        "count": len(results),
        "successful_count": len(successful_results),
        "error_count": len(errors),
        "errors": errors,
        "avg_total_score": avg_total_score,
        "median_total_score": median_total_score,
        "std_total_score": std_total_score,
        "criteria_avg": criteria_avg,
        "diagnostics_top": diagnostics_top,
        "flow_distribution": flow_distribution,
        "policy_violation_rate": policy_violation_rate,
        "metrics_overview": metrics_overview,
        "latency_stats": latency_stats
    }

def generate_insights(summary: Dict[str, Any]) -> List[str]:
    """
    Generate human-readable insights from summary statistics.
    
    Args:
        summary: Summary dictionary from make_summary()
        
    Returns:
        List of insight strings
    """
    insights = []
    
    if summary["successful_count"] == 0:
        insights.append("❌ Không có conversation nào được chấm thành công.")
        return insights
    
    # Score insights
    avg_score = summary["avg_total_score"]
    if avg_score >= 85:
        insights.append(f"✅ Chất lượng tổng thể xuất sắc với điểm trung bình {avg_score:.1f}/100.")
    elif avg_score >= 70:
        insights.append(f"📊 Chất lượng tổng thể khá tốt với điểm trung bình {avg_score:.1f}/100.")
    else:
        insights.append(f"⚠️ Chất lượng cần cải thiện với điểm trung bình {avg_score:.1f}/100.")
    
    # Weakest criteria
    criteria_avg = summary["criteria_avg"]
    if criteria_avg:
        weakest_criterion = min(criteria_avg.items(), key=lambda x: x[1])
        insights.append(f"🎯 Tiêu chí yếu nhất: {weakest_criterion[0]} ({weakest_criterion[1]:.1f}/100).")
    
    # Top diagnostic issues
    diagnostics_top = summary["diagnostics_top"]
    if diagnostics_top:
        top_issue = diagnostics_top[0]
        insights.append(f"🔍 Lỗi phổ biến nhất: {top_issue[0]} ({top_issue[1]} lần).")
    
    # Policy violations
    violation_rate = summary["policy_violation_rate"]
    if violation_rate > 0.3:
        insights.append(f"⚠️ Tỷ lệ vi phạm policy cao: {violation_rate:.1%} conversations.")
    elif violation_rate == 0:
        insights.append("✅ Không có vi phạm policy nào được phát hiện.")
    
    # Agent performance insight
    metrics = summary["metrics_overview"]
    agent_ratio = metrics.get("agent_user_ratio")
    if agent_ratio and agent_ratio > 2.0 and avg_score < 70:
        insights.append("💬 Agent nói quá nhiều so với user, có thể ảnh hưởng điểm số.")
    
    return insights
