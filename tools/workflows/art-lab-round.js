export const meta = {
  name: 'art-lab-round',
  description: 'One lab round of prime-game-art: an art-writer builder in steps of at most 60 calls, each ending in a handoff note, then an art-reader critic on the model the manager passes that ranks the variants from one contact sheet and recommends one; with a control model, a control critic beside it and a blind Opus judge of both critiques (the A/B of #46).',
  args: {
    brief: 'The round brief: goal, the variants to make, the acceptance checks (a few lines, no history).',
    lab_dir: 'The lab folder the builder works in, under D:/prime-art-raw/research/.',
    out_dir: 'The folder for handoff notes, the contact sheet and the ranking (inside lab_dir or the scratchpad).',
    steps: 'The most builder steps (1 to 4, default 2); a step that reports the round done ends the build early.',
    critic_model: 'Required: the critic model, passed per launch (opus, sonnet or haiku); the script names no default (#46).',
    control_model: 'Optional: the A/B control critic model (the ADR: opus), other than critic_model; adds the control critic and the blind judge.',
    round: 'With control_model: the trial round number (1, 2, ...); its parity decides which critique the judge sees as A.',
  },
};

// The template for a lab round (docs/agents.md, rules 2, 5 and 7). The manager copies it, edits the brief and the
// limits, and runs `tools/run.sh workflow-check <script>` before the launch.
// The critic's model is a per-launch arg with no default (docs/decisions/2026-10-08-art-critic-model-ab.md). With
// control_model, two critics with the same prompt rank the same contact sheet, both critiques are returned, and a
// blind judge rules each remark; the result's ab_record is what `tools/run.sh ab-tally` reads. The script writes no
// file of its own: the manager (or a writer step) saves ab_record as <out_dir>/ab-judge.json.

const MAX_STEPS = 4;
const MODELS = ['opus', 'sonnet', 'haiku']; // the shared list of prime-game's model guard; no default is chosen here
const SEVERITIES = ['serious', 'minor'];
const AB_RECORD_SCHEMA = 'art-critic-ab/1';

const RULES = `RULES (CLAUDE.md applies; these are the ones this round needs):
- WAIT RULE: no tool call blocks over 180 s. Blender, Godot and any run that may pass 180 s go to the background
  (run_in_background, \`<command> > <log> 2>&1; echo "exit=$?" >> <log>\`, the log in the lab folder); check its tail
  with short calls, with gaps of at most 180 s; no tail -f, no sleep loops, one run at a time.
- Quiet runs: read only a log's tail; grep it only on failure. Read large files by line range.
- Write only in the lab folder and the output folder. Nothing is committed; the raw folder is never deleted from or
  overwritten outside the lab folder.
- Python: standard library only; in Git Bash use $PYTHON_BIN. Blender only as blender -b through tools/runner.
- Images for agents are contact sheets of about 1280 px on the long side, one sheet per question.
- Tune a parameter with one grid run (one table, one sheet), not a render-and-look loop.`;

const HANDOFF_SCHEMA = {
  type: 'object',
  properties: {
    handoff_path: { type: 'string', description: 'Absolute path of the handoff note this step wrote.' },
    done: { type: 'boolean', description: 'True when every variant of the brief exists and the contact sheet is made.' },
    contact_sheet: { type: 'string', description: 'Absolute path of the contact sheet (about 1280 px), or empty.' },
    variants: { type: 'array', items: { type: 'string' }, description: 'The variant ids built so far.' },
  },
  required: ['handoff_path', 'done', 'contact_sheet', 'variants'],
};

const RANKING_SCHEMA = {
  type: 'object',
  properties: {
    ranking: {
      type: 'array',
      items: {
        type: 'object',
        properties: { variant: { type: 'string' }, reason: { type: 'string' } },
        required: ['variant', 'reason'],
      },
      description: 'Every variant, best first, each with a one-line reason.',
    },
    recommendation: { type: 'string', description: 'The variant to show the engineer first, and why, in two lines.' },
    remarks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          variant: { type: 'string' },
          remark: { type: 'string', description: 'One problem, in one line.' },
          severity: { type: 'string', enum: SEVERITIES },
        },
        required: ['variant', 'remark', 'severity'],
      },
      description: 'Every problem the critic sees, one per item.',
    },
    ranking_path: { type: 'string', description: 'Absolute path of the ranking note the critic wrote.' },
  },
  required: ['ranking', 'recommendation', 'remarks', 'ranking_path'],
};

const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'The remark id, such as A3.' },
          verdict: { type: 'string', enum: ['valid', 'invalid', 'unsure'] },
          severity: { type: 'string', enum: SEVERITIES, description: 'The severity the judge would give.' },
          reason: { type: 'string', description: 'One line: what on the sheet or in the files decides it.' },
        },
        required: ['id', 'verdict', 'severity', 'reason'],
      },
      description: 'One verdict for every remark of both critiques.',
    },
    pairs: {
      type: 'array',
      items: {
        type: 'object',
        properties: { a: { type: 'string' }, b: { type: 'string' } },
        required: ['a', 'b'],
      },
      description: 'Pairs of an A remark id and a B remark id that name the same problem.',
    },
  },
  required: ['verdicts', 'pairs'],
};

function builderPrompt(brief, labDir, outDir, step, steps, previous) {
  const from = previous
    ? `Continue from the previous step's handoff note: read ${previous} first, and only the files it names.`
    : 'This is the first step: start from the brief.';
  return `You build step ${step} of at most ${steps} of a lab round of prime-game-art (Windows laptop, Git Bash).
BOUNDS: at most 60 tool calls; stop earlier at the natural end of the round.
Lab folder: ${labDir}. Output folder: ${outDir}.
${from}

BRIEF:
${brief}

When the variants exist, render one contact sheet of every variant side by side with its id under it (about 1280 px on
the long side) to ${outDir}/contact-sheet.png.

END OF THE STEP: at about 50 calls (the handoff note must fit inside the bound), or when the round is done, write the handoff note ${outDir}/handoff-step-${step}.md
(done, next, files, open problems; short) and return it. The next step reads only that note.

${RULES}`;
}

function criticPrompt(brief, handoff, sheet, rankingPath) {
  return `You are the critic of a lab round of prime-game-art. You only read; the one file you write, through the shell, is the ranking below.
BOUNDS: at most 20 tool calls.
Read the builder's last handoff note ${handoff}, then look once at the contact sheet ${sheet} (about 1280 px).
Judge the variants against the brief below; rank every variant best first, one line of reason each, and recommend
the one to show the engineer first. List every problem you see as a remark: the variant, the problem in one line, and
its severity: serious when the engineer would reject the variant for it or it decides the ranking, else minor.
Write the ranking and the remarks to ${rankingPath} and return them.

BRIEF:
${brief}

${RULES}`;
}

function judgePrompt(brief, handoff, sheet, critiques) {
  return `You are the judge of two anonymous critiques, A and B, of one lab round of prime-game-art. You only read and write no file.
BOUNDS: at most 30 tool calls.
Read the builder's last handoff note ${handoff}, then look once at the contact sheet ${sheet} (about 1280 px); a
full-resolution crop of one variant is fine when a remark turns on a detail. Read nothing about who wrote A or B (no
ranking-*.md, no docs/decisions) and do not guess it.
For every remark of both critiques give a verdict: valid (the problem is there, or the variant fails the brief as
said), invalid (it is not there, or the remark is wrong about the brief), unsure (the sheet and the files cannot tell);
give the severity you would give (serious when the engineer would reject the variant for it or it decides the
ranking, else minor) and one line of reason. Then pair each A remark with the B remark that names the same problem in
the same variant, if any (each remark in at most one pair). Return the verdicts and the pairs.

BRIEF:
${brief}

THE CRITIQUES (JSON):
${critiques}

${RULES}`;
}

function remarksOf(label, crit) {
  return (crit.remarks || []).map((r, i) => ({
    id: `${label}${i + 1}`,
    side: label,
    variant: r.variant,
    text: r.remark,
    critic_severity: r.severity,
  }));
}

function cleanPairs(pairs, ids) {
  // Each pair as {a: 'A<n>', b: 'B<n>'} with known ids, each id in one pair at most (the first one wins).
  const used = new Set();
  const out = [];
  for (const p of pairs || []) {
    const [a, b] = String(p.a).startsWith('B') ? [p.b, p.a] : [p.a, p.b];
    if (ids.has(a) && ids.has(b) && a.startsWith('A') && b.startsWith('B') && !used.has(a) && !used.has(b)) {
      used.add(a);
      used.add(b);
      out.push({ a, b });
    }
  }
  return out;
}

async function critique(label, model, handoff, sheet, rankingPath) {
  /* per-launch-model: the manager passes the critic's and the control's model per launch (#46, the model guard); the script checks them against MODELS */
  const result = await agent(criticPrompt(brief, handoff, sheet, rankingPath), {
    label: label ? `critic ${label}` : 'critic',
    phase: 'critique',
    schema: RANKING_SCHEMA,
    model,
    effort: 'high',
    agentType: 'art-reader',
  });
  return result;
}

const brief = args && args.brief;
const labDir = args && args.lab_dir;
const outDir = args && args.out_dir;
if (!brief || !labDir || !outDir) {
  throw new Error('art-lab-round needs args brief, lab_dir and out_dir');
}
const criticModel = args.critic_model;
const controlModel = args.control_model || null;
if (!MODELS.includes(criticModel)) {
  throw new Error(`art-lab-round needs arg critic_model, one of ${MODELS.join(', ')}: the manager passes it per launch`);
}
if (controlModel !== null && (!MODELS.includes(controlModel) || controlModel === criticModel)) {
  throw new Error(`control_model must be one of ${MODELS.join(', ')} and differ from critic_model`);
}
const round = Number(args.round);
if (controlModel !== null && !(Number.isInteger(round) && round >= 1)) {
  throw new Error('with control_model, art-lab-round needs arg round (the trial round number, 1, 2, ...)');
}
const steps = Math.min(Math.max(Number(args.steps) || 2, 1), MAX_STEPS);

const handoffs = [];
let last = null;
for (let step = 1; step <= steps; step += 1) {
  last = await agent(builderPrompt(brief, labDir, outDir, step, steps, last && last.handoff_path), {
    label: `builder step ${step}`,
    phase: 'build',
    schema: HANDOFF_SCHEMA,
    model: 'opus',
    effort: 'high',
    agentType: 'art-writer',
  });
  handoffs.push(last.handoff_path);
  if (last.done) {
    break;
  }
}

if (!last || !last.contact_sheet) {
  return { handoffs, ranking: null, note: 'the builder made no contact sheet; read the last handoff note' };
}

const handoff = last.handoff_path;
const sheet = last.contact_sheet;
if (controlModel === null) {
  const verdict = await critique('', criticModel, handoff, sheet, `${outDir}/ranking.md`);
  return { handoffs, contact_sheet: sheet, critic_model: criticModel, ...verdict };
}

// The A/B: the trial critique is A on odd rounds and B on even ones, so a position bias of the judge falls on both.
const trialLabel = round % 2 === 1 ? 'A' : 'B';
const controlLabel = trialLabel === 'A' ? 'B' : 'A';
const modelOf = { [trialLabel]: criticModel, [controlLabel]: controlModel };
const [critA, critB] = await Promise.all([
  critique('A', modelOf.A, handoff, sheet, `${outDir}/ranking-A.md`),
  critique('B', modelOf.B, handoff, sheet, `${outDir}/ranking-B.md`),
]);
const remarks = [...remarksOf('A', critA), ...remarksOf('B', critB)];
const blind = {};
for (const [label, crit] of [['A', critA], ['B', critB]]) {
  blind[label] = {
    ranking: crit.ranking,
    recommendation: crit.recommendation,
    remarks: remarks
      .filter((r) => r.side === label)
      .map((r) => ({ id: r.id, variant: r.variant, remark: r.text, severity: r.critic_severity })),
  };
}
/* opus-reader: the A/B's judge only reads, and runs on Opus, not on the model under trial (docs/decisions/2026-10-08-art-critic-model-ab.md) */
const judged = await agent(judgePrompt(brief, handoff, sheet, JSON.stringify(blind, null, 2)), {
  label: 'judge',
  phase: 'judge',
  schema: JUDGE_SCHEMA,
  model: 'opus',
  effort: 'high',
  agentType: 'art-reader',
});

const byId = {};
for (const v of judged.verdicts || []) {
  byId[v.id] = v;
}
const ab_record = {
  schema: AB_RECORD_SCHEMA,
  round,
  labels: { [trialLabel]: 'trial', [controlLabel]: 'control' },
  models: { trial: criticModel, control: controlModel, judge: 'opus' },
  recommendations: { A: critA.recommendation, B: critB.recommendation },
  remarks: remarks.map((r) => {
    const v = byId[r.id];
    return v
      ? { ...r, verdict: v.verdict, severity: v.severity, reason: v.reason, judged: true }
      : { ...r, verdict: 'unsure', severity: r.critic_severity, reason: '(the judge returned no verdict)', judged: false };
  }),
  pairs: cleanPairs(judged.pairs, new Set(remarks.map((r) => r.id))),
  cost_usd: null,
};

return {
  handoffs,
  contact_sheet: sheet,
  critiques: { A: critA, B: critB },
  ab_record,
  note: `save ab_record as ${outDir}/ab-judge.json, fill its cost_usd {trial, control, judge} from tools/run.sh cost, then run tools/run.sh ab-tally`,
};
