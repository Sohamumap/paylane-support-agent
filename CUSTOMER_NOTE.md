**To:** Head of Support, Paylane
**Subject:** Support assistant prototype: ready for your review

Hi,

I've built a support assistant using mock accounts and payments. Before connecting real customers, I'd like your team to review it.

It checks the customer's email and last four card digits before discussing their account. It can refund a full, settled purchase of $75 or less that's under 30 days old and hasn't been refunded before. The software checks those limits before allowing a refund.

Frozen cards, suspected fraud, legal complaints, account closure and requests for a person go to your team with a written note. Larger or older refunds and transfer reversals also need a person. It cannot unfreeze cards, pull back transfers, reveal private account details or promise arrival dates or response times.

If a refund request times out, it checks the payment without trying again. If the result is still unclear, it records that uncertainty for your team rather than claiming success or failure.

I've tested 12 customer scenarios, including identity guessing and split-refund pressure. It still needs testing against your real systems before launch.

Could you confirm:

- Who receives handoffs, and what response times may we give customers?
- Which freeze reasons may we share, and how does your system distinguish purchases from transfers?
- How should we verify logged-in customers and reconcile uncertain refunds?
- Can you share 50–100 past chats with personal details removed for testing?

I'd start with your team approving refunds, then review the results before enabling automatic refunds. That approval step still needs to be built.

Thanks,
Soham
