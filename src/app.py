"""NyayaSetu MVP UI. Run with: streamlit run app.py"""
import streamlit as st
from rag_chain import answer_question
from db import get_connection

st.set_page_config(page_title="NyayaSetu MVP", page_icon="⚖️", layout="centered")

st.title("⚖️ NyayaSetu — Offline Legal Research (MVP)")
st.caption("Domain: Section 138 Negotiable Instruments Act (cheque bounce) cases. "
           "Runs entirely locally — no cloud, no API costs.")
st.info("Citations shown as 'Verified' are checked against this app's local database "
        "of curated judgments — not all of Indian case law. 'Unverified' may mean the "
        "citation was fabricated, or it may be a real case outside this small sample.")

query = st.text_area("Ask a legal question:", height=100,
                      placeholder="e.g. If a demand notice is returned undelivered, is the complaint still valid?")

ask = st.button("Ask", type="primary")

if ask and query.strip():
    with st.spinner("Retrieving relevant judgments and generating answer..."):
        result = answer_question(query)

    st.markdown("### Answer")
    st.write(result["clean_answer"])

    st.markdown("---")
    badge = "✅" if not result["unverified"] else "⚠️"
    st.markdown(f"**{badge} Citation check:** {result['accuracy_note']}")

    if result["verified"]:
        st.markdown("**Verified citations:**")
        for c in result["verified"]:
            st.markdown(f"- {c['title']} — {c['court']}, {c['date']} (`{c['case_id']}`)")

    if result["unverified"]:
        st.markdown("**⚠️ Unverified citations (not found in local database):**")
        for cid in result["unverified"]:
            st.markdown(f"- `{cid}`")

    with st.expander("Retrieved chunks used for this answer"):
        for rc in result["retrieved_cases"]:
            st.markdown(f"- {rc['title']} (`{rc['case_id']}`) — via {rc['source']} search")

    st.markdown("---")
    fcol1, fcol2 = st.columns(2)
    if fcol1.button("👍 Good answer"):
        conn = get_connection()
        conn.execute("INSERT INTO feedback (query, answer, rating) VALUES (?, ?, ?)",
                      (query, result["clean_answer"], "up"))
        conn.commit()
        conn.close()
        st.success("Thanks — feedback logged.")
    if fcol2.button("👎 Needs work"):
        conn = get_connection()
        conn.execute("INSERT INTO feedback (query, answer, rating) VALUES (?, ?, ?)",
                      (query, result["clean_answer"], "down"))
        conn.commit()
        conn.close()
        st.info("Thanks — feedback logged.")