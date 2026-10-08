export const meta = {
  name: 'art-lab-round',
  description: 'One lab round of prime-game-art: an art-writer builder in steps of at most 60 calls, each ending in a handoff note, then one Sonnet art-reader critic that ranks the variants from one contact sheet and recommends one.',
  args: {
    brief: 'The round brief: goal, the variants to make, the acceptance checks (a few lines, no history).',
    lab_dir: 'The lab folder the builder works in, under D:/prime-art-raw/research/.',
    out_dir: 'The folder for handoff notes, the contact sheet and the ranking (inside lab_dir or the scratchpad).',
    steps: 'The most builder steps (1 to 4, default 2); a step that reports the round done ends the build early.',
  },
};

// The template for a lab round (docs/agents.md, rules 2, 5 and 7). The manager copies it, edits the brief and the
// limits, and runs `tools/run.sh workflow-check <script>` before the launch.

const MAX_STEPS = 4;

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
    ranking_path: { type: 'string', description: 'Absolute path of the ranking note the critic wrote.' },
  },
  required: ['ranking', 'recommendation', 'ranking_path'],
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

function criticPrompt(brief, outDir, handoff, sheet) {
  return `You are the critic of a lab round of prime-game-art. You only read; the one file you write, through the shell, is the ranking below.
BOUNDS: at most 20 tool calls.
Read the builder's last handoff note ${handoff}, then look once at the contact sheet ${sheet} (about 1280 px).
Judge the variants against the brief below; rank every variant best first, one line of reason each, and recommend
the one to show the engineer first. Write the ranking to ${outDir}/ranking.md and return it.

BRIEF:
${brief}

${RULES}`;
}

const brief = args && args.brief;
const labDir = args && args.lab_dir;
const outDir = args && args.out_dir;
if (!brief || !labDir || !outDir) {
  throw new Error('art-lab-round needs args brief, lab_dir and out_dir');
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

const verdict = await agent(criticPrompt(brief, outDir, last.handoff_path, last.contact_sheet), {
  label: 'critic',
  phase: 'critique',
  schema: RANKING_SCHEMA,
  model: 'sonnet',
  effort: 'high',
  agentType: 'art-reader',
});

return { handoffs, contact_sheet: last.contact_sheet, ...verdict };
