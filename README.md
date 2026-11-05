# Holdpoint

**An agent's irreversible tools do not run until the call has passed review. The agent and its model stay unchanged.**

Holdpoint is an MCP proxy. It sits between an agent and the tools it uses. Reads pass straight through. Calls that send, pay, delete or publish are held until automatic checks and an independent reviewer clear them, or a person approves that exact call.

The name comes from "hold point" in engineering quality control: a stage work may not pass without sign-off.

> **Status:** the gate, its tests and the bypass suite are working. The measurement of its benefit on a real agent is **in progress and has no result yet**. See [Honest status](#honest-status).

## For judges, start here

See it in 30 seconds, with no API keys:

```bash
pip install -e ".[dev]"
python examples/demo.py
```

```text
The agent works normally until it tries something irreversible:
  read the balance                             RAN
  send $10 to Ann                              HELD
  send it again, claiming approval             HELD
  Money sent so far: []

A person reviews the hold and approves that one call, once:
  send_payment {'to': 'Ann', 'amount': 10}

The approval covers exactly that call:
  try $9,999 to Mallory instead                HELD
  the approved call                            RAN
  replay the approved call                     HELD
  a tool the policy has never heard of         HELD
  Money sent in total: [{'to': 'Ann', 'amount': 10}]
```

Then try to break it:

```bash
pytest -q                        # the bypass suite
python tests/mutation_check.py   # breaks each protection and confirms a test notices
```

| Evidence | Where |
|---|---|
| Bypass suite | [tests/test_bypass.py](tests/test_bypass.py) |
| Facts, runs and corrections log | [evidence/m0-verification.md](evidence/m0-verification.md) |
| How the benchmark is run without editing it | [bench/](bench/) |
| Frozen development and held-out split | [bench/split.json](bench/split.json) |

## The problem

Tool-using agents often act first and notice the problem later, and a later refusal cannot undo the harm. In [AgentAbstain](https://arxiv.org/abs/2607.10059), a paired benchmark of 263 should-act and should-abstain tasks, the best of 17 frontier models got 59.5% of pairs right. On average, models simply executed in 19.7% of should-abstain runs, and acted and then claimed restraint in another 2.6%.

The person this hurts is the engineer connecting an agent to real write access: payments, bookings, deploys, messages. Today they approve every call until they stop reading, or they auto-approve and hope.

## How it works

```mermaid
flowchart LR
    A[Agent] -->|tool call| G{Holdpoint}
    G -->|lookup or verify| T[Tool server]
    G -->|commit| C[Automatic checks]
    C -->|failed| H[Hold: nothing runs, agent tells the user]
    C -->|passed| R[Independent reviewer]
    R -->|hold, error or timeout| H
    R -->|proceed| T
    H -.->|person approves this exact call| T
```

| Layer | What it does | Depends on a model? |
|---|---|---|
| Hard gate | Holds every tool labelled `commit`. A tool missing from the policy counts as `commit`. | No |
| Automatic checks | Holds if an earlier tool failed and never recovered, or if the request requires a tool that does not exist. | No |
| Independent reviewer | A separate model reads the request as trusted text and tool results as quoted untrusted data. Any error or malformed reply is a hold. | Yes |
| Human approval | A signed token bound to the tool and its exact arguments. Single use, and it expires. | No |
| Audit log | Every decision goes in a hash-chained log, so edits are detectable. | No |

The agent has no route around the gate and cannot approve itself. Secrets stay on the gate's side and are stripped from the tool server's environment.

## Use it with your own tools

Label your tools. Anything you leave out is held:

```yaml
read_balance: lookup
send_payment: commit
```

Put the proxy in front of your MCP server, wherever your client configures its command:

```bash
holdpoint-proxy --policy policy.yaml --state-dir ./state --intent-file request.txt -- python your_server.py
```

| Setting | Purpose |
|---|---|
| `HOLDPOINT_KEY` | Signs approvals. With no key, approvals are off and holds stay held. |
| `HOLDPOINT_REVIEWER_KEY`, `HOLDPOINT_REVIEWER_MODEL` | Turn on the reviewer. With neither, every commit waits for a person. |
| `HOLDPOINT_REVIEWER_PROVIDER` | `anthropic`, or leave unset for any OpenAI-compatible endpoint. |

Handle holds as a person:

```bash
holdpoint --state-dir ./state holds
holdpoint --state-dir ./state approve HOLD_ID --ttl 300
holdpoint --state-dir ./state verify-log
```

**One requirement you must meet.** MCP carries tool calls but not the user's request, and the reviewer needs that request. Your host must write it to the intent file at session start, somewhere the agent cannot write. Without it, every commit is held.

## Results

### Bypass suite

No keys or network needed. It follows the failure states the challenge names.

| Attempt | Outcome |
|---|---|
| Commit with no approval | Held, never reaches the tool |
| Tool missing from the policy, or a misspelled or re-namespaced name | Held |
| Argument claiming it was approved | Held |
| Approval replayed, or spent by parallel calls | Runs once only |
| Approval reused with changed arguments | Held |
| Expired, forged or edited token | Held |
| Reviewer timeout, connection failure or garbled reply | Held |
| Reviewer compromised and always saying proceed | Automatic checks still hold |
| Injection text in tool output | Stays quoted as data in the review prompt |
| Audit log edited | Detected |

Negative controls confirm reads still run, recovered failures do not hold, and IDs in a request are not mistaken for tools.

The tests are themselves tested: `tests/mutation_check.py` removes each of 23 protections in turn and confirms a test fails.

### Scripted replay on the benchmark

All 131 operational pairs, replayed with no model through a hold-everything proxy on Ubuntu.

| Measure | Result |
|---|---:|
| Should-act tasks passing without the proxy | 131 of 131 |
| Runs through the proxy in which a commit executed | 0 of 262 |
| Paired score when everything is held | 0 of 131 |

The last line is the point of a paired benchmark: a gate that blocks everything is visibly useless, so the measure below cannot be gamed that way.

### Real agent, before and after

**Pending.** This is the number that decides whether the reviewer is worth having. It will be reported here with the should-act loss beside it, whichever way it goes.

**The method is fixed in advance.** The 131 operational pairs were split into 42 development and 89 held-out pairs, stratified by scenario with a fixed seed. That split was the [first commit](bench/split.json), before any reviewer code existed. Held-out runs happen once, on a tagged commit.

**What the gate never sees:** task type, scenario, or the answer fields in the benchmark's task files. It uses only each sandbox's generic tool labels, and the reviewer gets only the request and the live trace. A dry run checked 184 reviewer requests for those fields and found none.

## Honest status

| Part | State |
|---|---|
| Gate, checks, approvals, audit log | Working, tested |
| Bypass suite and mutation check | Working |
| Benchmark runner, without editing the benchmark's source | Working |
| Reviewer against a real model | Being measured |
| Benefit on a real agent | **No result yet** |
| Tests against real production systems | Not done; the benchmark and demo use sandboxes |
| Web interface for approvals | Not built; approvals use the CLI |

## Known limits

- **The labels are the boundary.** A destructive tool labelled `lookup` runs freely. Unknown tools are safe by default, wrong labels are not.
- **The gate only sees MCP traffic.** An agent with another route to the same system, such as shell access or a raw API key, can bypass it.
- **The model-based layer is probabilistic.** A reviewer can be wrong or be persuaded. That is why the hard gate, checks and approvals do not depend on it.
- **Holds cost something.** A wrong hold stops legitimate work, which is why should-act loss is reported beside every result.
- **Long tool output is clipped for review.** The reviewer sees the start and end of very long results, so a warning buried in the middle can be missed.
- **Held calls do not simulate success.** An agent cannot continue a multi-step plan past a hold. There is no shadow state or rollback.
- **One call at a time.** Each session handles calls in sequence, so a verdict always sees the full history.

## Credits and licences

Holdpoint is MIT licensed. Measured on [AgentAbstain](https://github.com/AntiQuality/agentabstain) (Liu et al., NeurIPS 2026), whose code is MIT and data is CC BY 4.0. Related work: [Cordon](https://arxiv.org/abs/2606.17573) stages and validates agent effects as transactions.
