# Paylane assignment — start here

**Submitted by Soham Umap · AI Solutions Engineer take-home · 19 October 2026**

I built a support agent that checks identity, handles eligible purchase refunds and passes cases outside its authority to a person. The part I paid most attention to was what happens when the customer pushes back: guessing verification details, pretending to be staff, splitting an oversized refund, or adding a new request after a handoff.

This is a working mock integration with fictional accounts. Claude handles the conversation through the Anthropic API; code checks the facts before a refund can reach the mock payment function. The test clock is fixed at 16 October 2026, 12:00 UTC.

## Where each deliverable is

| What the assignment asks for | Where to review it |
|---|---|
| Agent in code, system prompt and rulebook | [System prompt](paylane/prompt.py), [rulebook](paylane/rulebook.md), [agent loop](paylane/agent.py) |
| Four mock API functions, callable by the agent | [Mock API](paylane/mock_api.py), [guard around the tools](paylane/tools.py), [policy checks](paylane/policy.py) |
| Twelve customer conversations, chosen edge cases and actual transcripts | [Scenario files](conversations/), [why I chose each case](REPORT.md#the-12-conversations), [latest core transcripts](transcripts/20261019-1808-submission-core/) |
| Pass/fail checks, scores, a discovered failure and its fix | [Checks](evals/checks.py), [results and review findings](REPORT.md#results), [original failure and fix](REPORT.md#a-failure-i-found-and-the-fix) |
| Short email to Paylane's head of support | [Customer note](CUSTOMER_NOTE.md) |
| How to run it | [README](README.md#run-it); local tests need no API key |

The [flow diagrams](HOW_IT_WORKS.md) give a quick picture of the design. [Launch questions](LAUNCH_CHECKLIST.md) separate this exercise from what a real integration still needs.

## Two rounds of testing and review

I used **Claude Code** for the initial implementation and testing, then **Codex/GPT** for a second review that challenged the tests, inspected the transcripts and helped correct failures. **Both rounds ran the support bot through the Anthropic API.** GPT assisted the review; it was not a second support-bot model in an API benchmark. Scores come from deterministic checks over replies, tool calls and stored outcomes, supplemented by transcript reading.

The rounds deliberately overlap. All 12 core scripts and the two original extra scripts use the **same customer questions** in the 18 and 19 October runs. Repeating them checks whether fixes hold. The second round added two targeted scenarios: a fraud loss corrected from $100 to $600, and a refund that completed before its response was lost. This is a repeated regression suite with added coverage, not a separate unseen question bank. Customer messages are scripted; the bot's replies and tool calls are live model output.

| Round and evidence | Coverage | Automated result |
|---|---|---|
| Initial build, completed 18 October: [core](transcripts/20261018-1016-final3/summary.md), [extras](transcripts/20261018-1015-extra/summary.md) | 12 core + 2 extra scenarios, each repeated 3 times | Originally 252/252 core checks and 39/42 extra checks |
| Second review, rescoring those unchanged historical transcripts: [core](transcripts/20261019-review/20261018-1016-final3-rescored.md), [extras](transcripts/20261019-review/20261018-1015-extra-rescored.md) | Same saved model output; stronger and repaired checks | 248/252 core checks; 10/12 scenarios clean in every repeat. Extras: 42/42 after fixing false-positive patterns |
| Fresh runs after corrections, 19 October: [core](transcripts/20261019-1808-submission-core/summary.md), [extras](transcripts/20261019-1808-submission-extra/summary.md) | 12 core + 4 extra scenarios, each repeated 3 times | 36/36 core chats, 252/252 checks; 12/12 extra chats, 84/84 checks |

The reviewed source also passes **107 deterministic tests** without a model. The completed final live suites contain **48 chats and 336 check results**. Those are repeated observations of 16 scenarios, not 48 different scenarios. The [evidence index](transcripts/README.md) links both rounds and identifies interrupted exploratory runs separately.

Latest recorded model: `claude-opus-5-5`, effort `medium`. The historical 18 October core run also contains eight `claude-opus-4-8` fallback calls; the individual JSON records preserve this. Latest manifests record actual model names, timestamps, the system prompt and source/scenario hashes.

## What failed, and what changed

- **A handoff lost the customer's next request.** The first build could tell a customer to repeat a new refund request to the reviewer. The later review found the same class of problem with legal account records. New information now gets a linked handoff, and the checks inspect what was actually saved.
- **A perfect score missed bad replies.** Historical replies promised that a person would follow up and exposed “Check straight away.” The review strengthened promise/tone checks, clarified the instructions and kept internal tool-planning prose out of the displayed reply. The original transcripts remain available.
- **A correction to fraud loss could be discarded.** A repeated ticket for the same transaction could suppress the change from $100 to $600. The guard now preserves the correction in a linked ticket and raises priority; the new x03 case exercises it live.
- **Timeouts needed two distinct outcomes.** A read-back confirming a refund supports a success response. Without confirmation, the result stays unknown and goes to a person for reconciliation. Neither path retries the payment. Both are now covered by live cases.

The [full report](REPORT.md#what-the-independent-review-found) records the evidence and other corrections, including the faulty extra-case patterns and browser error handling.

## Decisions, limits and my contribution

I asked Deep about transfer reversals and retry safety before settling those behaviours. His answers are reflected in the implementation: a transfer reversal goes to a person because no reversal API exists; a failed or uncertain refund is never blindly retried. Purchase labels are identified as test fixtures, not an invented production API field.

I spent roughly four hours on the initial build and made the choices around verification, adversarial scenarios, guardrails and human handoff. Claude Code wrote most of the implementation, tests and scripts and helped draft the documents. The later Codex-assisted review and corrections took additional time beyond that initial build.

The current passing scores cover a small scripted set and wording-based checks. Manual reading still found two minor wording issues, recorded in the report. Recognising fraud or legal intent still depends on the model. Identity checking uses the exercise's email/last-four rule; state is in memory, tickets are mocked, and there is no production approval workflow or durable payment ledger. The customer note and launch checklist explain the decisions needed before real use.
