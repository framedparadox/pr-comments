#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname, "..");
const args = process.argv.slice(2);
const env = {
  ...process.env,
  PR_COMMENTS_SKILLS_DIR: path.join(root, "skills"),
  PYTHONPATH: [path.join(root, "src"), process.env.PYTHONPATH]
    .filter(Boolean)
    .join(path.delimiter),
};

function run(command, commandArgs) {
  return spawnSync(command, commandArgs, {
    stdio: "inherit",
    env,
    cwd: process.cwd(),
  });
}

let result = run("uv", ["run", "--project", root, "pr-comments", ...args]);
if (result.error || result.status === 127) {
  result = run("python3", ["-m", "pr_comments", ...args]);
}

process.exit(result.status == null ? 1 : result.status);
