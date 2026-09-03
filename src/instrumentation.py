import time

metrics = {}
config = {}
api_calls = 0

def log(section, msg):
    print(f"[{section}] {msg}", flush=True)

def start(metric_name):
    metrics[f"{metric_name}_start"] = time.perf_counter()

def end(metric_name):
    end_time = time.perf_counter()
    start_time = metrics.get(f"{metric_name}_start", end_time)
    duration = end_time - start_time
    metrics[metric_name] = duration
    return duration

def get(metric_name):
    return metrics.get(metric_name, 0.0)

def set_config(key, value):
    config[key] = value

def get_config(key, default=""):
    return config.get(key, default)

def increment_api_call():
    global api_calls
    api_calls += 1
    return api_calls

def reset():
    metrics.clear()
    config.clear()
    global api_calls
    api_calls = 0

def print_summary():
    print("\n================ LATENCY BREAKDOWN ================", flush=True)
    def pt(name, metric_name):
        val = get(metric_name)
        print(f"{name:<25} {val:.3f} sec", flush=True)

    pt("ML Model/DB Cold Start:", "Model/DB Cold Start")
    pt("Query preprocessing:", "Query preprocessing")
    pt("Embedding:", "Embedding")
    pt("ChromaDB search:", "ChromaDB search")
    pt("FTS5 search:", "FTS5 search")
    pt("Hybrid merge:", "Hybrid merge")
    pt("Context construction:", "Context construction")
    pt("Prompt construction:", "Prompt construction")
    pt("Groq API:", "Groq API")
    pt("JSON extraction/parsing:", "JSON parsing")
    pt("Evidence ref extraction:", "Evidence reference extraction")
    pt("Python citation mapping:", "Python citation mapping")
    pt("Citation extraction:", "Citation extraction")
    pt("Citation verification:", "Citation verification")
    pt("Final processing:", "Final processing")
    pt("Streamlit rendering:", "Streamlit rendering")
    print("----------------------------------------------------", flush=True)
    total = get("Total end-to-end")
    print(f"TOTAL END-TO-END:         {total:.3f} sec", flush=True)
    print("====================================================", flush=True)
    print(f"API CALLS: {api_calls}", flush=True)
    print("====================================================\n", flush=True)

def print_model_summary():
    print("\n================ MODEL TIMING ================", flush=True)
    print(f"Selected backend: {get_config('Selected backend')}", flush=True)
    print(f"Model: {get_config('Model')}", flush=True)
    print(f"USE_GROQ: {get_config('USE_GROQ')}", flush=True)
    print(f"Model initialization: {get('Model initialization'):.3f} sec", flush=True)
    print(f"Actual API call: {get('Actual API call'):.3f} sec", flush=True)
    print(f"Model response processing: {get('Model response processing'):.3f} sec", flush=True)
    print(f"Total model time: {get('Total model time'):.3f} sec", flush=True)
    print("===============================================", flush=True)
