// Builds the inline prompt for an MVP-tier review (docs/REVIEW_PROTOCOL.md) from
// a git repo, and checks it with the secret scan it is given. The command line,
// scripts/review-packet.mjs, always gives it gitleaks; only the tests give it a
// stand-in.
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { basename, relative, resolve } from "node:path";
import { stripVTControlCharacters } from "node:util";
import picomatch from "picomatch";
import { parse } from "yaml";

const PROMPT = "scripts/review-prompt.md";
const CONFIG = "review.config.yaml";
// A file or diff larger than this can't be inlined. Unless the config lists it
// as metadata only, such as a lockfile, the packet isn't built.
const LARGEST_FILE = 100_000;
const BOTH =
  "This is one of two independent reviews; you will not see the other until both are filed.";
const ONE = "This is the only review of this unit.";

// Why a packet wasn't built.
export class PacketError extends Error {}

function fail(message) {
  throw new PacketError(message);
}

// The secret scan a real review runs.
export function gitleaks(prompt) {
  return spawnSync("gitleaks", ["stdin", "--no-banner", "--redact"], {
    input: prompt,
    encoding: "utf8",
  });
}

function checkOptions(options) {
  if (!options.unit || !options.plan || !options.section?.length) {
    fail("--unit, --plan and at least one --section are required");
  }
  if (options.base === "HEAD") {
    fail(
      "--base HEAD compares HEAD with itself; leave --base out to review what is staged",
    );
  }
}

// The repo the packet is built from: its git, its files and its review config.
function openRepo(cwd) {
  const git = (...args) =>
    execFileSync("git", args, {
      cwd,
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  const config = parse(readFileSync(resolve(cwd, CONFIG), "utf8"));
  const isExcluded = picomatch(Object.values(config.exclude_paths).flat(), {
    dot: true,
  });
  return {
    cwd,
    git,
    config,
    isExcluded,
    isMetadataOnly: picomatch(config.metadata_only ?? [], { dot: true }),
    isDual: picomatch(config.mvp_dual, { dot: true }),
  };
}

// Reads a file given as an option, refusing any the exclusions cover, by its path
// in the repo or by its name.
function readInput(repo, path) {
  const given = resolve(repo.cwd, path);
  // Checked as given and as what it really is, so a link can't bring in a file
  // the exclusions cover.
  const real = realpathSync(given);
  for (const name of [given, real]) {
    if (
      repo.isExcluded(relative(realpathSync(repo.cwd), name)) ||
      repo.isExcluded(relative(repo.cwd, name)) ||
      repo.isExcluded(basename(name))
    ) {
      fail(`${path} is excluded from reviews and can't be an input`);
    }
  }
  return readFileSync(real, "utf8");
}

// The base, the reviewed side and the git arguments that compare them.
function scope(repo, base) {
  const { git } = repo;
  if (!base) {
    return {
      kind: "staged",
      base: git("rev-parse", "HEAD").trim(),
      tree: git("write-tree").trim(),
      range: ["--cached", "HEAD"],
      read: (path) => git("show", `:${path}`),
      has: (path) => git("ls-files", "--cached", "--", path).trim() !== "",
    };
  }
  const from = git("merge-base", base, "HEAD").trim();
  return {
    kind: "whole_branch",
    base: from,
    tree: git("rev-parse", "HEAD^{tree}").trim(),
    range: [from, "HEAD"],
    read: (path) => git("show", `HEAD:${path}`),
    has: (path) =>
      git("ls-tree", "--name-only", "HEAD", "--", path).trim() !== "",
  };
}

// Every changed path with its status, read from NUL-separated output so that no
// filename is quoted or split.
function changesIn(repo, review) {
  const fields = repo
    .git("diff", "--name-status", "--no-renames", "-z", ...review.range)
    .split("\0");
  const changes = [];
  for (let index = 0; index + 1 < fields.length; index += 2) {
    changes.push({ status: fields[index], path: fields[index + 1] });
  }
  return changes;
}

// The text of a plan's section: from the heading that names it to the next
// heading of the same or a higher level, ignoring lines inside code fences.
function planSection(text, title) {
  const lines = text.split("\n");
  let inFence = false;
  const levels = lines.map((line) => {
    if (line.startsWith("```")) inFence = !inFence;
    return !inFence && /^#+ /.test(line) ? /^#+/.exec(line)[0].length : 0;
  });
  const start = lines.findIndex(
    (line, index) => levels[index] > 0 && line.includes(title),
  );
  if (start === -1) fail(`no heading in the plan names "${title}"`);
  const end = levels.findIndex(
    (level, index) => index > start && level > 0 && level <= levels[start],
  );
  return lines.slice(start, end === -1 ? undefined : end).join("\n");
}

// A code fence longer than any run of backticks in the text, so the text can't
// close it early.
function fenced(text, language = "") {
  const runs = [...text.matchAll(/`+/g)].map((run) => run[0].length);
  const fence = "`".repeat(Math.max(2, ...runs) + 1);
  return `${fence}${language}\n${text.trimEnd()}\n${fence}`;
}

// A context doc as it is in the reviewed tree, never the working copy, so the
// reviewer sees only what is under review.
function contextDoc(repo, review, doc) {
  if (repo.isExcluded(doc))
    fail(`${doc} is excluded from reviews and can't be an input`);
  return `### ${doc}\n${review.has(doc) ? review.read(doc).trimEnd() : "(not written yet)"}`;
}

// Each file's diff, with a note in place of a metadata-only file's.
function diffOf(repo, review, visible) {
  return visible
    .map((change) => {
      const text = repo.git(
        "diff",
        "--no-renames",
        ...review.range,
        "--",
        change.path,
      );
      if (repo.isMetadataOnly(change.path)) {
        return `# ${change.path}: metadata only (${String(text.length)} bytes of diff)\n`;
      }
      if (text.length > LARGEST_FILE) {
        fail(
          `the diff of ${change.path} is too large to inline; split the change or list it in metadata_only`,
        );
      }
      return text;
    })
    .join("");
}

// The modified files in full. A new file's diff already holds the whole file.
function touchedFiles(repo, review, visible) {
  return visible
    .filter(
      (change) => change.status === "M" && !repo.isMetadataOnly(change.path),
    )
    .map((change) => {
      const text = review.read(change.path);
      if (text.length > LARGEST_FILE)
        fail(`${change.path} is too large to inline in full`);
      return `### ${change.path}\n${fenced(text)}`;
    });
}

function inspectionGaps(repo, changes) {
  return changes
    .map((change) => {
      if (repo.isExcluded(change.path))
        return `${change.status} ${change.path} (excluded)`;
      if (repo.isMetadataOnly(change.path))
        return `${change.status} ${change.path} (metadata only)`;
      return "";
    })
    .filter(Boolean);
}

// The packet's prompt and a one-line summary of it, or a PacketError. The scan
// takes the prompt and answers as spawnSync does: error, status and stdout.
export function buildPacket(options, { cwd, scan }) {
  checkOptions(options);
  const repo = openRepo(cwd);
  const review = scope(repo, options.base);
  const changes = changesIn(repo, review);
  const visible = changes.filter((change) => !repo.isExcluded(change.path));
  const dual = changes
    .filter((change) => repo.isDual(change.path))
    .map((change) => change.path);
  const both = dual.length > 0 || review.kind === "whole_branch";
  const plan = readInput(repo, options.plan);
  const checks = options.checks
    ? stripVTControlCharacters(readInput(repo, options.checks))
    : "(none given)";

  const filled = {
    KIND: "Code",
    UNIT: options.unit,
    SCOPE_KIND: review.kind,
    BASE: review.base,
    TREE: review.tree,
    SNAPSHOT_PATH: "none: everything is inline",
    HIGH_STAKES: dual.length > 0 ? "yes" : "no",
    HIGH_STAKES_MATCHES: dual.join(", "),
    AUTHORSHIP: options.author ?? "Claude (implementer)",
    COVERAGE: "the whole change",
    DUAL_NOTE: both ? BOTH : ONE,
    INSPECTION_GAPS: inspectionGaps(repo, changes).join(", ") || "none",
    PLAN_SECTION: options.section
      .map((title) => planSection(plan, title))
      .join("\n\n"),
    CONTEXT_DOCS: repo.config.context_docs
      .map((doc) => contextDoc(repo, review, doc))
      .join("\n\n"),
    DIFF: fenced(diffOf(repo, review, visible), "diff"),
    TOUCHED_FILES: touchedFiles(repo, review, visible).join("\n\n") || "(none)",
    TEST_OUTPUT: fenced(checks),
    NOTES: options.notes ? readInput(repo, options.notes).trimEnd() : "none",
  };
  const prompt = readFileSync(resolve(cwd, PROMPT), "utf8")
    .replace(/^<!--.*-->\n/gm, "")
    .replace(/ <!--.*-->/g, "")
    .replace(
      /\{\{([A-Z_]+)\}\}/g,
      (_, name) => filled[name] ?? fail(`no value for ${name}`),
    );

  const scanned = scan(prompt);
  if (scanned.error) fail(`gitleaks didn't run: ${scanned.error.message}`);
  if (scanned.status !== 0)
    fail(`gitleaks found a secret; nothing written\n${scanned.stdout}`);

  const reviewers = both
    ? `both reviewers (${filled.HIGH_STAKES_MATCHES || "whole branch"})`
    : "one reviewer";
  return {
    prompt,
    summary: `${review.kind}, ${String(visible.length)} files, ${reviewers}, gitleaks clean`,
  };
}
