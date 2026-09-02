"""
RAG Pipeline ?" Integrates ChromaDB retrieval with Ollama inference.
To use:
    ollama run llama3.1:8b
    ollama pull llama3.1:8b
"""
import ollama
from search import hybrid_search
from citation_verifier import verify_citations, extract_citations
import re
import json
import os
from dotenv import load_dotenv

load_dotenv()
USE_GROQ = os.environ.get("USE_GROQ", "false").lower() == "true"

MODEL_NAME = "llama3.1:8b"

SYSTEM_PROMPT = """You are a legal research assistant for Indian law. You answer ONLY \\
using the case excerpts provided below. Do not use any outside knowledge or cases you \\
recall from training.

CRITICAL RULES:
1. DO NOT state a broad legal conclusion unless the provided excerpts explicitly state that exact conclusion.
2. The mere presence of a cited case in the database does NOT mean it supports a specific legal interpretation. You must read the actual text of the excerpt.
3. Your answer must be grounded ONLY in the facts and reasoning directly present in the provided excerpts.
4. If the retrieved excerpts conflict, are ambiguous, or do not clearly support a definitive conclusion, you MUST explicitly state that the provided local cases do not provide a sufficiently clear basis for a definitive answer. Do not guess or overgeneralize.
5. Distinguish between facts/reasoning directly present in the excerpts and broader legal conclusions. Do not invent broader legal conclusions.

Your answer MUST ALWAYS begin with a natural-language sentence directly addressing the question.
NEVER begin your answer with a citation.
Case IDs (like NI138-12345) are citation tokens ONLY. NEVER use them as ordinary nouns in your prose.

For every specific claim about a case's facts, reasoning, or holding, complete the relevant legal statement first, then place the citation at the very end of that sentence or proposition.
Use this EXACT format: [CASE: <case_id>]
Use the case_id given with each excerpt below, exactly as written.



OUTPUT FORMAT:
You MUST respond with a valid JSON object matching exactly this structure:
{
  "answer": "Your natural-language answer, including [CASE: <case_id>] citations properly placed.",
  "citations": [
    {
      "case_id": "The ID of the cited case",
      "evidence_quote": "The EXACT verbatim text from the excerpt of THAT case_id that explicitly proves your claim. (Must be at least 5 words)."
    }
  ]
}
"""

CITATION_REMINDER = """Your last answer did not include any [CASE: <case_id>] citations properly placed at the ends of sentences. \\
Rewrite your answer as a JSON object, following the same schema, and ensure you include citations at the end of claims supported by the excerpts."""

def fix_leading_citation(text: str) -> str:
    text = text.strip()
    match = re.match(r'^(\\[CASE:\\s*[^\]]+\\]|\\[[A-Za-z0-9\\-]+\\])\\s*(.*)', text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        citation = match.group(1).strip()
        remainder = match.group(2).strip()
        
        id_match = re.search(r'([A-Za-z0-9\\-]+)', citation.replace("CASE:", "", 1))
        case_id = id_match.group(1) if id_match else citation
        
        if case_id not in remainder:
            sentence_end = re.search(r'([.?!])(?:\\s|$)', remainder)
            if sentence_end:
                idx = sentence_end.start(1) + 1
                remainder = remainder[:idx] + " " + citation + remainder[idx:]
            else:
                remainder = remainder + " " + citation
                
        if remainder:
            remainder = remainder[0].upper() + remainder[1:]
        return remainder
    return text

GEN_OPTIONS = {
    "num_predict": 800,
    "num_ctx": 4096,
    "temperature": 0.0,
    "seed": 42,
}

def build_context(hits):
    blocks = []
    for h in hits:
        if not h["text"]:
            continue
        blocks.append(
            f"--- case_id: {h['case_id']} | {h['title']} ({h['court']}, {h['date']}) "
            f"| section: {h['section']} ---\\n{h['text']}"
        )
    return "\\n\\n".join(blocks)

def _call_model(messages):
    if USE_GROQ:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: USE_GROQ is true but GROQ_API_KEY is not set.")
        
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.0,
            seed=42,
            max_tokens=4096
            # Removed response_format={"type": "json_object"} to prevent 400 error on reasoning tags
        )
        raw_output = response.choices[0].message.content
        
        # Remove <think>...</think> explicitly first to avoid `{` inside thinking block
        import re
        raw_output = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL).strip()
        
        start_idx = raw_output.find('{')
        end_idx = raw_output.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            return raw_output[start_idx:end_idx+1]
        
        return raw_output
    else:
        response = ollama.chat(model=MODEL_NAME, messages=messages, options=GEN_OPTIONS, format="json")
        return response["message"]["content"]

def normalize_text(text: str) -> str:
    if not text: return ""
    text = re.sub(r'[^\\w\\s]', '', text)
    return re.sub(r'\\s+', ' ', text).lower().strip()

def answer_question(question: str, top_k: int = 5):
    hits = hybrid_search(question, top_k=top_k)
    context = build_context(hits)

    if not context.strip():
        return {
            "raw_answer": "No relevant judgments were found in the database for this query.",
            "verified": [],
            "unverified": [],
            "clean_answer": "No relevant judgments were found in the database for this query.",
            "accuracy_note": "No citations were made",
            "retrieved_cases": [],
        }

    user_content = f"Excerpts:\\n{context}\\n\\nQuestion: {question}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    raw_answer_json = _call_model(messages)
    try:
        parsed = json.loads(raw_answer_json)
        raw_answer = parsed.get("answer", raw_answer_json)
        evidence_list = parsed.get("citations", [])
    except json.JSONDecodeError:
        raw_answer = raw_answer_json
        evidence_list = []
        
    raw_answer = fix_leading_citation(raw_answer)

    if not extract_citations(raw_answer):
        messages.append({"role": "assistant", "content": raw_answer_json})
        messages.append({"role": "user", "content": CITATION_REMINDER})
        raw_answer_json = _call_model(messages)
        try:
            parsed = json.loads(raw_answer_json)
            raw_answer = parsed.get("answer", raw_answer_json)
            evidence_list = parsed.get("citations", [])
        except json.JSONDecodeError:
            raw_answer = raw_answer_json
            evidence_list = []
        raw_answer = fix_leading_citation(raw_answer)

    hit_dict = {h['case_id']: h['text'] for h in hits if h['text']}
    
    validated_ids = set()
    if evidence_list and isinstance(evidence_list, list):
        for cit in evidence_list:
            if not isinstance(cit, dict): continue
            cid = cit.get("case_id")
            quote = cit.get("evidence_quote", "")
            if cid in hit_dict and quote:
                norm_q = normalize_text(quote)
                norm_t = normalize_text(hit_dict[cid])
                if norm_q and norm_q in norm_t:
                    validated_ids.add(cid)

    verification = verify_citations(raw_answer, validated_ids)

    return {
        "raw_answer": raw_answer,
        "retrieved_cases": [
            {"case_id": h["case_id"], "title": h["title"], "source": h["source"]}
            for h in hits
        ],
        "extracted_evidence": evidence_list, "validated_ids": list(validated_ids), **verification,
    }

if __name__ == "__main__":
    q = "If a demand notice is returned undelivered, is the complaint still valid under Section 138?"
    result = answer_question(q)
    print("QUESTION:", q)
    print("\\nANSWER:\\n", result["clean_answer"])
    print("\\n", result["accuracy_note"])
    if result["unverified"]:
        print("UNVERIFIED:", result["unverified"])
