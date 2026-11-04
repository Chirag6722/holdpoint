# Stage 3 — Tech stack

Labels: [Verified] read or parsed on 4 Nov 2026 · [To verify] confirm before code depends on it · [Assumption] our choice or estimate.

Facts and open items are in `evidence/m0-verification.md`.

## 1. What is forced

- **Python 3.11.** The benchmark is Python and speaks MCP over stdio. [Verified]
- **Google ADK or OpenAI SDK harness.** The other two hardcode `/tmp`, and OpenClaw also needs a pinned CLI. [Verified]
- **GPT-5.4 judge, unchanged.** Results must stay comparable, so we need an OpenAI-compatible key whatever else we pick. [Verified]

## 2. Options

Scores are 1–5, my judgement. Columns: you know it, cost, one command, runs locally, jury credit, reusable. I assume you know Python well.

| Layer | Option | Know | Cost | Cmd | Local | Jury | Reuse | Total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Gate | **Standalone stdio MCP proxy (FastMCP)** | 3 | 5 | 5 | 5 | 5 | 5 | **28** |
| Gate | Wrap `call_tool` inside the benchmark's server | 4 | 5 | 5 | 5 | 2 | 1 | 22 |
| Gate | LangGraph interrupts | 2 | 5 | 4 | 5 | 3 | 3 | 22 |
| Policy | **YAML file, unknown tools held by default** | 5 | 5 | 5 | 5 | 4 | 5 | **29** |
| Policy | Open Policy Agent or Cedar | 2 | 5 | 3 | 4 | 4 | 4 | 22 |
| Reviewer | **Plain OpenAI-compatible call, JSON schema reply** | 5 | 4 | 5 | 4 | 4 | 5 | **27** |
| Reviewer | Guardrails AI validators | 2 | 4 | 4 | 4 | 4 | 3 | 21 |
| Approval | **Standard-library HMAC token and CLI prompt** | 5 | 5 | 5 | 5 | 4 | 5 | **29** |
| Approval | Web approval app | 3 | 4 | 3 | 4 | 3 | 3 | 20 |
| Audit log | **Append-only JSONL with hash chain** | 5 | 5 | 5 | 5 | 5 | 5 | **30** |
| Audit log | SQLite | 4 | 5 | 5 | 5 | 3 | 4 | 26 |
| Tests and CI | **pytest, ruff, GitHub Actions, scripted agent with no keys** | 5 | 5 | 5 | 5 | 5 | 5 | **30** |
| Results page | **Generated Markdown plus static GitHub Pages** | 5 | 5 | 5 | 5 | 4 | 5 | **29** |
| Results page | Vite and React dashboard | 3 | 5 | 4 | 5 | 3 | 4 | 24 |
| Video | **Playwright, ffmpeg, edge-tts (playbook pipeline)** | 4 | 5 | 4 | 5 | 2 | 5 | **25** |
| Video | Screen recording | 5 | 5 | 2 | 5 | 2 | 1 | 20 |

## 3. Recommended stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11 with a lock file | Forced, and the benchmark's requirements are unpinned. |
| Gate | Standalone MCP proxy | It is the reusable product: one config line in front of any MCP server. |
| Policy | YAML, fail closed | A tool with no label is held, so a missing entry cannot open a hole. |
| Reviewer | One HTTP call with a JSON schema reply | Smallest thing that works, and easy to swap models. |
| Approval | HMAC token bound to tool and arguments, single use, expiring | Standard library only, and directly testable against the failure states the organisers name. |
| Audit | Hash-chained JSONL | Tampering is detectable, and the jury's monitoring and governance members can read it. |
| Tests | pytest with a scripted agent and fake reviewer | Judges can run the whole bypass suite with no keys and no cost. |
| Results | Tables generated from saved run files | Numbers cannot drift from the evidence. |
| Video | Playbook pipeline, last | Not a scored line, so it only gets time left over. |

**Skipped:** a web UI, hosting, a database, Docker, and any agent framework. The rubric does not score them and each adds risk for one person. Add a hosted page only if there is spare time.

**Measurement models.** All [To verify] until a key exists.

| Role | Model | Reason |
|---|---|---|
| Agent, primary | Gemini 3 Flash | Largest gap on the published leaderboard (act 91.7, abstain 43.6), so the most for a gate to fix. Cheap. |
| Agent, optional second | Gemini 3.1 Pro | Shows the result on the top-ranked model. |
| Reviewer | GPT-5.4 mini | Different vendor from the agent. It is never the same model as the judge, and we disclose that both come from OpenAI. |
| Judge | `gpt-5.4-2026-03-05` | Unchanged from the benchmark. |

## 4. Design decisions the source reading forced

1. **The proxy cannot see the user's request.** MCP only carries tool calls, yet the reviewer needs the original instruction. The host must hand it over at session start, through a channel the agent cannot write to. In the benchmark that is a small harness patch. We publish the patch and document this as a requirement for real deployments.
2. **Labels are not visible over MCP.** `kind` lives in the environment classes. A script exports them to the policy YAML, reading only the class attribute and never a task file.
3. **The export tool must pass through for scoring.** It is a benchmark-only allowance, off by default in the product, and the bypass suite tests that it stays off.
4. **Holding every commit scores zero on the operational pairs,** because each act side needs its critical tools to fire. So a blanket block is visibly punished. This follows from the scorer's logic and will be confirmed in a run.

## 5. Cost estimate

**This is a model, not a measurement.** The inputs are my assumptions: 6 model calls per run, 4,000 input tokens per call, 300 output tokens per call, 1 judge call of 2,000 in and 300 out, 1.2 reviewer calls per gated run of 5,000 in and 200 out. The smoke test replaces these.

Prices per million tokens, input and output, from public pricing pages on 4 Nov 2026: Gemini 3 Flash $0.50 and $3.00, DeepSeek V4 Pro $0.90 and $1.50, Gemini 3.1 Pro $2.00 and $12.00, GPT-5.4 $2.50 and $15.00. GPT-5.4 mini is $0.75 and $4.50; the table prices the reviewer at the lower Gemini 3 Flash rate, and using mini adds roughly $0.50 per full gated pass.

| Agent model | Baseline, 131 pairs | Gated, 131 pairs | One tuning round, 40 pairs |
|---|---:|---:|---:|
| Gemini 3 Flash | $7.05 | $8.02 | $2.45 |
| DeepSeek V4 Pro | $8.86 | $9.83 | $3.00 |
| Gemini 3.1 Pro | $20.72 | $21.70 | $6.63 |

| Budget level | Covers | About |
|---|---|---:|
| Minimum | Gemini 3 Flash: baseline, gated, 5 tuning rounds | $30 |
| Comfortable | Minimum, plus held-out runs repeated 3 times | $60 |
| With second model | Comfortable, plus Gemini 3.1 Pro baseline and gated | $100 |

Google lists a free tier for Gemini 3 Flash, which could remove the agent cost. Its rate limits are unknown, and its data may be used to improve Google's products; benchmark tasks are synthetic, so that is acceptable here. The judge still needs a paid OpenAI-compatible key.

## 6. What needs your action

| Item | Why | Wait |
|---|---|---|
| Permission to install and run the benchmark | Blocked in this session; every remaining check needs it. | Now |
| OpenAI API key with credit | Judge and reviewer. | Possible organisation verification [To verify] |
| Google AI Studio key | Agent. | Usually immediate [To verify] |
| Join Discord and ask the open questions | Deadline timezone, student proof, 40.5% source. | Now |

Keys go in a local `.env` file that is never committed. Do not paste them in chat.

## 7. Spike, about 1–2 hours

| Step | Done when | Needs keys |
|---|---|---|
| 1. Install on Windows, fetch dataset | Imports succeed and `data/` is populated. | No |
| 2. Start the task server directly, list tools | Tool list matches the task's environment. | No |
| 3. Thin proxy in front of it, hold one commit tool | The call returns a hold and `execution_log` has no success entry, while a lookup still works. | No |
| 4. Run the unmodified scorer's commit check on that log | Abstain side passes the commit check, act side fails. | No |
| 5. One real pair, baseline | Both sides run and are judged. Tokens and cost recorded. | Yes |
| 6. Same pair through the proxy | Same model, reviewer on. Cost recorded. | Yes |

**If step 3 or 4 fails,** fall back to wrapping `call_tool` inside the server, which the benchmark's own dump hook already does. We lose the clean product shape but keep the measurement.

**If Windows fails at step 1,** use WSL or GitHub Codespaces, and report the bug upstream.
