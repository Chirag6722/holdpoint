document.documentElement.classList.add('js');

// The nav names the chapter being read.
const current = document.getElementById('current');
const watcher = new IntersectionObserver(entries => {
  entries.forEach(entry => { if (entry.isIntersecting) current.textContent = entry.target.dataset.chapter; });
}, {rootMargin: '-40% 0px -55% 0px'});
document.querySelectorAll('[data-chapter]').forEach(section => watcher.observe(section));

// Step through the recorded demo. With no script, every row simply shows.
const rows = [...document.querySelectorAll('.steps li')];
const next = document.getElementById('next');
const ledger = document.getElementById('sent');
const status = document.getElementById('step-status');
let step = 0;
function renderDemo() {
  rows.forEach((row, i) => row.classList.toggle('waiting', i >= step));
  const shown = rows.slice(0, step).filter(row => row.dataset.sent);
  ledger.textContent = shown.length ? shown[shown.length - 1].dataset.sent : '$0';
  next.textContent = step === 0 ? 'Start the agent' : step >= rows.length ? 'Play again' : 'Next step';
  status.textContent = step ? rows[step - 1].textContent.replace(/(RAN|HELD)$/, ': $1') : '';
}
next.addEventListener('click', () => { step = step >= rows.length ? 0 : step + 1; renderDemo(); });
renderDemo();

// Read any attack and the reviewer's reply.
const data = JSON.parse(document.getElementById('attack-data').textContent);
const detail = document.getElementById('detail');
const buttons = document.querySelectorAll('.cell');
const words = {hold: 'Held', proceed: 'Ran', error: 'Error'};
function show(button) {
  buttons.forEach(b => b.setAttribute('aria-pressed', 'false'));
  button.setAttribute('aria-pressed', 'true');
  const scenario = data.scenarios.find(s => s.id === button.dataset.s);
  const attack = data.attacks.find(a => a.id === button.dataset.a);
  const cell = scenario.cells[attack.id];
  const fields = [['Request', scenario.intent], ['Proposed call', scenario.call],
    ['Attack in the tool output', attack.text],
    ['Reviewer said', cell.reason.length >= 240 ? cell.reason + ' [saved replies stop at 240 characters]' : cell.reason]];
  const dl = document.createElement('dl');
  fields.forEach(([k, v]) => {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    dl.append(dt, dd);
  });
  const h = document.createElement('h3');
  h.textContent = scenario.name + ': ' + attack.name + '. ' + words[cell.verdict] + '.';
  detail.replaceChildren(h, dl);
}
buttons.forEach(b => b.addEventListener('click', () => show(b)));
if (buttons.length) show(buttons[0]);
