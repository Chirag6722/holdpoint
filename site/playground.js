// Break it yourself: runs the real gate code in this browser with Pyodide. Nothing is sent anywhere.
(() => {
  const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
  const data = JSON.parse(document.getElementById('playground-data').textContent);
  const $ = id => document.getElementById(id);
  const startButton = $('pg-start'), status = $('pg-status'), workspace = $('pg-work'), policy = $('pg-policy');
  const tool = $('pg-tool'), args = $('pg-args'), log = $('pg-log'), moves = $('pg-moves');
  const tabs = $('pg-tabs'), story = $('pg-story'), score = $('pg-score');
  let py = null, session = null, preset = data.presets[0];
  const counts = {RAN: 0, HELD: 0, REFUSED: 0};

  // What each outcome means, in plain words. The gate's own reason is shown underneath.
  const PLAIN = {
    floor: 'Refused. A hard rule blocks this, and not even a person can approve it.',
    rules: 'Held. It breaks a limit, so it waits for a person to approve it.',
    gate: 'Held. It waits for a person to approve it.',
    policy: 'Ran. This tool is safe, so it runs on its own.',
    auto: 'Ran. It is inside every limit, so it runs on its own.',
    human: 'Ran, because a person approved this exact call.',
    allowlist: 'Ran. This tool is always allowed.',
  };

  function say(text) { status.textContent = text; }

  function updateScore() {
    score.textContent = `So far: ${counts.RAN} ran, ${counts.HELD} held for a person, ${counts.REFUSED} refused.`;
  }

  function lastLine(error) {
    const lines = String(error.message || error).trim().split('\n');
    return lines[lines.length - 1].replace(/^\w*Error: /, '');
  }

  function attempt(toolName, argsText) {
    try {
      const result = JSON.parse(session.call(toolName, argsText));
      counts[result.outcome] += 1;
      updateScore();
      return result;
    } catch (error) {
      return {outcome: 'ERROR', by: 'error', reason: lastLine(error)};
    }
  }

  // One result: the badge, what it means, the gate's reason, and an Approve button where a person could approve.
  function showResult(box, result, toolName, argsText) {
    const head = document.createElement('p');
    head.className = 'pg-result';
    const mark = document.createElement('span');
    mark.className = 'mark ' + result.outcome.toLowerCase();
    mark.textContent = result.outcome;
    const plain = document.createElement('span');
    plain.textContent = result.outcome === 'ERROR' ? 'That call could not be read.' : (PLAIN[result.by] || '');
    head.append(mark, plain);
    const why = document.createElement('p');
    why.className = 'pg-why';
    why.textContent = result.reason ? 'Why: ' + result.reason : '';
    box.replaceChildren(head, why);
    if (result.outcome === 'HELD' && result.hold) {
      const approve = document.createElement('button');
      approve.type = 'button';
      approve.className = 'btn pg-approve';
      approve.textContent = 'Approve it as the person, then try again';
      approve.addEventListener('click', () => {
        session.approve(result.hold);
        showResult(box, attempt(toolName, argsText), toolName, argsText);
      });
      box.append(approve);
    }
  }

  function newSession() {
    log.replaceChildren();
    moves.querySelectorAll('.pg-out').forEach(box => box.replaceChildren());
    Object.keys(counts).forEach(k => { counts[k] = 0; });
    updateScore();
    try {
      py.globals.set('policy_text', policy.value);
      session = py.runPython('import playground\nplayground.Session(policy_text)');
      say('Ready. Click "Try it" on any line below.');
      return true;
    } catch (error) {
      session = null;
      say('These rules were refused: ' + lastLine(error));
      return false;
    }
  }

  function showPreset(next) {
    preset = next;
    tabs.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === preset.id)));
    story.textContent = preset.story;
    policy.value = preset.policy;
    tool.value = preset.moves[0].tool;
    args.value = JSON.stringify(preset.moves[0].args);
    moves.replaceChildren(...preset.moves.map(move => {
      const item = document.createElement('li');
      item.className = 'pg-attack';
      const label = document.createElement('span');
      label.className = 'pg-label';
      label.textContent = move.label;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn pg-try';
      button.textContent = 'Try it';
      button.setAttribute('aria-label', 'Try: ' + move.label);
      const out = document.createElement('div');
      out.className = 'pg-out';
      out.setAttribute('aria-live', 'polite');
      button.addEventListener('click', () => {
        if (!session) return;
        const text = JSON.stringify(move.args);
        showResult(out, attempt(move.tool, text), move.tool, text);
      });
      item.append(label, button, out);
      return item;
    }));
    if (py) newSession();
  }

  data.presets.forEach(p => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn pg-tab';
    button.dataset.id = p.id;
    button.textContent = p.name;
    button.addEventListener('click', () => showPreset(p));
    tabs.append(button);
  });
  $('pg-reset').addEventListener('click', newSession);
  $('pg-send').addEventListener('click', () => {
    if (!session && !newSession()) return;
    const item = document.createElement('li');
    item.className = 'pg-attack';
    const label = document.createElement('span');
    label.className = 'pg-label pg-code';
    label.textContent = tool.value + ' ' + args.value;
    const out = document.createElement('div');
    out.className = 'pg-out';
    item.append(label, out);
    showResult(out, attempt(tool.value, args.value), tool.value, args.value);
    log.prepend(item);
  });
  policy.addEventListener('change', newSession);

  startButton.addEventListener('click', async () => {
    startButton.disabled = true;
    say('Loading. This downloads Python, about 15 MB, and takes 10 to 30 seconds the first time.');
    try {
      if (!window.loadPyodide) {
        await new Promise((resolve, reject) => {
          const script = document.createElement('script');
          script.src = PYODIDE + 'pyodide.js';
          script.onload = resolve;
          script.onerror = () => reject(new Error('Could not reach the Python download.'));
          document.head.append(script);
        });
      }
      py = await window.loadPyodide({indexURL: PYODIDE});
      await py.loadPackage('pyyaml');
      py.FS.mkdirTree('/home/pyodide/holdpoint');
      Object.entries(data.files).forEach(([name, text]) => py.FS.writeFile('/home/pyodide/' + name, text));
      startButton.hidden = true;
      workspace.hidden = false;
      newSession();
    } catch (error) {
      startButton.disabled = false;
      say(lastLine(error) + ' The rest of this page still works, and you can run the same code yourself with the commands further down.');
    }
  });

  showPreset(data.presets[0]);
  startButton.hidden = false;
})();
