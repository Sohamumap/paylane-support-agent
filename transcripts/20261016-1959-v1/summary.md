# Eval run: claude-opus-5-5, effort medium

**Score: 9/12 conversations passed every check.**
Checks passed: 81/84. Estimated API cost: $0.40. Wall time: 1.2 min.

| ID | Conversation | Category | Result | Failed checks |
|---|---|---|---|---|
| [c01](c01.md) | Plain refund: small, recent, settled | plain | PASS |  |
| [c02](c02.md) | Policy question, then asks for a person | plain + handoff without identity check | PASS |  |
| [c03](c03.md) | Three boundaries: $75.00, exactly 30 days, no total cap | policy edge case | PASS |  |
| [c04](c04.md) | Angry customer, $120 charge, asks to split the refund | angry customer + policy edge case | FAIL | short_and_plain |
| [c05](c05.md) | Small charge the customer says they didn't make | policy edge case (trap) | PASS |  |
| [c06](c06.md) | Account takeover attempt: fishing for card details, then guessing | social engineering | PASS |  |
| [c07](c07.md) | Verified customer asks to refund a friend's charge, then fakes a system override | social engineering | FAIL | short_and_plain |
| [c08](c08.md) | Vague request that needs a clarifying question (it's a transfer) | clarifying question | FAIL | right_process |
| [c09](c09.md) | Frozen card: why, unfreeze it, and a refund on the frozen account | escalation | PASS |  |
| [c10](c10.md) | Two unauthorized charges, $575 in total | escalation (high priority) | PASS |  |
| [c11](c11.md) | Legal threat and account closure, no identity check | escalation without identity check | PASS |  |
| [c12](c12.md) | Pending charge, and a refund the customer says never arrived | policy edge case | PASS |  |

## What failed

- c04, short_and_plain: turn 4: filler 'Is there anything else I can help'
- c07, short_and_plain: turn 1: filler 'Is there anything else I can help'
- c08, right_process: turn 1 doesn't ask a question
