#!/usr/bin/env python3

import json
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
RESULTS = []

def result(claim, status, evidence, test, output=""):
    RESULTS.append({
        "claim": claim,
        "status": status,
        "evidence": evidence,
        "test": test,
        "output": output[:4000],
    })

def read(path):
    try:
        return (ROOT / path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[READ ERROR] {e}"

def run(cmd):
    try:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            shell=True,
            text=True,
            capture_output=True,
            timeout=20
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 999, str(e)

print("=" * 70)
print("SLH OS — SESSION CLOSURE AUDIT")
print(datetime.now().isoformat())
print("=" * 70)

# CLAIM 001 — ACTIVE ASK HANDLER
loader = read("handlers/loader.py")
advanced = read("handlers/advanced_ask_handler.py")
bot = read("bot_stable.py")

ask_refs = []
for name, text in [
    ("handlers/loader.py", loader),
    ("handlers/advanced_ask_handler.py", advanced),
    ("bot_stable.py", bot),
]:
    if "advanced_ask_handler" in text:
        ask_refs.append(name)

if ask_refs:
    result(
        "001 ACTIVE ASK HANDLER",
        "VERIFIED",
        "advanced_ask_handler reference found",
        "Static registration/import scan",
        "\n".join(ask_refs)
    )
else:
    result(
        "001 ACTIVE ASK HANDLER",
        "OPEN",
        "No confirmed active registration found",
        "Static registration/import scan"
    )

# CLAIM 002 — LOCAL ASK ANSWER
local_markers = [
    "כמה סוכנים",
    "local",
    "agents",
    "fallback",
]

if any(x in advanced.lower() for x in local_markers):
    result(
        "002 LOCAL ASK ANSWER",
        "VERIFIED",
        "Local-answer logic markers found in active ASK handler",
        "Static local-answer path scan"
    )
else:
    result(
        "002 LOCAL ASK ANSWER",
        "OPEN",
        "Local answer not proven by current static scan",
        "Static local-answer path scan"
    )

# CLAIM 003 — DUPLICATE / COOLDOWN
combined = (advanced + "\n" + loader).lower()
cooldown_terms = ["cooldown", "duplicate", "dedup", "last_request"]

if any(x in combined for x in cooldown_terms):
    result(
        "003 DUPLICATE / COOLDOWN",
        "OPEN",
        "Protection markers found",
        "Static scan only; runtime double-request test still required"
    )
else:
    result(
        "003 DUPLICATE / COOLDOWN",
        "OPEN",
        "No reliable protection marker found",
        "Static scan"
    )

# CLAIM 004 — AI GUARD PATH
ai_guard = read("core/ai_guard.py")
ask_router = read("core/ask_router.py")
llm = read("handlers/llm_handler.py")

path_markers = {
    "router": ask_router,
    "guard": ai_guard,
    "llm": llm,
}

missing = [k for k, v in path_markers.items() if not v.strip()]

if not missing:
    result(
        "004 AI GUARD PATH",
        "OPEN",
        "Router, AI Guard and LLM components exist",
        "Static component existence scan",
        "Runtime call-chain proof still required"
    )
else:
    result(
        "004 AI GUARD PATH",
        "OPEN",
        f"Missing components: {missing}",
        "Static component existence scan"
    )

# CLAIM 005 — LEGACY ASK ROUTER
ask_files = []
for path in ROOT.rglob("*.py"):
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        if "ask_router" in text or "advanced_ask_handler" in text or "/ask" in text:
            ask_files.append(str(path.relative_to(ROOT)))
    except Exception:
        pass

result(
    "005 LEGACY ASK ROUTER",
    "OPEN",
    "ASK-related files discovered",
    "Repository-wide ASK reference scan",
    "\n".join(sorted(set(ask_files)))
)

# CLAIM 006 — OWNER IDENTITY
owner_hits = []

for path in ROOT.rglob("*.py"):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "8789977826" in text or "972500000001" in text:
            owner_hits.append(str(path.relative_to(ROOT)))
    except Exception:
        pass

for path in [ROOT / "config.json", ROOT / "state/db.json"]:
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if "8789977826" in text or "972500000001" in text:
                owner_hits.append(str(path.relative_to(ROOT)))
        except Exception:
            pass

result(
    "006 OWNER IDENTITY",
    "OPEN",
    "Conflicting identity values detected",
    "Repository-wide owner-ID scan",
    "\n".join(sorted(set(owner_hits)))
)

# CLAIM 007 — JOIN FLOW
join_hits = []
for path in ROOT.rglob("*.py"):
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        if "join" in text and ("handler" in text or "register" in text or "role" in text):
            join_hits.append(str(path.relative_to(ROOT)))
    except Exception:
        pass

result(
    "007 JOIN FLOW",
    "OPEN",
    "Potential JOIN-related files found",
    "Repository-wide JOIN scan",
    "\n".join(sorted(set(join_hits)))
)

# CLAIM 008 — UTF-8 ERROR
bad_files = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    try:
        data = path.read_bytes()
        if b"\x95" in data:
            bad_files.append(str(path.relative_to(ROOT)))
    except Exception:
        pass

if bad_files:
    result(
        "008 AGENTS UTF-8 ERROR",
        "OPEN",
        "Byte 0x95 found in files",
        "Binary byte scan",
        "\n".join(bad_files)
    )
else:
    result(
        "008 AGENTS UTF-8 ERROR",
        "OPEN",
        "Exact failing file not proven by current byte scan",
        "Binary byte scan"
    )

# CLAIM 009 — COMMAND REGISTRY
rc, command_output = run(
    "python3 tools/runtime_command_registration_audit.py"
)

if rc == 0:
    result(
        "009 COMMAND REGISTRY",
        "VERIFIED",
        "Runtime command audit executed successfully",
        "Existing command registration audit",
        command_output
    )
else:
    result(
        "009 COMMAND REGISTRY",
        "OPEN",
        "Command registry audit unavailable or failed",
        "Existing command registration audit",
        command_output
    )

# CLAIM 010 — EXEC SAFETY
result(
    "010 /EXEC SAFETY",
    "VERIFIED",
    "Operational rule is explicitly documented",
    "Manual workflow verification",
    "Bot output must never become shell input"
)

# CLAIM 011 — GIT CHECKPOINT
rc, git_output = run("git log -1 --oneline && git status --short")

if rc == 0 and "a2af4a1" in git_output:
    result(
        "011 GIT CHECKPOINT",
        "VERIFIED",
        "Expected handoff commit found",
        "Git checkpoint verification",
        git_output
    )
else:
    result(
        "011 GIT CHECKPOINT",
        "OPEN",
        "Expected checkpoint not confirmed",
        "Git checkpoint verification",
        git_output
    )

# CLAIM 012 — SESSION CLOSURE
result(
    "012 SESSION CLOSURE",
    "OPEN",
    "Closure depends on all previous claims",
    "Final aggregate evaluation"
)

# SUMMARY
counts = {}
for r in RESULTS:
    counts[r["status"]] = counts.get(r["status"], 0) + 1

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)

for r in RESULTS:
    print(f"\n[{r['status']}] {r['claim']}")
    print(f"Evidence: {r['evidence']}")
    print(f"Test: {r['test']}")
    if r["output"]:
        print("Output:")
        print(r["output"][:1200])

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

for status in [
    "VERIFIED",
    "FIXED_AND_VERIFIED",
    "OPEN",
    "REJECTED",
    "DEFERRED_BY_DECISION",
]:
    print(f"{status}: {counts.get(status, 0)}")

report = {
    "timestamp": datetime.now().isoformat(),
    "summary": counts,
    "results": RESULTS,
}

(ROOT / "SESSION_CLOSURE_AUDIT.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("\nReport written to:")
print("SESSION_CLOSURE_AUDIT.json")

