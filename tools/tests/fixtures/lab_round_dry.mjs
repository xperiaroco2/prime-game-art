// A dry run of a lab-round workflow script with a fake agent() (test_workflow_lab_round.py): node lab_round_dry.mjs
// <script.js> prints one JSON object with the arg refusals, the agents each launch called and the A/B records.
import { readFileSync } from 'node:fs';

const text = readFileSync(process.argv[2], 'utf8');
const body = text.slice(text.indexOf('\n};') + 3); // the script after `export const meta = {...};`
const run = new Function('args', 'agent', `return (async () => {${body}\n})();`);

let calls = [];
async function agent(prompt, opts) {
  calls.push({ label: opts.label, model: opts.model, agentType: opts.agentType, prompt });
  if (opts.phase === 'build') {
    return { handoff_path: 'O/handoff-step-1.md', done: true, contact_sheet: 'O/contact-sheet.png', variants: ['v1', 'v2'] };
  }
  if (opts.phase === 'critique') {
    return {
      ranking: [{ variant: 'v1', reason: 'r' }, { variant: 'v2', reason: 'r' }],
      recommendation: 'v1',
      remarks: [{ variant: 'v2', remark: 'hands clip', severity: 'serious' }, { variant: 'v1', remark: 'dull', severity: 'minor' }],
      ranking_path: 'p',
    };
  }
  return {
    verdicts: [
      { id: 'A1', verdict: 'valid', severity: 'serious', reason: 'seen' },
      { id: 'B1', verdict: 'valid', severity: 'serious', reason: 'seen' },
      { id: 'B2', verdict: 'invalid', severity: 'minor', reason: 'no' },
    ],
    pairs: [{ a: 'B1', b: 'A1' }, { a: 'A2', b: 'B1' }, { a: 'A9', b: 'B2' }],
  };
}

const base = { brief: 'b', lab_dir: 'L', out_dir: 'O' };
const out = { refusals: [], launches: {} };
for (const extra of [{}, { critic_model: 'fable' }, { critic_model: 'sonnet', control_model: 'sonnet' },
  { critic_model: 'sonnet', control_model: 'opus' }]) {
  try {
    await run({ ...base, ...extra }, agent);
    out.refusals.push(null);
  } catch (e) {
    out.refusals.push(e.message);
  }
}
for (const [name, extra] of [['single', { critic_model: 'sonnet' }],
  ['round1', { critic_model: 'sonnet', control_model: 'opus', round: 1 }],
  ['round2', { critic_model: 'sonnet', control_model: 'opus', round: 2 }]]) {
  calls = [];
  const result = await run({ ...base, ...extra }, agent);
  out.launches[name] = { calls: calls.map(({ prompt, ...c }) => c), judge_prompt: (calls.find((c) => c.label === 'judge') || {}).prompt || '', result };
}
console.log(JSON.stringify(out));
