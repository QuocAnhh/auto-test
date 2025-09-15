import json
from datetime import datetime

import streamlit as st
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

DEFAULT_BASE_URL = "http://103.141.140.243:14496"

st.set_page_config(page_title="Bus QA LLM Evaluator (Modular)", page_icon="🚌", layout="centered")
st.title("🚌 Bus QA LLM Evaluator — Modular Version")

load_dotenv()

with st.sidebar:
    st.subheader("API hội thoại")
    base_url = st.text_input("BASE_URL", value=DEFAULT_BASE_URL)
    conv_id = st.text_input("conversation_id", value="", placeholder="Nhập conversation_id")
    headers_raw = st.text_area("Headers (JSON, optional)", value="", height=80, placeholder='{"Authorization":"Bearer xxx"}')
    st.markdown("---")
    st.subheader("Brand Configuration")
    brand_options = ["son_hai", "long_van"]
    selected_brand = st.selectbox("Chọn brand", brand_options)
    
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
        st.error(f"Lỗi load brand: {e}")
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
    st.markdown("---")
    max_chars = st.number_input("Giới hạn ký tự transcript", min_value=2000, max_value=200000, value=24000, step=1000)

colA, colB = st.columns(2)
with colA:
    go = st.button("🚀 Chấm điểm")
with colB:
    show_raw = st.toggle("Hiện transcript & JSON thô", value=False)

# Load unified rubrics to show available flows
try:
    rubrics_cfg = load_unified_rubrics()
    flows = list(rubrics_cfg.get('flows_slots', {}).keys())
    st.caption(f"Flows hợp lệ: {', '.join(flows)}")
except Exception as e:
    st.error(f"Lỗi load rubrics: {e}")
    rubrics_cfg = None

# Load diagnostics config (outside sidebar to be accessible)
apply_diagnostics = st.session_state.get('apply_diagnostics', True)
try:
    from busqa.prompt_loader import load_diagnostics_config
    diagnostics_cfg = load_diagnostics_config()
except Exception as e:
    st.error(f"Warning: Could not load diagnostics config: {e}")
    diagnostics_cfg = None
    apply_diagnostics = False

if go:
    st.info("[LOG] Bắt đầu chấm điểm...")
    if not conv_id.strip():
        st.error("Hãy nhập conversation_id.")
        st.stop()

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

    # 1) Lấy dữ liệu
    try:
        st.info(f"[LOG] Gọi API lấy hội thoại: {base_url}/api/conversations/{conv_id.strip()}/messages")
        raw = fetch_messages(base_url, conv_id.strip(), safe_parse_headers(headers_raw))
        st.write("[LOG] Dữ liệu API trả về:", raw)
    except Exception as e:
        st.error(f"Lỗi API: {e}")
        st.stop()

    if show_raw:
        st.subheader("Raw JSON")
        st.code(json.dumps(raw, ensure_ascii=False, indent=2))

    # 2) Chuẩn hoá & metrics
    st.info("[LOG] Chuẩn hoá dữ liệu hội thoại...")
    messages = normalize_messages(raw)
    st.write("[LOG] Messages chuẩn hoá:", messages)
    if not messages:
        st.warning("Không có tin nhắn nào.")
        st.stop()

    st.info("[LOG] Xây transcript và tính metrics...")
    transcript = build_transcript(messages, max_chars=max_chars)
    metrics = compute_latency_metrics(messages)
    additional_metrics = compute_additional_metrics(messages)
    
    # Compute policy violations
    policy_violations_count = compute_policy_violations_count(messages, brand_policy)
    additional_metrics["policy_violations"] = policy_violations_count
    
    metrics.update(additional_metrics)
    
    # Filter out None values for LLM prompt
    metrics_for_llm = filter_non_null_metrics(metrics)
    
    st.write("[LOG] Metrics:", metrics)
    st.write("[LOG] Transcript (preview):", transcript[:500])

    if show_raw:
        st.subheader("Transcript")
        st.text(transcript)
        st.subheader("Metrics")
        st.code(json.dumps(metrics, ensure_ascii=False, indent=2))

    # 3) Prompting - Build unified prompts
    st.info("[LOG] Build unified prompts...")
    system_prompt = build_system_prompt_unified(rubrics_cfg, brand_policy, brand_prompt_text)
    user_prompt = build_user_instruction(metrics_for_llm, transcript, rubrics_cfg)
    
    st.write("[LOG] System prompt (preview):", system_prompt[:500] + "...")
    st.write("[LOG] User prompt (preview):", user_prompt[:500] + "...")

    # 4) Gọi LLM
    try:
        st.info("[LOG] Gọi LLM...")
        llm_json = call_llm(
            api_key=llm_api_key,
            model=llm_model.strip(),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            base_url=llm_base_url.strip() or None,
            temperature=temperature,
        )
        st.write("[LOG] LLM trả về:", llm_json)
    except Exception as e:
        st.error(f"Lỗi LLM: {e}")
        st.stop()

    # 5) Chuẩn hoá kết quả với unified system
    try:
        st.info("[LOG] Chuẩn hoá kết quả LLM...")
        diagnostics_hits = metrics.get("diagnostics", {}) if apply_diagnostics else {}
        
        result = coerce_llm_json_unified(
            llm_json, 
            rubrics_cfg=rubrics_cfg,
            brand_policy=brand_policy, 
            messages=messages, 
            transcript=transcript, 
            metrics=metrics,
            diagnostics_cfg=diagnostics_cfg if apply_diagnostics else None,
            diagnostics_hits=diagnostics_hits
        )
        st.write("[LOG] Kết quả chuẩn hoá:", result)
    except Exception as e:
        st.error(f"Kết quả không hợp lệ: {e}")
        st.stop()

    # 6) Hiển thị kết quả unified
    st.success("Đã chấm xong bằng Unified Rubric System ✅")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Flow", result.detected_flow)
    with col2:
        st.metric("Confidence", f"{round(result.confidence*100,1)}%")
    with col3:
        st.metric("Điểm tổng", f"{round(result.total_score,1)}/100")
    st.markdown(f"**Nhãn:** {result.label}")
    st.markdown(f"**Brand:** {selected_brand}")
    st.markdown(f"**Final:** {result.final_comment or '(không có)'}")

    st.subheader("📋 Chi tiết tiêu chí")
    for name, obj in result.criteria.items():
        st.markdown(f"**{name}** — {round(float(obj.get('score',0.0)),1)}/100")
        st.progress(min(max(float(obj.get('score',0.0))/100.0, 0.0), 1.0))
        note = obj.get("note")
        if note:
            st.caption(f"Note: {note}")

    cols = st.columns(3)
    with cols[0]:
        st.markdown("**🏷️ Tags**")
        st.write(", ".join(result.tags) if result.tags else "—")
    with cols[1]:
        st.markdown("**⚠️ Risks**")
        if result.risks:
            for r in result.risks:
                st.write(f"- {r}")
        else:
            st.write("—")
    with cols[2]:
        st.markdown("**🛠️ Suggestions**")
        if result.suggestions:
            for s in result.suggestions:
                st.write(f"- {s}")
        else:
            st.write("—")

    # Display diagnostics hits
    if diagnostics_cfg and apply_diagnostics:
        diagnostics_hits = metrics.get("diagnostics", {})
        if diagnostics_hits:
            st.subheader("🔍 Diagnostics Hits")
            
            col_or, col_rc = st.columns(2)
            
            with col_or:
                st.markdown("**Operational Readiness**")
                or_hits = diagnostics_hits.get("operational_readiness", [])
                if or_hits:
                    for hit in or_hits:
                        st.markdown(f"• **{hit['key']}**")
                        if hit.get('evidence'):
                            st.caption(f"Evidence: {hit['evidence'][0][:100]}...")
                else:
                    st.write("✅ No issues detected")
            
            with col_rc:
                st.markdown("**Risk Compliance**")
                rc_hits = diagnostics_hits.get("risk_compliance", [])
                if rc_hits:
                    for hit in rc_hits:
                        st.markdown(f"• **{hit['key']}**")
                        if hit.get('evidence'):
                            st.caption(f"Evidence: {hit['evidence'][0][:100]}...")
                else:
                    st.write("✅ No issues detected")
            
            penalty_status = "Applied" if apply_diagnostics else "Display only"
            st.caption(f"Penalty status: {penalty_status}")
        else:
            st.info("🎉 No diagnostic issues detected!")
    elif not apply_diagnostics:
        st.info("ℹ️ Diagnostic penalties disabled")

    export = {
        "conversation_id": conv_id.strip(),
        "base_url": base_url,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "llm_model": llm_model.strip(),
        "brand": selected_brand,
        "rubric_version": rubrics_cfg.get("version", "v1.0"),
        "result": result.model_dump(),
        "metrics": metrics,
        "transcript_preview": transcript[:2000],
    }
    st.download_button(
        "⬇️ Tải JSON kết quả",
        data=json.dumps(export, ensure_ascii=False, indent=2),
        file_name=f"evaluation_{conv_id.strip()}.json",
        mime="application/json"
    )