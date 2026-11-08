# Threat model

Holdpoint stops an agent's irreversible MCP tool calls from running until they are cleared. This page says who it defends against, and who it does not.

## What is trusted

| Part | Trust | Why |
|---|---|---|
| The person approving | Trusted | They are the final authority |
| Policy file, signing key, state folder | Trusted, and must stay out of the agent's reach | They define and record the decisions |
| The user's request in the intent file | Trusted | The host writes it, somewhere the agent cannot |
| The agent | Not trusted | It may be mistaken or under an attacker's influence |
| Tool output | Not trusted | It may carry injected instructions |
| Tool definitions and annotations | Not trusted | A server can lie about itself or change later |
| The reviewer | Partly trusted | It is a model, so it can be wrong or be persuaded |

## Attacks it is built to stop

Each has a test in [tests/test_bypass.py](../tests/test_bypass.py).

| Attacker can | Attempt | Result |
|---|---|---|
| Control the agent | Call a commit tool with no approval | Held |
| Control the agent | Use an unknown, misspelled or re-namespaced tool name | Held |
| Control the agent | Claim approval in the arguments | Held |
| Control the agent | Change the arguments of an approved call | Held |
| Control the agent | Replay an approval, or spend it in parallel | Runs once only |
| Control the agent | Retry a held call until the reviewer says yes | Stays held; reviews are limited per tool |
| Control tool output | Inject instructions aimed at the reviewer | Quoted as data. 0 of 60 attacks flipped a correct hold, on a fixed list we wrote |
| Control tool output and read replies | Forge facts until the reviewer agrees | **Not stopped by the reviewer: 2 of 18 attempts won.** A tool labelled `person`, or a call caught by a hard rule, never reaches the reviewer |
| Control the agent | Split a large payment into small ones | A session total sends it to a person, if a rule is set |
| Control the agent | Send a malformed or missing amount | Counts as matching the rule, so it does not pass |
| Control the agent | Send a negative amount to lower a session total | Counted by size, so it does not open room |
| Control the agent | Write the same number another way, such as `100.0` for `100` | Treated as the same call |
| Control the agent | Hide a blocked value inside a list or object, or in another script | Patterns check every piece of text |
| Control the agent | Get a call approved while it waits, to pass a session cap | The approval goes back through the gate, so caps and records still apply |
| Control the agent | Repeat a call that already ran, such as a payment after a timeout | Needs a person |
| Control the agent | Keep retrying a tool that keeps failing | Needs a person after 3 failures |
| Reach the approval screen from another website | Post an approval to localhost, or use a rebinding DNS name | Refused without the secret link and a local host name |
| Control the tool server | Label a dangerous tool safe, while the server admits it is dangerous | Held |
| Control the tool server | Change a tool's definition after first use | Held until a person accepts it |
| Break the reviewer | Timeout, failure or malformed reply | Held |
| Compromise the reviewer | Always answer proceed | Automatic checks still apply, but other wrong calls would run |
| Write to the log, without the key | Edit, cut short or rewrite it | Detected |
| Write to the state folder, without the key | Edit a hold before approval, or forge a token | Refused |

## What it does not stop

- **A route around MCP.** An agent with shell access or a raw API key can reach the system directly. Remove that route.
- **A wrong label.** A destructive tool labelled `lookup` runs, unless its server admits it can change things.
- **A wrong "proceed" from the reviewer.** Each one runs a real call, and forged tool output can cause one. Label your highest-stakes tools `person`, or add hard rules.
- **A harmful call inside your rules.** Rules only cover what someone wrote down. A $40 payment to an allowed person can still be the wrong payment, and `label: auto` runs it with no second look.
- **Rules that need live facts.** A policy file is fixed, so "only this customer's orders" needs a list written for that session.
- **A leaked approval link.** Anyone on the machine with the link can approve calls, and it can appear in shell history or process output.
- **A person approving something harmful.** Approval binds the exact call, not good judgement.
- **A stolen signing key.** With it, an attacker can approve calls and rewrite the log.
- **A rollback of the whole state folder.** This goes unnoticed unless you pass a hash saved elsewhere to `verify-log --expect`.
- **A tool that was malicious when first seen.** Fingerprints only catch later changes.
- **Harm from allowed reads.** Reads pass straight through, so a read can still expose data to the agent.

## How far this was tested

The hard gate, signatures, log and fingerprints have no-key tests and a mutation check. `holdpoint prove` covers limits over every value of a call's arguments, for rules as written, and its model is tested against the real gate on random policies. The proof and tests do not show the rules are the right ones. The reviewer was measured on one model pair, once per task, and those numbers come from tag `heldout-v1`. Later fixes have tests but have not been measured on the benchmark. No outside party has audited this code, and it has not run against production systems.
