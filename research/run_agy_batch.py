"""Launch a batch of Gemini (agy) experimenters in parallel.

Each experiment = one hypothesis in a JSON list file:
  [{"id": "G001", "hypothesis": "...", "magic": 994001}, ...]
The shared prompt template lives in research/agy_prompt_template.txt ({ID}, {HYPOTHESIS}, {MAGIC}, {LAB_HINT}).

Usage:
  python research/run_agy_batch.py hyps_batch1.json --workers 10 --model gemini-3.8-flash-medium
Results are read afterwards from reports/ea_backtests/*/result.json (never trust agent prose).
Agent stdout/stderr -> reports/agy_batches/<batch>/<id>.txt
"""
import argparse, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "research" / "agy_prompt_template.txt"


def run_one(h, model, outdir, timeout):
    prompt = TEMPLATE.read_text(encoding="utf-8").format(
        ID=h["id"], ID_L=h["id"].lower(), HYPOTHESIS=h["hypothesis"], MAGIC=h["magic"])
    out = outdir / f"{h['id']}.txt"
    t0 = time.time()
    try:
        r = subprocess.run(
            ["agy", "--dangerously-skip-permissions", "--model", model,
             f"--print={prompt}", "--print-timeout", f"{timeout}s"],
            cwd=ROOT, capture_output=True, text=True, timeout=timeout + 60)
        out.write_text((r.stdout or "") + "\n--stderr--\n" + (r.stderr or ""), encoding="utf-8")
        return h["id"], r.returncode, round(time.time() - t0)
    except subprocess.TimeoutExpired:
        out.write_text("TIMEOUT", encoding="utf-8")
        return h["id"], -1, round(time.time() - t0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("hyps")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--model", default="gemini-3.8-flash-medium")
    ap.add_argument("--timeout", type=int, default=3000)
    a = ap.parse_args()
    hyps = json.loads(Path(a.hyps).read_text(encoding="utf-8"))
    outdir = ROOT / "reports" / "agy_batches" / Path(a.hyps).stem
    outdir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for hid, code, secs in ex.map(lambda h: run_one(h, a.model, outdir, a.timeout), hyps):
            print(f"{hid} exit={code} {secs}s", flush=True)
