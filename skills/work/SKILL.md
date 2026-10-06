---
name: work
description: >-
  Take one GitHub, GitLab, or Jira issue, or a problem statement, through
  planning, implementation, tests, and up to three review rounds to an open
  PR or MR. Delegate coding and review when agents are available. Use as
  $work in Codex or /yavosh:work in Claude Code.
---

# work

You are the **coordinator**. Take **one** issue to an open, reviewed PR (GitHub)
or MR (GitLab) — "PR" below
means either. When agent delegation is available, assign implementation to a
**coder** and independent review to a **reviewer**. You alone change git and
forge state. When delegation is unavailable, implement and review directly;
report that the review was your own.

Your job is understanding the issue, designing the plan, judging the reviewer's
findings, and owning git state. Do not delegate the plan or finding triage.

## 0. Preconditions (check once, up front)

- `git rev-parse --git-dir` — is this a git repo?
- **Detect the forge** from `git remote -v`: GitHub uses `gh`; GitLab uses
  `git push` merge request options. Confirm GitHub auth with `gh auth status`.
  For GitLab, check whether a push is authorized before publishing.
  - **Authorized forge access** → full path: branch → commit → PR.
  - **No forge access** → degraded path: branch → commit, no PR.
    Say so up front.
- `git status` — note pre-existing dirt. **Shared checkout hazard:** other
  agent sessions may share this checkout — ignore stray files/dirs that aren't
  yours. Never stage them: add your own files by name, never `git add -A`/`.`.
- You are the **only** writer of git state. Subagents get code and context, not
  commit/PR authority.
- **Resolve the conventions, project and global.** Read `CLAUDE.md` / `AGENTS.md` /
  `CONTEXT.md` at the repo root, every style doc they point at
  (`docs/code-style.md`, `CONTRIBUTING.md`, a `docs/style/` dir — whatever the
  repo names), and the active agent's global directives (for example,
  `~/.claude/CLAUDE.md` or Codex instructions). Follow their imports. Record the
  paths for the coder and reviewer. If no such doc exists, use surrounding code.
- **Extract the directives the linter cannot see** from those files, and record
  them for the review. Three kinds recur:
  - **Documentation** — which docs must move with a behaviour change (a repo
    often names them: `README.md`, `CLAUDE.md`, a config example), and the
    house doc style.
  - **Comments** — density, length, and what a comment is for.
  - **Everything else stated as a rule** — naming, error strings, banned
    APIs, branch naming, commit format, attribution trailers, draft-vs-ready
    PRs, "ask before push", scope limits. Steps 5, 7 and 9 defer to what you
    record here.

## 1. Resolve the issue

Parse the invocation argument:
- `#N` or a forge issue URL → use the available forge tool or connector to read
  the issue and comments (`gh issue view <N> --json number,title,body,labels,comments`
  on GitHub). If none is available, ask for the issue text. The real
  reproduction is often there, not in the body.
- A Jira key (`ABC-123`) or Jira URL → fetch it through the Atlassian MCP
  tools if configured (`getJiraIssue`); otherwise ask the human to paste the
  text. Record the key: it goes in the branch name, commit subject, and PR title
  if the repo's conventions say so.
- Anything else → treat the argument as the problem statement verbatim.
- No argument → ask the human what to work on. Do not guess.

Record the **issue key** (`#N`, `ABC-123`, or none) — steps 5, 7 and 9 use it.

Restate the issue in your own words in one or two sentences, including what you
believe the **observable wrong behaviour** is (or the wanted new behaviour). If
you cannot state that, the issue is under-specified — ask before you spend a
subagent on it.

## 2. Triage — pick the class

Classify as exactly one. The class drives the plan, the gates, and the review.

| Class | Looks like | Plan must include | Review weights |
|---|---|---|---|
| **security** | vulnerability, bypass, injection, auth gap, resource exhaustion, leak | the attacker model, and a test that fails before the fix | security ≫ regression > stability |
| **bug** | wrong output, crash, race, regression from working behaviour | a failing test that reproduces it first | regression ≈ stability > security |
| **feature** | new capability, new flag, new endpoint | the interface (signature/flag/route), and the default-off path staying byte-identical | regression > stability > security |

Two guards:
- **Under-specified feature** — if the issue asks for a capability but does not
  fix the interface, do not invent one silently. State the interface you chose
  and why, then continue.
- **Escalate-on-sight** — if the fix is inherently high-blast-radius or is a
  product decision (auth model, DB migration semantics, DNS, prod deploy,
  "should this be public?"), say so **now**. You may still implement it, but say
  in the final report that a human must decide before merge.

## 3. Design the plan — you, not a subagent

Read the relevant code yourself. Delegate broad searches when useful, but read
the files the fix will touch yourself.

Write a plan with:
- **Root cause** — the mechanism, at `file:line`. For a feature, the insertion
  point instead.
- **Change set** — each file, and what changes in it, including the docs the
  repo requires for a change of this kind. Surgical: only what the issue
  requires.
- **Tests** — the specific test that fails now and passes after, and the edge
  cases around it.
- **Non-goals** — adjacent things you noticed and will *not* fix. Name them; they
  go in the report.
- **Risk** — what could break, and which existing test covers it.

Print the plan before implementation — visible, not a blocking approval;
the human can interrupt. Keep it short — this is a work plan, not a design doc.

## 4. Detect the gates

Detect the toolchain from what is in the repo, and use its native commands. All
of these must pass before you commit:

| Marker | Format | Lint | Test | Build |
|---|---|---|---|---|
| `go.mod` | `goimports -w .` / `gofmt -w .` | `golangci-lint run ./...` or `go vet ./...` | `go test ./... -race` | `go build ./...` |
| `*.sln` / `*.csproj` / `Directory.Build.props` | `dotnet format <sln>` (check: `--verify-no-changes`) | analyzers run inside `dotnet build`; `dotnet format analyzers <sln>` if `.editorconfig` enables them | `dotnet test <sln>` (`--filter` for the CI's unit/integration split) | `dotnet build <sln> -warnaserror` if CI does, else `dotnet build <sln>` |
| `package.json` | `prettier --write` (if configured) | `npm run lint` | `npm test` | `npm run build` / `tsc --noEmit` |
| `pyproject.toml` | `ruff format` / `black` | `ruff check` / `flake8` | `pytest` | `mypy` (if configured) |
| `Cargo.toml` | `cargo fmt` | `cargo clippy -- -D warnings` | `cargo test` | `cargo build` |
| `pom.xml` / `build.gradle(.kts)` | `spotless:apply` / `spotlessApply` (if configured) | `checkstyle` / `detekt` (if configured) | `mvn test` / `gradle test` | `mvn -q compile` / `gradle build -x test` |
| other | whatever `Makefile` / CI config declares | | | |

**Prefer what CI runs.** Read the CI definition — `.github/workflows/*`,
`.gitlab-ci.yml` (and any `include:`d files), `azure-pipelines.yml`,
`Jenkinsfile` — and the `Makefile`, and use those exact commands: they are the
real contract. Only fall back to the table above when there is no CI. If a
command in the table does not exist in the repo, skip it; do not install
tooling.

Some gates need services CI provides (a database, a message broker). Detect
this from the CI job (`services:`, a `docker compose` step) and run only the
jobs that work locally; name the ones you skipped in the report. Where the
solution has several test projects or CI splits tests into jobs, mirror that
split — a `dotnet test` on the whole solution can take far longer than the
unit job you actually need.

Print the gate list you resolved. If you find **no** test command at all, say so
— an unverifiable change is a finding in itself.

## 5. Branch

Resolve the default branch with `git symbolic-ref refs/remotes/origin/HEAD`.
Fall back to the available forge tool or remote metadata.
**Do not check out the default branch.** The shared checkout can contain
another session's work.
Prefer an isolated worktree (`git worktree add` or an agent worktree tool) when
available; otherwise branch straight off the remote ref:
`git fetch origin && git checkout -b <branch> origin/<default>` (no remote:
`git checkout -b <branch> <default>`).

**Branch name:** use the convention recorded in step 0 if the repo or the
global directives state one. Otherwise `<type>/<issue-key>-<short-slug>` when
there is an issue key (`fix/abc-123-null-payee`), else `<type>/<short-slug>`.
`<type>` is `fix` for security/bug and `feat` for feature. Lowercase throughout.

**Verify the branch** (`git branch --show-current`) — the shared checkout means
you can end up somewhere unexpected. Record the base for the review loop:
`git rev-parse HEAD`. Then run the test gate once on this clean base and record
any failures already present — step 7's bar is "no new failures".

## 6. Code it — coder, with fallback

If delegation is available, assign a **coder** agent and wait for its result.
Use an available model; do not require a provider-specific model name.
Give it:
- the issue statement and the class from step 2,
- **your plan from step 3, verbatim** — it implements the plan, it does not
  redesign it,
- the exact files and functions involved,
- the repo's conventions — the style-doc paths you resolved in step 0 (project
  *and* global), with the instruction to read them before writing code, plus the
  documentation, commenting, and other directives you extracted, quoted inline;
  match the surrounding style,
- the gate commands from step 4, so it can self-check,
- the instruction to add or adjust tests,
- the instruction to update the docs the repo requires for this change — the doc
  edit is part of the change, not a follow-up,
- the instruction to run **no** git or forge commands.

It returns a summary of its edits. You own the tree. If delegation is
unavailable, implement the plan yourself.

**If the coder disagrees with the plan**, it must explain why before changing
scope. Then decide whether to revise the plan.

If the coder errors out or returns incomplete work, implement the remaining
plan directly. Do not retry a failing agent repeatedly.

## 7. Gates, then checkpoint commit

Run the step-4 commands. Fix until green — "green" means no failures beyond
the baseline recorded in step 5. Never commit red; a pre-existing failure that
is not yours is a report item, not yours to fix.

Pre-existing lint hits that are not in your diff are OK to leave — do not fix
unrelated code. Say in the report that you left them.

When green, commit — the review loop diffs commits, so uncommitted work is
invisible to it:
- `git add` each file by name (never `-A`/`.` — shared checkout), then
  `git status` — **confirm every file your change touched is staged** and
  nothing stray is. A forgotten `git add` ships an incomplete PR.
- **Subject format:** the convention recorded in step 0 wins (many repos
  want the issue key first: `ABC-123: short description`). With no stated
  convention, mirror `git log --oneline -20`; if that is inconsistent too, use
  Conventional Commits (`fix(scope): …` / `feat(scope): …`). The body explains
  the *why*.
- **Attribution trailer:** follow the recorded conventions. Add no AI
  attribution unless the user or repository explicitly requires it.
- Later rounds: same format, subject "address review findings (round N)" —
  same trailer rule on every commit.

## 8. Review loop — max 3 rounds

Track the round count. Round 1 reviews the whole change; rounds 2 and 3 review
only the delta.

### a. Reviewer

If delegation is available, assign an independent **reviewer** agent. Select
the strongest available model: prefer Fable in Claude Code or `gpt-6-astra` in
Codex when offered. If selection or execution fails because the model is
unavailable or out of credits, try the next strongest available model. For
example, try Opus or `gpt-6.1-sol`. Try each model at most once. Record the
model that completes the review.

Give the reviewer `git diff <base>...HEAD`; you run git, while it may read repo
files. If no reviewer model runs, review the diff yourself and disclose that
limitation. Prompt the reviewer to challenge the change:

- "**Try HARD to break it.**"
- Give it the issue and the plan, so it can also judge *whether the change
  actually solves the issue* — not only whether the code is clean.
- Cover **three risk dimensions explicitly**, weighted by the class from step 2, each
  with concrete failure modes to hunt (tailor them to the change):
  - **Security** — can it still be exploited? bypasses, injection, smuggling,
    auth gaps, parser/encoder divergence, unbounded resources.
  - **Functionality regression** — does it break legitimate flows? existing
    tests, edge inputs, the default/flag-off path being byte-identical.
  - **Stability** — crashes and unhandled exceptions, null/nil dereferences,
    races/locking, leaked resources (connections, handles, streams), and the
    stack's own async traps — e.g. in .NET: a dropped `CancellationToken`,
    sync-over-async (`.Result`/`.Wait()`), `async void`, a disposable not
    disposed; in Go: goroutine leaks, unchecked errors.
- **Conventions compliance — a fourth dimension, always checked, never weighted
  away.** Give it the style-doc paths from step 0 (project *and* global) and tell
  it to read them, then judge the added and changed lines against them. Four
  things to check, not just the first:
  - **Code style** — naming, error strings, banned APIs, and the idioms the
    docs mandate (Go receivers and error wrapping; C# records, `sealed`,
    nullable annotations, `CancellationToken` flow — whatever the repo lists).
  - **Documentation** — did the change touch behaviour the docs describe, and
    did the diff update them? Name the specific files the repo requires (a repo
    that says "keep `README.md`, `CLAUDE.md`, and the config example fresh with
    every feature" means a missing doc edit is a finding, not a nit). Judge the
    prose against the house doc style too.
  - **Comments** — the repo's density and length rules, comments that restate
    the code, and a non-obvious mechanism left unexplained.
  - **Other directives** — anything else the project or global file states as a
    rule: scope limits ("surgical edits"), commit and attribution rules, secret
    handling, forbidden operations.

  This is the house standard, not the reviewer's taste: every finding must
  quote the rule it breaks and say which file states it. Ignore what the
  formatter or linter already enforces mechanically, ignore untouched code, and
  raise nothing that is only a personal preference.
- Demand a verdict: **APPROVE / APPROVE WITH NITS / REQUEST CHANGES**, with
  `file:line`, a concrete failing input, and a suggested fix for each finding.
- Tell it its final message is the report — it does not talk to the user.

### b. You triage the findings

This step is yours. Do not forward the review to the coder unchanged. For each
finding decide one of:

- **Fix** — real, and in scope. Goes to the coder.
- **Decline** — wrong, or a style preference you disagree with. Record the
  reason; it goes in the report.
- **Defer** — real but out of scope for this issue. Record it; it goes in the
  report as a follow-up.

If **every** finding is declined or deferred, the loop is done — do not spend a
round on nothing.

### c. Back to the coder

Send the **fix** findings to the coder. Use a follow-up or resume tool to start
an idle agent; use messaging for an active agent. If no coder is available, fix
them yourself. Give the coder your triage, including declined findings.

Re-run the gates (step 7).

### d. Re-review the delta

Ask the same reviewer to review `git diff <prev-sha>..HEAD`. Use the agent's
follow-up or resume tool. `<prev-sha>` is the commit it last reviewed. If that
model can no longer run, use the next available reviewer model. Give a replacement
the full diff, issue, plan, and prior findings. If no reviewer is available,
review the delta yourself. Confirm each finding is closed and no new issue was
introduced.

### e. Exit conditions

Leave the loop when **any** of these is true:
- verdict is **APPROVE** or **APPROVE WITH NITS**, or
- every open finding is declined/deferred with a reason, or
- **you have finished round 3**.

**On the 3-round cap:** stop. Do not start a fourth round. Commit what you have,
open the PR, and put the unresolved findings in the PR body and the report,
marked clearly as **unresolved after 3 rounds**. A stuck loop is a signal that
the plan was wrong — say that in the report.

## 9. Push and PR

`git status` — confirm nothing of yours is left uncommitted (the commits
happened in step 7).

**Pushing publishes the branch.** Follow the user's authorization and recorded
conventions. If approval is required, stop with the prepared branch and PR text.
If authorized, continue:

- **GitHub:** `git push -u origin <branch>`, then `gh pr create`. Use a body file
  for the PR text. Add `--draft` when conventions require a draft.
- **GitLab:** create the MR with the branch push:

  ```sh
  git push -u origin <branch> -o merge_request.create \
    -o merge_request.target=<default> -o merge_request.squash=true \
    -o merge_request.remove_source_branch=true
  ```

  Add `-o merge_request.draft` when conventions require a draft. Set the title
  and description with `merge_request.title` and `merge_request.description`.
  Escape description newlines as `\n`; push options reject literal newlines.

Use the lead commit's subject as the title. The PR body covers:
- what changed and why,
- the closing reference — **`Fixes #N`** (GitHub) / **`Closes #N`** (GitLab)
  when the input was a forge issue, or the Jira key when it was a Jira issue,
- what the review caught and you fixed,
- declined / deferred / unresolved findings,
- how it was tested — the gates that ran, and any you had to skip.

Apply the same attribution rule as commits (step 7) to the PR body.

**Do not merge.** The PR stays open. Merging is the human's call.

If there is no authorized forge access (step 0), stop after the last commit and
say the branch name.

## 10. Report

Give a concise summary:
- **Issue** → class → PR link (or branch name).
- **What changed** — one line.
- **What the review caught** and you fixed before the PR. This is the payoff —
  surface it.
- **Reviewer model** — name the model used, or disclose a self-review.
- **Declined / deferred / unresolved**, each with the reason.
- **Non-goals** you named in the plan.
- **Escalation**, if you flagged one in triage — what the human must decide.

## Hard rules (never violate)

- **Never push to the default branch.** Feature branch always. One issue per
  branch/PR.
- **Never merge.** The PR is the deliverable.
- **You own all git and forge state.** Subagents never run git or forge commands.
- **Never chain git in parallel tool calls** — they race on `.git/index.lock`;
  chain with `&&`.
- **Stage by name.** Never `git add -A`/`.` — the shared checkout has strays.
- **Max 3 review rounds.** Report the remainder instead of looping.
- **Surgical edits** — change only what the issue requires; don't "improve"
  adjacent code. Clean up orphans *you* created; leave pre-existing dead code.
- **Destructive ops** (force-push, history rewrite, deleting others' work) — hand
  to the human, don't run them.
