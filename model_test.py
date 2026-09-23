"""
Dry-run model tester — tests each confirmed-live Gemini model against
the first professor in the CSV, bypassing the sent-email dedup.
"""
import os, sys, shutil, subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
LOG = BASE / "EMAIL_LOG.csv"
LOG_BAK = BASE / "EMAIL_LOG.csv.testbak"

# Confirmed-live models from API (ordered best → lightest)
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]

# Back up real log
if LOG_BAK.exists():
    LOG_BAK.unlink()
shutil.copy2(LOG, LOG_BAK)
print(f"[backup] {LOG.name} → {LOG_BAK.name}")

results = {}

for model in MODELS:
    print(f"\n{'='*70}")
    print(f"  TESTING MODEL: {model}")
    print(f"{'='*70}")

    # Write blank log so no emails are "already sent"
    LOG.write_text("", encoding="utf-8")

    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "DRY_RUN": "True",
        "MAX_EMAILS": "1",
        "GEMINI_MODELS": model,
    }
    result = subprocess.run(
        [sys.executable, "chinese.py"],
        cwd=str(BASE),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    output = result.stdout + result.stderr

    valid = "✓ Valid professional email generated." in output
    preview_start = output.find("EMAIL PREVIEW")
    preview = output[preview_start:preview_start + 2000] if preview_start != -1 else "(no preview)"

    results[model] = {
        "exit_code": result.returncode,
        "valid_email": valid,
        "preview": preview,
        "output": output,
    }

    if valid:
        print(output)
    else:
        # Print just the error lines
        for line in output.splitlines():
            if any(k in line for k in ["✗", "✓", "SKIP", "FAIL", "404", "ERROR", "DRY RUN", "FINAL"]):
                print(line)

# Restore real log
shutil.copy2(LOG_BAK, LOG)
LOG_BAK.unlink()
print(f"\n[restored] {LOG.name}")

# ── FINAL SUMMARY ─────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  MODEL TEST SUMMARY")
print(f"{'='*70}")
for model, r in results.items():
    status = "✓ PASS" if r["valid_email"] else "✗ FAIL"
    print(f"  {status}  {model}")

# ── EMAIL PREVIEWS FOR PASSING MODELS ─────────────────────────────────────────
print()
for model, r in results.items():
    if r["valid_email"]:
        print(f"\n{'─'*70}")
        print(f"  EMAIL PREVIEW — {model}")
        print(f"{'─'*70}")
        print(r["preview"])
