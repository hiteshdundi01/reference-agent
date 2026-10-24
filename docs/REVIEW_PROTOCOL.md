# Review protocol: GPT and Argon

Every AI engineering review and every delegated task (subagent) in this repo uses **GPT-6.1-Sol** (Codex CLI) or **Gemini 4 Argon** (Antigravity CLI), at **high** effort. No other model reviews or takes delegated work.

## 0. Tiers

**MVP tier (default during internal development).** Use it while the repo is internal: no real users, no real personal data, and no environment that external users can reach.

The build process:

- There is one build plan with a checklist for each phase, approved by the owner once. No sub-plan per phase.
- Each phase goes: implement → run the checks once → one review → targeted checks on any fixes → commit.
- The owner is asked only about material departures from the plan.

Review rules:

- **Reviewers:**
  - one eligible model per unit of work, alternating (independence rules in §2);
  - both models, independently, for the repo's dual-review triggers (`review.config.yaml → mvp_dual`) and the final whole-branch review.
- **Rounds:**
  - at most two;
  - round 2 only checks whether round 1's blockers were fixed and whether the fixes broke anything; it is not a fresh review;
  - if blockers remain after round 2, the owner adjudicates. A review is never approved automatically.
  - **The owner's standing exception:** when a round-2 blocker's fix is exactly what that reviewer prescribed and has been verified, one round 3 in the same session may check that blocker alone. Anything still blocked after it goes to the owner. The appendix's step 6 describes this.
- **What counts as a blocker:** a concrete bug, or a violated acceptance criterion from the plan. Everything else is a note.
- **Kept from the production tier:**
  - GPT/Argon only, fresh sessions, no self-review;
  - the verdict format (§6);
  - sanitized inputs, with no secrets, personal data or sealed data in prompts and a secret scan before each call. Internal development already has real API keys.
  - inline-only reviews: "Do NOT call any tools", with no tools that can change anything.
- **Record:** one short review note per unit in the status log (models, sessions, verdict, open notes).
- **Not used in this tier:** snapshot/payload binding, the record schema, the eligibility validator, the `commit-msg` hook and the bootstrap (§4–§8 machinery beyond sanitization).

**Production tier (§1–§8 in full).** Switch to it before the first real user or pilot participant is admitted, before real personal data is accepted, or before deploying to any environment reachable by external users, whichever comes first. This applies to so-called internal pilots too.

- Build and bootstrap the tooling (§5, §8) as the first production-tier unit.
- Run the release acceptance checks and the dual whole-branch review.
- The switch applies going forward only. Don't manufacture retrospective attestations for MVP-tier commits.

## 1. Scope

- **Covers:**
  - the code review of each unit of work (a plan phase), which is merge-blocking;
  - the whole-branch review before release;
  - design reviews of screenshots;
  - delegated work: research, label and fixture checks, adversarial-case drafting, plan and doc reviews.
- **Doesn't replace human approvals.** These stay human: whatever `review.config.yaml → human_approvals` lists for the product (e.g. domain-expert content review, safety or legal sign-off, licensing checks), plus owner adjudication (§6).
- **Engineering agents only.** It doesn't govern which models the product itself calls at runtime.
- **Delegates are read-only.** They return text, and the implementer applies it.

## 2. Authorship and independence

- **Authorship is recorded per contribution:** path or artifact, author family (`gpt | argon | other | human`), author session, and role (`implementer | delegate`). The implementer's own family and session are recorded too.
- **Fresh sessions.** Each review runs in a fresh session. Resuming it is allowed only to check fixes to that review's own findings.
- **No self-approval.**
  - A session never approves anything it authored.
  - A reviewer never approves a contribution from its own family, except under the dual-review rule below.
- **Eligibility and coverage are computed per artifact.**
  - **Routine change:** every contribution must be covered by a PASS from a model of a different family from its author.
    - If the implementer is GPT, Argon reviews, and vice versa.
    - If the implementer is neither, either may review.
    - Mixed authorship (e.g. a GPT implementer plus Argon-drafted fixtures) needs both models, each covering the other's contributions.
- **Dual review (§3):** needs one PASS from each family, each covering the whole change.
  - The PASS from the author's family must come from a fresh session that authored nothing in the change, with the authorship disclosed.
  - When the implementer is GPT or Argon, this is the normal case for every high-stakes change, not an exception.
- Records also disclose when a reviewer authored prompts, fixtures or tests used in what it reviews.

## 3. Which reviewer

- **Routine changes:** the minimum set of eligible reviewers that gives full coverage (§2). When both models are eligible for the whole change, alternate by default so neither model's blind spots dominate. Switch when the default is unavailable or ineligible. For UI work, one model may review the code and the other the screenshots.
- **High-stakes changes: both models, independently.** Neither sees the other's report until both are filed.
  - A change is high-stakes if it touches any path in any category of `review.config.yaml → high_stakes`, including excluded paths (§4).
  - That list must cover these categories, or the config must declare a category "not applicable" with a reason. Repos may add their own extra categories:
    - authentication and authorization;
    - privacy and personal-data handling;
    - deletion and retention;
    - safety policy;
    - payments;
    - security controls and secrets handling;
    - schema migrations;
    - release and evaluation gates;
    - the tests, thresholds, fixtures and deploy permissions of all of the above;
    - the review tooling itself (trigger list, hooks, shared security dependencies).
  - The trigger is the change, not the phase it happens in.
  - The **whole-branch review** before release is always dual.

## 4. What a reviewer gets (every channel sanitized)

- **Scope** (§7): base, reviewed tree and scope kind.
- **Snapshot:** a read-only export of the reviewed tree, identified by its tree id. It is built from that same tree and checked against it (contents and modes).
- **Context:**
  - the diff between base and reviewed tree;
  - the full touched files;
  - the docs in `review.config.yaml → context_docs`;
  - the plan section for the unit of work;
  - test/coverage output (or screenshots + brand guide).
- **Exclusions apply to every channel:** snapshot, both sides of the diff (so a secret deleted from the base doesn't leak), full files, test output, screenshots and follow-up prompts. The excluded set is `review.config.yaml → exclude_paths`:
  - secrets;
  - personal or production data;
  - **sealed data** (held-out evaluation sets, answer keys).
- **Excluded changes appear only as metadata:** path, change type and high-stakes match. They are recorded as inspection gaps. An excluded change on a high-stakes path also needs the human approval named for it in the config.
- **Secret scan:** every assembled prompt and the snapshot are scanned before each call. The scan is an extra layer; it never replaces path exclusion.
- **Sealed data never appears in any prompt.** Reviewers see only aggregate scores.
- **Instruction:** review as a strict senior engineer deciding whether to merge.

## 5. Qualifying reviews: isolation and identity

A review **qualifies** (it can satisfy the merge gate and earn a trailer) only if the evidence below is recorded. Otherwise it is **advisory**: kept in the record, never gating.

- **Enforced isolation:** launched by the review tooling (§8) at a version whose smoke tests pass. The tooling must ensure:
  - model-visible reads are confined to the snapshot at the OS level (container, bubblewrap or `sandbox-exec`), plus approved docs or web search for research;
  - inherited MCP servers/connectors, hooks, plugins, slash commands and unapproved tools are disabled, and nested delegation is off;
  - each CLI runs with a stripped environment and an isolated home/config holding only that CLI's own minimal auth.
- **Launcher identity evidence** for the requested model and effort. A model's self-report doesn't count.
  - **GPT:** the Codex run header (`model:`, `reasoning effort:`, `sandbox:`, `session id:`) must match the request.
  - **Argon:** `agy` exits with an error on an unrecognised model. Its `--log-file` must show `Resolving model gemini-4-argon-high` and `Propagating selected model override … label="Gemini 4 Argon (High)"` (the effort is part of the model id). The JSON gives `conversation_id`.
  - Missing or mismatched evidence makes the review `INCOMPLETE`. There is no silent substitution.
- **Tool-use evidence:** for inline-only reviews, the Argon transcript (`~/.gemini/antigravity-cli/brain/<conversation_id>/.system_generated/logs/transcript.jsonl`) must show zero `tool_calls`. For Codex, the run log must show no command executions outside the allowed read set.
- **Never** use `--dangerously-skip-permissions`.
- **Bootstrap exception:** it covers only the commits that create the review tooling itself, and it waives only the requirement that the tooling already be committed with its hook installed. It never waives isolation or identity.
  - The **uncommitted candidate tooling** must pass its smoke tests.
  - It then runs its own dual review under enforced isolation, with identity evidence, before it is committed.
  - The record sets `bootstrap.active: true`, with the candidate tooling's tree and the smoke-test result.
- **Hand-run reviews never qualify.** That holds during bootstrap too.

## 6. Output, failure and disagreement

- **Output contract:**
  - `VERDICT: PASS | BLOCK | INCOMPLETE`;
  - the scope inspected (base, tree, files, inspection gaps);
  - findings, each with an id, severity and file/line.
    A PASS with no findings is valid.
- **Dispositions:** every finding gets one: `open`, `fixed` (with commit), `disputed` (with reason), `closed_by_reviewer`, or adjudicated. A gate never passes with an open or disputed blocker.
- **Attempts:** every attempt is kept, including failed ones that never got a session id. A retry never erases one.
- **Failures:**
  - A failed, empty, malformed, truncated or wrong-model call gets one retry, then goes to the other model if it is eligible. Otherwise the commit is blocked. A review is never skipped.
  - In dual review, failover never replaces a missing family's PASS.
- **Disputes:**
  - A disputed blocking finding is closed by the same reviewer on its resumed session, or by **the project owner** (`review.config.yaml → owner`) adjudicating.
  - After two fix cycles in one unit of work, the dispute escalates to the owner. That never permits committing an unresolved blocker.
  - Adjudication decides whether a finding applies. It never substitutes for a required model review and never waives a failing safety, privacy or acceptance criterion.
  - When dual reviewers disagree on safety, privacy or security, the stricter finding stands until closed as above.
  - On other matters, the coding standards and then the simpler design guide the implementer's proposal; neither closes a correctness dispute by itself.

## 7. Scope, binding and record

**Scope kinds.** Each review is bound to one immutable `(base, tree)` pair.

| Kind                  | Base                                                                              | Reviewed tree                             |
| --------------------- | --------------------------------------------------------------------------------- | ----------------------------------------- |
| `staged`              | `HEAD`                                                                            | `git write-tree` of the index, taken once |
| `pr` / `whole_branch` | `git merge-base <target> HEAD`                                                    | `HEAD^{tree}`                             |
| `initial`             | the empty tree (`git hash-object -t tree /dev/null`, in the repo's object format) | `git write-tree`                          |
| `delta`               | the previously reviewed tree                                                      | the new tree                              |

**Single source.** The snapshot export, the review diff and the payload id are all derived from that one tree object, never from the live index.

**Payload id.**

- Computation: the git tree id of the reviewed tree with `review.config.yaml → attestation_paths` removed (review records only). It is computed in a temporary index: `read-tree <tree>` → remove attestation paths → `write-tree`.
- The id is platform-independent because it hashes git's stored objects.
- The status log carries no generated lines; it is hand-written and part of the payload.

**Record.**

- Each review writes `docs/reviews/<unit>-<n>.json` per `review-record.schema.json`. Records are sanitized and kept out of any production or personal-data store.
- Schema validity is necessary but not sufficient. The **eligibility validator** in the tooling decides qualification from all of the following:
  - identities and effort evidenced;
  - isolation enforced (or a valid bootstrap);
  - independence and coverage per §2;
  - both families present where required;
  - no truncation in a PASS;
  - no open or disputed blockers;
  - the payload id matches.

**Delta review.** Any change after a review needs a delta review.

**Commit trailer.** `Reviewed-by: <model> <session> PASS` (one per required family) is added only when the validator passes. The `commit-msg` hook recomputes the payload id from the staged index and rejects any trailer without a qualifying record for it.

## 8. Tooling (build first; it is high-stakes)

`scripts/review.mjs`, in cross-platform Node:

- **Launching:**
  - argument arrays only, no shell interpolation;
  - prompts sent on stdin, never argv: Codex `-`; for `agy`, `--input-format stream-json` with `--output-format stream-json` (smoke-test this);
  - `agy --json-schema` to enforce the output contract, plus `--disable-slash-commands` and `--log-file`;
  - the same timeout (900 seconds) for both CLIs;
  - images attached explicitly;
  - token/time budgets that report truncation rather than hiding it.
- **Components:**
  - config validator (category coverage or "not applicable", no remaining placeholders, globs that compile);
  - snapshot builder and channel sanitizer;
  - secret scan;
  - high-stakes matcher;
  - payload-id calculator;
  - evidence collector (Codex header, `agy` log and transcript);
  - record writer;
  - eligibility validator;
  - `commit-msg` hook (lefthook or husky).
- **Smoke tests:**
  - both CLIs return a valid verdict;
  - an unknown model fails;
  - a write in the snapshot fails;
  - a read of a credential outside the snapshot is refused;
  - an external mutation (e.g. via an MCP tool) is refused;
  - a planted secret blocks the call;
  - excluded content can't leak through the base side of a diff;
  - an Argon tool call is detected in the transcript;
  - a trailer without a qualifying record is rejected;
  - the payload id is identical on macOS, Linux and Windows.

## Appendix: running an MVP-tier review

These commands are run by hand. They are POSIX shell; on Windows, run them in Git Bash or WSL. They need `codex`, `agy` and `gitleaks` on `PATH`. `review-packet.mjs` refuses to build a prompt without gitleaks.

1. **Build the prompt.** `node scripts/review-packet.mjs --unit "Phase 3" --plan docs/PLAN.md --section "Phase 3" > review/prompt.md` writes the prompt from the files listed below, then scans it with gitleaks. It exits with an error, and writes nothing, if gitleaks finds anything.
   - `scripts/review-prompt.md`;
   - the plan section;
   - `context_docs`;
   - the diff against the base, with `exclude_paths` left out;
   - the touched files;
   - the last `npm run check` output, if `--checks <file>` is given;
   - the implementer's notes, if `--notes <file>` is given: choices the reviewer should judge, and anything not visible in the diff.

   `review/` is in `.gitignore`. With no `--base`, it reviews what is staged against `HEAD`. Add `--base main` for a whole-branch review, which compares `HEAD` with its merge base with `main`. Files in `metadata_only` (lockfiles) reach the reviewer as metadata only, and any other file too large to inline stops the packet.

2. **Pick the reviewers.** If any changed path matches `mvp_dual`, or this is the whole-branch review, use both. Otherwise use one, alternating with the last unit's.
3. **Run them, in fresh sessions.** When both run, run them at once, and neither sees the other's report.
   - GPT: `codex exec -m gpt-6.1-sol -c model_reasoning_effort="high" -s read-only --skip-git-repo-check --color never -C <empty dir> -o review/out_gpt.md - < review/prompt.md > review/log_gpt.txt 2>&1`
   - Argon: `agy -p "$(cat review/prompt.md)" --model gemini-4-argon-high --effort high --output-format json --print-timeout 900s --sandbox --disable-slash-commands --log-file review/log_argon.txt > review/out_argon.json`, then read `.response`.
   - Never `--dangerously-skip-permissions`.
4. **Check the evidence.** A missing or mismatched item makes the review INCOMPLETE.
   - Codex's log header shows `model: gpt-6.1-sol`, `reasoning effort: high` and `sandbox: read-only`, plus the session id.
   - Argon's log shows `Resolving model gemini-4-argon-high` and `label="Gemini 4 Argon (High)"`.
   - Argon's transcript (`~/.gemini/antigravity-cli/brain/<conversation_id>/.system_generated/logs/transcript.jsonl`) has no `tool_calls`.
5. **Fix, then go to round 2.** Resume the same session (`codex exec resume <session id> -` or `agy --conversation <id>`). Send only the dispositions and the fixed files, and ask the reviewer to check its blockers and any regressions.
6. **Round 3, by the owner's standing rule.** It applies only to a round-2 blocker whose fix is exactly what the reviewer prescribed and has been verified. Run one more round in the same session, checking only that blocker. Anything still blocked after that goes to the owner.
7. **Record it.** Add one line to `docs/STATUS.md`'s review log: the unit, the reviewers and their sessions, the verdicts by round, and any open notes.
