/**
 * adversarial-review.js — Dynamic Workflow for adversarial diff review
 *
 * Spawns an afk-verifier subagent to review diffs produced by afk-implementer.
 * Flags quality issues, missing tests, security concerns, and scope creep.
 *
 * Usage:
 *   claude workflow run .claude/workflows/adversarial-review.js \
 *     --input '{"workstream":"my-feature","taskId":"WS-A1","diffBase":"HEAD~1"}'
 */

const REPO_ROOT = "/Users/imaxxs/repositories/deepsecure-mvp";

async function run({ workstream, taskId, diffBase, files }) {
  if (!workstream || !taskId) {
    return {
      error: "Required: workstream, taskId",
      usage:
        'adversarial-review.js --input \'{"workstream":"x","taskId":"WS-A1"}\'',
    };
  }

  const base = diffBase || "HEAD~1";
  const startTime = Date.now();

  console.log(`[adversarial-review] Reviewing ${taskId} (diff from ${base})`);

  const fileList = files?.length
    ? `Focus on these files: ${files.join(", ")}`
    : "Review all files changed in the diff.";

  const prompt = [
    `You are reviewing the implementation of task ${taskId} for the ${workstream} workstream.`,
    "",
    "CONTEXT:",
    `- Repo: ${REPO_ROOT}`,
    `- Diff base: ${base}`,
    `- Task ticket: docs/workstreams/${workstream}/tasks/${taskId}-*.md`,
    `- Task spec: docs/workstreams/${workstream}/specs/${taskId}-spec.md`,
    "",
    `${fileList}`,
    "",
    "REVIEW INSTRUCTIONS:",
    "1. Read the task ticket and spec to understand requirements",
    `2. Run: git diff ${base} -- . to see all changes`,
    "3. For each changed file, check:",
    "   a. Does the change match the task description? Flag anything unexplained.",
    "   b. Are there missing tests? Every new function/class needs at least one test.",
    "   c. Security concerns: hardcoded secrets, injection, path traversal.",
    "   d. Is the change minimal? Flag unnecessary refactoring or formatting.",
    "   e. Are all acceptance criteria from the ticket met?",
    "4. Return a JSON review with:",
    '   - verdict: "approve" | "request-changes" | "block"',
    "   - findings: [{severity, file, line, description}]",
    "   - summary: one-paragraph assessment",
    "",
    "SEVERITY LEVELS:",
    '- "critical": Security issue, data loss risk, or acceptance criterion not met',
    '- "major": Missing test, broken contract, or logic error',
    '- "minor": Style issue, naming, or documentation gap',
    '- "nitpick": Subjective preference, optional improvement',
  ].join("\n");

  try {
    const result = await claude({
      agent: "afk-verifier",
      prompt,
      isolation: "worktree",
      maxBudgetUsd: 3,
    });

    const duration = Date.now() - startTime;
    console.log(
      `[adversarial-review] Review of ${taskId} complete (${Math.round(duration / 1000)}s)`
    );

    return {
      taskId,
      workstream,
      status: "reviewed",
      review: result?.summary || "Review complete",
      durationMs: duration,
    };
  } catch (err) {
    return {
      taskId,
      workstream,
      status: "review-failed",
      error: err.message || String(err),
      durationMs: Date.now() - startTime,
    };
  }
}

module.exports = { run };
