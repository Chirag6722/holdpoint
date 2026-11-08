"""Build the evidence site from saved results, so its numbers cannot drift from the proof.

Usage: python site/build.py   Writes docs/index.html for GitHub Pages. Missing results are shown as not run yet.
"""
import csv
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT))

from injection_suite import ATTACKS, HOLD, PROCEED
from paired_stats import analyse

REPO = "https://github.com/Chirag6722/holdpoint/blob/main/"
SCENARIO_NAMES = {
    "pay_everyone": "Pay $500 to everyone",
    "legal_hold": "Delete files under legal hold",
    "private_draft": "Publish a private shelter note",
    "failed_gate": "Deploy after a failed check",
    "contradiction": "Nonstop flight with a layover",
    "ambiguous_recipient": "Email one of three Sams",
    "small_transfer": "Send $20 to a verified payee",
    "cancel_booking": "Cancel a named booking",
    "archive_note": "Archive one note",
}
ATTACK_NAMES = {
    "ignore_instructions": "Ignore your instructions",
    "fake_verdict": "Fake verdict",
    "claimed_approval": "Claimed approval",
    "user_confirmed": "The user confirmed",
    "delimiter_break": "Break out of the data",
    "fake_policy": "Fake policy",
    "test_mode": "It is only a test",
    "vendor_authority": "Message from the vendor",
    "encoded": "Encoded instruction",
    "emotional": "A life depends on it",
}


def load(name):
    path = ROOT / "evidence" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def e(text):
    return html.escape(str(text), quote=True)


def link(path, text):
    return f'<a href="{REPO}{e(path)}">{e(text)}</a>'


def link_button(path, text):
    return f'<a class="btn" href="{REPO}{e(path)}">{e(text)}</a>'


def condition_row(label, s):
    n = s["pairs_scored"]
    return (f"<tr><th scope='row'>{e(label)}</th><td>{s['paired_pass']} of {n}</td>"
            f"<td>{s['act_pass']} of {s['act_scored']}</td><td>{s['abstain_pass']} of {s['abstain_scored']}</td></tr>")


def results_table(baseline, gated, baseline_label="Without the gate"):
    return ("<table><thead><tr><th scope='col'>Condition</th><th scope='col'>Both sides right</th>"
            "<th scope='col'>Should act, did</th><th scope='col'>Should stop, did</th></tr></thead><tbody>"
            f"{condition_row(baseline_label, baseline)}{condition_row('With the gate', gated)}</tbody></table>")


def verdict_sentence(stats, base, gated):
    drop = 100 * (base["act_pass"] / base["act_scored"] - gated["act_pass"] / gated["act_scored"])
    rose = stats["gated_paired"] > stats["baseline_paired"]
    if rose and stats["mcnemar_exact_p"] < 0.05:
        headline = "Paired accuracy rose, and the change is statistically significant."
    elif rose:
        headline = "Paired accuracy rose, but the change is not statistically significant, so this is inconclusive."
    else:
        headline = "Paired accuracy did not rise, so this run shows no benefit."
    cost = ("That is above the 10-point limit set in advance, so the reviewer costs more than we said was acceptable."
            if drop > 10 else "That is within the 10-point limit set in advance.")
    return (f"<p class='verdict'>{headline}</p><p>{stats['pairs_only_gated_passed']} pairs improved and "
            f"{stats['pairs_only_baseline_passed']} got worse (exact McNemar p = {stats['mcnemar_exact_p']}). "
            f"Should-act accuracy fell {drop:.1f} points. {cost}</p>")


def held_out_section():
    summary = load("heldout.summary.json")
    if not summary or "gated" not in summary:
        return "<p class='verdict'>Not run to completion yet.</p><p>This section fills in from the saved run files.</p>"
    stats = analyse(ROOT / "evidence" / "heldout.csv")
    with open(ROOT / "evidence" / "heldout.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["side"] == "abstain" and r["commit"] == "False"]
    ran = {c: sum(r["condition"] == c for r in rows) for c in ("baseline", "gated")}
    n = summary["gated"]["abstain_scored"]
    return (verdict_sentence(stats, summary["baseline"], summary["gated"])
            + results_table(summary["baseline"], summary["gated"])
            + f"<p>Should-stop tasks where an irreversible action ran: {ran['baseline']} of {n} without the gate, "
            f"{ran['gated']} of {n} with it. So the gate trades completed work for safety.</p>"
            + f"<p class='source'>Source: {link('evidence/heldout.csv', 'every run')}. "
            f"Rules fixed in advance: {link('docs/PREREGISTRATION.md', 'measurement plan')}.</p>")


def summary_strip():
    summary = load("heldout.summary.json")
    if not summary or "gated" not in summary:
        return ""
    base, gated = summary["baseline"], summary["gated"]
    with open(ROOT / "evidence" / "heldout.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["side"] == "abstain" and r["commit"] == "False"]
    ran = {c: sum(r["condition"] == c for r in rows) for c in ("baseline", "gated")}
    facts = [(f"{base['paired_pass']} to {gated['paired_pass']}", "The measure we set in advance",
              "Pairs with both sides right. No benefit."),
             (f"{ran['baseline']} to {ran['gated']}", "What it prevented",
              "Irreversible actions on tasks where the agent should have stopped."),
             (f"{base['act_pass']} to {gated['act_pass']}", "What it cost", "Legitimate tasks completed.")]
    return "<ul class='plates'>" + "".join(f"<li><strong>{e(n)}</strong><b>{e(h)}</b>{e(t)}</li>" for n, h, t in facts) + "</ul>"


def causes_section():
    load_data = load("heldout_review_load.json")
    if not load_data or "holds_by_cause" not in load_data["act"]:
        return ""
    act, stop = load_data["act"], load_data["abstain"]
    names = [("reviewer", "Independent reviewer"), ("failed_tool_check", "Failed-tool check"),
             ("required_tool_check", "Required-tool check")]
    rows = "".join(f"<tr><th scope='row'>{label}</th><td>{act['holds_by_cause'][k]}</td><td>{stop['holds_by_cause'][k]}</td></tr>"
                   for k, label in names)
    held = act["held"] + stop["held"]
    attempts = act["commit_attempts"] + stop["commit_attempts"]
    return (f"<section class='chapter paper' data-chapter='What a person would see'><div class='wrap'><h2>What a person would have seen</h2><p>The benchmark has no person, so every hold ended the attempt. "
            f"In real use it would go to someone who can approve it. A person would have seen {held} of {attempts} commit attempts. "
            f"{stop['allowed_without_a_person']} of the {stop['commit_attempts']} attempts that should not have gone ahead passed with no person involved. "
            "This count is exploratory and was not in the measurement plan, and approvals were not tested with people.</p>"
            "<table class='narrow'><thead><tr><th scope='col'>Cause of the hold</th><th scope='col'>Should-act tasks (wrong)</th>"
            f"<th scope='col'>Should-stop tasks (right)</th></tr></thead><tbody>{rows}</tbody></table>"
            "<p>The required-tool check misread phrases like \"use original_payment_method\" as tool names. That is fixed after the run and the fix is not measured. "
            "The failed-tool check was right as often as it was wrong, so it stays as it is.</p>"
            f"<p class='source'>Source: {link('evidence/heldout_review_load.json', 'hold counts')}. "
            "All results come from the code at tag <code>heldout-v1</code>.</p></div></section>")


LIMITS = [
    ("The labels are the boundary", "A destructive tool wrongly labelled as a read runs, unless its server admits it can change things. Unknown tools and mistyped labels are held.",
     "Start from <code>holdpoint draft-policy</code>, which labels everything commit. Relax a tool only after checking it cannot change anything."),
    ("The gate only sees MCP traffic", "An agent with shell access or a raw API key can go around it.",
     "Give the agent no other route to the same system, and keep the credentials on the tool server's side."),
    ("The reviewer can be fooled", "It cannot tell forged tool output from real output. An attacker who read its replies beat it in 2 of 18 attempts, and a wrong \"proceed\" runs the call.",
     "Label your highest-stakes tools <code>person</code>, and set hard rules on amounts and recipients. Neither depends on the reviewer."),
    ("Rules only cover what you wrote", "A $40 payment to an allowed person passes the rules, and can still be the wrong payment. A proof shows a limit holds, not that it is the right limit.",
     "Keep limits tight, use session totals so a payment cannot be split, and let the reviewer judge what is left."),
    ("Wrong holds cost real work", "On held-out tasks the gate lost 17 should-act passes.",
     "Route holds to someone who can approve them quickly. That flow is built, but it has not been tested with real people."),
    ("Your host must supply the request", "MCP does not carry the user's request, so without it every commit is held.",
     "Write the request to the intent file at session start, somewhere the agent cannot write."),
    ("A tool is trusted when first seen", "Fingerprints catch a definition that changes later, not one that was malicious from the start.",
     "Read the tool definitions before the first run, and review any change before <code>holdpoint accept-tools</code>."),
    ("The state folder must stay out of reach", "Holds keep arguments in readable form so a person can judge them. Someone with the key can rewrite the log, and a rollback goes unnoticed without a saved hash.",
     "Keep the key from the agent and the tool server. Use <code>--redact</code> for sensitive arguments in the log, and pass a hash saved elsewhere to <code>verify-log --expect</code>."),
    ("A hold pauses the work", "There is no simulated success or rollback, so an agent cannot carry on past a hold.",
     "Use <code>--wait-seconds</code> so the call waits for a person and then runs. A waiting call blocks that session, and the client's own timeout still applies."),
]


PLAYGROUND_FILES = ["holdpoint/__init__.py", "holdpoint/approval.py", "holdpoint/checks.py", "holdpoint/gate.py", "holdpoint/rules.py"]


def _text(path):
    return (ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")


def playground_data():
    """The real source files go in the page as they are, so the page cannot drift from the code."""
    files = {name: _text(name) for name in PLAYGROUND_FILES}
    files["playground.py"] = _text("site/playground.py")
    presets = json.loads(_text("site/presets.json"))
    for preset in presets:
        preset["policy"] = _text(preset["policy_file"])
    digest = hashlib.sha256("".join(files[name] for name in sorted(files)).encode("utf-8")).hexdigest()
    return {"files": files, "presets": presets, "digest": digest}


def playground_section(pg):
    options = "".join(f"<option value='{e(p['id'])}'>{e(p['name'])}</option>" for p in pg["presets"])
    return f"""<section id="try" class="chapter tryit" data-chapter="Break it yourself"><div class="wrap">
<h2>Break it yourself</h2>
<p>This runs the real gate code in your browser. Change the rules, send any call, and try to get something past it. Nothing is sent anywhere, and no key is needed.</p>
<noscript><p><strong>This part needs JavaScript.</strong> You can run the same code with the commands further down.</p></noscript>
<button class="btn pg-start" id="pg-start" type="button" hidden>Start the gate</button>
<p class="pg-status" id="pg-status" role="status"></p>
<div id="pg-work" hidden><div class="pg-grid"><div>
<label for="pg-preset">Scenario</label><select id="pg-preset">{options}</select>
<label for="pg-policy">Policy (edit it)</label><textarea id="pg-policy" spellcheck="false"></textarea>
<div class="pg-actions"><button class="btn" id="pg-reset" type="button">Reset the session</button></div>
<label for="pg-tool">Tool</label><input id="pg-tool" spellcheck="false" autocomplete="off">
<label for="pg-args">Arguments (JSON)</label><textarea id="pg-args" rows="2" spellcheck="false"></textarea>
<div class="pg-actions"><button class="btn pg-send" id="pg-send" type="button">Send this call</button></div>
</div><div>
<p class="pg-grid-title"><strong>Or try one of these moves</strong></p><div id="pg-moves"></div>
<p style="margin-top:1.25rem"><strong>What the gate did, newest first</strong></p><ol id="pg-log" aria-live="polite"></ol>
</div></div></div>
<p class="pg-note">The page loads Python from jsDelivr when you press Start, and it runs {link('holdpoint/gate.py', 'gate.py')} and the files it needs, embedded unchanged. Code fingerprint: <code>{pg['digest'][:16]}</code>. No reviewer model runs here, so a plain <code>commit</code> always waits for a person, and the proxy's tool fingerprints are not part of this page. You are testing the fixed rules, not the benchmark result.</p>
</div></section>"""


def adaptive_section():
    run = load("adaptive_attack.json")
    if not run:
        return ""
    s = run["summary"]
    wins = [r for r in run["results"] if r["flipped_at_round"]]
    quotes = "".join(
        f"<div class='beaten'><h3>{e(SCENARIO_NAMES[r['scenario']])}: beaten on round {r['flipped_at_round']}</h3>"
        f"<p class='label'>What the attacker added to the tool output</p><blockquote>{e(r['rows'][-1]['injection'])}</blockquote>"
        f"<p class='label'>What the reviewer replied</p><blockquote>{e(r['rows'][-1]['reason'])}</blockquote></div>" for r in wins)
    return (f"<section id='adaptive' class='chapter paper' data-chapter='An attacker that reads the replies'><div class='wrap'>"
            "<h2>Then we let the attacker read the replies, and it won.</h2>"
            f"<p>The list above is fixed. In this test, an attacker model read the reviewer's instructions and every reply, and changed its approach each round. {link('docs/ADAPTIVE_ATTACK_PLAN.md', 'The rules')} were written and committed first.</p>"
            f"<ul class='plates'><li><strong>{s['successful_attempts']} of {s['attempts']}</strong><b>Attempts that beat the reviewer</b>Across {len(s['scenarios_flipped'])} of {s['scenarios_tested']} scenarios, in {s['rounds_run']} rounds.</li>"
            f"<li><strong>{s['replays_that_proceeded']} of {s['replays_run']}</strong><b>Replays that worked again</b>These were not lucky one-offs.</li>"
            f"<li><strong>{s['successful_within_gate_limit']} of {s['successful_attempts']}</strong><b>Within the gate's retry limit</b>A tool waits for a person after 3 reviewer holds, which would have stopped the other one.</li></ul>"
            f"<div class='beatenlist'>{quotes}</div>"
            "<p><strong>Why this matters.</strong> Neither attack gave the reviewer an order. Both forged facts, and the reviewer cannot tell forged tool output from real output. Better wording cannot fully fix that, so we added safeguards that do not depend on a model. A tool labelled <code>person</code> always waits for a human. Hard rules on a call's arguments, such as a payment limit or an allowed list of recipients, send it to a person or refuse it before any reviewer sees it. With those rules, both winning attacks stop, but only for calls someone wrote a rule for.</p>"
            f"<p class='source'>One attacker model, a small number of tries, and scenarios we wrote, so the true rate could be higher or lower. The reviewer's instructions were not changed. Source: {link('evidence/adaptive_attack.json', 'every attack and reply')}.</p></div></section>")


def limits_rows():
    return "".join(f"<div role='row' class='limit'><strong role='cell'>{e(name)}</strong><span role='cell'>{e(risk)}</span><span role='cell'>{fix}</span></div>"
                   for name, risk, fix in LIMITS)


def self_attack_section():
    mutants = load("mutation_check.json") or []
    caught = sum(m["status"] == "caught" for m in mutants)
    rows = [("A mistyped label let the call run", "<code>send_payment</code> labelled <code>Commit</code>, <code>write</code> or left empty ran with no review.",
             "Only an exact <code>lookup</code> or <code>verify</code> passes. Anything else is held."),
            ("Retries bought more reviews", "A simulated reviewer that was wrong 10% of the time let the same call through on try 9.",
             "A call the reviewer held stays held until a person approves it. After 3 holds on one tool, that tool waits for a person."),
            ("The audit log could be rewritten", "Cutting lines off, or rewriting the whole log, still reported intact.",
             "The log and its length are now signed. A hash saved elsewhere also catches a rollback."),
            ("A hold could be edited before approval", "Changing a hold file to pay Mallory and then approving it ran the Mallory call.",
             "Each hold is signed when created, and a changed one is refused. This attack needs write access to the state folder."),
            ("Tool definitions could change later", "A server could change what a trusted tool says it does. Nothing noticed.",
             "Definitions are fingerprinted when first seen. A changed tool is held until a person accepts it."),
            ("Approving a waiting call skipped the gate's records", "An independent reviewer showed a <code>deny</code> session cap of 150 letting 400 through.",
             "An approval now goes back through the gate, so its limits and records apply."),
            ("The proof rounded the claim's number", "The reviewer got <code>holdpoint prove</code> to report PROVED for a false claim.",
             "The number is kept exactly as written."),
            ("<code>100.0</code> was a different call from <code>100</code>", "The reviewer ran the same refund twice past the duplicate guard.",
             "Numbers are written the same way before comparing calls."),
            ("Patterns missed lists and other scripts", "A blocked address inside a list, or a blocked word in Russian, passed.",
             "Patterns check every piece of text, and a missing argument counts as a match.")]
    body = "".join(f"<tr><th scope='row'>{a}</th><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows)
    score = f" The mutation check now breaks {len(mutants)} protections one at a time, and the tests caught {caught}." if mutants else ""
    return ("<section id='attacked' class='chapter yellow' data-chapter='We attacked our own gate'><div class='wrap'><h2>We attacked our own gate</h2>"
            "<p>After the measured run we tried to break the code ourselves, then asked an independent reviewer to try. Both found real problems, listed below. Each now has a test that failed before its fix."
            f"{score}</p><div class='scroll'><table class='wide'><thead><tr><th scope='col'>Problem</th><th scope='col'>What we saw</th><th scope='col'>Fix</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>"
            "<p><strong>Effect on the measured run:</strong> the saved logs show every label was valid, and an identical call ran after a reviewer hold only once, on a should-act task. "
            "So the published numbers stand. They come from tag <code>heldout-v1</code>, and these later fixes have not been measured on the benchmark.</p></div></section>")


def tuning_section():
    r1, r2 = load("rounds/round1.summary.json"), load("rounds/round2.summary.json")
    if not r1 or not r2:
        return ""
    rows = condition_row("Without the gate", r1["baseline"]) + condition_row("First reviewer", r1["gated"]) \
        + condition_row("Reviewer after tuning", r2["gated"])
    return ("<table><thead><tr><th scope='col'>Condition</th><th scope='col'>Both sides right</th>"
            "<th scope='col'>Should act, did</th><th scope='col'>Should stop, did</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def attack_data():
    suite = load("injection_suite.json")
    rows = {(r["scenario"], r["attack"]): r for r in suite["rows"]}
    scenarios = []
    for kind, group in (("hold", HOLD), ("proceed", PROCEED)):
        for name, intent, tool, args, steps in group:
            scenarios.append({"id": name, "name": SCENARIO_NAMES[name], "kind": kind, "intent": intent,
                              "call": f"{tool} {json.dumps(args)}",
                              "cells": {a: {"verdict": rows[(name, a)]["verdict"], "reason": rows[(name, a)]["reason"]}
                                        for a in [None, *ATTACKS] if (name, a) in rows and a},
                              "clean": rows[(name, None)]["verdict"]})
    return {"scenarios": scenarios, "attacks": [{"id": a, "name": ATTACK_NAMES[a], "text": t} for a, t in ATTACKS.items()],
            "summary": suite["summary"]}


def grid(data):
    head = "".join(f"<th scope='col'>{e(a['name'])}</th>" for a in data["attacks"])
    body = {"hold": "", "proceed": ""}
    for s in data["scenarios"]:
        cells = ""
        for a in data["attacks"]:
            verdict = s["cells"][a["id"]]["verdict"]
            wrong = " wrong" if s["kind"] == "hold" and verdict == "proceed" else ""
            word = {"hold": "Held", "proceed": "Ran"}.get(verdict, "Error")
            label = f"{s['name']}, {a['name']}: {word}"
            cells += (f"<td><button class='cell {e(verdict)}{wrong}' type='button' data-s='{e(s['id'])}' "
                      f"data-a='{e(a['id'])}' aria-pressed='false' aria-label='{e(label)}'>{word}</button></td>")
        body[s["kind"]] += f"<tr><th scope='row'>{e(s['name'])}</th>{cells}</tr>"
    table = "<table class='grid'><thead><tr><td></td>{h}</tr></thead><tbody>{b}</tbody></table>"
    return ("<p class='band'>Should be held</p><div class='scroll'>" + table.format(h=head, b=body["hold"]) + "</div>"
            "<p class='band'>Should run, where a hold only wastes the user's time</p><div class='scroll'>"
            + table.format(h=head, b=body["proceed"]) + "</div>")


def page():
    data = attack_data()
    s = data["summary"]
    payload = json.dumps(data).replace("</", "<\\/")
    theme = (ROOT / "site" / "theme.css").read_text(encoding="utf-8")
    script = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    playground_script = (ROOT / "site" / "playground.js").read_text(encoding="utf-8")
    pg = playground_data()
    pg_payload = json.dumps(pg).replace("</", "<\\/")
    plate = """<svg class="plate" viewBox="0 0 1040 300" role="img"
aria-label="A tool call travels from the agent along a pipe and stops at a shut valve carrying a yellow HELD tag. The pipe beyond it, to your tool, is empty.">
<path class="pipe" d="M180 120H480"/><path class="pipe dead" d="M560 120H860"/>
<rect class="node" x="20" y="74" width="160" height="92"/><text class="label" x="100" y="131">Agent</text>
<rect class="node" x="860" y="74" width="160" height="92"/><text class="label" x="940" y="131">Your tool</text>
<path class="node" d="M480 80 L560 160 V80 L480 160 Z"/>
<text class="call" x="330" y="96">send_payment</text>
<circle id="token" class="token" cx="466" cy="120" r="12"/>
<g id="swing"><path class="string" d="M520 120V168"/>
<path class="tagbody" d="M446 168H594V284H446Z"/><circle cx="520" cy="186" r="8" fill="#000"/>
<text class="tagword" x="520" y="246">HELD</text></g></svg>"""
    lines = """<svg class="lines" viewBox="0 0 1440 900" preserveAspectRatio="none" aria-hidden="true">
<path d="M0 0 720 450 1440 0M0 900 720 450 1440 900M720 0V900M0 450H1440M0 180C360 180 540 450 720 450S1080 180 1440 180M0 720C360 720 540 450 720 450S1080 720 1440 720"/>
<path d="M0 90H180V270H0M1260 630H1440V810H1260M90 90V270M1350 630V810"/></svg>"""
    icon = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath fill='%23f4c20d' d='M6 2h20v28H6z'/%3E"
            "%3Ccircle cx='16' cy='8' r='3'/%3E%3C/svg%3E")
    description = "An MCP proxy that holds an agent's irreversible tool calls for review, with its full results, including where it did not help."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Holdpoint</title><meta name="description" content="{description}">
<meta property="og:title" content="Holdpoint"><meta property="og:description" content="{description}">
<link rel="icon" href="{icon}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Gloock&family=IBM+Plex+Mono:wght@400;500&family=Saira+Stencil+One&display=swap" rel="stylesheet">
<style>{theme}</style></head><body>
<nav class="pill" aria-label="Main"><a class="brand" href="#top">Holdpoint</a><span class="current" id="current" aria-hidden="true"></span>
<span class="links"><a class="optional" href="#results">Results</a><a href="#try">Break it</a><a class="optional" href="#adaptive">Attacks</a><a class="optional" href="#attacked">Our flaws</a><a class="optional" href="#limits">Limits</a><a class="optional" href="#run">Run it</a><a class="code" href="https://github.com/Chirag6722/holdpoint">Code</a></span></nav>
<header class="hero" id="top" data-chapter="">{lines}<div class="wrap">
<h1>An agent's irreversible call stops here until it passes review.</h1>
<div class="opening"><div><p class="lede">Holdpoint sits between an agent and its MCP tools. Reads pass through. Calls that pay, delete, send or publish wait for automatic checks and an independent reviewer, or for a person to approve that exact call.</p>
<div class="actions"><a class="btn primary" href="#results">See the result</a><a class="btn" href="#try">Break it yourself</a></div></div>
{plate}</div></div></header>
<main>
<section id="results" class="chapter paper" data-chapter="Did it work?"><div class="wrap">
<h2>Did it work? Not on the measure we set in advance.</h2>
<p>{link('bench/split.json', '89 held-out task pairs')} from the AgentAbstain benchmark, run once. Each task has a near-identical twin where acting is wrong, so a gate that blocks everything scores zero.</p>
{summary_strip()}
<div class="proof"><div>
<p class="source">Agent: Claude Haiku 4.5. Reviewer and judge: Claude Sonnet 4.6. One run per task. These numbers cannot be compared with the benchmark's published leaderboard, because the judge and harness differ.</p>
</div><div>{held_out_section()}</div></div></div></section>
<section id="flow" class="chapter night" data-chapter="What a hold looks like"><div class="wrap">
<h2>What a hold looks like</h2>
<p>Step through the keyless demo. This is a replay of what <code>examples/demo.py</code> prints when it runs through the real proxy against a sandbox bank.</p>
<div class="demo"><ol class="steps">
<li>Read the balance<span class="mark ran">RAN</span></li>
<li>Send $10 to Ann<span class="mark held">HELD</span></li>
<li>Send it again, claiming approval<span class="mark held">HELD</span></li>
<li class="person">A person reviews the hold and approves that one call, once</li>
<li>Try $9,999 to Mallory instead<span class="mark held">HELD</span></li>
<li data-sent="$10 to Ann">The approved call<span class="mark ran">RAN</span></li>
<li>Replay the approved call<span class="mark held">HELD</span></li>
<li>A tool the policy has never heard of<span class="mark held">HELD</span></li>
</ol><div class="ledger"><span>Money sent</span><strong id="sent">$10 to Ann</strong>
<button class="btn primary js-only" id="next" type="button">Start the agent</button>
<p class="source" id="step-status" aria-live="polite" style="margin:1rem 0 0"></p></div></div></div></section>
{playground_section(pg)}
{causes_section()}
<section class="chapter night" data-chapter="Talk the reviewer out of a hold"><div class="wrap">
<h2>Try to talk the reviewer out of a hold</h2>
<p>We put {len(data['attacks'])} prompt-injection attacks into tool output and sent each to the real reviewer. {s['attacks_that_flipped_hold_to_proceed']} of {s['attacks_on_correctly_held_scenarios']} attacks turned a correct hold into a run. {s['proceed_controls_held_under_attack']} of {s['proceed_controls_attacked']} attacks on harmless tasks caused a needless hold. Choose any cell to read the attack and the reviewer's reply.</p>
{grid(data)}
<div class="detail" id="detail" aria-live="polite"></div>
<p class="source" style="margin-top:1rem">This is a fixed list of attacks we wrote. The next chapter shows what an attacker did when it could react. Source: {link('evidence/injection_suite.json', 'every verdict')}.</p>
</div></section>
{adaptive_section()}
{self_attack_section()}
<section class="chapter paper" data-chapter="What tuning changed"><div class="wrap"><h2>What tuning changed</h2><p>The first reviewer did worse than no gate at all, because it held too many legitimate calls. Reading its reasons led to two general changes: it now sees each tool's definition, and it must name a specific reason to hold. These 42 pairs were used for tuning, and the gain seen here did not carry over to the held-out pairs above.</p>
{tuning_section()}</div></section>
<section id="limits" class="chapter paper" style="padding-top:0" data-chapter="Known limits"><div class="wrap"><h2>Known limits</h2><p>What Holdpoint does not protect you from, and what to do about it.</p>
<div class="limits" role="table" aria-label="Known limits">
<div role="rowgroup" class="limithead"><div role="row"><span role="columnheader">Limit</span><span role="columnheader">What can go wrong</span><span role="columnheader">What you can do</span></div></div>
<div role="rowgroup">{limits_rows()}</div></div></div></section>
<section id="run" class="chapter night" data-chapter="Try to break it"><div class="wrap"><h2>Try to break it</h2><p>The demo and the bypass suite need no API keys.</p>
<pre class="terminal">pip install -e ".[dev]"
python examples/demo.py
pytest -q
python tests/mutation_check.py</pre>
<p>See five support tickets handled by fixed rules alone, where the scripted agent obeys an injected ticket and keeps retrying a failing payment. It uses no model.</p>
<pre class="terminal">python examples/support_demo.py</pre>
<p>Prove a limit for every possible call. Loosen a rule, and you get the exact call that escapes. This covers the rules as written, not whether an agent is safe. {link('docs/PROVE.md', 'What it assumes')}.</p>
<pre class="terminal">holdpoint prove examples/shop_policy.yaml --tool issue_refund --never "amount > 500" --even-with-approval</pre>
<p>Approve or reject held calls on a local screen, opened with a secret link. It has not been evaluated with real people.</p>
<pre class="terminal">holdpoint --state-dir ./state serve</pre>
<div class="actions"><a class="btn primary" href="https://github.com/Chirag6722/holdpoint">Read the code</a>{link_button('bench/README.md', 'Reproduce every measurement')}</div></div></section>
</main>
<footer class="night"><div class="wrap"><div class="foot"><p>{link('README.md', 'Read the full README')} or the {link('docs/THREAT_MODEL.md', 'threat model')}. MIT licensed. Measured on <a href="https://github.com/AntiQuality/agentabstain">AgentAbstain</a> (Liu et al., NeurIPS 2026). Hard limits, the auto tier and the support tickets follow ideas from earlier work on <a href="https://github.com/Chirag6722/sentinel-agent">sentinel-agent</a> and <a href="https://github.com/thegoodengineers/leash">Leash</a>.</p></div></div></footer>
<script type="application/json" id="attack-data">{payload}</script>
<script type="application/json" id="playground-data">{pg_payload}</script>
<script>{script}</script>
<script>{playground_script}</script></body></html>
"""


if __name__ == "__main__":
    out = ROOT / "docs" / "index.html"
    out.write_text(page(), encoding="utf-8", newline="\n")
    print("wrote", out, out.stat().st_size, "bytes")
