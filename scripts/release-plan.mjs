#!/usr/bin/env node
// Find the actions whose package version has no release tag yet.
//
// Each action is a workspace package; its version is the action's version and
// is released as the tag `<action>-v<version>`, with `<action>-v<major>` moved
// to it. Prints JSON to stdout:
//
//   { "releases": [{ "action", "version", "major", "tag", "majorTag", "image" }] }
//
// `image` is true when the action has a Dockerfile to publish. With
// GITHUB_OUTPUT set, also writes `releases` (the array) and `any` (true/false).
//
// Usage: node scripts/release-plan.mjs [--help]

import { execFileSync } from "node:child_process";
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

if (process.argv.includes("--help")) {
  console.error("usage: node scripts/release-plan.mjs\nPrints the actions with an untagged version as JSON.");
  process.exit(0);
}

const root = new URL("..", import.meta.url).pathname;

const workspace = readFileSync(join(root, "pnpm-workspace.yaml"), "utf8");
const dirs = [...workspace.matchAll(/^\s*-\s*"?([^"\n]+)"?\s*$/gm)].map((m) => m[1]);

const tags = new Set(
  execFileSync("git", ["tag", "--list"], { cwd: root, encoding: "utf8" }).split("\n").filter(Boolean),
);

const releases = [];
for (const dir of dirs) {
  const manifest = join(root, dir, "package.json");
  if (!existsSync(join(root, dir, "action.yml")) || !existsSync(manifest)) {
    console.error(`skipping ${dir}: needs action.yml and package.json`);
    continue;
  }
  const { name, version } = JSON.parse(readFileSync(manifest, "utf8"));
  if (name !== dir) {
    console.error(`${dir}/package.json is named ${name}; the name must match the directory`);
    process.exit(1);
  }
  const tag = `${name}-v${version}`;
  if (tags.has(tag)) continue;
  const major = version.split(".")[0];
  releases.push({
    action: name,
    version,
    major,
    tag,
    majorTag: `${name}-v${major}`,
    image: existsSync(join(root, dir, "Dockerfile")),
  });
}

console.log(JSON.stringify({ releases }, null, 2));

if (process.env.GITHUB_OUTPUT) {
  appendFileSync(
    process.env.GITHUB_OUTPUT,
    `releases=${JSON.stringify(releases)}\nany=${releases.length > 0}\n`,
  );
}
