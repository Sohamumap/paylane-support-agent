# Paylane support agent

A chat support agent for Paylane, a pretend card and payments app, built for Fini's take-home. Claude runs the conversation. Code checks identity, ownership, amount, age, status and handoff holds before allowing a refund. Recognising a fraud report or legal threat still depends on the model; the conversations test that judgement.

- **[SUBMISSION.md — start here](SUBMISSION.md)**: the assignment mapped to deliverables, both review rounds, what failed, what changed, and my contribution.
- **[REPORT.md#results](REPORT.md#results)**: results and the failures the checks originally missed.
- **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)**: the flow, in pictures.
- **[REPORT.md](REPORT.md)**: how it works, the 12 conversations and why I chose them, the checks, a failure I found and how I fixed it, decisions, tradeoffs.
- **[CUSTOMER_NOTE.md](CUSTOMER_NOTE.md)**: the email to Paylane's head of support.
- **[LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md)**: the integration gaps and customer decisions before real use.
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
| `python -m paylane eval --extra` | Four extra cases: unknown timeout, explicit decline, revised fraud loss and a timeout confirmed by read-back | Yes |
| `python -m paylane rescore transcripts/<run>` | Re-grades a saved run with the current checks | No |
| `python -m paylane web` | Chat with the agent in your browser at http://127.0.0.1:8765, with a side panel showing every tool call, what the guard blocked, refunds and tickets | Yes |
| `python -m paylane chat` | The same in the terminal; every tool call is printed | Yes |

Defaults: `claude-opus-5-5` at effort `medium`. Override with `--model` and `--effort`, or `PAYLANE_MODEL` and `PAYLANE_EFFORT`.

The demo uses fictional accounts and a fixed clock of **16 October 2026, 12:00 UTC**. It never moves real money. The browser's side panel is a reviewer inspector containing mock tool inputs; it is not a production customer interface. Every chat gets its own mock bank. Dependencies in `requirements.txt` are pinned to the versions used for this review. Model runs send the fictional fixtures to Anthropic and incur charges; deterministic tests and rescoring do not.

## Results

**Reviewed version, 19 October:** all **12 required conversations passed all seven checks in all three repeats (252/252 checks)**. The **four extra cases passed all three repeats (84/84)**. [Core transcripts and summary](transcripts/20261019-1808-submission-core/summary.md), [extra cases](transcripts/20261019-1808-submission-extra/summary.md), [run index](transcripts/README.md). The deterministic suite passes **107 tests**. The report also records two wording imperfections found by manual reading.

The 18 October run originally scored **12/12 (252/252 checks)**. An independent review on 19 October found contact promises and a missing follow-up handoff that those checks missed. With stronger checks, the same unchanged transcripts score **10/12 across all three repeats (248/252 checks)**. See [REPORT.md#results](REPORT.md#results) for the current evidence and corrections. A score describes these scripted cases, not a guarantee of safe production behaviour.

The original runs and failures remain in the repo. New runs also save source and conversation hashes, timestamps, SDK version and actual model names in `manifest.json`. Claude Code assisted the first round and Codex/GPT assisted the second review; both tested the bot through Anthropic's API. The second round repeated the original questions and added two new cases. See [the comparison](SUBMISSION.md#two-rounds-of-testing-and-review).

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

I spent roughly four hours working with Claude Code on the initial build. My focus was verification, adversarial scenarios, guardrails and when a person should take over. Claude Code generated most of the implementation, tests and documentation. A later Codex-assisted review challenged the checks, found additional failures and helped make corrections; that work was additional to the initial build time. The agent itself uses Claude through the Anthropic API.
