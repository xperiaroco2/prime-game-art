export const meta = { name: 'good', description: describe(), args: { brief: 'text' }, steps: [1, -2, true, null] };

// A fixture for test_workflow_check_*: passes every check.
const RULES = 'WAIT RULE: no tool call blocks over 180 s; long runs go to the background.';
const READER = { model: 'sonnet', agentType: 'art-reader' };

function builderPrompt(step) {
  return `Step ${step}.
BOUNDS: at most 60 tool calls; stop earlier at the natural end.
${RULES}`;
}

const built = await agent(builderPrompt(1), { label: 'builder', phase: 'build', model: 'opus', effort: 'high', agentType: 'art-writer' });
const verdict = await agent(`Rank it. BOUNDS: at most 20 tool calls. ${RULES}`, { label: 'critic', ...READER });
/* general-agent: needs the Artifact tool to publish the review page */
await agent('Publish. BOUNDS: at most 10 tool calls.', { label: 'publisher', model: 'sonnet' });
return { built, verdict, ratio: 4 / 2 };
