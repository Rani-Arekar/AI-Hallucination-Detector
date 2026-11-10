# Legacy UI -- superseded by the React frontend in frontend/. Kept here for
# reference/optional local use, but no longer part of the main deployment
# and not installed by requirements.txt. To run this, install its own
# dependency first: `pip install streamlit`.
import streamlit as st
import requests

API_URL = "https://ai-hallucination-detector-1.onrender.com/ask"

st.set_page_config(page_title="Hallucination Detector", layout="wide")

st.title("🧠 AI Hallucination Detector")
st.caption("Fact-checking • Web evidence • Logical consistency • Risk scoring")

prompt = st.text_area("Enter your question", height=120)


def score_card(label, value):
    pct = int(value * 100)
    col1, col2 = st.columns([1, 4])
    with col1:
        st.metric(label, f"{pct}%")
    with col2:
        st.progress(value)


if st.button("Ask + Analyze"):

    with st.spinner("Generating answer and verifying claims..."):
        res = requests.post(API_URL, json={"prompt": prompt})
        data = res.json()

    # =========================
    # Answer Section
    # =========================
    st.subheader("📌 Model Answer")
    st.write(data["answer"])

    # =========================
    # Risk Meter
    # =========================
    risk = data["risk_score"]

    st.subheader("🚨 Hallucination Risk Score")

    if risk < 30:
        st.success(f"Low Risk — {risk}%")
    elif risk < 60:
        st.warning(f"Medium Risk — {risk}%")
    else:
        st.error(f"High Risk — {risk}%")

    st.progress(risk / 100)

    # =========================
    # Module Visualization
    # =========================
    st.subheader("🔍 Module Breakdown")

    scores = data["module_scores"]

    score_card("Fact Check", scores["fact"])
    score_card("Logic", scores["logic"])
    score_card("Citation", scores["citation"])
    score_card("Confidence", scores["confidence"])
    score_card("Cross Model", scores["cross"])

    # =========================
    # Claims Section
    # =========================
    st.subheader("🧾 Extracted Claims")

    for c in data["claims"]:
        st.markdown(f"• {c}")

    # =========================
    # Raw JSON (optional expander)
    # =========================
    # with st.expander("🔧 Raw JSON (debug)"):
    #     st.json(data)


