"""Run the scripted conversations against the live model, save transcripts, and score them."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import anthropic

from paylane.agent import SupportAgent
from paylane.mock_api import MockPaylaneAPI
from paylane.session import Session
from paylane.tools import ToolBox

from .checks import run_checks

ROOT = Path(__file__).resolve().parent.parent
CONVERSATIONS = ROOT / "conversations"
TRANSCRIPTS = ROOT / "transcripts"

# USD per million tokens: input, output, cache read, cache write (5-minute TTL).
PRICES = {"claude-opus-5-5": (4.00, 20.00, 0.20, 5.00)}


def load_conversations(only=None):
    specs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CONVERSATIONS.glob("*.json"))]
    return [s for s in specs if not only or s["id"] in only]


def run_conversation(spec, *, client=None, model=None, effort=None) -> dict:
    api, session = MockPaylaneAPI(), Session()
    agent = SupportAgent(ToolBox(api, session), client=client, model=model, effort=effort)
    started = time.monotonic()
    turns = [asdict(agent.reply(text)) for text in spec["turns"]]
    record = {
        "id": spec["id"],
        "title": spec["title"],
        "category": spec["category"],
        "model": agent.model,
        "effort": agent.effort,
        "seconds": round(time.monotonic() - started, 1),
        "turns": turns,
        "final": {
            "verified_customer": session.customer_id,
            "failed_checks": session.failed_checks,
            "account_hold": session.account_hold,
            "refunds": api.refunds,
            "tickets": session.tickets,
        },
    }
    record["checks"] = run_checks(spec, record)
    record["passed"] = all(c["passed"] for c in record["checks"])
    return record


def run_suite(specs, *, repeat=1, workers=4, label="run", model=None, effort=None, client=None):
    out = TRANSCRIPTS / f"{datetime.now():%Y%m%d-%H%M}-{label}"
    out.mkdir(parents=True, exist_ok=True)
    client = client or anthropic.Anthropic(max_retries=4, timeout=180)
    started = time.monotonic()

    def job(item):
        spec, attempt = item
        try:
            record = run_conversation(spec, client=client, model=model, effort=effort)
        except Exception as exc:  # one broken conversation shouldn't sink the whole run
            record = {"id": spec["id"], "title": spec["title"], "category": spec["category"],
                      "error": repr(exc), "passed": False, "checks": [], "turns": []}
        record["attempt"] = attempt
        name = spec["id"] if repeat == 1 else f"{spec['id']}-r{attempt}"
        (out / f"{name}.md").write_text(render_markdown(record), encoding="utf-8")
        (out / f"{name}.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        failed = ", ".join(c["name"] for c in record["checks"] if not c["passed"]) or record.get("error", "")
        print(f"  {name}: {'PASS' if record['passed'] else 'FAIL  ' + failed}", flush=True)
        return record

    jobs = [(spec, attempt) for spec in specs for attempt in range(1, repeat + 1)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(job, jobs))
    summary = render_summary(records, repeat, time.monotonic() - started)
    (out / "summary.md").write_text(summary, encoding="utf-8")
    return out, records, summary


def rescore(run_dir) -> str:
    """Re-run the checks on a saved run, using the current conversation files. No API calls, no cost."""
    specs = {spec["id"]: spec for spec in load_conversations()}
    records = []
    for path in sorted(Path(run_dir).glob("c*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if "error" not in record:
            record["checks"] = run_checks(specs[record["id"]], record)
            record["passed"] = all(c["passed"] for c in record["checks"])
        records.append(record)
    repeat = max((r.get("attempt", 1) for r in records), default=1)
    return render_summary(records, repeat, elapsed=None)


def estimate_cost(records) -> float:
    total = 0.0
    for record in records:
        for turn in record.get("turns", []):
            for call in turn["model_calls"]:
                prices = PRICES.get(call["model"])
                if prices:
                    p_in, p_out, p_read, p_write = prices
                    total += (call["input_tokens"] * p_in + call["output_tokens"] * p_out
                              + call["cache_read_input_tokens"] * p_read
                              + call["cache_creation_input_tokens"] * p_write) / 1_000_000
    return total


def render_markdown(record) -> str:
    verdict = "PASS" if record["passed"] else "FAIL"
    lines = [f"# {record['id']}: {record['title']}", ""]
    if "error" in record:
        return "\n".join(lines + [f"Run crashed: `{record['error']}`", ""])
    lines += [f"Category: {record['category']} | Model: {record['model']} (effort {record['effort']}) | "
              f"Result: **{verdict}**", ""]
    for turn in record["turns"]:
        lines += [f"**Customer:** {turn['customer']}", ""]
        for e in turn["tools"]:
            flag = f" **BLOCKED: {e['blocked']}**" if e["blocked"] else ""
            lines.append(f"> `{e['tool']}` `{json.dumps(e['input'])}` -> `{json.dumps(e['result'])}`{flag}  ")
        if turn["tools"]:
            lines.append("")
        lines += [f"**Agent:** {turn['reply']}", ""]
        if turn["hidden"]:
            lines += [f"_(hidden before sending: {', '.join(turn['hidden'])})_", ""]
    lines += ["## Checks", ""]
    for c in record["checks"]:
        lines.append(f"- [{'x' if c['passed'] else ' '}] {c['name']}" + (f": {c['detail']}" if c["detail"] else ""))
    lines += ["", "## Tickets opened", ""]
    for t in record["final"]["tickets"] or []:
        lines += [f"{t['ticket_id']}:", "", "```", t["summary"], "```", ""]
    if not record["final"]["tickets"]:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def render_summary(records, repeat, elapsed) -> str:
    by_id = {}
    for record in records:
        by_id.setdefault(record["id"], []).append(record)
    clean = sum(all(r["passed"] for r in runs) for runs in by_id.values())
    checks = [c for r in records for c in r.get("checks", [])]
    first = next((r for r in records if "model" in r), {"model": "?", "effort": "?"})
    runs_note = f" in all {repeat} runs" if repeat > 1 else ""
    timing = f" Wall time: {elapsed / 60:.1f} min." if elapsed is not None else " (Rescored from saved transcripts.)"
    lines = [
        f"# Eval run: {first['model']}, effort {first['effort']}",
        "",
        f"**Score: {clean}/{len(by_id)} conversations passed every check{runs_note}.**",
        f"Checks passed: {sum(c['passed'] for c in checks)}/{len(checks)}. "
        f"Estimated API cost: ${estimate_cost(records):.2f}.{timing}",
        "",
        "| ID | Conversation | Category | Result | Failed checks |",
        "|---|---|---|---|---|",
    ]
    for cid, runs in sorted(by_id.items()):
        passes = sum(r["passed"] for r in runs)
        result = ("PASS" if passes == len(runs) else "FAIL") + (f" {passes}/{len(runs)}" if repeat > 1 else "")
        failed = sorted({c["name"] for r in runs for c in r.get("checks", []) if not c["passed"]}
                        | ({"crashed"} if any("error" in r for r in runs) else set()))
        link = f"[{cid}]({cid}.md)" if repeat == 1 else cid
        lines.append(f"| {link} | {runs[0]['title']} | {runs[0]['category']} | {result} | {', '.join(failed)} |")
    failures = [(r, c) for r in records for c in r.get("checks", []) if not c["passed"]]
    if failures:
        lines += ["", "## What failed", ""]
        for r, c in failures:
            run = f" run {r['attempt']}" if repeat > 1 else ""
            lines.append(f"- {r['id']}{run}, {c['name']}: {c['detail']}")
    return "\n".join(lines) + "\n"
