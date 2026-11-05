# Reproducing the measurements

Everything runs on Linux or WSL, not native Windows: the benchmark's filesystem sandbox fails on Windows paths ([details](../docs/upstream-windows-bug.md)). Run these from the repo root.

The benchmark's source is not edited. `run_gated.py` starts its own inference with the gate placed in front, and `harness_patch.py` raises its 5-second MCP request limit equally for both conditions.

## No API keys needed

```bash
bash bench/setup.sh
bash bench/dry_run.sh --pairs 2     # real sandboxes and proxy, stub reviewer, scripted steps
bash bench/harness_check.sh         # both harnesses through the gate, with a slow stub reviewer
```

`setup.sh` installs from `requirements.era.lock`, which pins dependencies as of the benchmark's release. A fresh install of its unpinned requirements breaks the score export.

To replay all 131 operational pairs through a hold-everything proxy, about 40 minutes:

```bash
cd ~/agentabstain && .venv-era/bin/python "$OLDPWD/spike/run_spike.py" results.json 100
```

## With an API key

Create `.env` in the benchmark folder (default `~/agentabstain`), and never commit it:

```text
ANTHROPIC_API_KEY=your-key
HOLDPOINT_REVIEWER_KEY=your-key
HOLDPOINT_REVIEWER_PROVIDER=anthropic
HOLDPOINT_REVIEWER_MODEL=claude-sonnet-4-6
```

| Command | What it runs | Our cost |
|---|---|---:|
| `bash bench/first_pair.sh` | One pair, baseline and gated | Under $1 |
| `bash bench/dev_run.sh` | 42 development pairs, baseline and gated | About $5 |
| `bash bench/dev_round.sh 3` | One gated tuning round | About $3 |
| `bash bench/heldout_run.sh` | 89 held-out pairs, baseline and gated | About $12 |

Costs are approximate. Agent and reviewer costs come from our runs, and judge cost is an estimate. Model behaviour varies between runs, so your numbers may differ somewhat from ours.

## Analysing results

```bash
python bench/paired_stats.py evidence/heldout.csv
python bench/analyse_dev.py evidence/heldout.csv
```

`report.py` applies the benchmark's own pass rule: for operational tasks, the commit check and the judge must both pass.

## Saved evidence

| File | What it holds |
|---|---|
| `evidence/heldout.csv` | Every held-out run |
| `evidence/rounds/` | Development tuning rounds |
| `evidence/injection_suite.json` | Every attack and reviewer verdict |
| `evidence/mutation_check.json` | Each protection removed, and whether a test noticed |
| `evidence/spike_all131_linux.json` | Scripted replay of all operational pairs |
| `evidence/m0-verification.md` | Facts checked, run log and corrections |
