"""
RAG Chain ?\" orchestrates retrieval and LLM generation.
Dependencies:
    pip install ollama
    ollama run llama3.1:8b
    ollama pull llama3.1:8b
"""
import ollama
import json
import re
import os
import instrumentation

from search import hybrid_search
from citation_verifier import verify_citations, extract_citations

MODEL_NAME = "llama3.1:8b"

USE_GROQ = os.environ.get("USE_GROQ", "false").lower() == "true"

SYSTEM_PROMPT = """You are a legal research assistant for Indian law. You answer ONLY \
using the case excerpts provided below. Do not use any outside knowledge or cases you \
recall from training.

CRITICAL RULES:
1. DO NOT state a broad legal conclusion unless the provided excerpts explicitly state that exact conclusion.
2. The mere presence of a cited case in the database does NOT mean it supports a specific legal interpretation. You must read the actual text of the excerpt.
3. Your answer must be grounded ONLY in the facts and reasoning directly present in the provided excerpts.
4. If the retrieved excerpts conflict, are ambiguous, or do not clearly support a definitive conclusion, you MUST explicitly state that the provided local cases do not provide a sufficiently clear basis for a definitive answer. Do not guess or overgeneralize.
5. Distinguish between facts/reasoning directly present in the excerpts and broader legal conclusions. Do not invent broader legal conclusions.

Your answer MUST ALWAYS begin with a natural-language sentence directly addressing the question.
DO NOT EMBED CITATION TOKENS (like [CASE: xxx]) in your answer text. 
Provide citations ONLY in the separate citations array.

OUTPUT FORMAT:
You MUST respond with a valid JSON object matching exactly this structure:
{
  "answer": "Your natural-language answer without any citation tokens.",
  "citations": [
    {
      "case_id": "The ID of the cited case",
      "evidence_quote": "The EXACT verbatim text from the excerpt of THAT case_id that explicitly proves your claim. (Must be at least 5 words)."
    }
  ]
}
"""

def fix_leading_citation(text: str) -> str:
    text = text.strip()
    match = re.match(r'^(\\[CASE:\s*[^\]]+\\]|\\[[A-Za-z0-9\-]+\\])\s*(.*)', text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        citation = match.group(1).strip()
        remainder = match.group(2).strip()
        
        id_match = re.search(r'([A-Za-z0-9\-]+)', citation.replace("CASE:", "", 1))
        case_id = id_match.group(1) if id_match else citation
        
        if case_id not in remainder:
            sentence_end = re.search(r'([.?!])(?:\s|$)', remainder)
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
    instrumentation.log("8", "Context construction START")
    instrumentation.start("Context construction")
    blocks = []
    for h in hits:
        if not h["text"]:
            continue
        blocks.append(
            f"--- case_id: {h['case_id']} | {h['title']} ({h['court']}, {h['date']}) "
            f"| section: {h['section']} ---\n{h['text']}"
        )
    result = "\n\n".join(blocks)
    dur = instrumentation.end("Context construction")
    instrumentation.log("8", f"Context construction END: {dur:.3f} sec")
    instrumentation.log("8", f"Context length: {len(result)} characters")
    return result

def _call_model(messages):
    call_num = instrumentation.increment_api_call()
    
    raw_use_groq = os.environ.get("USE_GROQ", "not set")
    instrumentation.log("MODEL CONFIG", f"USE_GROQ raw value: {raw_use_groq}")
    instrumentation.log("MODEL CONFIG", f"USE_GROQ type: {type(raw_use_groq)}")
    instrumentation.log("MODEL CONFIG", f"USE_GROQ = {USE_GROQ}")
    
    backend = "GROQ" if USE_GROQ else "OLLAMA"
    model_name = "qwen/qwen3.6-27b" if USE_GROQ else MODEL_NAME
    instrumentation.log("MODEL CONFIG", f"Selected backend = {backend}")
    instrumentation.log("MODEL CONFIG", f"Model = {model_name}")
    
    instrumentation.set_config("Selected backend", backend)
    instrumentation.set_config("Model", model_name)
    instrumentation.set_config("USE_GROQ", str(USE_GROQ))

    instrumentation.start("Total model time")
    
    if USE_GROQ:
        instrumentation.log("GROQ", "ENTER _call_model")
        instrumentation.start("Model initialization")
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Configuration Error: USE_GROQ is true but GROQ_API_KEY is not set.")
        
        from groq import Groq
        client = Groq(api_key=api_key)
        instrumentation.end("Model initialization")
        
        instrumentation.log("GROQ", "API CALL START")
        instrumentation.start("Actual API call")
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages,
            temperature=0.0,
            seed=42,
            max_tokens=1500,
            response_format={"type": "json_object"},
            extra_body={"reasoning_effort": "none"}
        )
        dur = instrumentation.end("Actual API call")
        instrumentation.log("GROQ", f"API CALL END: {dur:.3f} sec")
        
        instrumentation.start("Model response processing")
        instrumentation.log("GROQ", "Response received")
        raw_output = response.choices[0].message.content
        raw_output = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL).strip()
        instrumentation.end("Model response processing")
        
        instrumentation.log("GROQ", "EXIT _call_model")
        instrumentation.end("Total model time")
        
        instrumentation.log("12", "JSON extraction START")
        instrumentation.start("JSON extraction")
        start_idx = raw_output.find('{')
        end_idx = raw_output.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            extracted = raw_output[start_idx:end_idx+1]
        else:
            extracted = raw_output
        dur_ex = instrumentation.end("JSON extraction")
        instrumentation.log("12", f"JSON extraction END: {dur_ex:.3f} sec")
        return extracted
    else:
        instrumentation.log("OLLAMA", "ENTER _call_model")
        instrumentation.start("Model initialization")
        # Ollama initializes its client internally per request in the module
        instrumentation.end("Model initialization")
        
        instrumentation.log("OLLAMA", "API CALL START")
        instrumentation.start("Actual API call")
        response = ollama.chat(model=MODEL_NAME, messages=messages, options=GEN_OPTIONS, format="json")
        dur = instrumentation.end("Actual API call")
        instrumentation.log("OLLAMA", f"API CALL END: {dur:.3f} sec")
        
        # New diagnostic logs for Ollama metrics
        if "total_duration" in response:
            instrumentation.log("OLLAMA_METRICS", f"load_duration: {response.get('load_duration', 0) / 1e9:.3f} sec")
            instrumentation.log("OLLAMA_METRICS", f"prompt_eval_duration: {response.get('prompt_eval_duration', 0) / 1e9:.3f} sec")
            instrumentation.log("OLLAMA_METRICS", f"prompt_eval_count: {response.get('prompt_eval_count', 0)}")
            instrumentation.log("OLLAMA_METRICS", f"eval_duration: {response.get('eval_duration', 0) / 1e9:.3f} sec")
            instrumentation.log("OLLAMA_METRICS", f"eval_count: {response.get('eval_count', 0)}")
            instrumentation.log("OLLAMA_METRICS", f"total_duration: {response.get('total_duration', 0) / 1e9:.3f} sec")
        
        extracted = response.get("message", {}).get("content", "")
        instrumentation.log("OLLAMA_PAYLOAD", f"Raw response: {extracted}")
        
        instrumentation.start("Model response processing")
        instrumentation.log("OLLAMA", "Response received")
        instrumentation.end("Model response processing")
        
        instrumentation.log("OLLAMA", "EXIT _call_model")
        instrumentation.end("Total model time")
        
        instrumentation.log("12", "JSON extraction START")
        instrumentation.start("JSON extraction")
        start_idx = extracted.find('{')
        end_idx = extracted.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            extracted = extracted[start_idx:end_idx+1]
        dur_ex = instrumentation.end("JSON extraction")
        instrumentation.log("12", f"JSON extraction END: {dur_ex:.3f} sec")
        
        return extracted

def normalize_text(text: str) -> str:
    if not text: return ""
    text = re.sub(r'[^\w\s]', '', text)
    return re.sub(r'\s+', ' ', text).lower().strip()

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

    instrumentation.log("9", "Prompt construction START")
    instrumentation.start("Prompt construction")
    user_content = f"Excerpts:\n{context}\n\nQuestion: {question}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    dur_prompt = instrumentation.end("Prompt construction")
    instrumentation.log("9", f"Prompt construction END: {dur_prompt:.3f} sec")

    raw_answer_json = _call_model(messages)
    
    instrumentation.log("12", "JSON parsing START")
    instrumentation.start("JSON parsing")
    try:
        parsed = json.loads(raw_answer_json)
        raw_answer = parsed.get("answer", raw_answer_json)
        evidence_list = parsed.get("citations", [])
    except json.JSONDecodeError:
        raw_answer = raw_answer_json
        evidence_list = []
    dur_parse = instrumentation.end("JSON parsing")
    instrumentation.log("12", f"JSON parsing END: {dur_parse:.3f} sec")
        
    instrumentation.start("Fix leading citation")
    raw_answer = fix_leading_citation(raw_answer)
    dur_fix = instrumentation.end("Fix leading citation")
    instrumentation.log("12", f"Fix leading citation END: {dur_fix:.3f} sec")

    instrumentation.log("15", "Final answer processing START")
    instrumentation.start("Final processing")
    
    # We ignore the LLM's generated case_id and use authoritative metadata from chunks
    hit_list = [
        {"norm_text": normalize_text(h['text']), "authoritative_case_id": h['case_id']} 
        for h in hits if h['text']
    ]
    
    validated_ids = set()
    appended_citations = []
    
    instrumentation.start("Evidence reference extraction")
    if evidence_list and isinstance(evidence_list, list):
        for cit in evidence_list:
            if not isinstance(cit, dict): continue
            
            # The LLM's case_id is untrusted; we map using the quote alone
            quote = cit.get("evidence_quote", "")
            if quote:
                norm_q = normalize_text(quote)
                if not norm_q: continue
                
                authoritative_cid = None
                for h in hit_list:
                    if norm_q in h["norm_text"]:
                        authoritative_cid = h["authoritative_case_id"]
                        break
                
                if authoritative_cid:
                    validated_ids.add(authoritative_cid)
                    # keep order but ensure uniqueness
                    cit_str = f"[CASE: {authoritative_cid}]"
                    if cit_str not in appended_citations:
                        appended_citations.append(cit_str)
    dur_ev = instrumentation.end("Evidence reference extraction")
    instrumentation.log("15", f"Evidence extraction END: {dur_ev:.3f} sec")
    
    instrumentation.start("Python citation mapping")
    if appended_citations:
        raw_answer = raw_answer.strip() + " " + " ".join(appended_citations)
    dur_map = instrumentation.end("Python citation mapping")
    instrumentation.log("15", f"Python citation mapping END: {dur_map:.3f} sec")

    dur_fp = instrumentation.end("Final processing")
    instrumentation.log("15", f"Final answer processing END: {dur_fp:.3f} sec")

    verification = verify_citations(raw_answer, validated_ids)

    return {
        "raw_answer": raw_answer,
        "clean_answer": verification.get("clean_answer", raw_answer),
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
    print("\nANSWER:\n", result["clean_answer"])
    print("\n", result["accuracy_note"])
    if result["unverified"]:
        print("UNVERIFIED:", result["unverified"])
