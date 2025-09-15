import json
import asyncio
from datetime import datetime
from io import BytesIO
import base64

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os
from dotenv import load_dotenv

from busqa.api_client import fetch_messages
from busqa.normalize import normalize_messages, build_transcript
from busqa.metrics import compute_latency_metrics, compute_additional_metrics, compute_policy_violations_count, filter_non_null_metrics
from busqa.prompt_loader import load_unified_rubrics
from busqa.brand_specs import load_brand_prompt
from busqa.prompting import build_system_prompt_unified, build_user_instruction
from busqa.llm_client import call_llm
from busqa.evaluator import coerce_llm_json_unified
from busqa.utils import safe_parse_headers
from busqa.aggregate import make_summary, generate_insights

# Import evaluation functions from CLI
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from evaluate_cli import evaluate_conversation, evaluate_conversations_batch

DEFAULT_BASE_URL = "http://103.141.140.243:14496"

def display_conversation_details(result, rubrics_cfg):
    """Display detailed information for a single conversation."""
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
    
    # Criteria breakdown
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
    
    # Additional info
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
    
    # Diagnostics
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
    """Display analytics charts and insights."""
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
        
        # Create CSV data
        csv_data = []
        for result in results:
            if "error" not in result:
                row = {
                    "conversation_id": result["conversation_id"],
                    "detected_flow": result["result"]["detected_flow"],
                    "total_score": result["result"]["total_score"],
                    "label": result["result"]["label"],
                    "confidence": result["result"]["confidence"],
                    "policy_violations": result["metrics"].get("policy_violations", 0),
                }
                
                # Add criteria scores
                for criterion, details in result["result"]["criteria"].items():
                    row[f"{criterion}_score"] = details["score"]
                
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
            pdf_data = create_pdf_report(results, summary)
            st.download_button(
                label="Download PDF",
                data=pdf_data,
                file_name=f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"PDF generation failed: {e}")
            # Fallback to HTML
            html_data = create_html_report(results, summary)
            st.download_button(
                label="Download HTML Report",
                data=html_data,
                file_name=f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html"
            )


def create_pdf_report(results, summary):
    """Create a PDF report using matplotlib and reportlab."""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Build story
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=24, textColor=colors.darkblue)
    story.append(Paragraph("Bus QA Evaluation Batch Report", title_style))
    story.append(Spacer(1, 12))
    
    # Summary
    story.append(Paragraph("Executive Summary", styles['Heading1']))
    story.append(Paragraph(f"Total Conversations: {summary['count']}", styles['Normal']))
    story.append(Paragraph(f"Successful Evaluations: {summary['successful_count']}", styles['Normal']))
    story.append(Paragraph(f"Average Score: {summary['avg_total_score']:.1f}/100", styles['Normal']))
    story.append(Paragraph(f"Policy Violation Rate: {summary['policy_violation_rate']:.1%}", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Insights
    insights = generate_insights(summary)
    if insights:
        story.append(Paragraph("Key Insights", styles['Heading1']))
        for insight in insights:
            story.append(Paragraph(f"• {insight}", styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Results table
    story.append(Paragraph("Results Summary", styles['Heading1']))
    table_data = [["Conversation ID", "Flow", "Score", "Label"]]
    
    for result in results[:10]:  # Limit to first 10 for PDF
        if "error" not in result:
            table_data.append([
                result["conversation_id"][:20],  # Truncate long IDs
                result["result"]["detected_flow"],
                f"{result['result']['total_score']:.1f}",
                result["result"]["label"]
            ])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer.getvalue()


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
st.set_page_config(page_title="Bus QA LLM Evaluator (Batch)", page_icon="🚌", layout="wide")
st.title("🚌 Bus QA LLM Evaluator — Batch Evaluation System")

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
    st.subheader("Conversation IDs")
    
    # Multiple input methods
    input_method = st.radio("Input method:", ["Text Area", "File Upload"])
    
    conversation_ids = []
    if input_method == "Text Area":
        conv_ids_text = st.text_area(
            "Conversation IDs (one per line, max 10)",
            value="",
            height=120,
            placeholder="conv_123\nconv_456\nconv_789"
        )
        if conv_ids_text.strip():
            lines = [line.strip() for line in conv_ids_text.strip().split('\n')]
            conversation_ids = [line for line in lines if line]
    
    else:  # File Upload
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
    
    # Dedupe and limit to 10
    if conversation_ids:
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for id in conversation_ids:
            if id not in seen:
                seen.add(id)
                unique_ids.append(id)
        
        if len(unique_ids) > 10:
            st.warning(f"Found {len(unique_ids)} IDs. Limiting to first 10.")
            unique_ids = unique_ids[:10]
        
        conversation_ids = unique_ids
        st.success(f"Ready to evaluate {len(conversation_ids)} conversation(s)")
        
        # Show IDs
        with st.expander("Preview IDs"):
            for i, conv_id in enumerate(conversation_ids, 1):
                st.text(f"{i}. {conv_id}")
    
    st.markdown("---")
    st.subheader("Brand Configuration")
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
    st.subheader("Cấu hình LLM")
    st.caption("Model: gemini-2.5-flash | API key lấy từ file .env")
    llm_base_url = st.text_input("LLM Base URL (optional)", value="", help="Để trống nếu dùng OpenAI chính thống")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1)
    max_concurrency = st.slider("Max Concurrency", 1, 10, 5, 1, help="Số lượng conversation xử lý song song")
    st.markdown("---")
    max_chars = st.number_input("Giới hạn ký tự transcript", min_value=2000, max_value=200000, value=24000, step=1000)

# Main evaluation section
col1, col2 = st.columns([2, 1])
with col1:
    eval_button = st.button("🚀 Chấm điểm batch (tối đa 10)", disabled=not conversation_ids, type="primary")
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

# Batch evaluation logic
if eval_button and conversation_ids:
    if not rubrics_cfg:
        st.error("Không thể load unified rubrics.")
        st.stop()
        
    if not brand_policy:
        st.error("Không thể load brand policy.")
        st.stop()

    llm_api_key = os.getenv("GEMINI_API_KEY", "")
    llm_model = "gemini-2.5-flash"
    if not llm_api_key.strip():
        st.error("Không tìm thấy GEMINI_API_KEY trong file .env hoặc biến môi trường.")
        st.stop()

    # Show progress
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Run batch evaluation
    try:
        status_text.text("Starting batch evaluation...")
        
        # Prepare arguments for batch evaluation
        eval_args = {
            'base_url': base_url,
            'brand_prompt_path': brand_path,
            'rubrics_cfg': rubrics_cfg,
            'brand_prompt_text': brand_prompt_text,
            'brand_policy': brand_policy,
            'llm_api_key': llm_api_key,
            'llm_model': llm_model,
            'temperature': temperature,
            'llm_base_url': llm_base_url.strip() or None,
            'apply_diagnostics': apply_diagnostics,
            'diagnostics_cfg': diagnostics_cfg,
            'max_concurrency': max_concurrency,
            'headers': safe_parse_headers(headers_raw)
        }
        
        # Run batch evaluation with progress updates
        results = []
        for i, conv_id in enumerate(conversation_ids):
            progress = (i + 1) / len(conversation_ids)
            progress_bar.progress(progress)
            status_text.text(f"Evaluating conversation {i+1}/{len(conversation_ids)}: {conv_id}")
            
            try:
                result = evaluate_conversation(
                    conversation_id=conv_id,
                    base_url=base_url,
                    brand_prompt_path=brand_path,
                    rubrics_cfg=rubrics_cfg,
                    brand_prompt_text=brand_prompt_text,
                    brand_policy=brand_policy,
                    llm_api_key=llm_api_key,
                    llm_model=llm_model,
                    temperature=temperature,
                    llm_base_url=llm_base_url.strip() or None,
                    apply_diagnostics=apply_diagnostics,
                    diagnostics_cfg=diagnostics_cfg
                )
                results.append(result)
            except Exception as e:
                st.error(f"Error evaluating {conv_id}: {e}")
                results.append({
                    "conversation_id": conv_id,
                    "error": str(e),
                    "evaluated_at": datetime.utcnow().isoformat() + "Z"
                })
        
        progress_bar.progress(1.0)
        status_text.text("Batch evaluation completed!")
        
        # Generate summary
        summary = make_summary(results)
        
        # Store in session state
        st.session_state.evaluation_results = results
        st.session_state.summary_data = summary
        
        st.success(f"✅ Batch evaluation completed! {summary['successful_count']}/{summary['count']} successful")
        
    except Exception as e:
        st.error(f"Batch evaluation failed: {e}")
        st.stop()

# Display results if available
if st.session_state.evaluation_results and st.session_state.summary_data:
    results = st.session_state.evaluation_results
    summary = st.session_state.summary_data
    
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["📊 Results Table", "📈 Analytics", "⬇️ Export"])
    
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
                    "Policy Violations": result["metrics"].get("policy_violations", 0)
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
                    "Policy Violations": "N/A",
                    "Error": result["error"]
                })
        
        if table_data:
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True)
            
            # Show detailed view for selected conversation
            if len([r for r in results if "error" not in r]) > 0:
                st.subheader("💬 Conversation Details")
                successful_results = [r for r in results if "error" not in r]
                conv_options = {r["conversation_id"]: r for r in successful_results}
                
                selected_conv = st.selectbox(
                    "Select conversation to view details:",
                    options=list(conv_options.keys()),
                    format_func=lambda x: f"{x} (Score: {conv_options[x]['result']['total_score']:.1f})"
                )
                
                if selected_conv:
                    display_conversation_details(conv_options[selected_conv], rubrics_cfg)
    
    with tab2:
        display_analytics(summary, results, rubrics_cfg)
    
    with tab3:
        display_export_options(results, summary)

else:
    # Show welcome message when no results
    st.info("👋 Welcome! Enter conversation IDs in the sidebar and click '🚀 Chấm điểm batch' to start evaluation.")