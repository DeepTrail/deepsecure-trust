/**
 * Demo data extraction / validation script.
 *
 * Validates all 6 scene JSON data files in src/data/demo/
 * against the SceneData interface.
 *
 * Usage: npx tsx scripts/extract-demo-data.ts
 */

import { readFileSync, readdirSync } from "fs";
import { resolve } from "path";

interface SceneStep {
  id: string;
  label: string;
  description: string;
  actor: string;
  action: string;
  result?: string;
  metadata?: Record<string, unknown>;
}

interface SceneData {
  sceneId: string;
  title: string;
  description: string;
  steps: SceneStep[];
}

const DATA_DIR = resolve(__dirname, "../src/data/demo");

const EXPECTED_FILES = [
  "sso-login.json",
  "service-connection.json",
  "agent-registration.json",
  "delegation.json",
  "mcp-tool-call.json",
  "audit-review.json",
];

function validate(): void {
  const errors: string[] = [];
  const jsonFiles = readdirSync(DATA_DIR).filter((f) => f.endsWith(".json"));

  for (const expected of EXPECTED_FILES) {
    if (!jsonFiles.includes(expected)) {
      errors.push(`Missing file: ${expected}`);
    }
  }

  let totalSteps = 0;

  for (const file of EXPECTED_FILES) {
    const filePath = resolve(DATA_DIR, file);
    try {
      const raw = readFileSync(filePath, "utf-8");
      const data: SceneData = JSON.parse(raw);

      if (!data.sceneId) errors.push(`${file}: missing sceneId`);
      if (!data.title) errors.push(`${file}: missing title`);
      if (!data.description) errors.push(`${file}: missing description`);
      if (!data.steps || data.steps.length === 0) {
        errors.push(`${file}: no steps defined`);
      } else {
        for (const step of data.steps) {
          if (!step.id) errors.push(`${file}: step missing id`);
          if (!step.label) errors.push(`${file}: step ${step.id}: missing label`);
          if (!step.actor) errors.push(`${file}: step ${step.id}: missing actor`);
          if (!step.action) errors.push(`${file}: step ${step.id}: missing action`);
        }
        totalSteps += data.steps.length;
      }
    } catch (e) {
      errors.push(`${file}: ${e instanceof Error ? e.message : "parse error"}`);
    }
  }

  if (errors.length > 0) {
    console.error("Validation failed:");
    errors.forEach((e) => console.error(`  - ${e}`));
    process.exit(1);
  }

  console.log(
    `✅ Demo data valid: ${EXPECTED_FILES.length} scenes, ${totalSteps} total steps`
  );
  console.log(`   Files: ${EXPECTED_FILES.join(", ")}`);
}

validate();
