#!/usr/bin/env node
// Bumps the extension version and packages a fresh .vsix.
// Usage: node scripts/package.mjs [major|minor|patch]   (default: patch)
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const pkgPath = join(root, "package.json");

const part = process.argv[2] || "patch";
const order = ["major", "minor", "patch"];
if (!order.includes(part)) {
  console.error("Usage: node scripts/package.mjs [major|minor|patch]");
  process.exit(1);
}

const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
const [major, minor, patch] = pkg.version.split(".").map(Number);
let next;
if (part === "major") next = `${major + 1}.0.0`;
else if (part === "minor") next = `${major}.${minor + 1}.0`;
else next = `${major}.${minor}.${patch + 1}`;

pkg.version = next;
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
console.log(`Bumped version -> ${next}`);

console.log("Building .vsix (runs vscode:prepublish -> compile) ...");
execFileSync("npx", ["vsce", "package"], { cwd: root, stdio: "inherit" });
console.log(`\nDone: vscode-workflow-runner-${next}.vsix`);
