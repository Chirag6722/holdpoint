# Milestone 0 — fact verification

Date: 4 Nov 2026. Machine: Windows 11, Python 3.11.9, Node 22.23.2, no Docker, no GPU detected, no API keys in the environment.

Benchmark source read at the commit cloned on this date (shallow clone of `AntiQuality/agentabstain`, main). All checks below are static. **No benchmark code has been installed or run.**

## Confirmed by reading or parsing

| Fact | Result | How it was checked |
|---|---|---|
| Task rows | 526 (263 act, 263 abstain) | Parsed `tasks.jsonl` |
| Operational pairs | 131 | Same |
| Informational pairs | 132 | Same |
| Operational pairs with commit tools on both sides | 131 | Same |
| Informational pairs with a commit tool on the abstain side only | 31 | Same |
| Informational pairs with no commit tool | 101 | Same |
| Tools labelled | 541: 246 lookup, 119 verify, 176 commit. Matches the project site. | `ast` parse of 42 `environment.py` files, not executed |
| Critical-tool references labelled `commit` | 378 of 378 | Cross-check of the two above |
| Environment files with no label block | 0 | Same |
| Code and data licences | MIT, CC BY 4.0 | Repo README |
| Scoring reads only successful calls in `execution_log` | Yes | `eval/evaluators/commit_check.py` |
| Answer-bearing fields sit in `task.yaml` | Yes: `critical_actions`, `abstention_trigger`, `abstain_escalated_tool` | Sample task. The gate must never read them. |
| OpenClaw and Claude SDK harnesses hardcode `/tmp` | Yes | Grep of `src/runtime/`. Avoid on Windows. |
| OpenAI SDK and Google ADK harnesses launch the server through `build_runtime_server_args` | Confirmed for both | Read `openaisdk.py`, `googleadk.py` |
| Requirements are unpinned | Yes | `requirements.txt`. We must publish a lock file. |

**Correction.** A first version of the label parser handled only plain assignments, reported 362 tools, and showed 130 critical references as unlabelled. That was my parser's bug. Handling annotated assignments gave the figures above, which match the published counts.

**Risky-call scan of all 127 dataset `.py` files.** Pattern search for `subprocess`, `socket`, `urllib`, `requests`, `httpx`, `ctypes`, `pickle`, `os.system`, `os.popen`, `os.remove`, `os.environ`, `eval(`, `exec(`, `__import__`, `open(`, `shutil.rmtree`. The four hits were three uses of the word "requests" in docstrings or sample text and one inline `__import__('datetime')`. A pattern search is not a security review. I did not read those files in full, or the installed packages.

## Not yet verified

| Item | Needs | Blocks |
|---|---|---|
| Install succeeds on Windows | Running pip | Everything below |
| Dataset loads and sandbox mounts | Running the server | Spike |
| Held call never reaches `execution_log` through a proxy | Running the server | Core design |
| FastMCP proxy forwards schemas and the export tool | Running the server | Core design |
| One real pair runs and scores end to end | OpenAI key plus an agent key | Measured cost |
| `gemini-3-flash-preview` is still served | Google key | Model choice |
| `gpt-5.4-2026-03-05` judge is still served | OpenAI key | Comparability |
| Gemini free-tier rate limits are workable | Google key | Budget |
| Cordon's full evaluation does not already report paired results | Reading the paper | Our claim |
