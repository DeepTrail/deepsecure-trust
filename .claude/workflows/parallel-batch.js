/**
 * parallel-batch.js — Dynamic Workflow for intra-batch parallel task execution
 *
 * Spawns afk-implementer subagents in isolated worktrees to execute independent
 * tasks within a wave concurrently. Collects results and reports back.
 *
 * Usage (invoked by ralph.sh or manually):
 *   claude workflow run .claude/workflows/parallel-batch.js \
 *     --input '{"workstream":"my-feature","batch":"P1-B1","wave":2,"tasks":["WS-A1","WS-A2"]}'
 */

const REPO_ROOT = "/Users/imaxxs/repositories/deepsecure-mvp";

async function run({ workstream, batch, wave, tasks }) {
  if (!workstream || !batch || !wave || !tasks?.length) {
    return {
      error: "Required: workstream, batch, wave, tasks[]",
      usage:
        'parallel-batch.js --input \'{"workstream":"x","batch":"P0-B1","wave":1,"tasks":["WS-A1"]}\'',
    };
  }

  const results = [];
  const startTime = Date.now();

  console.log(
    `[parallel-batch] Starting wave ${wave} of ${batch}: ${tasks.length} tasks`
  );

  // Spawn subagents for each task — Claude Code handles worktree isolation
  const promises = tasks.map(async (taskId) => {
    const ticketGlob = `docs/workstreams/${workstream}/tasks/${taskId}-*.md`;
    const specPath = `docs/workstreams/${workstream}/specs/${taskId}-spec.md`;

    const prompt = [
      `You are executing task ${taskId} for the ${workstream} workstream.`,
      "",
      "CONTEXT:",
      `- Main repo: ${REPO_ROOT}`,
      `- Feature: ${workstream}`,
      `- Task ID: ${taskId}`,
      `- Task ticket: ${ticketGlob}`,
      `- Task spec: ${specPath}`,
      "",
      "INSTRUCTIONS:",
      "1. Read the task ticket and spec",
      "2. Implement the code as specified",
      "3. Run lints on all modified files",
      "4. Run tests as specified in the ticket",
      "5. Verify all acceptance criteria",
      `6. Create completion report at docs/workstreams/${workstream}/reports/${taskId}-completion.md`,
      "7. Return a JSON summary with: taskId, status, filesModified, testResults",
    ].join("\n");

    try {
      const result = await claude({
        agent: "afk-implementer",
        prompt,
        isolation: "worktree",
        maxBudgetUsd: 5,
      });

      return {
        taskId,
        status: "complete",
        result: result?.summary || "Task completed",
        duration: Date.now() - startTime,
      };
    } catch (err) {
      return {
        taskId,
        status: "failed",
        error: err.message || String(err),
        duration: Date.now() - startTime,
      };
    }
  });

  const settled = await Promise.allSettled(promises);

  for (const outcome of settled) {
    if (outcome.status === "fulfilled") {
      results.push(outcome.value);
    } else {
      results.push({
        taskId: "unknown",
        status: "failed",
        error: outcome.reason?.message || String(outcome.reason),
      });
    }
  }

  const completed = results.filter((r) => r.status === "complete").length;
  const failed = results.filter((r) => r.status === "failed").length;
  const totalDuration = Date.now() - startTime;

  console.log(
    `[parallel-batch] Wave ${wave} done: ${completed}/${tasks.length} complete, ${failed} failed (${Math.round(totalDuration / 1000)}s)`
  );

  return {
    workstream,
    batch,
    wave,
    totalTasks: tasks.length,
    completed,
    failed,
    durationMs: totalDuration,
    results,
  };
}

module.exports = { run };
