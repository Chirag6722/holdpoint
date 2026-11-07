# Proving a limit

Tests try some calls. `holdpoint prove` covers every possible value of an argument, using the z3 solver, and gives one of two answers.

```bash
pip install -e ".[prove]"
holdpoint prove examples/shop_policy.yaml --tool issue_refund --never "amount > 50"
holdpoint prove examples/shop_policy.yaml --tool issue_refund --never "amount > 500" --even-with-approval
holdpoint prove examples/shop_policy.yaml --tool send_email --never "to not in [customer@shop.example]"
```

- **PROVED:** no call where that claim is true can run.
- **ESCAPE:** here is an exact call that does run. Every escape is replayed on the real gate before it is shown.

By default the question is "can this run without a person?". `--even-with-approval` also rules out what a person could approve, so only `deny` rules count.

## What a proof does and does not mean

**It covers rules someone wrote, not whether an agent is safe.** Proving "no refund above $500 can run" says nothing about a $40 refund to the wrong customer, or about a limit set too high.

To keep a PROVED result from relying on anything uncertain:

- `pattern` rules are assumed to pass anything.
- The reviewer is assumed to say yes to anything.
- `--allow` flags are not considered, because they skip the rules on purpose.
- It looks at one call on a fresh session. The duplicate guard, circuit breaker and retry limits only stop more calls, so leaving them out cannot make a proof wrong.

A session total is modelled as a limit on one call, which is exact for that call. Proving a limit across a whole session's total is not covered.

Numbers are modelled as exact values, and the gate compares single values as Python numbers. The model has no rounding of a running total, because it looks at one call.

## How we check the proof itself

A proof of the wrong model would be worse than no proof, so `tests/test_prove.py` compares the model with the real gate:

- Random policies and calls, with a fixed seed, must get the same answer from the formula and from the real `Gate`.
- When the solver rules a claim out, random calls making that claim true must never run on the real gate.
- Every escape must really run on the real gate.

These are tests of the model, not a proof that the model is correct, and z3 itself is trusted.

The method is from de Moura and Bjorner, *Z3: An Efficient SMT Solver* (TACAS 2008). Leash, an earlier project, showed a similar idea with Cedar's own symbolic compiler. This code is separate and written for Holdpoint's rules.
