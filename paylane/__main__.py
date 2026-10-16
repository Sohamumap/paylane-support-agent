"""Command line.

    python -m paylane chat              talk to the agent in the terminal (mock data)
    python -m paylane eval              run the 12 scripted conversations and score them
    python -m paylane rescore <folder>  re-grade a saved run with the current checks (no API key needed)
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path=ROOT / ".env"):
    """Read KEY=value lines from .env without overriding variables already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value


def run_chat(args):
    from . import data
    from .agent import SupportAgent
    from .mock_api import MockPaylaneAPI
    from .session import Session
    from .tools import ToolBox

    print("Paylane support chat with mock data. Type 'quit' to leave. Test customers:")
    for c in data.CUSTOMERS:
        print(f"  {c['name']}: {c['email']}, card ending {c['card_last4']} ({c['status']})")
    agent = SupportAgent(ToolBox(MockPaylaneAPI(), Session()), model=args.model, effort=args.effort)
    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        turn = agent.reply(text)
        for e in turn.tools:
            flag = f"  [BLOCKED: {e['blocked']}]" if e["blocked"] else ""
            print(f"  - {e['tool']} {json.dumps(e['input'])} -> {json.dumps(e['result'])}{flag}")
        print(f"\nPaylane: {turn.reply}")


def run_eval(args):
    from evals.runner import load_conversations, run_suite

    only = set(args.only.split(",")) if args.only else None
    specs = load_conversations(only)
    print(f"Running {len(specs)} conversation(s) x {args.repeat}...")
    out, _records, summary = run_suite(specs, repeat=args.repeat, workers=args.workers, label=args.label,
                                       model=args.model, effort=args.effort)
    print("\n" + summary)
    print(f"Transcripts: {out}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m paylane")
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="talk to the agent in the terminal")
    evaluate = sub.add_parser("eval", help="run the scripted conversations and score them")
    evaluate.add_argument("--only", help="comma-separated conversation IDs, for example c03,c05")
    evaluate.add_argument("--repeat", type=int, default=1, help="run each conversation N times")
    evaluate.add_argument("--workers", type=int, default=4, help="conversations run in parallel")
    evaluate.add_argument("--label", default="run", help="suffix for the transcripts folder")
    for p in (chat, evaluate):
        p.add_argument("--model", help="default: claude-opus-5-5, or PAYLANE_MODEL")
        p.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"],
                       help="default: medium, or PAYLANE_EFFORT")
    rescore = sub.add_parser("rescore", help="re-grade a saved run with the current checks")
    rescore.add_argument("folder", help="a run folder under transcripts/")
    args = parser.parse_args(argv)

    if args.command == "rescore":
        from evals.runner import rescore as rescore_run
        print(rescore_run(args.folder))
        return
    load_env_file()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and paste your key after the = sign.")
    if args.command == "chat":
        run_chat(args)
    else:
        run_eval(args)


if __name__ == "__main__":
    main()
