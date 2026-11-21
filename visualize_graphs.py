"""
Generates and opens the PNG diagrams of the 4 LangGraph graphs.
Uses mermaid.ink (requires an internet connection) for rendering.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSISTANT = os.path.join(ROOT, "assistant")
OUT_DIR = os.path.join(ROOT, "graphs_output")

sys.path.insert(0, ASSISTANT)
os.makedirs(OUT_DIR, exist_ok=True)

# Load the .env variables manually (python-dotenv not required)
env_path = os.path.join(ASSISTANT, ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

GRAPHS = [
    ("1_extractor",  "agents.extractor.graph", "build_extractor_graph"),
    ("2_auditor",    "agents.auditor.graph",   "build_auditor_graph"),
    ("3_analyst",    "agents.analyst.graph",   "build_analyst_graph"),
    ("4_chatbot",     "agents.chatbot.graph",   "build_chatbot_graph"),
]

print("=" * 55)
print("  LangGraph graph rendering — OCR PFE GLM")
print("=" * 55)

files_opened = []

for name, module_path, fn_name in GRAPHS:
    print(f"\n[{name}] Import en cours...", end="", flush=True)
    try:
        import importlib
        mod = importlib.import_module(module_path)
        build_fn = getattr(mod, fn_name)
        g = build_fn()
        print(" OK", flush=True)
    except Exception as e:
        print(f" Import ERROR: {e}")
        continue

    png_path = os.path.join(OUT_DIR, f"{name}.png")
    print(f"  Rendu PNG (mermaid.ink)...", end="", flush=True)
    try:
        png_data = g.get_graph(xray=True).draw_mermaid_png()
        with open(png_path, "wb") as f:
            f.write(png_data)
        print(f" {len(png_data)//1024} KB  →  {png_path}")
        files_opened.append(png_path)
    except Exception as e:
        print(f" Rendering ERROR: {e}")
        # ASCII fallback in the terminal
        try:
            ascii_art = g.get_graph().draw_ascii()
            txt_path = os.path.join(OUT_DIR, f"{name}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(ascii_art)
            print(f"  → ASCII saved: {txt_path}")
            files_opened.append(txt_path)
        except Exception as e2:
            print(f"  → ASCII also failed: {e2}")

print("\n" + "=" * 55)
if files_opened:
    print(f"  {len(files_opened)} file(s) generated — opening...")
    print("=" * 55)
    for path in files_opened:
        os.startfile(path)
        time.sleep(0.4)
else:
    print("  No file generated.")
    print("=" * 55)

print("\nOutput folder:", OUT_DIR)
input("\nPress Enter to close...")
