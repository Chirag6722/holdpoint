# Stage 1 — How we get judged

Event: Drawerrr AI Safety Challenge, brief "Prevent irreversible AI autonomous actions"
https://www.drawerrr.com/challenge/ai-safety-and-control/prevent-irreversible-autonomous-actions

Labels: [Verified] read from the official page on 4 Nov 2026 · [To verify] confirm before code depends on it · [Assumption] our choice.

Team: one person. Time: 4 Nov → 15 Nov 2026 = 11 days.

## 1. Rubric → what we must SHOW

| Criterion | Weight | What judges look for | What we must SHOW for full marks |
|---|---|---|---|
| Safety effectiveness | 35% | "Does the safeguard reliably prevent the targeted unauthorized or harmful action?" | One named irreversible action, blocked every time. A results table: N attack runs, 0 irreversible actions executed, with the agent still completing the safe variants (no "block everything" cheat). A 30 s clip of the block happening live. |
| Testing and robustness | 25% | "tested against realistic failure scenarios and bypass attempts" | A test suite judges can run in one command. Scenarios the page itself lists: ambiguous instructions, missing info, prompt injection, unauthorized requests, edge cases, approval bypass, expired approvals, malformed tool arguments, timeouts. A held-out set plus negative controls (should-act cases that must NOT be blocked). Pass/fail table generated from a real run. |
| Real-world relevance | 20% | "Is the problem meaningful, and does the safeguard address it?" | A named persona with a frequent pain, a real-shaped environment (mock API of a real system), a one-line claim a test can check. Cite the AgentAbstain paper's own numbers (59.5% best paired accuracy). Do not quote the page's 40.5%, which is not stated in the paper (see STAGE2-PROBLEM.md). |
| Reproducibility and reuse | 15% | "Can another team understand, test, or adapt the solution?" | Public repo, one-command setup/run/test, README quick start, pinned deps, CI badge, a "adapt it to your tool" section showing a second environment in <20 lines. |
| Clarity of communication | 5% | "implementation, evidence, and limitations clearly presented" | README order: pitch → why it matters (4 numbers) → for judges start here → results table → how it works → known limits → honest status. Short video optional but cheap with our pipeline. |

[Verified] Weights and wording copied exactly from the FAQ on 4 Nov 2026.

Reading of the weights: 60% of marks are "did it stop the bad action" + "did you try to break it". UI and video are not scored lines here (unlike neatHack). They still matter because the single submission link is the judge's first 10 seconds, but the budget goes to the safeguard and the attack suite, not to polish.

## 2. Compliance checklist

| # | Requirement [source] | How we meet it | Evidence | Owner-only action |
|---|---|---|---|---|
| 1 | Deadline: submit by 15 Nov 2026 [Verified, FAQ 8]. Time of day and timezone not stated [To verify, ask in Discord]. | Code freeze 13 Nov, submit 14 Nov. | Submission confirmation screenshot in `evidence/` | Submit the form |
| 2 | Form fields: Name*, Email*, School/uni affiliation (optional), Link* [Verified, submit page]. ONE link only. | The link is the GitHub repo README (or landing page) with "For judges, start here" at the top. Everything else is one click from it. | README | Fill and submit the form |
| 3 | Can resubmit; each submit is a new record [Verified, FAQ 11]. | Submit an early version on ~10 Nov, final on 14 Nov. | Two confirmations | Submit twice |
| 4 | Must "address preventing AI agents from taking unauthorized or harmful irreversible actions. Explain the problem, how your approach works, and how it helps" [Verified, FAQ 4]. | README sections: Problem, How it works, What it prevents. | README | — |
| 5 | Suggested contents: overview, motivation, technical explanation, demo, testing and results, reproducibility materials, known limitations [Verified, FAQ 6]. | One README section per item, same order. | README | — |
| 6 | "Be transparent about what is implemented, what is tested, and what remains theoretical" [Verified, FAQ 6]. | A status table: working today / tested / not built. | README "Honest status" | — |
| 7 | Remove credentials, personal data, security-sensitive details from shared code [Verified, FAQ 7]. | `.env.example` only, secret scan in CI, no real API keys. | CI log | Check before pushing |
| 8 | Confirm rights to any employer/third-party content [Verified, FAQ 7, 12]. | Only own code + permissively licensed deps; licence list in README. | README "Licences" | — |
| 9 | Student cash prize needs university or high-school student eligibility [Verified, FAQ 2, 9]. | Fill the affiliation field. | Form | Fill affiliation [To verify: proof required?] |
| 10 | Open-sourcing not required [Verified, FAQ 7]. | We open-source anyway: it is the cheapest way to score Reproducibility 15%. | Public repo | Make repo public |
| 11 | IP: we keep ownership; Drawerrr gets display/evaluation licence [Verified, FAQ 12]. | Nothing to do. | — | — |
| 12 | Suggested 5-day method: identify scenario → test env → safeguard stack → document failure states → make reproducible [Verified, "Master the challenge"]. | Our plan follows exactly these five steps so the judges' own checklist maps to our README headings. | README | — |
| 13 | Failure states the organisers name: ambiguous instructions, missing info, prompt injection, unauthorized requests, edge cases, approval bypass, expired approvals, malformed tool args, timeouts [Verified, Day 4]. | One test per item, listed by the same names. | `tests/`, results table | — |
| 14 | Winners announced 30 Nov 2026 [Verified, FAQ 8]. | Keep repo frozen until then. | — | — |
| 15 | Discord for rule changes and expert questions [Verified]: https://discord.gg/yWKtf8usH | Re-read daily; ask deadline timezone and student-proof question on day 1. | `docs/QUESTIONS.md` | Join Discord, ask |
| 16 | Submissions open to professionals and students [Verified]. | — | — | — |

## 3. Hidden expectations

No sponsor tools are mandated, so "sponsor-native" here means speaking the organisers' and jury's own language:

1. **The cited benchmark.** The headline stat on the page comes from AgentAbstain (arXiv 2607.10059, 11 Jul 2026, CC BY 4.0): 263 paired should-act / should-abstain tasks in 42 sandbox environments, 8 abstention scenarios, best agent 59.5% paired accuracy, failure mode "post-hoc abstention" (irreversible action executed before the agent notices). Code (MIT) and data (CC BY 4.0) are public at agentabstain.github.io [Verified 4 Nov 2026]. Whether the sandboxes run on Windows is still [To verify]. Running our safeguard on a slice of THEIR benchmark and reporting before/after paired accuracy is the strongest possible evidence for Safety effectiveness 35% and the closest thing to a "causal record" this event offers.
2. **Google SAIF** is linked on four of the five days (Agent Risk Self-Assessment, Agent Permissions, Security Controls, Red Teaming). Map our controls to SAIF names in a short table [To verify: current SAIF agent page].
3. **Guardrails AI and LangGraph** are the two named tools. Using LangGraph's interrupt/human-in-the-loop natively, or shipping a Guardrails AI validator, counts as "used the recommended tool as designed". Not mandatory. Decide in Stage 3.
4. **Jury profile** (8 announced, more coming): 3 offensive-security people (Amazon, Opera, TryHackMe), 1 IBM agent-monitoring researcher (Granite Guardian / agentic guardrail papers), 1 governance specialist (UCL), 3 applied AI engineers (Meta, Microsoft, Sybilion). Translation: they will try to bypass it in their heads, they expect a monitor/guardrail vocabulary, and one of them will look for a governance mapping (NIST AI RMF and EU AI Office are in the page header).
5. **Award categories** [Verified]: best overall, delegated actions, physical-world, consequential decisions, information access, digital system changes, financial transactions. Top 10 recognised. Nominee tags on the category page: Best real-world use case, Strongest safeguard, Best human handoff, Most reusable approach. Pick one category and aim to be the obvious winner of it rather than a weak "overall".
6. **Submission types accepted**: agent, Skill, Bot, plugin, MCP, custom build, test harness, implementation, article/case study. An MCP-shaped or plugin-shaped deliverable scores Reuse without extra work.
7. **Tech partner on the category page: Exa.ai** (credits for winner and finalists) [Verified]. No run-time role required; ignore unless it fits naturally.
8. **The usual**: public repo, CI green, one-command run, honest limits, a short video (not required, "a demo helps").

## 4. Past winners

- This is the first edition of this brief: the Winners section shows placeholders ("Project name", "Author's names") [Verified 4 Nov 2026]. Other Drawerrr AI briefs are all "Coming soon". There are no prior winners to copy.
- What to study instead:
  - AgentAbstain repo and task format (the organisers' own evidence standard).
  - The IBM juror's agentic guardrail paper (arXiv 2510.09781, ICLR 2026) for vocabulary: pre-execution risk, tool-call guardrail, monitoring.
  - The playbook's proven README and video structure (Beacon): "For judges, start here", 4 numbers, results table, one-command run.
- Re-check the Winners section and Discord weekly for shortlisted entries from other participants.

## 5. Open questions (carried to docs/QUESTIONS.md)

| Question | Default assumption |
|---|---|
| Deadline time and timezone? | Treat as 15 Nov 2026 00:00 UTC; submit 14 Nov. |
| Does the student prize need proof of enrolment? | Fill affiliation truthfully; no proof upload exists on the form. |
| AgentAbstain local runnability on Windows? | Licence settled (MIT, CC BY 4.0). Smoke test in Milestone 0. |
| Is a single link enough or do they read the repo? | Assume the link is all they see first; README must sell in 10 seconds. |
