// Tests of packet.mjs, each in a git repo of its own with the repo's review
// config and prompt, and a stand-in for gitleaks.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { PacketError, buildPacket } from "./packet.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
const PLAN =
  "# Plan\n\n## Phase 1\n\n```sh\n# not a heading\n```\n\nThe work.\n\n## Phase 2\n\nLater.\n";
// A token in GitHub's shape, which the stand-in scan finds as gitleaks would.
const TOKEN = "ghp_" + "aB3dE6gH9jK2mN5pQ8sT1vW4yZ7cF0hL3oR6";

// Answers as gitleaks does through spawnSync: 1 when the prompt holds a token.
function scanStandIn(prompt) {
  return prompt.includes(TOKEN)
    ? { status: 1, stdout: "a GitHub token\n" }
    : { status: 0, stdout: "" };
}

function repo(files) {
  const root = mkdtempSync(join(tmpdir(), "review-packet-"));
  const git = (...args) => execFileSync("git", args, { cwd: root });
  git("init", "-q", "-b", "main");
  git("config", "user.email", "test@example.com");
  git("config", "user.name", "Test");
  mkdirSync(join(root, "scripts"));
  copyFileSync(
    join(ROOT, "scripts/review-prompt.md"),
    join(root, "scripts/review-prompt.md"),
  );
  copyFileSync(
    join(ROOT, "review.config.yaml"),
    join(root, "review.config.yaml"),
  );
  writeFileSync(join(root, "PLAN.md"), PLAN);
  git("add", "-A");
  git("commit", "-q", "-m", "base");
  write(root, files);
  git("add", "-f", "-A");
  return root;
}

function write(root, files) {
  for (const [path, text] of Object.entries(files)) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    writeFileSync(join(root, path), text);
  }
}

function packet(root, options = {}, scan = scanStandIn) {
  return buildPacket(
    { unit: "Test", plan: "PLAN.md", section: ["Phase 1"], ...options },
    { cwd: root, scan },
  );
}

function refusal(build) {
  try {
    build();
  } catch (error) {
    assert.ok(error instanceof PacketError, error);
    return error.message;
  }
  assert.fail("the packet was built");
}

test("a staged change is in the packet", () => {
  const { prompt } = packet(repo({ "src/app.py": "print('hello')\n" }));
  assert.match(prompt, /print\('hello'\)/);
});

test("a planted secret stops the packet", () => {
  const root = repo({ "src/config.py": `TOKEN = "${TOKEN}"\n` });
  assert.match(
    refusal(() => packet(root)),
    /gitleaks found a secret/,
  );
});

test("with no gitleaks to run, the packet is refused", () => {
  const root = repo({ "src/app.py": "x = 1\n" });
  const missing = () => ({ error: new Error("spawnSync gitleaks ENOENT") });
  assert.match(
    refusal(() => packet(root, {}, missing)),
    /gitleaks didn't run/,
  );
});

test("excluded files are named but never shown, at any depth", () => {
  const { prompt } = packet(
    repo({
      ".env": "ROOT_VALUE=one\n",
      ".env.local": "LOCAL_VALUE=two\n",
      "deploy/.env": "NESTED_VALUE=three\n",
      "src/app.py": "x = 1\n",
    }),
  );
  assert.doesNotMatch(prompt, /ROOT_VALUE|LOCAL_VALUE|NESTED_VALUE/);
  assert.match(prompt, /A \.env \(excluded\)/);
  assert.match(prompt, /A deploy\/\.env \(excluded\)/);
});

test(".env.example is reviewed like any file", () => {
  const { prompt } = packet(repo({ ".env.example": "EXAMPLE_SETTING=\n" }));
  assert.match(prompt, /EXAMPLE_SETTING=/);
});

test("an excluded file can't be given as notes, checks or the plan", () => {
  const root = repo({ "src/app.py": "x = 1\n" });
  writeFileSync(join(root, ".env.local"), "LOCAL_VALUE=two\n");
  for (const option of ["notes", "checks", "plan"]) {
    assert.match(
      refusal(() => packet(root, { [option]: ".env.local" })),
      /is excluded from reviews/,
      option,
    );
  }
});

test("a file too large to inline stops the packet unless it is metadata only", () => {
  const large = "line of text\n".repeat(10_000);
  assert.match(
    refusal(() => packet(repo({ "src/big.txt": large }))),
    /too large to inline/,
  );
  const { prompt } = packet(repo({ "uv.lock": large }));
  assert.match(prompt, /A uv\.lock \(metadata only\)/);
});

test("a filename git would quote is reviewed", () => {
  const { prompt } = packet(repo({ "docs/café.md": "Bonjour\n" }));
  assert.match(prompt, /Bonjour/);
});

test("a heading inside a code fence doesn't end the plan's section", () => {
  const { prompt } = packet(repo({ "src/app.py": "x = 1\n" }));
  assert.match(prompt, /The work\./);
  assert.doesNotMatch(prompt, /Later\./);
});

test("a file with backticks can't close its own fence", () => {
  const root = repo({ "docs/guide.md": "Start\n" });
  execFileSync("git", ["commit", "-q", "-m", "guide"], { cwd: root });
  write(root, { "docs/guide.md": "Start\n```\nEnd\n" });
  execFileSync("git", ["add", "-A"], { cwd: root });
  const { prompt } = packet(root);
  assert.match(prompt, /\n````\nStart\n```\nEnd\n````/);
});

test("a dual-review path asks for both reviewers", () => {
  const { prompt, summary } = packet(repo({ "backend/auth.py": "x = 1\n" }));
  assert.match(prompt, /High-stakes: yes backend\/auth\.py/);
  assert.match(summary, /both reviewers/);
});

test("--base HEAD is refused", () => {
  const root = repo({ "src/app.py": "x = 1\n" });
  assert.match(
    refusal(() => packet(root, { base: "HEAD" })),
    /leave --base out/,
  );
});

test("context docs come from the reviewed tree, not the working copy", () => {
  const root = repo({ "docs/CODE_STANDARDS.md": "Staged standards\n" });
  write(root, {
    "docs/CODE_STANDARDS.md": "Unstaged draft\n",
    "docs/SPEC.md": "Untracked spec\n",
  });
  const { prompt } = packet(root);
  assert.match(prompt, /Staged standards/);
  assert.doesNotMatch(prompt, /Unstaged draft|Untracked spec/);
  assert.match(prompt, /### docs\/SPEC\.md\n\(not written yet\)/);
});

test("a link into an excluded folder can't be given as notes, checks or the plan", () => {
  const root = repo({ "src/app.py": "x = 1\n" });
  const config = join(root, "review.config.yaml");
  writeFileSync(
    config,
    readFileSync(config, "utf8").replace(
      /sealed: \[\]/,
      'sealed: ["sealed/**"]',
    ),
  );
  write(root, { "sealed/answers.md": "SEALED_ANSWER=yes\n" });
  // A junction on Windows needs no special rights; elsewhere it is a folder link.
  symlinkSync(join(root, "sealed"), join(root, "public"), "junction");
  for (const option of ["notes", "checks", "plan"]) {
    assert.match(
      refusal(() => packet(root, { [option]: "public/answers.md" })),
      /is excluded from reviews/,
      option,
    );
  }
});
