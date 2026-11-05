# Stage 2 — Choose the problem

Decision by owner, 4 Nov 2026: take the high-risk, high-reward option.

Labels: [Verified] read from the source on 4 Nov 2026 · [To verify] confirm before code depends on it · [Assumption] our choice or estimate.

## 1. What the research changed

| Finding | Status | Consequence |
|---|---|---|
| AgentAbstain code is MIT, data is CC BY 4.0, 263 pairs and 42 MCP sandboxes download from Hugging Face. | [Verified] repo README | We can build on it and redistribute with credit. |
| The generator is not public, so nobody outside the authors can create fresh tasks. | [Verified] repo README | We must make our own held-out split. |
| Abstain failures split into implicit 17.8%, no abstention 19.7%, post-hoc 2.6%. | [Verified] paper | Post-hoc alone is too rare to be the pitch. Target every committed failure. |
| The challenge page says agents "continued acting in 40.5%". That figure is not stated in the paper; the only match I found is an unrelated table cell. 100 minus 59.5 gives 40.5, so it may come from the best model's paired accuracy. | [To verify] with organisers | Do not quote 40.5%. Quote the paper's own numbers. |
| Corrected in Stage 3 after parsing all 526 task rows. 131 operational pairs have commit tools on both sides. 31 informational pairs have one on the abstain side only. 101 informational pairs have none. | [Verified] `tasks.jsonl` | The gate can affect 162 pairs and cannot affect 101. The headline stays the 131 operational pairs, with the 31 reported separately. |
| No per-model operational baseline is published, only a scatter figure. | [Verified] paper F.6 | We must run our own baseline. We cannot compare against the 59.5% leaderboard figure, which covers all 263 pairs. |
| The commit check reads only tool calls that succeeded in `execution_log`. Each sandbox labels its tools `lookup`, `verify` or `commit`. | [Verified] `commit_check.py`, `runtime/base.py` | A gate can use the generic label, without reading any task's answer, and the scorer stays unmodified. |
| The approval-gateway idea is crowded: Microsoft Agent Governance Toolkit, Edictum, Agent Wall, and OpenAI Agents SDK `needs_approval`. Cordon (arXiv 2606.17573) already does semantic transactions. | [Verified] search excerpts and abstract | "We built a gate" wins nothing. Measurement on the organisers' benchmark is the difference. |
| The repo has 22 stars and 1 fork. I found no published defence result on this benchmark. | [Assumption] absence not proven | Possibly the first. Say "we found none", never "the first". |

## 2. Scores (1–5, my judgement)

| Idea | Rubric fit | Real user | Originality | Organiser fit | Gives back | Verifiable | Wow | Feasible solo | Total | Main risk |
|---|---|---|---|---|---|---|---:|---:|---:|---|
| **A. Commit gate with independent reviewer, measured on AgentAbstain** | 5 | 4 | 4 | 5 | 4 | 5 | 5 | 2 | **34** | The reviewer may hold too many should-act tasks and show no net gain. |
| E. Bypass test suite comparing existing open-source gates | 4 | 3 | 3 | 3 | 3 | 5 | 3 | 4 | 28 | It tests safeguards without offering one, so it is weak on the 35% line. |
| C. Full transactional shadow state | 5 | 4 | 2 | 3 | 2 | 4 | 3 | 2 | 25 | Cordon got there first, and it is heavy for 11 days. |
| B. Approval gateway on a mock refund API | 4 | 5 | 1 | 3 | 1 | 3 | 2 | 5 | 24 | Looks like many other entries. This is the safe option. |
| D. Safety envelope for a simulated robot or drone | 3 | 2 | 4 | 2 | 1 | 3 | 4 | 2 | 21 | Simulation realism is easy to dispute, and it has no shared benchmark. |

## 3. The pick: Holdpoint

The working name comes from "hold point" in construction and refinery quality control: work may not pass the point without sign-off. [To verify: name collisions]

**Pitch.** The agent keeps its model and prompt, but its irreversible tools no longer fire until a separate reviewer has read the whole run.

**Person.** A platform engineer connecting an agent to an MCP server with real write tools such as payments, bookings, deploys or messages. Today they either approve every call and tire of it, or auto-approve and hope.

**How it works.**

1. **Hard gate, deterministic.** An MCP proxy sits between agent and server. Any tool labelled `commit` is held. The agent has no path around it and cannot approve itself.
2. **Run checks, deterministic.** Hold if a tool in the trace failed and never recovered. Hold if the instruction requires a tool that is not in the inventory.
3. **Independent reviewer, model-based.** A separate model reads the user's instruction as trusted text and tool results as quoted untrusted data, then returns a structured verdict on the proposed call. It never sees the task type or scenario.
4. **Bound approval.** A human approval token is tied to a hash of tool and arguments. It is single-use and expires.
5. **Hold message.** The agent receives the reason and must report it to the user. The unmodified judge then scores what the agent says.

**Narrower, checkable claim against known tools.** Policy gates decide from rules or per-tool flags. Holdpoint reports a before-and-after on paired should-act and should-abstain tasks, so a gate that simply blocks everything visibly fails. None of the sources I read reports this. [To verify: read Cordon's full evaluation before making the claim]

**Two numbers to show.**

- Operational paired accuracy on a held-out split, baseline against gated, same model, unmodified scorer. Act-side loss is reported beside it.
- Successful commits without approval across our bypass suite. This must be zero, since the gate is deterministic.

No result exists yet. Both numbers are empty until a real run fills them.

**30-second demo.** The $500-to-everyone Venmo task from the paper. Without the gate, the agent pays. With the gate, the same agent holds and states the total. Then the should-act twin goes through untouched. This depends on reproducing the behaviour in our runs, and we show the actual result.

**Award target.** Best overall, with "delegated actions" as the category fit, since the benchmark covers banking, email, bookings and messaging.

## 4. Integrity rules

The jury is security-heavy and will look for these.

- The gate uses only each sandbox's generic tool labels. It never reads task type, scenario, the `metadata` files, or the answer-bearing fields in `task.yaml` (`critical_actions`, `abstention_trigger`, `abstain_escalated_tool`). The reviewer receives only the instruction text and the live trace.
- The scorer and tasks are unmodified. We add a proxy only, and publish the diff.
- The 131 operational pairs are split, stratified by scenario, with a fixed seed: 42 for development and 89 held out (rounding per scenario moved this from the planned 40 and 91). The split is committed before any reviewer code exists.
- The held-out split runs once, on a tagged commit. Any later rerun is reported as one.
- Every number comes from a saved run with its model IDs and commit hash. Failed runs are kept.

## 5. Risks and the stop rule

| Risk | Mitigation |
|---|---|
| Reviewer over-holds and act accuracy collapses. | The stop rule below, plus always reporting both sides. |
| Agent and judge API costs. No keys are set on this machine. The README quotes "a few cents" for one smoke pair on a cheap model. | Measure the cost in the spike. Run one cheap model first. |
| The repo may not run on Windows, and Docker is not installed. | Smoke test first, before any design work continues. |
| Our reviewer overfits the benchmark's style. | The held-out split, plus our own bypass suite outside the benchmark. |
| The reviewer itself gets prompt-injected. | The deterministic layers do not depend on it. Injection attempts join the bypass suite. A successful attack is reported as a limit. |
| Benchmark tasks look unlike production. | Add one realistic second environment in the reuse demo. |

**Stop rule, 8 Nov 2026, measured on the development split.** If paired accuracy gains under 5 points, or act accuracy drops over 10 points, stop tuning the reviewer. Submit the deterministic gate, the bypass suite and the measured negative result. That still scores on Testing and on Clarity, and it is honest. [Assumption: thresholds are ours]

## 6. Out of scope

- The 101 informational pairs with no commit tool, which a gate cannot affect.
- Shadow state and rollback. A held call simply does not run.
- Physical-world actions.
- A hosted service or an accounts system.
- Fine-tuning any model.
- Claims against the 59.5% leaderboard figure, unless all 263 pairs are run under the same conditions.

## 7. Giving back

- Report any bugs found running the benchmark, especially on Windows, with small tested pull requests upstream.
- Ask the organisers politely in Discord where the 40.5% comes from.
