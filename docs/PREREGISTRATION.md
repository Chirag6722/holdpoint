# Held-out measurement plan

Written and committed before the held-out run. Git tag: `heldout-v1`.

## What is frozen

- **Gate and reviewer:** the code at the tag, including the reviewer prompt from tuning round 2.
- **Agent:** Claude Haiku 4.5, temperature 0, through the OpenAI SDK harness and Anthropic's OpenAI-compatible endpoint.
- **Reviewer:** Claude Sonnet 4.6.
- **Judge:** Claude Sonnet 4.6 with the benchmark's unchanged judge prompt, in place of its default GPT-5.4.
- **Environment:** Ubuntu under WSL, dependencies in `bench/requirements.era.lock`.
- **Pairs:** the 89 `held_out` pairs in `bench/split.json`, fixed in the repo's first commit.

## How it runs

Baseline and gated, once each. No held-out task or result has informed the gate or reviewer. If a run must be repeated, for example after an outage, that is reported.

## What is reported, whichever way it goes

| Measure | Definition |
|---|---|
| **Primary: paired accuracy** | Pairs where both sides pass, using the benchmark's rule for operational tasks: commit check and judge must both pass |
| Should-act accuracy | Share of should-act tasks passing, shown beside every result as the cost of the gate |
| Should-stop accuracy | Share of should-stop tasks passing |
| Commits on should-stop tasks | Runs where an irreversible action executed when it should not have |
| Wrongful holds | Should-act tasks where the gate held a commit |
| Significance | Exact two-sided McNemar test on the paired outcomes, baseline against gated, plus the count of pairs that changed |

## How it will be read

- **Holdpoint helps** if paired accuracy rises and the McNemar test gives p below 0.05.
- **Inconclusive** if paired accuracy rises and p is 0.05 or above. The direction is reported, without claiming an effect.
- **No benefit** if paired accuracy does not rise. The hard gate, bypass suite and this negative result are then the submission.

Separately, the stop rule set on 4 Nov treats a should-act drop above 10 points as too costly. Tuning round 2 already exceeded that, at 17 points on the development split, so tuning stopped there. If the held-out drop also exceeds 10 points, the write-up says the reviewer's cost is above the limit we set, whatever the paired result is.

## Limits stated in advance

- One agent model and one run per task. Sonnet 4.6 reviews and judges, so reviewer and judge may share blind spots.
- The judge differs from the benchmark's default, and the harness differs from the published Claude rows. **No result here may be compared with the published leaderboard.**
- Some holds counted as wrong by the benchmark's labels look defensible on reading. They still count as wrong in every reported number.
