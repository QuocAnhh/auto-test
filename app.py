# -*- coding: utf-8 -*-
import json
from datetime import datetime

import streamlit as st
import os
from dotenv import load_dotenv

from busqa.api_client import fetch_messages
from busqa.normalize import normalize_messages, build_transcript
from busqa.metrics import compute_latency_metrics
from busqa.prompting import SYSTEM_PROMPT, build_user_prompt
from busqa.llm_client import call_llm
from busqa.evaluator import coerce_llm_json
from busqa.rubrics import ALLOWED_INTENTS
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
    st.subheader("Cấu hình LLM (cố định)")
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

st.caption(f"Intent hợp lệ: {', '.join(ALLOWED_INTENTS)}")

if go:
    st.info("[LOG] Bắt đầu chấm điểm...")
    if not conv_id.strip():
        st.error("Hãy nhập conversation_id.")
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
    st.write("[LOG] Metrics:", metrics)
    st.write("[LOG] Transcript (preview):", transcript[:500])

    if show_raw:
        st.subheader("Transcript")
        st.text(transcript)
        st.subheader("Metrics")
        st.code(json.dumps(metrics, ensure_ascii=False, indent=2))

    # 3) Prompting
    st.info("[LOG] Build user prompt...")
    user_prompt = build_user_prompt(metrics, transcript)
    st.write("[LOG] User prompt:", user_prompt)

    # 4) Gọi LLM
    try:
        st.info("[LOG] Gọi LLM...")
        llm_json = call_llm(
            api_key=llm_api_key,
            model=llm_model.strip(),
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            base_url=llm_base_url.strip() or None,
            temperature=temperature,
        )
        st.write("[LOG] LLM trả về:", llm_json)
    except Exception as e:
        st.error(f"Lỗi LLM: {e}")
        st.stop()

    # 5) Chuẩn hoá kết quả
    try:
        st.info("[LOG] Chuẩn hoá kết quả LLM...")
        result = coerce_llm_json(llm_json)
        st.write("[LOG] Kết quả chuẩn hoá:", result)
    except Exception as e:
        st.error(f"Kết quả không hợp lệ: {e}")
        st.stop()

    # 6) Hiển thị
    st.success("Đã chấm xong bằng LLM ✅")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Intent", result.detected_intent)
    with col2:
        st.metric("Confidence", f"{round(result.confidence*100,1)}%")
    with col3:
        st.metric("Điểm tổng", f"{round(result.total_score,1)}/100")
    st.markdown(f"**Nhãn:** {result.label}")
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

    export = {
        "conversation_id": conv_id.strip(),
        "base_url": base_url,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "llm_model": llm_model.strip(),
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