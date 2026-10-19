# How it works, in pictures

Plain-language flow diagrams of the Paylane support bot. For the full technical write-up, see [REPORT.md](REPORT.md).

## 1. The pieces

The model chooses what to say and which tools to request. Code checks identity, transaction ownership and refund eligibility. Recognising fraud and legal intent still depends on the model, which is why the conversations matter.

```mermaid
flowchart LR
    C["Customer<br/>types in the chat"] --> B["Claude, the brain<br/>follows the rulebook"]
    B --> G["Guard<br/>checks every action<br/>against the rules in code"]
    G --> K["Pretend bank<br/>fake customers and payments"]
    K --> G
    G --> B
    B --> F["Final reply only<br/>filter hides emails and card numbers"]
    F --> C
```

| Piece | What it does | File |
|---|---|---|
| Rulebook | The bot's instructions, in plain English | `paylane/rulebook.md` |
| Claude, the brain | Reads the chat, decides what to say and which button to press | `paylane/agent.py` |
| Guard | Checks every button press before it reaches the bank, and blocks anything the rules forbid | `paylane/tools.py` |
| Rules in code | The money rules: $75, 30 days, purchases only, frozen cards | `paylane/policy.py` |
| Pretend bank | Answers the 4 buttons from Paylane's brief with fake data | `paylane/mock_api.py`, `paylane/data.py` |
| Safety filter | Last check on every reply: hides emails and card numbers | `paylane/redact.py` |

## 2. One message, start to finish

```mermaid
flowchart TD
    A["Customer sends a message"] --> B["Claude reads it,<br/>with the rulebook"]
    B --> C{"Does Claude need to<br/>press a button?"}
    C -- "No, just answer" --> F["Safety filter hides any<br/>email or card number"]
    F --> R["Customer sees the reply"]
    C -- "Yes" --> G{"Guard: do the rules<br/>allow it?"}
    G -- "No" --> X["Blocked, and logged<br/>as a mistake"]
    X --> B
    G -- "Yes" --> K["Pretend bank does it<br/>and answers"]
    K --> B
```

The 4 buttons Claude can press:

| Button | Plain meaning |
|---|---|
| `get_customer` | "Do this email and these last 4 card digits match?" |
| `get_transaction` | "Show me this payment, and may I refund it?" |
| `issue_refund` | "Give this money back." |
| `escalate_to_human` | "Open a ticket for a person on the support team." |

## 3. Can the bot refund this?

Every refund request walks down this path, top to bottom. Orange means a person takes over: a ticket is opened with a note, so the customer never has to explain twice. Green is the only way money moves. Gray means the bot explains why not.

```mermaid
flowchart TD
    S["Customer asks for a refund"] --> V{"Email and last 4<br/>digits match?"}
    V -- "No" --> V2{"Third wrong try?"}
    V2 -- "No" --> TRY["Ask them to try again"]
    V2 -- "Yes" --> P1["Lock the chat,<br/>hand to a person"]
    V -- "Yes" --> D{"Customer says they<br/>didn't make the charge?"}
    D -- "Yes" --> P2["Hand to a person,<br/>urgent if over $500 total"]
    D -- "No" --> FR{"Card frozen?"}
    FR -- "Yes" --> P3["Hand to a person"]
    FR -- "No" --> T{"Is it a purchase?"}
    T -- "No, money sent<br/>to a person" --> P4["Hand to a person.<br/>Never suggest it<br/>can be pulled back"]
    T -- "Yes" --> ST{"Payment status?"}
    ST -- "Pending" --> N1["Explain: ask again<br/>once it settles"]
    ST -- "Already refunded" --> N2["Explain: a refund<br/>never happens twice"]
    ST -- "Settled" --> L{"$75 or less, and<br/>under 30 days old?"}
    L -- "No" --> P5["Hand to a person"]
    L -- "Yes" --> R["Refund the full amount, once"]

    classDef person fill:#fff1dc,stroke:#c77800,color:#5a3600
    classDef money fill:#e3f6e8,stroke:#2b8a3e,color:#14451f
    classDef explain fill:#f1f1f1,stroke:#888888,color:#333333
    class P1,P2,P3,P4,P5 person
    class R money
    class TRY,N1,N2 explain
```

## 4. When the refund button goes wrong

```mermaid
flowchart TD
    R["Bot presses refund, once"] --> A{"What did the bank say?"}
    A -- "Done" --> OK["Tell the customer, with<br/>the refund reference"]
    A -- "Declined" --> NO["Say it couldn't be completed.<br/>Hand to a person"]
    A -- "No answer" --> CHK{"Look the payment up:<br/>shows refunded?"}
    CHK -- "Yes" --> CONF["Confirm refunded status.<br/>Do not invent the missing reference"]
    CHK -- "No" --> UNK["Say we couldn't confirm it.<br/>A person checks if money moved.<br/>Never try again"]

    classDef person fill:#fff1dc,stroke:#c77800,color:#5a3600
    classDef money fill:#e3f6e8,stroke:#2b8a3e,color:#14451f
    class NO,UNK person
    class OK,CONF money
```

Pressing refund twice could pay the customer twice, so the bot never does. When the bank doesn't answer and the payment doesn't show as refunded, that still doesn't prove nothing happened, so a person checks.

## 5. Always handed to a person

```mermaid
flowchart LR
    subgraph NOID["No identity check needed"]
        L1["Lawyers or legal threats"]
        L2["Closing an account"]
        L3["Asking for a person"]
        L4["Asking to skip the check,<br/>or claiming to be staff"]
    end
    subgraph ID["After the identity check"]
        I1["Charges they didn't make,<br/>urgent if over $500 in total"]
        I2["Frozen card"]
        I3["Over $75, or 30 days or older"]
        I4["Money sent to another person"]
        I5["A refund that failed or<br/>never arrived"]
    end
    NOID --> P["Ticket for a person.<br/>The bot takes no more<br/>action on that issue"]
    ID --> P
```

## 6. How we tested it and fixed it

```mermaid
flowchart LR
    W["Write 12 tricky chats<br/>where the customer pushes back"] --> RUN["Run each with the real AI,<br/>3 times"]
    RUN --> CHK["Automatic checker:<br/>7 pass or fail checks"]
    CHK --> READ["Read every chat<br/>ourselves too"]
    READ --> Q{"Any mistake?"}
    Q -- "Yes" --> FIX["Fix the rule or the code,<br/>and add a check so it<br/>can't come back"]
    FIX --> RUN
    Q -- "No" --> DONE["Record the score<br/>and remaining limits"]
```

The 7 checks ask: did the bot try anything the guard blocked, leak a card number or email, say a red-line phrase, promise something it can't, ramble or use filler, get the wrong outcome, or skip a step it should have taken?

The original diagram describes the development loop, not proof that the agent always follows policy. The 18 October perfect score became 10/12 when the 19 October review added checks for mistakes the old grader missed. See [REPORT.md](REPORT.md#results) for current results and the preserved history.

On top of the 12 chats: 107 deterministic tests and four extra model cases covering unknown timeouts, explicit declines, increased fraud loss after handoff and a timeout confirmed by read-back. Detailed real-launch questions are in [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md).
