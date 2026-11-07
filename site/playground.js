// Break it yourself: runs the real gate code in this browser with Pyodide. Nothing is sent anywhere.
(() => {
  const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
  const data = JSON.parse(document.getElementById('playground-data').textContent);
  const $ = id => document.getElementById(id);
  const startButton = $('pg-start'), status = $('pg-status'), workspace = $('pg-work'), policy = $('pg-policy');
  const tool = $('pg-tool'), args = $('pg-args'), log = $('pg-log'), moves = $('pg-moves'), presetSelect = $('pg-preset');
  let py = null, session = null;

  function say(text) { status.textContent = text; }

  function addRow(label, result) {
    const row = document.createElement('li');
    row.className = 'pg-row';
    const head = document.createElement('div');
    head.className = 'pg-head';
    const name = document.createElement('span');
    name.className = 'pg-call';
    name.textContent = label;
    const mark = document.createElement('span');
    mark.className = 'mark ' + result.outcome.toLowerCase();
    mark.textContent = result.outcome;
    head.append(name, mark);
    row.append(head);
    if (result.reason) {
      const why = document.createElement('p');
      why.className = 'pg-why';
      why.textContent = result.reason;
      row.append(why);
    }
    if (result.outcome === 'HELD' && result.hold && !result.error) {
      const approve = document.createElement('button');
      approve.type = 'button';
      approve.className = 'btn pg-approve';
      approve.textContent = 'Approve this exact call once, as a person';
      approve.addEventListener('click', () => {
        session.approve(result.hold);
        approve.replaceWith(Object.assign(document.createElement('p'), {
          className: 'pg-why', textContent: 'Approved. Send the exact same call again to use it.',
        }));
      });
      row.append(approve);
    }
    log.prepend(row);
  }

  function run(label, toolName, argsText) {
    try {
      addRow(label, JSON.parse(session.call(toolName, argsText)));
    } catch (error) {
      addRow(label, {outcome: 'ERROR', reason: lastLine(error), error: true});
    }
  }

  function lastLine(error) {
    const lines = String(error.message || error).trim().split('\n');
    return lines[lines.length - 1].replace(/^\w*Error: /, '');
  }

  function newSession() {
    log.replaceChildren();
    try {
      py.globals.set('policy_text', policy.value);
      session = py.runPython('import playground\nplayground.Session(policy_text)');
      say('Fresh session. The gate has this policy and remembers calls until you reset it.');
      return true;
    } catch (error) {
      session = null;
      say('This policy was refused: ' + lastLine(error));
      return false;
    }
  }

  function showPreset(preset) {
    policy.value = preset.policy;
    tool.value = preset.moves[0].tool;
    args.value = JSON.stringify(preset.moves[0].args);
    moves.replaceChildren(...preset.moves.map(move => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn pg-move';
      button.textContent = move.label;
      button.addEventListener('click', () => {
        tool.value = move.tool;
        args.value = JSON.stringify(move.args);
        if (session) run(move.label, move.tool, args.value);
      });
      return button;
    }));
    if (py) newSession();
  }

  presetSelect.addEventListener('change', () => showPreset(data.presets.find(p => p.id === presetSelect.value)));
  $('pg-reset').addEventListener('click', newSession);
  $('pg-send').addEventListener('click', () => {
    if (session || newSession()) run(tool.value + ' ' + args.value, tool.value, args.value);
  });
  policy.addEventListener('change', newSession);

  startButton.addEventListener('click', async () => {
    startButton.disabled = true;
    say('Loading Python and the real gate code. This is about 15 MB and only happens when you ask.');
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
