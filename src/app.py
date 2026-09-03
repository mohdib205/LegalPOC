"""NyayaSetu MVP UI. Run with: streamlit run app.py"""
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from rag_chain import answer_question
from db import get_connection
import instrumentation

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
    instrumentation.reset()
    instrumentation.start("Total end-to-end")
    instrumentation.log("1", "REQUEST START")
    instrumentation.log("1", f"Question received: {query}")
    
    with st.spinner("Retrieving relevant judgments and generating answer..."):
        instrumentation.log("2", "Calling answer_question()")
        instrumentation.start("answer_question")
        result = answer_question(query)
        dur_aq = instrumentation.end("answer_question")
        instrumentation.log("2", "answer_question() returned")
        instrumentation.log("2", f"Duration: {dur_aq:.3f} sec")
        
        instrumentation.log("16", f"answer_question TOTAL: {dur_aq:.3f} sec")
        instrumentation.log("16", f"API calls made: {instrumentation.api_calls}")
        instrumentation.log("16", "REQUEST END")

    instrumentation.log("17", "Streamlit rendering START")
    instrumentation.start("Streamlit rendering")
    
    st.markdown("### Answer")
    import re
    # Remove ONLY the exact citation token pattern [CASE: <case_id>]
    displayed_answer = re.sub(r"\[CASE:\s*[A-Za-z0-9\-]+\]", "", result["clean_answer"])
    # Clean up stranded 'and' left over from multiple citations
    displayed_answer = re.sub(r"\s+and\s+(?=\s|$|\.)", " ", displayed_answer)
    displayed_answer = displayed_answer.replace("  ", " ").strip()
    
    st.write(displayed_answer)
    st.markdown("---")
    
    if result["verified"]:
        st.markdown("### Sources")
        for c in result["verified"]:
            date_val = c.get('date', 'Unknown Date')
            st.markdown(f"**✓ {c['title']}**\n\n&nbsp;&nbsp;&nbsp;&nbsp;{c['court']} — {date_val}")

    if result["unverified"]:
        st.markdown("### ⚠️ Unverified citations")
        for cid in result["unverified"]:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{cid}")

    badge = "🟢" if not result["unverified"] else "🔴"
    st.markdown(f"**{badge} Citation check:** {result['accuracy_note']}")

    with st.expander("Retrieved chunks used for this answer"):
        for rc in result["retrieved_cases"]:
            st.markdown(f"- {rc['title']} (`{rc['case_id']}`) — via {rc['source']} search")

    dur_rend = instrumentation.end("Streamlit rendering")
    instrumentation.log("17", f"Streamlit rendering END: {dur_rend:.3f} sec")
    instrumentation.end("Total end-to-end")
    instrumentation.print_summary()
    instrumentation.print_model_summary()
    
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