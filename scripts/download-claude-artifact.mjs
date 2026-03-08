#!/usr/bin/env node
// Download and summarize a claude-execution artifact from a GitHub Actions run.
// Usage: node scripts/download-claude-artifact.mjs <RUN_ID>

import { execSync } from "child_process";
import { readFileSync, existsSync, unlinkSync } from "fs";

const runId = process.argv[2];
if (!runId) {
  console.error("Usage: node scripts/download-claude-artifact.mjs <RUN_ID>");
  process.exit(1);
}

const outputFile = "claude-execution-output.json";

if (existsSync(outputFile)) {
  unlinkSync(outputFile);
}

console.log(`Downloading claude-execution artifact from run ${runId}...`);
try {
  execSync(`gh run download ${runId} -n claude-execution -D .`, {
    stdio: "inherit",
  });
} catch {
  console.error("Failed to download artifact. Check that the run ID is correct and the artifact exists.");
  process.exit(1);
}

if (!existsSync(outputFile)) {
  console.error(`Expected ${outputFile} not found after download.`);
  process.exit(1);
}

const data = JSON.parse(readFileSync(outputFile, "utf-8"));
const result = data.find((item) => item.type === "result");

if (!result) {
  console.log("No result event found in trace.");
  process.exit(0);
}

const denials = result.permission_denials ?? [];

console.log("\n=== Claude Execution Summary ===");
console.log(`num_turns:          ${result.num_turns}`);
console.log(`total_cost_usd:     $${result.total_cost_usd?.toFixed(4)}`);
console.log(`permission_denials: ${denials.length}`);

if (denials.length > 0) {
  console.log("\nDenied commands:");
  for (const d of denials) {
    const cmd = d.tool_input?.command ?? `[${d.tool_name}]`;
    console.log(`  - ${cmd}`);
  }
}

console.log("\nResult (first 500 chars):");
console.log(result.result?.slice(0, 500) ?? "(empty)");
