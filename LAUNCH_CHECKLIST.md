# Before connecting real customers

The submitted agent uses mock accounts, payments and tickets. This checklist keeps the detailed launch questions out of the short [customer email](CUSTOMER_NOTE.md).

## Decisions for Paylane's support team

- **Freeze reasons:** which reasons may the assistant share, and which must stay private? The supplied API only says whether a card is frozen.
- **Timing:** what refund arrival times and human response times may we tell customers? None were supplied, so the prototype promises neither.
- **Handoff ownership:** who watches the queue, including evenings and weekends? What should happen if nobody is available?
- **Frozen-card refunds:** the prototype holds otherwise eligible refunds for the person reviewing the freeze. Confirm this cautious choice.
- **Fraud scope:** named disputed charges are held for review. An unrelated eligible refund may still proceed; a fraud report with no named charges pauses refunds across the chat. Confirm the intended scope.
- **Real examples:** supply 50–100 past chats with personal details removed, including complaints and difficult handoffs, to expand the evaluation set.

## Gaps to resolve in the real systems

- **Identity:** replace the email-and-last-four check with trusted app sign-in or another approved verification flow. Those two facts alone are weak proof of identity.
- **Transaction type:** provide a reliable way to distinguish a purchase from a transfer. The prototype's purchase labels are fixture data, not a field promised by the API.
- **Transaction lookup:** customers may not know transaction IDs. Add a read-only view of the verified customer's own recent transactions if Paylane can support it.
- **Ticket updates:** the supplied API cannot append to a ticket, so follow-ups currently create linked tickets. Agree how the live support system should collect updates.
- **Refund uncertainty:** define how support reconciles a timeout, how the refund API prevents duplicate payment, and how a confirmed refund is identified. A read-back that doesn't show refunded is still an uncertain outcome.
- **Durable state:** persist verification state, attempted refunds, holds and tickets, with safe handling of simultaneous requests and restarts. The prototype keeps state in one process.

## Proposed launch gates

- Connect and test the real APIs before enabling any real refunds.
- Run the expanded cases repeatedly, inspect the transcripts, and review failures with the support team. Passing the current scripted checks alone is insufficient launch evidence.
- Build a human approval step for refunds and an operational way to pause automation. Neither is part of the submitted mock.
- Start with staff approval, review the early conversations and only then agree whether to enable automatic refunds.
