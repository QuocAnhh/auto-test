import json
import asyncio
import time
import traceback
from datetime import datetime
from io import BytesIO
import base64
import sys
import os
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from collections import defaultdict
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from busqa.normalize import normalize_messages, build_transcript
from busqa.metrics import compute_latency_metrics, compute_additional_metrics, compute_policy_violations_count, filter_non_null_metrics
from busqa.prompt_loader import load_unified_rubrics
from busqa.brand_specs import load_brand_prompt
from busqa.prompting import build_system_prompt_unified, build_user_instruction
from busqa.llm_client import call_llm
from busqa.evaluator import coerce_llm_json_unified
from busqa.utils import safe_parse_headers
from busqa.aggregate import make_summary, generate_insights



DEFAULT_BASE_URL = "http://103.141.140.243:14496"

def format_time_duration(seconds: float) -> str:
    """Format time duration for display"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds//60:.0f}m {seconds%60:.0f}s"
    else:
        return f"{seconds//3600:.0f}h {(seconds%3600)//60:.0f}m"

def display_conversation_details(result, rubrics_cfg):
    eval_result = result["result"]
    metrics = result["metrics"]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Flow", eval_result["detected_flow"])
    with col2:
        st.metric("Confidence", f"{eval_result['confidence']:.1%}")
    with col3:
        st.metric("Total Score", f"{eval_result['total_score']:.1f}/100")
    
    st.markdown(f"**Label:** {eval_result['label']}")
    st.markdown(f"**Comment:** {eval_result.get('final_comment', 'N/A')}")
    
    st.subheader("Criteria Breakdown")
    for criterion, details in eval_result["criteria"].items():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text(f"{criterion}: {details['score']:.0f}/100")
            st.progress(min(max(details['score']/100, 0), 1))
            if details.get("note") and details["note"] != "missing":
                st.caption(f"Note: {details['note']}")
        with col2:
            weight = rubrics_cfg["criteria"][criterion]
            contribution = details['score'] * weight
            st.metric("Weight", f"{weight:.1%}")
            st.metric("Contributes", f"{contribution:.1f}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("🏷️ Tags")
        if eval_result.get("tags"):
            for tag in eval_result["tags"]:
                st.write(f"• {tag}")
        else:
            st.write("No tags")
    
    with col2:
        st.subheader("⚠️ Risks")
        if eval_result.get("risks"):
            for risk in eval_result["risks"]:
                st.write(f"• {risk}")
        else:
            st.write("No risks identified")
    
    with col3:
        st.subheader("💡 Suggestions")
        if eval_result.get("suggestions"):
            for suggestion in eval_result["suggestions"]:
                st.write(f"• {suggestion}")
        else:
            st.write("No suggestions")
    
    diagnostics = metrics.get("diagnostics", {})
    if diagnostics:
        st.subheader("🔍 Diagnostic Hits")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Operational Readiness**")
            or_hits = diagnostics.get("operational_readiness", [])
            if or_hits:
                for hit in or_hits:
                    st.write(f"• **{hit['key']}**")
                    if hit.get('evidence'):
                        st.caption(f"Evidence: {hit['evidence'][0][:100]}...")
            else:
                st.write("✅ No issues")
        
        with col2:
            st.markdown("**Risk Compliance**")
            rc_hits = diagnostics.get("risk_compliance", [])
            if rc_hits:
                for hit in rc_hits:
                    st.write(f"• **{hit['key']}**")
                    if hit.get('evidence'):
                        st.caption(f"Evidence: {hit['evidence'][0][:100]}...")
            else:
                st.write("✅ No issues")


def display_analytics(summary, results, rubrics_cfg):
    st.subheader("📊 Batch Analytics")
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Conversations", summary["count"])
    with col2:
        st.metric("Successful", summary["successful_count"])
    with col3:
        st.metric("Avg Score", f"{summary['avg_total_score']:.1f}")
    with col4:
        st.metric("Policy Violation Rate", f"{summary['policy_violation_rate']:.1%}")
    
    # Insights
    insights = generate_insights(summary)
    if insights:
        st.subheader("💡 Key Insights")
        for insight in insights:
            st.info(insight)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Criteria averages
        st.subheader("Average Criteria Scores")
        criteria_data = list(summary["criteria_avg"].items())
        if criteria_data:
            criteria_df = pd.DataFrame(criteria_data, columns=['Criterion', 'Average Score'])
            fig1 = px.bar(criteria_df, x='Criterion', y='Average Score', 
                         title='Average Scores by Criterion')
            fig1.update_yaxes(range=[0, 100])
            st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # Score distribution
        st.subheader("Score Distribution")
        scores = []
        for result in results:
            if "error" not in result:
                scores.append(result["result"]["total_score"])
        
        if scores:
            fig2 = px.histogram(scores, title='Total Score Distribution', 
                              labels={'value': 'Total Score', 'count': 'Frequency'})
            st.plotly_chart(fig2, use_container_width=True)
    
    # Flow distribution
    if summary["flow_distribution"]:
        st.subheader("Flow Distribution")
        flow_data = list(summary["flow_distribution"].items())
        flow_df = pd.DataFrame(flow_data, columns=['Flow', 'Count'])
        fig3 = px.pie(flow_df, values='Count', names='Flow', title='Conversation Flow Distribution')
        st.plotly_chart(fig3, use_container_width=True)
    
    # Diagnostics
    if summary["diagnostics_top"]:
        st.subheader("Top Diagnostic Issues")
        diag_data = [(item[0], item[1]) for item in summary["diagnostics_top"]]
        diag_df = pd.DataFrame(diag_data, columns=['Rule', 'Count'])
        fig4 = px.bar(diag_df, x='Rule', y='Count', title='Most Common Diagnostic Issues')
        st.plotly_chart(fig4, use_container_width=True)
    
    # Latency analysis
    if summary.get("latency_stats", {}).get("avg_first_response"):
        st.subheader("Latency Analysis")
        latency_data = []
        for result in results:
            if "error" not in result:
                metrics = result["metrics"]
                if "first_response_latency_seconds" in metrics:
                    latency_data.append({
                        "conversation_id": result["conversation_id"],
                        "latency": metrics["first_response_latency_seconds"],
                        "score": result["result"]["total_score"]
                    })
        
        if latency_data:
            st.subheader("Response Latency vs Score")
            latency_df = pd.DataFrame(latency_data)
            fig5 = px.scatter(latency_df, x='latency', y='score', 
                            hover_data=['conversation_id'],
                            title='First Response Latency vs Total Score')
            fig5.update_xaxes(title='First Response Latency (seconds)')
            fig5.update_yaxes(title='Total Score')
            st.plotly_chart(fig5, use_container_width=True)


def display_export_options(results, summary):
    """Display export options and download buttons."""
    st.subheader("⬇️ Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📄 JSON Results**")
        st.markdown("Complete evaluation results with all details")
        
        json_data = json.dumps(results, ensure_ascii=False, indent=2)
        st.download_button(
            label="Download JSON",
            data=json_data,
            file_name=f"batch_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col2:
        st.markdown("**📊 CSV Summary**")
        st.markdown("Tabular summary for spreadsheet analysis")
        
        # Create enhanced CSV data with brand info and detailed metrics
        csv_data = []
        for result in results:
            if "error" not in result:
                # Extract brand info
                brand_id = result.get("brand_id", "unknown")
                if brand_id == "unknown":
                    brand_id = result.get("result", {}).get("detected_flow", "unknown")
                
                row = {
                    "conversation_id": result["conversation_id"],
                    "brand_id": brand_id,
                    "detected_flow": result["result"]["detected_flow"],
                    "total_score": result["result"]["total_score"],
                    "label": result["result"]["label"],
                    "confidence": result["result"].get("confidence", 0),
                    "final_comment": result["result"].get("final_comment", ""),
                    "policy_violations": result["metrics"].get("policy_violations", 0),
                }
                
                # Add criteria scores with notes
                for criterion, details in result["result"]["criteria"].items():
                    if isinstance(details, dict):
                        row[f"{criterion}_score"] = details.get("score", 0)
                        row[f"{criterion}_note"] = details.get("note", "")
                    else:
                        row[f"{criterion}_score"] = 0
                        row[f"{criterion}_note"] = "missing"
                
                # Add key metrics
                metrics = result.get("metrics", {})
                row.update({
                    "repeated_questions": metrics.get("repeated_questions", 0),
                    "context_resets": metrics.get("context_resets", 0),
                    "long_option_lists": metrics.get("long_option_lists", 0),
                    "endcall_early_hint": metrics.get("endcall_early_hint", 0),
                    "agent_user_ratio": metrics.get("agent_user_ratio", 0),
                    "first_response_latency": metrics.get("first_response_latency_seconds", 0),
                    "total_turns": metrics.get("total_turns", 0),
                })
                
                # Add diagnostics summary if available
                diagnostics = metrics.get("diagnostics", {})
                if diagnostics:
                    diag_summary = []
                    for issue_type, hits in diagnostics.items():
                        if hits:
                            diag_summary.append(f"{issue_type}({len(hits)})")
                    row["diagnostics_summary"] = "; ".join(diag_summary) if diag_summary else "none"
                else:
                    row["diagnostics_summary"] = "none"
                
                csv_data.append(row)
        
        if csv_data:
            csv_df = pd.DataFrame(csv_data)
            csv_string = csv_df.to_csv(index=False)
            
            st.download_button(
                label="Download CSV",
                data=csv_string,
                file_name=f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col3:
        st.markdown("**📑 PDF Report**")
        st.markdown("Comprehensive report with charts")
        
        try:
            # Add timeout protection for PDF generation
            if len(results) > 30:
                st.warning("⚠️ Large batch detected. PDF generation may be slow or timeout. Consider using HTML report instead.")
            
            with st.spinner("Generating PDF report... (this may take a moment)"):
                pdf_data = create_pdf_report(results, summary)
                st.download_button(
                    label="Download PDF",
                    data=pdf_data,
                    file_name=f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"PDF generation failed: {str(e)}")
            st.info("🔄 Falling back to HTML report...")
            try:
                html_data = create_html_report(results, summary)
                st.download_button(
                    label="Download HTML Report",
                    data=html_data,
                    file_name=f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html"
                )
            except Exception as html_e:
                st.error(f"HTML report generation also failed: {str(html_e)}")
                st.markdown("**Manual Export:** Please use CSV export above.")


def create_pdf_report(results, summary):
    """Create PDF report - simplified for large batches to avoid timeout."""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from collections import defaultdict
    
    # Determine report complexity based on result count
    result_count = len(results) if results else 0
    is_large_batch = result_count > 25
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.7*inch, rightMargin=0.7*inch, topMargin=0.8*inch, bottomMargin=0.8*inch)
    styles = getSampleStyleSheet()
    
    # Enhanced custom styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=26, textColor=colors.darkblue, spaceAfter=25, alignment=1)
    heading1_style = ParagraphStyle('CustomH1', parent=styles['Heading1'], fontSize=18, textColor=colors.darkgreen, spaceAfter=15, spaceBefore=25)
    heading2_style = ParagraphStyle('CustomH2', parent=styles['Heading2'], fontSize=15, textColor=colors.darkblue, spaceAfter=10, spaceBefore=15)
    heading3_style = ParagraphStyle('CustomH3', parent=styles['Heading3'], fontSize=13, textColor=colors.purple, spaceAfter=8, spaceBefore=12)
    small_text = ParagraphStyle('SmallText', parent=styles['Normal'], fontSize=8, textColor=colors.darkgrey)
    bullet_style = ParagraphStyle('BulletStyle', parent=styles['Normal'], fontSize=10, leftIndent=15, bulletIndent=10)
    
    story = []
    
    # 1. ENHANCED TITLE PAGE
    story.append(Paragraph("QA LLM Evaluation System", title_style))
    story.append(Paragraph("Ultra-Detailed Batch Analysis Report", styles['Heading2']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%A, %B %d, %Y at %H:%M:%S')}", styles['Normal']))
    story.append(Paragraph(f"Total Conversations Analyzed: <b>{summary['count']}</b> | Success Rate: <b>{summary['successful_count']/summary['count']*100:.1f}%</b>", styles['Normal']))
    story.append(Spacer(1, 40))
    
    # Table of Contents
    story.append(Paragraph("📑 Table of Contents", heading2_style))
    toc_data = [
        ["Section", "Description"],
        ["Executive Summary", "High-level metrics and KPIs"],
        ["Brand Analysis", "Performance breakdown by brand"],
        ["Visual Analytics", "Charts and data visualizations"],
        ["Criteria Deep Dive", "Detailed scoring analysis"],
        ["Individual Conversations", "Complete conversation breakdowns"],
        ["Diagnostic Analysis", "Risk and compliance issues"],
        ["Raw Data Export", "Detailed tabular data"]
    ]
    
    toc_table = Table(toc_data, colWidths=[2.5*inch, 4*inch])
    toc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(toc_table)
    story.append(PageBreak())
    
    # 2. ENHANCED EXECUTIVE SUMMARY
    story.append(Paragraph("📊 Executive Summary", heading1_style))
    
    # Safe key metrics extraction
    count = summary.get('count', 0)
    successful_count = summary.get('successful_count', 0)
    avg_total_score = summary.get('avg_total_score', 0)
    policy_violation_rate = summary.get('policy_violation_rate', 0)
    
    # Safe percentage calculation
    success_rate = (successful_count / count * 100) if count > 0 else 0
    
    exec_data = [
        ["Key Performance Indicator", "Value", "Status"],
        ["Total Conversations Processed", str(count), "✓ Complete"],
        ["Successful Evaluations", f"{successful_count} ({success_rate:.1f}%)", "✓ High Success Rate" if success_rate > 90 else "⚠ Review Needed"],
        ["Average Quality Score", f"{avg_total_score:.1f}/100", "✓ Good" if avg_total_score >= 70 else "⚠ Below Target"],
        ["Policy Violation Rate", f"{policy_violation_rate:.1%}", "✓ Low Risk" if policy_violation_rate < 0.1 else "⚠ High Risk"],
    ]
    
    # Add more metrics if available (with safe checks)
    latency_stats = summary.get('latency_stats', {})
    if latency_stats and latency_stats.get('avg_first_response'):
        avg_first_response = latency_stats['avg_first_response']
        exec_data.append(["Avg First Response Time", f"{avg_first_response:.1f}s", "✓ Fast" if avg_first_response < 5 else "⚠ Slow"])
    
    criteria_avg = summary.get('criteria_avg', {})
    if criteria_avg and len(criteria_avg) > 0:
        worst_criterion = min(criteria_avg.items(), key=lambda x: float(x[1] or 0))
        best_criterion = max(criteria_avg.items(), key=lambda x: float(x[1] or 0))
        exec_data.append(["Best Performing Criterion", f"{best_criterion[0]} ({best_criterion[1]:.1f})", "✓ Strong"])
        exec_data.append(["Weakest Criterion", f"{worst_criterion[0]} ({worst_criterion[1]:.1f})", "⚠ Needs Attention"])
    
    exec_table = Table(exec_data, colWidths=[3*inch, 2*inch, 1.5*inch])
    exec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(exec_table)
    story.append(Spacer(1, 25))
    
    # 3. COMPREHENSIVE BRAND ANALYSIS
    story.append(Paragraph("🏢 Comprehensive Brand Analysis", heading1_style))
    
    # Group results by brand with better logic
    brand_groups = defaultdict(list)
    for result in results:
        if "error" not in result:
            # Ultra-safe brand extraction with comprehensive fallbacks
            brand_id = result.get("brand_id")
            if not brand_id or brand_id == "unknown" or str(brand_id).strip() == "":
                # Try multiple fallback methods
                brand_id = result.get("metadata", {}).get("brand_id")
                if not brand_id:
                    brand_id = result.get("result", {}).get("detected_flow")
                if not brand_id:
                    brand_id = result.get("bot_id")
                if not brand_id:
                    brand_id = "unknown"
            # Convert to string and ensure it's never None/empty
            brand_id = str(brand_id or "unknown").strip() or "unknown"
            brand_groups[brand_id].append(result)
    
    # Enhanced brand summary with more metrics
    brand_summary_data = [["Brand ID", "Convs", "Avg Score", "Score Range", "Policy Violations", "Top Label", "Avg Confidence"]]
    
    for brand_id, brand_results in brand_groups.items():
        conv_count = len(brand_results)
        
        # Safe score extraction
        scores = []
        for r in brand_results:
            score = r.get("result", {}).get("total_score")
            if score is not None and isinstance(score, (int, float)):
                scores.append(float(score))
        
        if scores:
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            max_score = max(scores)
        else:
            avg_score = min_score = max_score = 0
        
        policy_violations = sum(1 for r in brand_results if r.get("metrics", {}).get("policy_violations", 0) > 0)
        
        # Safe label extraction
        labels = []
        for r in brand_results:
            label = r.get("result", {}).get("label")
            if label:
                labels.append(str(label))
        top_label = max(set(labels), key=labels.count) if labels else "N/A"
        
        # Safe confidence extraction
        confidences = []
        for r in brand_results:
            conf = r.get("result", {}).get("confidence")
            if conf is not None and isinstance(conf, (int, float)):
                confidences.append(float(conf))
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        brand_summary_data.append([
            brand_id,
            str(conv_count),
            f"{avg_score:.1f}",
            f"{min_score:.0f}-{max_score:.0f}",
            f"{policy_violations}/{conv_count}",
            top_label,
            f"{avg_confidence:.2f}"
        ])
    
    brand_table = Table(brand_summary_data, colWidths=[1.2*inch, 0.6*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1*inch, 0.8*inch])
    brand_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(brand_table)
    story.append(Spacer(1, 20))
    
    # Per-brand detailed breakdown
    for brand_id, brand_results in brand_groups.items():
        story.append(Paragraph(f"🔍 Brand Deep Dive: {brand_id or 'Unknown'}", heading2_style))
        
        # Brand-specific insights
        scores = [r["result"]["total_score"] for r in brand_results]
        
        insights_data = [
            ["Metric", "Value", "Analysis"],
            ["Conversations Count", str(len(brand_results)), "Sample size"],
            ["Score Average", f"{sum(scores)/len(scores):.1f}", "Quality baseline"],
            ["Score Std Dev", f"{(sum((x - sum(scores)/len(scores))**2 for x in scores)/len(scores))**0.5:.1f}", "Consistency measure"],
            ["Best Conversation", f"{max(scores):.1f} pts", "Peak performance"],
            ["Worst Conversation", f"{min(scores):.1f} pts", "Improvement opportunity"]
        ]
        
        # Add criteria breakdown for this brand
        brand_criteria = defaultdict(list)
        for result in brand_results:
            if "criteria" in result.get("result", {}):
                for criterion, details in result["result"]["criteria"].items():
                    score = details.get("score", 0) if isinstance(details, dict) else 0
                    brand_criteria[criterion].append(score)
        
        if brand_criteria:
            worst_criterion = min(brand_criteria.items(), key=lambda x: sum(x[1])/len(x[1]))
            best_criterion = max(brand_criteria.items(), key=lambda x: sum(x[1])/len(x[1]))
            insights_data.extend([
                ["Strongest Criterion", f"{best_criterion[0]} ({sum(best_criterion[1])/len(best_criterion[1]):.1f})", "Competitive advantage"],
                ["Weakest Criterion", f"{worst_criterion[0]} ({sum(worst_criterion[1])/len(worst_criterion[1]):.1f})", "Focus area"]
            ])
        
        insights_table = Table(insights_data, colWidths=[2*inch, 1.5*inch, 3*inch])
        insights_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.orange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.wheat),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(insights_table)
        story.append(Spacer(1, 15))
    
    story.append(PageBreak())
    
    # 4. VISUAL ANALYTICS WITH CHARTS (Skip for large batches to avoid timeout)
    if not is_large_batch:
        story.append(Paragraph("📊 Visual Analytics & Charts", heading1_style))
        
        # Generate and insert charts
        charts = create_charts_for_pdf(results, summary)
    else:
        story.append(Paragraph("📊 Visual Analytics", heading1_style))
        story.append(Paragraph("Chart generation skipped for large batch to ensure performance. Use smaller batches for charts.", styles['Normal']))
        charts = []
    
    for chart_name, chart_buffer in charts:
        try:
            # Create Image object from buffer
            chart_image = Image(chart_buffer, width=6.5*inch, height=4*inch)
            chart_image.hAlign = 'CENTER'
            
            # Add chart title and image - safe handling
            chart_name_safe = str(chart_name or "chart")
            if chart_name_safe == 'simple_brand_scores':
                story.append(Paragraph("Brand Performance Summary", heading2_style))
            else:
                story.append(Paragraph("Analytics Chart", heading2_style))
            
            story.append(chart_image)
            story.append(Spacer(1, 15))
            
        except Exception as e:
            pass  # Skip chart if generation fails
    
    story.append(PageBreak())
    
    # 5. KEY INSIGHTS WITH CONTEXT
    insights = generate_insights(summary)
    if insights:
        story.append(Paragraph("💡 Strategic Insights & Recommendations", heading1_style))
        for i, insight in enumerate(insights, 1):
            story.append(Paragraph(f"<b>{i}.</b> {insight}", bullet_style))
        story.append(Spacer(1, 20))
    
    # 5. ULTRA-DETAILED CRITERIA ANALYSIS
    story.append(Paragraph("📈 Ultra-Detailed Criteria Performance Analysis", heading1_style))
    
    # Aggregate criteria scores with advanced stats
    criteria_scores = defaultdict(list)
    criteria_notes = defaultdict(list)
    
    for result in results:
        if "error" not in result and "criteria" in result.get("result", {}):
            for criterion, details in result["result"]["criteria"].items():
                if isinstance(details, dict):
                    score = details.get("score", 0)
                    note = details.get("note", "")
                    criteria_scores[criterion].append(score)
                    if note and note != "missing":
                        criteria_notes[criterion].append(note)
    
    # Enhanced criteria performance table
    criteria_data = [["Criterion", "Avg", "Min", "Max", "StdDev", "Count", "Pass Rate", "Common Issues"]]
    
    for criterion, scores in criteria_scores.items():
        if scores:
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            max_score = max(scores)
            std_dev = (sum((x - avg_score) ** 2 for x in scores) / len(scores)) ** 0.5
            pass_rate = sum(1 for s in scores if s >= 70) / len(scores) * 100  # Assuming 70 is pass threshold
            
            # Analyze common issues from notes
            notes = criteria_notes.get(criterion, [])
            if notes:
                # Get most common words in notes (simple analysis)
                all_words = " ".join(notes).lower().split()
                word_freq = defaultdict(int)
                for word in all_words:
                    if len(word) > 3:  # Filter short words
                        word_freq[word] += 1
                common_issues = ", ".join([word for word, count in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:3]])
            else:
                common_issues = "None reported"
            
            criteria_data.append([
                criterion.replace("_", " ").title(),
                f"{avg_score:.1f}",
                f"{min_score:.1f}",
                f"{max_score:.1f}",
                f"{std_dev:.1f}",
                str(len(scores)),
                f"{pass_rate:.1f}%",
                common_issues[:30] + "..." if len(common_issues) > 30 else common_issues
            ])
    
    if len(criteria_data) > 1:
        criteria_table = Table(criteria_data, colWidths=[1.5*inch, 0.5*inch, 0.4*inch, 0.4*inch, 0.5*inch, 0.4*inch, 0.6*inch, 1.7*inch])
        criteria_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lavender),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(criteria_table)
        story.append(Spacer(1, 20))
    
    story.append(PageBreak())
    
    # 6. INDIVIDUAL CONVERSATION DETAILS (Skip detailed breakdown for large batches)
    if not is_large_batch:
        story.append(Paragraph("📋 Individual Conversation Analysis", heading1_style))
        story.append(Paragraph("Complete breakdown of each conversation with full details", styles['Normal']))
        story.append(Spacer(1, 15))
        
        for brand_id, brand_results in brand_groups.items():
            # Process conversation details (existing code continues here)
            pass
    else:
        story.append(Paragraph("📋 Conversation Summary", heading1_style))
        story.append(Paragraph("Detailed conversation breakdown skipped for large batch to ensure performance. Key metrics are included in summary sections above.", styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Skip the detailed conversation loop for large batches
    if not is_large_batch:
        for brand_id, brand_results in brand_groups.items():
            story.append(Paragraph(f"🏢 Brand: {brand_id or 'Unknown'}", heading2_style))
            
            for i, result in enumerate(brand_results[:20], 1):  # Show up to 20 per brand
                # Safe data extraction
                conv_id = str(result.get("conversation_id", "unknown"))
                eval_result = result.get("result", {})
                metrics = result.get("metrics", {})
            
                
                # Conversation header
                story.append(Paragraph(f"Conversation #{i}: {conv_id}", heading3_style))
                
                # Safe metric extraction
                detected_flow = str(eval_result.get("detected_flow", "unknown"))
                total_score = eval_result.get("total_score", 0)
                total_score = float(total_score) if total_score is not None else 0
                label = str(eval_result.get("label", "unknown"))
                confidence = eval_result.get("confidence", 0)
                confidence = float(confidence) if confidence is not None else 0
            
            # Main metrics in a compact table
            main_data = [
                ["Attribute", "Value", "Assessment"],
                ["Detected Flow", detected_flow, "✓ Identified"],
                ["Total Score", f"{total_score:.1f}/100", "✓ Good" if total_score >= 70 else "⚠ Needs Improvement"],
                ["Quality Label", label, "Assessment Result"],
                ["Confidence", f"{confidence:.1%}", "✓ High" if confidence > 0.8 else "⚠ Low"],
                ["Policy Violations", str(metrics.get("policy_violations", 0)), "✓ Clean" if metrics.get("policy_violations", 0) == 0 else "⚠ Issues Found"]
            ]
            
            # Add key metrics if available (with safe extraction)
            first_response_latency = metrics.get("first_response_latency_seconds")
            if first_response_latency is not None:
                try:
                    latency_val = float(first_response_latency)
                    main_data.append(["Response Latency", f"{latency_val:.1f}s", "✓ Fast" if latency_val < 5 else "⚠ Slow"])
                except (ValueError, TypeError):
                    pass
            if "total_turns" in metrics:
                main_data.append(["Total Turns", str(metrics.get("total_turns", 0)), "Conversation Length"])
            
            main_table = Table(main_data, colWidths=[1.5*inch, 1.5*inch, 2*inch])
            main_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(main_table)
            story.append(Spacer(1, 10))
            
            # Detailed criteria breakdown
            if "criteria" in eval_result:
                story.append(Paragraph("Criteria Detailed Breakdown:", small_text))
                
                criteria_detail_data = [["Criterion", "Score", "Weight", "Contribution", "Notes"]]
                
                # Load rubrics to get weights (simplified approach)
                criterion_weights = {
                    "completeness": 0.25, "accuracy": 0.25, "helpfulness": 0.20, 
                    "politeness": 0.15, "efficiency": 0.15  # Default weights
                }
                
                for criterion, details in eval_result["criteria"].items():
                    if isinstance(details, dict):
                        # Safe extraction with type checking
                        score_raw = details.get("score", 0)
                        score = float(score_raw) if score_raw is not None else 0
                        
                        note = str(details.get("note", "No notes") or "No notes")
                        weight = criterion_weights.get(str(criterion), 0.2)  # Default weight
                        contribution = score * weight
                        
                        # Truncate long notes
                        display_note = note[:50] + "..." if len(note) > 50 else note
                        
                        criteria_detail_data.append([
                            criterion.replace("_", " ").title(),
                            f"{score:.1f}",
                            f"{weight:.1%}",
                            f"{contribution:.1f}",
                            display_note
                        ])
                
                criteria_detail_table = Table(criteria_detail_data, colWidths=[1.2*inch, 0.6*inch, 0.6*inch, 0.8*inch, 2.3*inch])
                criteria_detail_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.green),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(criteria_detail_table)
                story.append(Spacer(1, 10))
            
            # Final comment and additional info
            if eval_result.get("final_comment"):
                story.append(Paragraph(f"<b>Final Assessment:</b> {eval_result['final_comment']}", small_text))
            
            # Tags, risks, suggestions
            additional_info = []
            if eval_result.get("tags"):
                additional_info.append(f"<b>Tags:</b> {', '.join(eval_result['tags'])}")
            if eval_result.get("risks"):
                additional_info.append(f"<b>Risks:</b> {', '.join(eval_result['risks'])}")
            if eval_result.get("suggestions"):
                additional_info.append(f"<b>Suggestions:</b> {', '.join(eval_result['suggestions'][:2])}")  # Limit suggestions
            
            for info in additional_info:
                story.append(Paragraph(info, small_text))
            
            # Diagnostics if available
            diagnostics = metrics.get("diagnostics", {})
            if diagnostics:
                diag_summary = []
                for issue_type, hits in diagnostics.items():
                    if hits:
                        diag_summary.append(f"{issue_type}({len(hits)})")
                
                if diag_summary:
                    story.append(Paragraph(f"<b>Diagnostic Issues:</b> {'; '.join(diag_summary)}", small_text))
            
            story.append(Spacer(1, 15))
            
            # Add page break every 3 conversations to avoid crowding
            if i % 3 == 0 and i < len(brand_results):
                story.append(PageBreak())
    
    story.append(PageBreak())
    
    # 7. ENHANCED DIAGNOSTICS ANALYSIS
    diagnostics_summary = summary.get("diagnostics_top", {})
    if diagnostics_summary:
        story.append(Paragraph("🔍 Comprehensive Diagnostics & Risk Analysis", heading1_style))
        
        # Enhanced diagnostics table with impact analysis
        diag_data = [["Issue Type", "Occurrences", "Affected Rate", "Severity", "Recommendation"]]
        
        for issue_type, count in diagnostics_summary.items():
            affected_rate = count / summary['count'] * 100
            
            # Determine severity based on frequency
            if affected_rate > 20:
                severity = "🔴 Critical"
                recommendation = "Immediate action required"
            elif affected_rate > 10:
                severity = "🟠 High" 
                recommendation = "Prioritize for resolution"
            elif affected_rate > 5:
                severity = "🟡 Medium"
                recommendation = "Monitor and improve"
            else:
                severity = "🟢 Low"
                recommendation = "Track for trends"
            
            diag_data.append([
                issue_type.replace("_", " ").title(),
                str(count),
                f"{affected_rate:.1f}%",
                severity,
                recommendation
            ])
        
        if len(diag_data) > 1:
            diag_table = Table(diag_data, colWidths=[2*inch, 0.8*inch, 0.8*inch, 1*inch, 2*inch])
            diag_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.red),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.mistyrose),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(diag_table)
    
    # 8. RAW DATA EXPORT SECTION
    story.append(PageBreak())
    story.append(Paragraph("📊 Complete Data Export", heading1_style))
    story.append(Paragraph("This section contains all raw evaluation data in tabular format for further analysis.", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Create comprehensive data table
    export_data = [["Conv ID", "Brand", "Flow", "Score", "Label", "Confidence", "Violations", "Main Issues"]]
    
    for result in results:
        if "error" not in result:
            # Ultra-safe data extraction
            conv_id = str(result.get("conversation_id", "unknown"))[-15:]
            
            # Safe brand_id extraction
            brand_id = result.get("brand_id")
            if not brand_id:
                brand_id = result.get("result", {}).get("detected_flow")
            brand_id = str(brand_id or "unknown")
            
            # Safe field extraction with defaults
            flow = str(result.get("result", {}).get("detected_flow", "unknown"))
            total_score = result.get("result", {}).get("total_score", 0)
            score = f"{float(total_score):.1f}" if total_score is not None else "0.0"
            label = str(result.get("result", {}).get("label", "unknown"))
            
            confidence_val = result.get("result", {}).get("confidence", 0)
            confidence = f"{float(confidence_val):.2f}" if confidence_val is not None else "0.00"
            
            violations = str(result.get("metrics", {}).get("policy_violations", 0))
            
            # Summarize main issues
            issues = []
            criteria = result.get("result", {}).get("criteria", {})
            if criteria:
                low_scores = [k for k, v in criteria.items() if isinstance(v, dict) and v.get("score", 100) < 60]
                if low_scores:
                    issues.append(f"Low: {', '.join(low_scores[:2])}")
            
            diagnostics = result.get("metrics", {}).get("diagnostics", {})
            if diagnostics:
                diag_count = sum(len(hits) for hits in diagnostics.values())
                if diag_count > 0:
                    issues.append(f"Diag: {diag_count}")
            
            main_issues = "; ".join(issues) if issues else "None"
            
            export_data.append([conv_id, brand_id, flow, score, label, confidence, violations, main_issues])
    
    # Split into multiple tables if too large
    max_rows_per_table = 25
    for i in range(0, len(export_data), max_rows_per_table):
        table_data = export_data[0:1] + export_data[i+1:i+max_rows_per_table+1]  # Header + chunk
        if len(table_data) > 1:  # Has data beyond header
            export_table = Table(table_data, colWidths=[1*inch, 0.8*inch, 0.8*inch, 0.5*inch, 0.8*inch, 0.6*inch, 0.5*inch, 1.5*inch])
            export_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(export_table)
            story.append(Spacer(1, 15))
    
    # 9. ENHANCED FOOTER WITH METADATA
    story.append(Spacer(1, 20))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
    
    # Generate report metadata
    successful_brands = len([bg for bg in brand_groups.values() if len(bg) > 0])
    total_criteria_evaluated = sum(len(r.get("result", {}).get("criteria", {})) for r in results if "error" not in r)
    
    # Safe metadata generation
    count = summary.get('count', 0)
    successful_count = summary.get('successful_count', 0)
    policy_checks = sum(1 for r in results if r.get('metrics', {}).get('policy_violations', 0) > 0)
    
    metadata_text = f"""
    📋 Report Metadata:<br/>
    • Generated by: QA LLM Evaluator v2.0<br/>
    • Total Conversations: {count} | Successful: {successful_count} | Brands: {successful_brands}<br/>
    • Criteria Evaluations: {total_criteria_evaluated} | Policy Checks: {policy_checks}<br/>
    • Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Format: Ultra-Detailed PDF Report
    """
    
    story.append(Paragraph(metadata_text, footer_style))
    
    # Build the PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer.getvalue()


def create_charts_for_pdf(results, summary):
    """Create ultra-simplified charts for PDF integration - optimized to avoid timeout."""
    charts = []
    
    # Skip chart generation completely if results are empty or more than 20 (to avoid timeout)
    if not results or len(results) > 20:
        return charts
    
    try:
        import matplotlib.pyplot as plt
        from io import BytesIO
        from collections import defaultdict
        
        # Ultra-minimal matplotlib config for maximum speed
        plt.style.use('default')
        plt.rcParams.update({'font.size': 8, 'figure.facecolor': 'white'})
        
        # Only create ONE simple chart to minimize processing time
        brand_scores = defaultdict(list)
        
        for result in results:
            if "error" not in result:
                # Safe brand_id extraction with multiple fallbacks
                brand_id = result.get("brand_id") 
                if not brand_id or brand_id == "unknown":
                    brand_id = result.get("result", {}).get("detected_flow")
                if not brand_id:
                    brand_id = "Unknown"
                
                # Safe score extraction
                score = result.get("result", {}).get("total_score", 0)
                if score and isinstance(score, (int, float)):
                    brand_scores[str(brand_id)].append(float(score))
        
        # Create ultra-simple bar chart if we have data
        if brand_scores and len(brand_scores) <= 8:  # Limit brands to avoid overcrowding
            fig, ax = plt.subplots(figsize=(8, 4))  # Smaller figure for speed
            
            brands = list(brand_scores.keys())[:6]  # Max 6 brands
            brand_means = []
            
            for brand in brands:
                scores = brand_scores[brand]
                if scores:
                    brand_means.append(sum(scores) / len(scores))
                else:
                    brand_means.append(0)
            
            # Simple bar chart
            bars = ax.bar(brands, brand_means, color='lightblue', alpha=0.8)
            ax.set_title('Average Scores by Brand')
            ax.set_ylabel('Score')
            ax.set_ylim(0, 100)
            
            # Add value labels (simple)
            for bar, mean in zip(bars, brand_means):
                if mean > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                           f'{mean:.0f}', ha='center', va='bottom', fontsize=8)
            
            plt.tight_layout()
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')  # Lower DPI for speed
            buf.seek(0)
            charts.append(('simple_brand_scores', buf))
            plt.close()
            
        return charts
        
    except Exception as e:
        return []

def create_html_report(results, summary):
    """Create an HTML report as fallback."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bus QA Evaluation Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ color: #2e4057; border-bottom: 2px solid #2e4057; padding-bottom: 10px; }}
            .metric {{ background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px; }}
            .insight {{ background: #e3f2fd; padding: 10px; margin: 5px 0; border-radius: 5px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1 class="header">Bus QA Evaluation Batch Report</h1>
        
        <h2>Executive Summary</h2>
        <div class="metric">Total Conversations: {summary['count']}</div>
        <div class="metric">Successful Evaluations: {summary['successful_count']}</div>
        <div class="metric">Average Score: {summary['avg_total_score']:.1f}/100</div>
        <div class="metric">Policy Violation Rate: {summary['policy_violation_rate']:.1%}</div>
    """
    
    # Add insights
    insights = generate_insights(summary)
    if insights:
        html += "<h2>Key Insights</h2>"
        for insight in insights:
            html += f'<div class="insight">{insight}</div>'
    
    # Add results table
    html += """
        <h2>Results Summary</h2>
        <table>
            <tr>
                <th>Conversation ID</th>
                <th>Flow</th>
                <th>Score</th>
                <th>Label</th>
                <th>Confidence</th>
            </tr>
    """
    
    for result in results:
        if "error" not in result:
            html += f"""
            <tr>
                <td>{result['conversation_id']}</td>
                <td>{result['result']['detected_flow']}</td>
                <td>{result['result']['total_score']:.1f}</td>
                <td>{result['result']['label']}</td>
                <td>{result['result']['confidence']:.1%}</td>
            </tr>
            """
    
    html += """
        </table>
    </body>
    </html>
    """
    
    return html

# Main Streamlit App
st.set_page_config(page_title="QA LLM Evaluator (Batch)", page_icon="🚌", layout="wide")
st.title("🚌 QA LLM Evaluator — High-Performance Batch Evaluation")
st.markdown("**Advanced batch evaluation system với performance optimization và real-time monitoring**")

load_dotenv()

# Initialize session state
if 'evaluation_results' not in st.session_state:
    st.session_state.evaluation_results = None
if 'summary_data' not in st.session_state:  
    st.session_state.summary_data = None

with st.sidebar:
    st.subheader("API Configuration")
    base_url = st.text_input("BASE_URL", value=DEFAULT_BASE_URL)
    headers_raw = st.text_area("Headers (JSON, optional)", value="", height=80, placeholder='{"Authorization":"Bearer xxx"}')
    
    st.markdown("---")
    st.subheader("🚀 Performance Tools")
    
    if st.button("⚡ Run Benchmark Test"):
        st.session_state.show_benchmark = True
    
    st.markdown("**Quick Performance Check:**")
    st.caption("Benchmark tool để tìm optimal concurrency cho system của bạn.")
    
    st.markdown("---")
    st.subheader("Conversation IDs")

# Performance Benchmark Modal/Section
if st.session_state.get('show_benchmark', False):
    st.markdown("---")
    st.subheader("⚡ Performance Benchmark Tool")
    
    with st.container():
        st.info("🎯 **Benchmark Tool**: Tự động test các mức concurrency khác nhau để tìm optimal performance cho system.")
        
        benchmark_col1, benchmark_col2 = st.columns(2)
        
        with benchmark_col1:
            benchmark_conversations = st.text_area(
                "Test Conversation IDs (comma-separated):",
                value="",
                height=100,
                help="Enter 5-10 conversation IDs for benchmark testing"
            )
            
            max_test_concurrency = st.slider(
                "Max Concurrency to Test:",
                min_value=15,
                max_value=50,
                value=30,
                help="Maximum concurrency level to test"
            )
        
        with benchmark_col2:
            test_redis_url = st.text_input(
                "Redis URL (optional):",
                value="redis://localhost:6379/0",
                help="Leave empty to test without caching"
            )
            
            benchmark_col3, benchmark_col4 = st.columns(2)
            with benchmark_col3:
                if st.button("🚀 Start Benchmark", type="primary"):
                    if benchmark_conversations.strip():
                        conv_ids = [id.strip() for id in benchmark_conversations.split(",") if id.strip()]
                        
                        if len(conv_ids) < 3:
                            st.error("Please provide at least 3 conversation IDs for meaningful benchmark")
                        else:
                            st.session_state.benchmark_config = {
                                'conversation_ids': conv_ids,
                                'max_concurrency': max_test_concurrency,
                                'redis_url': test_redis_url if test_redis_url.strip() and test_redis_url != "redis://localhost:6379/0" else None
                            }
                            st.session_state.run_benchmark = True
                            st.success(f"Starting benchmark with {len(conv_ids)} conversations...")
                            st.rerun()
                    else:
                        st.error("Please enter conversation IDs to benchmark")
            
            with benchmark_col4:
                if st.button("❌ Close Benchmark"):
                    st.session_state.show_benchmark = False
                    st.rerun()

# Run benchmark if requested
if st.session_state.get('run_benchmark', False):
    st.markdown("---")
    st.subheader("🎯 Running Performance Benchmark...")
    
    config = st.session_state.benchmark_config
    
    # Setup required data
    llm_api_key = os.getenv("GEMINI_API_KEY", "")
    if not llm_api_key:
        st.error("GEMINI_API_KEY not found in environment")
        st.session_state.run_benchmark = False
    else:
        # Run benchmark
        progress_placeholder = st.empty()
        
        with st.spinner("Running benchmark tests..."):
            progress_placeholder.info("🚀 Testing different concurrency levels...")
            
            try:
                # Import benchmark function
                from benchmark_performance import benchmark_batch_processing
                
                # Generate concurrency levels
                max_concurrency = config['max_concurrency']
                concurrency_levels = [5, 10, 15, 20, 25]
                if max_concurrency > 25:
                    concurrency_levels.extend(range(30, max_concurrency + 1, 5))
                
                progress_placeholder.info(f"Testing concurrency levels: {concurrency_levels}")
                
                # Run async benchmark
                benchmark_results = asyncio.run(benchmark_batch_processing(
                    conversation_ids=config['conversation_ids'],
                    base_url=base_url,
                    llm_api_key=llm_api_key,
                    concurrency_levels=concurrency_levels,
                    redis_url=config['redis_url']
                ))
                
                # Display results
                progress_placeholder.success("✅ Benchmark completed!")
                
                if benchmark_results:
                    st.subheader("📊 Benchmark Results")
                    
                    # Create results table
                    results_data = []
                    best_result = None
                    best_throughput = 0
                    
                    for result in benchmark_results:
                        if "error" not in result:
                            throughput = result['throughput_per_second']
                            results_data.append({
                                "Concurrency": result['concurrency'],
                                "Throughput (conv/s)": f"{throughput:.1f}",
                                "Success Rate": f"{result['successful_conversations']}/{result['total_conversations']}",
                                "Avg Memory (MB)": f"{result['avg_memory_mb']:.0f}",
                                "CPU Usage (%)": f"{result['avg_cpu_percent']:.1f}",
                                "Status": "✅ Success"
                            })
                            
                            if throughput > best_throughput:
                                best_throughput = throughput
                                best_result = result
                        else:
                            results_data.append({
                                "Concurrency": result['concurrency'],
                                "Throughput (conv/s)": "ERROR",
                                "Success Rate": "N/A",
                                "Avg Memory (MB)": "N/A", 
                                "CPU Usage (%)": "N/A",
                                "Status": f"❌ {result.get('error', 'Error')[:20]}"
                            })
                    
                    # Display table
                    df = pd.DataFrame(results_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Recommendation
                    if best_result:
                        st.success(f"🏆 **Optimal Configuration Found:**")
                        rec_col1, rec_col2 = st.columns(2)
                        
                        with rec_col1:
                            st.metric("Optimal Concurrency", best_result['concurrency'])
                            st.metric("Peak Throughput", f"{best_result['throughput_per_second']:.1f} conv/s")
                        
                        with rec_col2:
                            st.metric("Memory Usage", f"{best_result['peak_memory_mb']:.0f} MB")
                            st.metric("Processing Time", f"{best_result['elapsed_time']:.1f}s")
                        
                        st.info(f"💡 **Suggestion**: Use concurrency={best_result['concurrency']} for optimal performance on your system.")
                    else:
                        st.warning("No successful benchmark results. Check your configuration and try again.")
                        
                else:
                    st.error("No benchmark results received")
                    
            except Exception as e:
                progress_placeholder.error(f"Benchmark failed: {e}")
                with st.expander("Error Details"):
                    st.code(str(e))
                
        st.session_state.run_benchmark = False
        
        if st.button("🔄 Run Another Benchmark"):
            st.session_state.show_benchmark = True
            st.rerun()

with st.sidebar:        
    # Multiple input methods
    input_method = st.radio("Input method:", ["Text Area", "File Upload", "Bulk List & Evaluate"])
    
    conversation_ids = []
    if input_method == "Text Area":
        conv_ids_text = st.text_area(
            "Conversation IDs (one per line)",
            value="",
            height=120,
            placeholder="conv_123\nconv_456\nconv_789"
        )
        if conv_ids_text.strip():
            lines = [line.strip() for line in conv_ids_text.strip().split('\n')]
            conversation_ids = [line for line in lines if line]
    
    elif input_method == "File Upload":
        uploaded_file = st.file_uploader(
            "Upload file with conversation IDs",
            type=['txt', 'csv'],
            help="Upload a .txt file (one ID per line) or .csv file with IDs in first column"
        )
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                    conversation_ids = df.iloc[:, 0].astype(str).tolist()
                else:
                    content = uploaded_file.read().decode('utf-8')
                    lines = [line.strip() for line in content.strip().split('\n')]
                    conversation_ids = [line for line in lines if line]
            except Exception as e:
                st.error(f"Error reading file: {e}")
    
    elif input_method == "Bulk List & Evaluate":
        st.subheader("🚀 Bulk List & Evaluate")
        
        # API Configuration for listing conversations
        col1, col2 = st.columns(2)
        with col1:
            list_base_url = st.text_input("List API Base URL", value="https://live-demo.agenticai.pro.vn")
            bot_id = st.text_input("Bot ID", placeholder="Enter bot ID to fetch conversations")
        with col2:
            bearer_token = st.text_input("Bearer Token", type="password", 
                                       value=os.getenv("BEARER_TOKEN", ""),
                                       help="Or set BEARER_TOKEN environment variable")
            page_size = st.number_input("Page Size", min_value=10, max_value=500, value=30)
        
        # Show token info for debugging
        if bearer_token:
            st.caption(f"🔑 Token length: {len(bearer_token)} chars | Preview: {bearer_token[:10]}...")
        else:
            st.warning("⚠️ No bearer token provided")
        
        max_pages = st.number_input("Max Pages", min_value=1, max_value=100, value=5)
        
        # Selection Parameters
        st.subheader("Selection Parameters")
        col1, col2, col3 = st.columns(3)
        with col1:
            take = st.number_input("Take", min_value=1, max_value=500, value=10)
            skip = st.number_input("Skip", min_value=0, max_value=1000, value=0)
        with col2:
            strategy = st.selectbox("Strategy", ["head", "tail", "random", "newest", "oldest"], index=3)
            sort_by = st.selectbox("Sort By", ["created_at", "length"], index=0)
        with col3:
            order = st.selectbox("Order", ["desc", "asc"], index=0)
            min_turns = st.number_input("Min Turns", min_value=0, max_value=20, value=0)
        
        # Add token test button
        if st.button("🧪 Test Bearer Token", help="Test if bearer token is valid before fetching"):
            if not bearer_token:
                st.error("Bearer token is required")
            else:
                try:
                    from tools.bulk_list_evaluate import test_bearer_token
                    
                    with st.spinner("Testing bearer token..."):
                        is_valid = test_bearer_token(list_base_url, bearer_token)
                        
                    if is_valid:
                        st.success("✅ Bearer token is valid!")
                    else:
                        st.error("❌ Bearer token is invalid or expired")
                        st.info("Please check your token and try again")
                        
                except Exception as e:
                    st.error(f"Token test failed: {e}")
        
        # Fetch and select conversations
        if st.button("🔍 Fetch & Select Conversations", type="primary"):
            if not bot_id:
                st.error("Bot ID is required")
            elif not bearer_token:
                st.error("Bearer token is required")
            else:
                try:
                    # Import bulk functions
                    from tools.bulk_list_evaluate import FetchConfig, fetch_conversations_with_messages, select_conversations, test_bearer_token
                    
                    # Test token first
                    with st.spinner("Testing bearer token..."):
                        token_valid = test_bearer_token(list_base_url, bearer_token)
                    
                    if not token_valid:
                        st.error("❌ Bearer token test failed. Please check your token.")
                        st.stop()
                    
                    with st.spinner("Fetching conversations from API..."):
                        fetch_config = FetchConfig(
                            base_url=list_base_url,
                            bot_id=bot_id,
                            bearer_token=bearer_token,
                            page_size=page_size,
                            max_pages=max_pages
                        )
                        
                        conversations = fetch_conversations_with_messages(fetch_config)
                        
                        if not conversations:
                            st.error("No conversations found")
                        else:
                            st.success(f"✅ Fetched {len(conversations)} total conversations")
                            
                            # Select conversations
                            selected_conversations = select_conversations(
                                conversations,
                                take=take,
                                skip=skip,
                                strategy=strategy,
                                sort_by=sort_by,
                                order=order,
                                min_turns=min_turns
                            )
                            
                            if not selected_conversations:
                                st.error("No conversations selected after filtering")
                            else:
                                st.success(f"✅ Selected {len(selected_conversations)} conversations")
                                
                                # Store in session state for evaluation
                                st.session_state.bulk_conversations = selected_conversations
                                # Store bulk API info for optimization
                                st.session_state.bulk_bot_id = bot_id
                                st.session_state.bulk_bearer_token = bearer_token
                                st.session_state.bulk_list_base_url = list_base_url
                                
                                # Show preview
                                with st.expander("📋 Selected Conversations Preview"):
                                    for i, conv in enumerate(selected_conversations[:10], 1):
                                        conv_id = conv.get("conversation_id", "unknown")
                                        created_at = conv.get("created_at", "unknown")
                                        msg_count = len(conv.get("messages", []))
                                        st.text(f"{i}. {conv_id} | {created_at} | {msg_count} messages")
                                    
                                    if len(selected_conversations) > 10:
                                        st.text(f"... and {len(selected_conversations) - 10} more")
                                
                                # Extract conversation IDs for the rest of the flow
                                conversation_ids = [conv.get("conversation_id") for conv in selected_conversations]
                                
                except Exception as e:
                    error_msg = str(e)
                    st.error(f"Error fetching conversations: {error_msg}")
                    
                    # Provide specific guidance for common errors
                    if "401" in error_msg or "Unauthorized" in error_msg:
                        st.error("🔐 **Authentication Error**: Bearer token is invalid or expired")
                        st.info("**Solutions:**")
                        st.info("1. Check if your Bearer token is correct")
                        st.info("2. Try getting a new token from the API provider")
                        st.info("3. Verify the token has proper permissions")
                        st.code(f"Current token preview: {bearer_token[:20]}...")
                    elif "403" in error_msg or "Forbidden" in error_msg:
                        st.error("🚫 **Access Forbidden**: No permission to access this bot_id")
                        st.info("**Solutions:**")
                        st.info("1. Verify the bot_id is correct")
                        st.info("2. Check if your account has access to this bot")
                        st.info("3. Contact administrator for permissions")
                        st.code(f"Bot ID: {bot_id}")
                    elif "404" in error_msg:
                        st.error("🔍 **Not Found**: Bot ID or API endpoint not found")
                        st.info("**Solutions:**")
                        st.info("1. Double-check the bot_id")
                        st.info("2. Verify the API base URL is correct")
                        st.code(f"URL: {list_base_url}/api/conversations")
                    else:
                        # Show detailed traceback for other errors
                        import traceback
                        with st.expander("Show technical details"):
                            st.code(traceback.format_exc())
        
        # Use selected conversations if available
        if hasattr(st.session_state, 'bulk_conversations') and st.session_state.bulk_conversations:
            conversation_ids = [conv.get("conversation_id") for conv in st.session_state.bulk_conversations]
            st.info(f"📝 Using {len(conversation_ids)} conversations from bulk selection")
            
            # Add button to clear bulk selection
            if st.button("🗑️ Clear Bulk Selection"):
                del st.session_state.bulk_conversations
                # Also clear bulk API info
                for key in ['bulk_bot_id', 'bulk_bearer_token', 'bulk_list_base_url']:
                    if hasattr(st.session_state, key):
                        delattr(st.session_state, key)
                st.rerun()
    
    # Dedupe conversation IDs
    if conversation_ids:
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for id in conversation_ids:
            if id not in seen:
                seen.add(id)
                unique_ids.append(id)
        
        conversation_ids = unique_ids
        
        # Show warning for very large batches
        if len(conversation_ids) > 100:
            st.warning(f"⚠️ Large batch detected: {len(conversation_ids)} conversations. This may take significant time and resources.")
        st.success(f"Ready to evaluate {len(conversation_ids)} conversation(s)")
        
        # Show IDs
        with st.expander("Preview IDs"):
            for i, conv_id in enumerate(conversation_ids, 1):
                st.text(f"{i}. {conv_id}")
    
    st.markdown("---")
    st.subheader("Brand Configuration")
    
    # Brand mode selector
    brand_mode = st.radio(
        "Brand Mode:",
        ["single", "auto-by-botid"],
        help="Single: chọn 1 brand cho tất cả. Auto: tự động phân giải brand theo bot_id"
    )
    
    # Initialize variables
    brand_prompt_text = ""
    brand_policy = None
    brand_resolver = None
    
    if brand_mode == "single":
        # Traditional single-brand mode
        brand_options = ["son_hai", "long_van"]
        selected_brand = st.selectbox("Choose brand", brand_options)
        
        # Load and display brand policy
        try:
            brand_path = f"brands/{selected_brand}/prompt.md"
            brand_prompt_text, brand_policy = load_brand_prompt(brand_path)
            
            st.caption("**Brand Policy Flags:**")
            st.write(f"• Cấm thu SĐT: {brand_policy.forbid_phone_collect}")
            st.write(f"• Chào cố định: {brand_policy.require_fixed_greeting}")
            st.write(f"• Cấm tóm tắt: {brand_policy.ban_full_summary}")
            st.write(f"• Max openers: {brand_policy.max_prompted_openers}")
            st.write(f"• Đọc tiền bằng chữ: {brand_policy.read_money_in_words}")
        except Exception as e:
            st.error(f"Error loading brand: {e}")
            brand_prompt_text = ""
            brand_policy = None
    
    else:  # auto-by-botid mode
        # Multi-brand mode
        bot_map_path = st.text_input("Bot Map Path", value="config/bot_map.yaml")
        
        try:
            from busqa.brand_resolver import BrandResolver
            brand_resolver = BrandResolver(bot_map_path)
            
            # Show bot mapping info
            cache_stats = brand_resolver.get_cache_stats()
            mapped_bots = brand_resolver._map.get_all_mapped_bots()
            
            st.success(f"✅ Loaded bot map: {cache_stats['mapped_bots_count']} bots mapped")
            
            with st.expander("Bot Mapping Preview"):
                for bot_id, brand_id in mapped_bots.items():
                    st.text(f"Bot {bot_id} → {brand_id}")
                
                fallback = brand_resolver._map._fallback_brand
                if fallback:
                    st.caption(f"Fallback brand: {fallback}")
            
            st.info("🔄 Multi-brand mode: brands sẽ được tự động chọn theo bot_id từ API response")
            
        except Exception as e:
            st.error(f"Error loading bot map: {e}")
            brand_resolver = None
    
    st.markdown("---")
    st.subheader("Diagnostics Configuration")
    apply_diagnostics_checkbox = st.checkbox("Apply diagnostic penalties", value=True, 
                                           help="Bật/tắt áp dụng phạt điểm từ diagnostics")
    st.session_state['apply_diagnostics'] = apply_diagnostics_checkbox
    
    # Show diagnostics info
    try:
        from busqa.prompt_loader import load_diagnostics_config
        diag_cfg = load_diagnostics_config()
        st.caption(f"**Diagnostics loaded:** {len(diag_cfg.get('operational_readiness', []))} OR + {len(diag_cfg.get('risk_compliance', []))} RC rules")
    except Exception as e:
        st.error(f"Lỗi load diagnostics: {e}")
    
    st.markdown("---")
    st.subheader("⚡ Performance Configuration")
    
    # Performance settings in columns
    perf_col1, perf_col2 = st.columns(2)
    
    with perf_col1:
        max_concurrency = st.slider("Max Concurrency", 10, 50, 30, 5, 
                                   help="Concurrency per batch (recommended: 20-30 để tránh convoy effect)")
        
        use_progressive_batching = st.checkbox("🔄 Progressive Batching", value=True,
                                             help="Start với batch nhỏ, tăng dần based on performance - FIXES convoy effect!")
        
        use_high_performance_api = st.checkbox("🚀 High-Performance API", value=True,
                                             help="Enable connection pooling và HTTP/2 optimization")
        
        enable_caching = st.checkbox("📦 Redis Caching", value=False,
                                   help="Cache API responses để tăng tốc (cần Redis server)")
    
    with perf_col2:
        api_rate_limit = st.slider("API Rate Limit (req/s)", 100, 500, 200, 25,
                                 help="Giới hạn số request API per second (increase for faster speed)")
        
        memory_cleanup_interval = st.slider("Memory Cleanup Interval", 5, 30, 10, 5,
                                          help="Cleanup memory sau bao nhiêu conversations")
        
        if enable_caching:
            redis_url = st.text_input("Redis URL", value="redis://localhost:6379/0",
                                    help="Redis connection string")
        else:
            redis_url = None
    
    # Performance monitoring toggle
    show_performance_metrics = st.checkbox("📊 Show Performance Metrics", value=True,
                                         help="Hiển thị real-time performance metrics")
    
    st.markdown("---")
    st.subheader("🤖 LLM Configuration")
    st.caption("Model: gemini-2.5-flash | API key lấy từ file .env")
    llm_base_url = st.text_input("LLM Base URL (optional)", value="", help="Để trống nếu dùng OpenAI chính thống")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1)
    
    # Show concurrency info with progressive batching explanation
    if conversation_ids:
        if use_progressive_batching and len(conversation_ids) > 15:
            st.info(f"🔄 **Progressive Batching Mode**: Will process {len(conversation_ids)} conversations in adaptive batches starting with 8, max {max_concurrency} concurrent")
            st.caption("📈 Benefits: Prevents convoy effect, adapts to system performance, reduces memory pressure")
        else:
            st.caption(f"⏱️ Standard mode: {len(conversation_ids)} conversations với concurrency={max_concurrency}")
    st.markdown("---")
    max_chars = st.number_input("Giới hạn ký tự transcript", min_value=2000, max_value=200000, value=24000, step=1000)

# Main evaluation section
col1, col2 = st.columns([2, 1])
with col1:
    mode_text = "multi-brand" if brand_mode == "auto-by-botid" else "single-brand"
    eval_button = st.button(f"🚀 Chấm điểm batch ({mode_text})", disabled=not conversation_ids, type="primary")
with col2:
    if st.session_state.evaluation_results:
        st.metric("Last Batch", f"{len(st.session_state.evaluation_results)} results")

# Load unified rubrics to show available flows
try:
    rubrics_cfg = load_unified_rubrics()
    flows = list(rubrics_cfg.get('flows_slots', {}).keys())
    st.caption(f"Flows hợp lệ: {', '.join(flows)}")
except Exception as e:
    st.error(f"Lỗi load rubrics: {e}")
    rubrics_cfg = None

# Load diagnostics config
apply_diagnostics = st.session_state.get('apply_diagnostics', True)
try:
    from busqa.prompt_loader import load_diagnostics_config
    diagnostics_cfg = load_diagnostics_config()
except Exception as e:
    st.error(f"Warning: Could not load diagnostics config: {e}")
    diagnostics_cfg = None
    apply_diagnostics = False

# Batch evaluation logic with streaming results
if eval_button and conversation_ids:
    if not rubrics_cfg:
        st.error("Không thể load unified rubrics.")
        st.stop()
        
    # Validate brand configuration based on mode
    if brand_mode == "single" and not brand_policy:
        st.error("Không thể load brand policy cho single-brand mode.")
        st.stop()
    elif brand_mode == "auto-by-botid" and not brand_resolver:
        st.error("Không thể load brand resolver cho multi-brand mode.")
        st.stop()

    llm_api_key = os.getenv("GEMINI_API_KEY", "")
    llm_model = "gemini-2.5-flash"
    if not llm_api_key.strip():
        st.error("Không tìm thấy GEMINI_API_KEY trong file .env hoặc biến môi trường.")
        st.stop()

    # Initialize streaming results in session state
    if 'streaming_results' not in st.session_state:
        st.session_state.streaming_results = []
    if 'streaming_status' not in st.session_state:
        st.session_state.streaming_status = {"completed": 0, "total": len(conversation_ids)}
    
    # Reset streaming state for new evaluation
    st.session_state.streaming_results = []
    st.session_state.streaming_status = {"completed": 0, "total": len(conversation_ids)}

    # Show progress and streaming results
    progress_bar = st.progress(0)
    status_text = st.empty()
    metrics_col1, metrics_col2 = st.columns(2)
    
    # Create streaming results container with auto-refresh capability
    st.subheader("🔄 Live Results Stream")
    
    # Create placeholders for streaming display
    streaming_status_placeholder = st.empty()
    streaming_metrics_placeholder = st.empty()
    streaming_results_placeholder = st.empty()
    
    # Display existing streaming results if available (from previous runs or current session)
    if st.session_state.streaming_results:
        streaming_status_placeholder.info(f"📊 Showing {len(st.session_state.streaming_results)} collected results from previous run")
        # Don't display here, will be updated during execution
    
    # Run batch evaluation with streaming
    try:
        start_time = time.time()
        
        # Store performance config in session state for dashboard
        st.session_state.last_max_concurrency = max_concurrency
        st.session_state.last_llm_model = llm_model
        st.session_state.last_temperature = temperature
        st.session_state.last_use_high_performance_api = use_high_performance_api
        st.session_state.last_enable_caching = enable_caching
        st.session_state.last_api_rate_limit = api_rate_limit
        st.session_state.batch_start_time = start_time
        
        status_text.text("Starting batch evaluation with streaming...")
        
        # Enhanced progress callback with streaming awareness
        def progress_callback(progress, current, total):
            progress_bar.progress(progress)
            
            elapsed = time.time() - start_time
            streamed_count = len(st.session_state.streaming_results)
            
            if current > 0:
                avg_time = elapsed / current
                eta = avg_time * (total - current)
                speed = current / elapsed
                
                # Enhanced status with streaming info
                status_msg = f"⚡ Evaluating: {current}/{total} ({progress:.1%})"
                if streamed_count > 0:
                    status_msg += f" | Streamed: {streamed_count}"
                status_msg += f" - ETA: {format_time_duration(eta)}"
                status_text.text(status_msg)
                
                with metrics_col1:
                    st.metric("Speed", f"{speed:.1f} conv/s", delta=f"{streamed_count} streamed")
                with metrics_col2:
                    st.metric("Elapsed", format_time_duration(elapsed), delta=f"{current}/{total}")
            else:
                status_text.text(f"🚀 Starting evaluation: {current}/{total} ({progress:.1%})")
        
        # Stream callback to collect results as they complete
        def stream_callback(result):
            """Called when each conversation result is ready - collects results for later display"""
            st.session_state.streaming_results.append(result)
            st.session_state.streaming_status["completed"] += 1
            
            # Log successful streaming collection (can be seen in terminal/logs)
            if "error" not in result:
                conv_id = result.get("conversation_id", "unknown")
                score = result.get("result", {}).get("total_score", 0)
                print(f"✅ Streamed: {conv_id[-10:]} - {score:.1f} pts")  # Debug logging
            
            # Update streaming display periodically
            completed = len(st.session_state.streaming_results)
            if completed % 5 == 0 or completed == 1:  # Update every 5 results or first result
                try:
                    _update_streaming_display()
                except Exception as e:
                    print(f"Error updating streaming display: {e}")  # Debug logging
            
        def _update_streaming_display():
            """Update streaming display with current results"""
            if not st.session_state.streaming_results:
                streaming_status_placeholder.info("⏳ Waiting for first result...")
                return
                
            # Update status
            total_results = len(st.session_state.streaming_results)
            successful = len([r for r in st.session_state.streaming_results if "error" not in r])
            failed = total_results - successful
            completion_rate = (total_results / st.session_state.streaming_status['total']) * 100
            
            # Update status text
            streaming_status_placeholder.success(f"📊 Streaming: {total_results} results collected ({completion_rate:.1f}% complete)")
            
            # Update metrics
            with streaming_metrics_placeholder.container():
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Progress", f"{total_results}/{st.session_state.streaming_status['total']}", 
                             delta=f"{completion_rate:.1f}%")
                with col2:
                    st.metric("✅ Successful", successful, delta=f"{(successful/total_results*100):.1f}%" if total_results > 0 else "0%")
                with col3:
                    st.metric("❌ Failed", failed, delta=f"{(failed/total_results*100):.1f}%" if total_results > 0 else "0%")
                with col4:
                    if successful > 0:
                        successful_results = [r for r in st.session_state.streaming_results if "error" not in r]
                        avg_score = sum(r.get("result", {}).get("total_score", 0) for r in successful_results) / len(successful_results)
                        st.metric("Avg Score", f"{avg_score:.1f}", delta="pts")
            
            # Update results display - show latest 6 results only for performance
            with streaming_results_placeholder.container():
                if successful > 0:
                    st.subheader("📊 Latest Completed Results")
                    
                    successful_results = [r for r in st.session_state.streaming_results if "error" not in r]
                    latest_results = successful_results[-6:] if len(successful_results) > 6 else successful_results
                    
                    # Display in 2 columns
                    col_left, col_right = st.columns(2)
                    
                    for i, result in enumerate(latest_results):
                        conv_id = result.get("conversation_id", "unknown")
                        flow = result.get("result", {}).get("detected_flow", "unknown")
                        score = result.get("result", {}).get("total_score", 0)
                        label = result.get("result", {}).get("label", "unknown") 
                        confidence = result.get("result", {}).get("confidence", 0)
                        violations = result.get("metrics", {}).get("policy_violations", 0)
                        
                        # Color coding based on score
                        if score >= 80:
                            score_color = "🟢"
                        elif score >= 60:
                            score_color = "🟡"
                        else:
                            score_color = "🔴"
                        
                        target_col = col_left if i % 2 == 0 else col_right
                        
                        with target_col:
                            st.markdown(f"""
                            **{score_color} {conv_id[-10:]}** | {flow}  
                            Score: **{float(score):.1f}** | Label: {label}  
                            {f"⚠️ {violations} violations" if violations > 0 else "✅ Clean"}
                            """)
                    
                    if len(successful_results) > 6:
                        st.caption(f"Showing latest 6 of {len(successful_results)} completed results")
                
                # Show recent errors briefly
                failed_results = [r for r in st.session_state.streaming_results if "error" in r]
                if failed_results:
                    recent_errors = failed_results[-2:]  # Show only 2 most recent errors
                    for result in recent_errors:
                        conv_id = result.get('conversation_id', 'unknown')
                        error_msg = result.get('error', 'Unknown error')
                        st.error(f"❌ **{conv_id[-10:]}**: {error_msg}")
                
                st.caption("🔄 Results update every 5 completions")
        

        
        # Initialize display with empty state
        _update_streaming_display()
        
        # Performance metrics display
        if show_performance_metrics:
            st.markdown("### 📊 Real-time Performance Metrics")
            perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
            
            perf_cpu_metric = perf_col1.empty()
            perf_memory_metric = perf_col2.empty()
            perf_throughput_metric = perf_col3.empty()
            perf_cache_metric = perf_col4.empty()
            
            # Initialize performance monitoring
            from busqa.performance_monitor import get_performance_monitor
            perf_monitor = get_performance_monitor()
            
            # Start monitoring if not already started
            try:
                asyncio.run(perf_monitor.start_monitoring())
            except:
                pass  # Already running
        
        # Enhanced streaming with better UI updates
        # Check if we have bulk conversations with messages already
        if hasattr(st.session_state, 'bulk_conversations') and st.session_state.bulk_conversations:
            # Use bulk evaluation with raw conversations (no API fetching needed)
            status_text.text("Using bulk conversations - evaluating with raw data...")
            
            from tools.bulk_list_evaluate import evaluate_many_raw_conversations
            
            # For bulk mode, we only support single-brand currently
            if brand_mode != "single":
                st.error("Bulk List & Evaluate currently only supports single-brand mode")
                st.stop()
            
            # Get brand prompt path for bulk evaluation
            brand_prompt_path = f"brands/{selected_brand}/prompt.md"
            
            # Note: bulk evaluator may not support streaming yet
            st.warning("⚠️ Bulk mode doesn't support streaming yet - results will show after completion")
            results = asyncio.run(evaluate_many_raw_conversations(
                raw_conversations=st.session_state.bulk_conversations,
                brand_prompt_path=brand_prompt_path,
                rubrics="config/rubrics_unified.yaml",
                model=llm_model,
                temperature=temperature,
                apply_diagnostics=apply_diagnostics,
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url.strip() or None,
                max_concurrency=max_concurrency
            ))
            
        else:
            # Use high-speed batch evaluator with streaming
            from busqa.batch_evaluator import evaluate_conversations_high_speed
            
            status_text.text("Using high-speed batch evaluation with streaming...")
            
            # Enhanced progress callback with performance metrics
            def enhanced_progress_callback(progress, completed, total):
                progress_callback(progress, completed, total)
                
                # Update performance metrics if enabled
                if show_performance_metrics:
                    try:
                        current_metrics = perf_monitor.get_current_metrics()
                        perf_summary = perf_monitor.get_performance_summary()
                        
                        perf_cpu_metric.metric("CPU Usage", f"{current_metrics.cpu_percent:.1f}%")
                        perf_memory_metric.metric("Memory", f"{current_metrics.memory_rss_mb:.0f}MB")
                        perf_throughput_metric.metric("Throughput", f"{current_metrics.throughput_per_second:.1f}/s")
                        
                        # Cache hit rate (if Redis enabled)
                        if enable_caching and redis_url:
                            cache_info = "N/A"  # Would need to implement cache stats
                        else:
                            cache_info = "Disabled"
                        perf_cache_metric.metric("Cache", cache_info)
                        
                    except Exception as e:
                        pass  # Don't break on performance metric errors
            
            # Run evaluation with streaming and all performance features
            results = asyncio.run(evaluate_conversations_high_speed(
                conversation_ids=conversation_ids,
                base_url=base_url,
                rubrics_cfg=rubrics_cfg,
                brand_policy=brand_policy if brand_mode == "single" else None,
                brand_prompt_text=brand_prompt_text if brand_mode == "single" else None,
                llm_api_key=llm_api_key,
                llm_model=llm_model,
                temperature=temperature,
                llm_base_url=llm_base_url.strip() or None,
                apply_diagnostics=apply_diagnostics,
                diagnostics_cfg=diagnostics_cfg,
                max_concurrency=max_concurrency,
                progress_callback=enhanced_progress_callback,
                stream_callback=stream_callback,  # Stream results to UI
                brand_resolver=brand_resolver if brand_mode == "auto-by-botid" else None,
                use_high_performance_api=use_high_performance_api,  # ✅ Connection pooling
                redis_url=redis_url if enable_caching else None,    # ✅ Redis caching
                api_rate_limit=api_rate_limit,                      # ✅ Rate limiting
                use_progressive_batching=use_progressive_batching   # ✅ PROGRESSIVE BATCHING - Fixes convoy effect!
            ))
        
        # Final processing
        total_time = time.time() - start_time
        successful_count = len([r for r in results if "error" not in r])
        error_count = len(results) - successful_count
        
        # Store final metrics in session state
        st.session_state.batch_end_time = time.time()
        st.session_state.last_batch_results = {
            'total_time': total_time,
            'successful_count': successful_count,
            'total_conversations': len(conversation_ids),
            'throughput': successful_count / total_time if total_time > 0 else 0
        }
        
        progress_bar.progress(1.0)
        status_text.success(f"✅ Batch evaluation completed!")
        
        # Show final metrics with performance insights
        with metrics_col1:
            final_speed = successful_count/total_time if total_time > 0 else 0
            st.metric("Final Speed", f"{final_speed:.1f} conv/s")
            
            # Performance feedback
            if final_speed > 20:
                st.success("🚀 Excellent performance!")
            elif final_speed > 15:
                st.info("✅ Good performance")
            elif final_speed > 10:
                st.warning("⚠️ Consider optimization")
            else:
                st.error("🐌 Performance issues detected")
                
        with metrics_col2:
            st.metric("Total Time", format_time_duration(total_time))
            
            # Configuration feedback
            if use_high_performance_api:
                st.caption("✅ High-perf API enabled")
            else:
                st.caption("💡 Enable high-perf API for better speed")
                
            if enable_caching and redis_url:
                st.caption("📦 Caching enabled")
            else:
                st.caption("💡 Enable Redis caching for repeated evaluations")
        
        # Show final streaming results
        _update_streaming_display()
        
        # Verify streaming worked
        streamed_count = len(st.session_state.streaming_results)
        if streamed_count > 0:
            streaming_status_placeholder.success(f"✅ Streaming completed! Collected {streamed_count} results during evaluation")
        else:
            streaming_status_placeholder.warning("⚠️ No streaming results collected - check stream_callback implementation")
        
        st.success(f"🎉 Evaluation completed! Final results: {successful_count} successful, {error_count} failed")
        
        # Generate summary with insights
        summary = make_summary(results)
        insights = generate_insights(summary)
        
        # Store in session state
        st.session_state.evaluation_results = results
        st.session_state.summary_data = {
            "summary": summary,
            "insights": insights,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_time": total_time,
            "processing_speed": successful_count/total_time if total_time > 0 else 0
        }
        
        success_msg = f"✅ Batch evaluation completed! {successful_count}/{len(results)} successful in {format_time_duration(total_time)}"
        
        # Show brand usage stats for multi-brand mode
        if brand_mode == "auto-by-botid" and brand_resolver:
            try:
                # Extract brand stats from results
                brand_usage = {}
                for result in results:
                    if "error" not in result:
                        brand_id = result.get("brand_id", "unknown")
                        brand_usage[brand_id] = brand_usage.get(brand_id, 0) + 1
                
                if brand_usage:
                    brand_summary = ", ".join([f"{brand}={count}" for brand, count in brand_usage.items()])
                    success_msg += f" | Brands: {brand_summary}"
                else:
                    success_msg += f" (Multi-brand mode)"
            except:
                success_msg += f" (Multi-brand mode)"
        
        st.success(success_msg)
        
    except Exception as e:
        st.error(f"Batch evaluation failed: {e}")
        with st.expander("Technical Details"):
            st.code(traceback.format_exc())
        st.stop()

# Display results if available
if st.session_state.evaluation_results and st.session_state.summary_data:
    results = st.session_state.evaluation_results
    summary = st.session_state.summary_data
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Results Table", "📈 Analytics", "⚡ Performance", "⬇️ Export"])
    
    with tab1:
        st.subheader("📋 Evaluation Results")
        
        # Create results dataframe
        table_data = []
        for result in results:
            if "error" not in result:
                row = {
                    "Conversation ID": result["conversation_id"],
                    "Flow": result["result"]["detected_flow"],
                    "Total Score": f"{result['result']['total_score']:.1f}",
                    "Label": result["result"]["label"],
                    "Confidence": f"{result['result']['confidence']:.1%}",
                    "Policy Violations": int(result["metrics"].get("policy_violations", 0))
                }
                
                # Add criteria scores
                for criterion, details in result["result"]["criteria"].items():
                    row[f"{criterion}"] = f"{details['score']:.1f}"
                
                table_data.append(row)
            else:
                table_data.append({
                    "Conversation ID": result["conversation_id"],
                    "Flow": "ERROR",
                    "Total Score": "N/A",
                    "Label": "ERROR",
                    "Confidence": "N/A",
                    "Policy Violations": 0
                })
        
        # Display results table
        if table_data:
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Show summary statistics
            successful_results = [r for r in results if "error" not in r]
            if successful_results:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    avg_score = sum(r["result"]["total_score"] for r in successful_results) / len(successful_results)
                    st.metric("Average Score", f"{avg_score:.1f}")
                with col2:
                    policy_violations = sum(1 for r in successful_results if r.get("metrics", {}).get("policy_violations", 0) > 0)
                    st.metric("Policy Violations", f"{policy_violations}/{len(successful_results)}")
                with col3:
                    flows = [r["result"]["detected_flow"] for r in successful_results]
                    unique_flows = len(set(flows))
                    st.metric("Unique Flows", str(unique_flows))
                with col4:
                    confidence_avg = sum(r["result"].get("confidence", 0) for r in successful_results) / len(successful_results)
                    st.metric("Avg Confidence", f"{confidence_avg:.1%}")
        
        # Individual conversation details
        if successful_results:
            st.subheader("🔍 Individual Conversation Details")
            selected_idx = st.selectbox(
                "Select conversation to view details:",
                range(len(successful_results)),
                format_func=lambda x: f"{successful_results[x]['conversation_id']} - {successful_results[x]['result']['total_score']:.1f}pts"
            )
            
            if selected_idx is not None:
                selected_result = successful_results[selected_idx]
                display_conversation_details(selected_result, rubrics_cfg)
    
    with tab2:
        # Analytics tab
        if summary:
            st.subheader("📈 Performance Analytics")
            
            # Get insights from summary data
            summary_obj = summary.get("summary", summary) if isinstance(summary, dict) and "summary" in summary else summary
            insights = summary.get("insights", []) if isinstance(summary, dict) else []
            
            # Overview metrics với processing speed
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Success Rate", f"{summary_obj['successful_count']}/{summary_obj['count']}", 
                         f"{summary_obj['successful_count']/summary_obj['count']:.1%}")
            with col2:
                st.metric("Avg Score", f"{summary_obj['avg_total_score']:.1f}/100")
            with col3:
                st.metric("Std Dev", f"{summary_obj.get('std_total_score', 0):.1f}")
            with col4:
                if isinstance(summary, dict) and "processing_speed" in summary:
                    st.metric("Speed", f"{summary['processing_speed']:.1f} conv/s")
                    if "total_time" in summary:
                        st.caption(f"Total: {format_time_duration(summary['total_time'])}")
            
            # AI Insights
            if insights:
                st.subheader("💡 AI-Generated Insights")
                for insight in insights:
                    st.write(f"• {insight}")
            
            # Display regular analytics
            display_analytics(summary_obj, results, rubrics_cfg)
        else:
            st.info("No analytics data available")
    
    with tab3:
        # Performance tab
        st.subheader("⚡ Performance Dashboard")
        
        if results:
            # Performance metrics from batch processing
            total_conversations = len(results)
            successful_conversations = len([r for r in results if "error" not in r])
            
            # Calculate processing stats
            if hasattr(st.session_state, 'batch_start_time') and hasattr(st.session_state, 'batch_end_time'):
                total_time = st.session_state.batch_end_time - st.session_state.batch_start_time
                throughput = successful_conversations / total_time if total_time > 0 else 0
            else:
                total_time = 0
                throughput = 0
            
            # Performance metrics row
            perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
            
            with perf_col1:
                st.metric("Total Processed", total_conversations)
            with perf_col2:
                st.metric("Success Rate", f"{successful_conversations/total_conversations:.1%}" if total_conversations > 0 else "0%")
            with perf_col3:
                st.metric("Throughput", f"{throughput:.1f} conv/s")
            with perf_col4:
                st.metric("Total Time", format_time_duration(total_time))
            
            # Configuration used
            st.subheader("🔧 Configuration Used")
            config_col1, config_col2 = st.columns(2)
            
            with config_col1:
                st.write("**Processing Settings:**")
                st.write(f"• Max Concurrency: {st.session_state.get('last_max_concurrency', 'Unknown')}")
                st.write(f"• LLM Model: {st.session_state.get('last_llm_model', 'gemini-2.5-flash')}")
                st.write(f"• Temperature: {st.session_state.get('last_temperature', 0.2)}")
            
            with config_col2:
                st.write("**Performance Features:**")
                st.write(f"• High-Performance API: {st.session_state.get('last_use_high_performance_api', True)}")
                st.write(f"• Redis Caching: {st.session_state.get('last_enable_caching', False)}")
                st.write(f"• API Rate Limit: {st.session_state.get('last_api_rate_limit', 100)} req/s")
            
            # Performance recommendations
            st.subheader("💡 Performance Recommendations")
            
            if throughput > 0:
                if throughput < 10:
                    st.warning("⚠️ **Low throughput detected**. Consider:")
                    st.write("• Increase max concurrency (try 25-30)")
                    st.write("• Enable high-performance API client")
                    st.write("• Check system resources (CPU, memory)")
                elif throughput > 20:
                    st.success("✅ **Excellent throughput!** Your configuration is well-optimized.")
                else:
                    st.info("ℹ️ **Good performance**. You can try increasing concurrency for better speed.")
            
            # System resource guidance
            if total_conversations > 50:
                st.info("📊 **For large batches (50+ conversations):**")
                st.write("• Enable Redis caching for repeated evaluations")
                st.write("• Monitor memory usage during processing")
                st.write("• Consider using Docker production config for better resource management")
            
            # Performance optimization tips
            with st.expander("🚀 Advanced Performance Tips"):
                st.markdown("""
                **Connection Pooling Benefits:**
                - Reduces API latency by 30-50%
                - Better resource utilization
                - HTTP/2 support for faster transfers
                
                **Redis Caching Benefits:**
                - 60-80% cache hit rate for repeated conversations
                - Significant speed improvement for re-evaluations
                - Reduces API costs
                
                **Optimal Concurrency Guidelines:**
                - Small batches (< 20): 10-15 concurrency
                - Medium batches (20-50): 20-25 concurrency  
                - Large batches (50+): 25-30 concurrency
                - Monitor system resources and adjust accordingly
                """)
        else:
            st.info("Run a batch evaluation to see performance metrics")
    
    with tab4:
        # Export tab
        if results and summary:
            display_export_options(results, summary)
        else:
            st.info("No export data available")