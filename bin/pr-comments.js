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
    shell: process.platform === "win32",
  });
}

function missing(result) {
  return Boolean(result.error) || result.status === 127;
}

let result = run("uv", ["run", "--project", root, "pr-comments", ...args]);
if (missing(result)) {
  const pythons = process.platform === "win32" ? ["python", "py", "python3"] : ["python3", "python"];
  result = { status: 1 };
  for (const python of pythons) {
    const attempt = run(python, ["-m", "pr_comments", ...args]);
    if (!missing(attempt)) {
      result = attempt;
      break;
    }
  }
}

process.exit(result.status == null ? 1 : result.status);
