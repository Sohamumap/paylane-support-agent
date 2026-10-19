# Model-run evidence

There are two assisted review rounds: the initial Claude Code-assisted build and the later Codex/GPT-assisted review. **The support bot uses Claude through Anthropic's API in both.** All 12 core customer scripts and the two original extra scripts are identical across the 18 and 19 October completed runs. The latest round adds x03 (revised fraud loss) and x04 (a timeout after the refund applied), alongside changes to the implementation, instructions and checks. See [the submission comparison](../SUBMISSION.md#two-rounds-of-testing-and-review).

Start with the completed runs of the reviewed version:

| Run | Evidence | Automated result |
|---|---|---|
| 19 October core | [12 conversations, three repeats each](20261019-1808-submission-core/summary.md) | 36/36 chats; 252/252 checks |
| 19 October extra | [Four cases, three repeats each](20261019-1808-submission-extra/summary.md) | 12/12 chats; 84/84 checks |

Each completed run contains the customer and model replies in Markdown and JSON, tool traces, outcomes and a summary. New `manifest.json` files preserve the system prompt, source/conversation hashes, timestamps, SDK version and actual model names. `intermediate_replies` is internal tool-planning prose, retained for audit; it is not shown to the customer.

An automated pass means these checks accepted these scripted conversations. [REPORT.md](../REPORT.md#results) also records wording issues found manually and the remaining limits.

## Historical evidence

The 16 and 18 October folders are preserved as generated. Their check marks describe the grader at the time. The old 18 October core score of 252/252 becomes **248/252** under the current checks; the original extra suite becomes **42/42** after repairing the patterns. Separate current regrades are saved in [20261019-review](20261019-review/).

- **18 October core:** [original summary](20261018-1016-final3/summary.md), [current rescore](20261019-review/20261018-1016-final3-rescored.md).
- **18 October extras:** [original summary](20261018-1015-extra/summary.md), [current rescore](20261019-review/20261018-1015-extra-rescored.md).

The 18 October core records include 214 `claude-opus-5-5` calls and eight `claude-opus-4-8` fallback calls (in c06-r1 and c06-r2). Its summary names the configured model; the per-call JSON is the fuller record. The 18 October extras and both latest completed suites record only `claude-opus-5-5`. The original build iterations on 16 October remain available as additional history.

Two exploratory 19 October core suites were stopped before completion. Their summaries and manifests say **interrupted**. They are not counted as final evaluations.

Regrade any complete saved run without an API key:

```bash
python -m paylane rescore transcripts/20261019-1808-submission-core
```
