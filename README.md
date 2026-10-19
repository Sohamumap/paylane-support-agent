# Paylane support agent

A chat support agent for Paylane, a pretend card and payments app, built for Fini's take-home. Claude runs the conversation. The money rules also live in code, so the agent can't refund what the policy forbids even if a customer talks it into trying.

- **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)**: the whole thing as plain-language flow diagrams. Start here.
- **[REPORT.md](REPORT.md)**: how it works, the 12 conversations and why I chose them, the checks, a failure I found and how I fixed it, decisions, tradeoffs.
- **[CUSTOMER_NOTE.md](CUSTOMER_NOTE.md)**: the email to Paylane's head of support.
- **[transcripts/](transcripts/)**: every live model run, with a summary per run.

## Run it

Needs Python 3.11 or newer and an Anthropic API key.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then paste your key after ANTHROPIC_API_KEY=
```

| Command | What it does | Key needed |
|---|---|---|
| `python -m pytest` | Deterministic tests: policy boundaries, the guard, the checks, and the chat loop with a fake model | No |
| `python -m paylane eval` | Runs the 12 conversations against the live model, saves transcripts and scores them (about $0.50, under 2 minutes) | Yes |
| `python -m paylane eval --repeat 3` | The same, three times per conversation | Yes |
| `python -m paylane eval --extra` | Two failure tests: the refund call times out, or is declined | Yes |
| `python -m paylane rescore transcripts/<run>` | Re-grades a saved run with the current checks | No |
| `python -m paylane web` | Chat with the agent in your browser at http://127.0.0.1:8765, with a side panel showing every tool call, what the guard blocked, refunds and tickets | Yes |
| `python -m paylane chat` | The same in the terminal; every tool call is printed | Yes |

Defaults: `claude-opus-5-5` at effort `medium`. Override with `--model` and `--effort`, or `PAYLANE_MODEL` and `PAYLANE_EFFORT`.

## Results

Final run, Claude Opus 5.5 at medium effort, each conversation three times: **12/12 conversations passed every check in all three runs (252/252 checks)**. [Summary](transcripts/20261018-1016-final3/summary.md), with every transcript in the same folder. Two extra failure tests (a refund call that times out, and one that's declined) passed all three runs too.

It took several rounds to get there. The first run scored 9/12, a repeated run caught a failure that a single clean run had hidden, and Fini's answers to my two questions led to the last changes. [REPORT.md](REPORT.md#results) has the history and every failure I found.

## Layout

```
paylane/      the agent: rulebook.md, prompt.py, agent.py (chat loop), tools.py (guard),
              policy.py, mock_api.py (the 4 endpoints), session.py, redact.py, data.py,
              web.py + web.html (the browser chat page, standard library only)
evals/        checks.py (7 deterministic checks), runner.py
conversations/ the 12 scripted conversations, each with why it's there and what must happen
tests/        deterministic tests, no API key needed
transcripts/  live runs: v1, v2, v3 and the final run
```

## How this was built

With a lot of help from Claude Code, Anthropic's AI coding assistant, which the brief allows if disclosed. Claude Code wrote most of the code, the tests and the conversation scripts, and drafted these documents, working from my decisions and review. I've read all of it and can explain or change any part. The agent itself runs on Claude Opus 5.5 through the Anthropic API.
