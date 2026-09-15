---
name: work
description: >-
  Take one issue and drive it to a reviewed PR using a three-role loop
  (orchestrator designs the plan → coder subagent implements it → reviewer
  subagent attacks it → orchestrator triages the findings and sends
  them back to the coder). Max 3 review loops. Triages the issue as security /
  bug / feature and shapes the plan, gates, and review dimensions accordingly.
  Language- and forge-agnostic — detects the toolchain (Go, .NET, Node, Python,
  Rust, JVM, or whatever CI declares) and the forge (GitHub via `gh`, GitLab via
  `glab`) and runs their native commands. Accepts a GitHub/GitLab issue (`#142`,
  issue URL), a Jira key (`ABC-123`), or a plain-text problem description.
  Stops at an open PR/MR; merging is the human's call. Invoke as /yavosh:work.
model: opus
---

# work

You are the **orchestrator** (Opus — pinned by this skill's frontmatter). You
take **one** issue to an open, reviewed PR (GitHub) or MR (GitLab) — "PR" below
means either. Two kinds of subagent do the work — a **coder** (Sonnet) and a
**reviewer** (Fable, falling back to Opus when Fable is unavailable) — and you
alone touch `git` and the forge CLI (`gh` / `glab`).

Your job is the parts a subagent cannot do: understanding the issue, designing
the plan, judging the reviewer's findings, and owning git state. Do not delegate
the plan and do not delegate the triage of findings.

## 0. Preconditions (check once, up front)

- `git rev-parse --git-dir` — is this a git repo?
- **Detect the forge** from `git remote -v`: a `github.com` host → `gh`; a
  `gitlab.com` or self-hosted GitLab host → `glab`. Confirm auth with
  `gh auth status` / `glab auth status`. Record the CLI; every forge command
  below is written as `gh` with the `glab` equivalent in brackets.
  - **Authenticated forge** → full path: branch → commit → PR.
  - **No forge / not authenticated** → degraded path: branch → commit, no PR.
    Say so up front.
- `git status` — note pre-existing dirt. **Shared checkout hazard:** other
  Claude sessions may share this checkout — ignore stray files/dirs that aren't
  yours. Never stage them: add your own files by name, never `git add -A`/`.`.
- You are the **only** writer of git state. Subagents get code and context, not
  commit/PR authority.
- **Resolve the conventions, project and global.** Read `CLAUDE.md` / `AGENTS.md` /
  `CONTEXT.md` at the repo root, every style doc they point at
  (`docs/code-style.md`, `CONTRIBUTING.md`, a `docs/style/` dir — whatever the
  repo names), and the user's global directives at `~/.claude/CLAUDE.md` plus
  anything it `@`-imports. Record the paths: the coder and the reviewer both get
  them. If there is no such doc, say so — the surrounding code is then the only
  standard.
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
- `#N` or a forge issue URL → `gh issue view <N> --json number,title,body,labels,comments`
  [`glab issue view <N> --comments`]. Read the comments too — the real
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

Read the relevant code yourself. Use the Explore agent for broad fan-out
searches if you must, but read the files the fix will touch with your own eyes.

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

Print the plan before you spawn the coder — visible, not a blocking approval;
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

Resolve the default branch: `git symbolic-ref refs/remotes/origin/HEAD` first
(forge-agnostic); fall back to `gh repo view --json defaultBranchRef`
[`glab repo view`]. **Do not check out the default branch** — the shared
checkout means switching or pulling it can clobber another session's work.
Prefer an isolated worktree (`EnterWorktree` / `git worktree add`) when
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

## 6. Code it — coder subagent, with fallback

Spawn a **coder** (general-purpose Agent, `model: sonnet`, run synchronously).
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
- the instruction to run **no** `git`, `gh` or `glab` commands.

It returns a summary of its edits. You own the tree.

**If the coder disagrees with the plan**, it must say so in its return message
rather than deviate silently. Then you decide: revise the plan, or restate it
and re-spawn.

**Subagents die.** If the coder errors out (API/session limit, "connection
closed") or returns incomplete work, **do not loop retrying it — take over and
implement the plan directly.** Resuming a flaky agent wastes cycles.

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
- **Attribution trailer:** follow the recorded conventions. If they forbid AI
  attribution, add none. If they are silent, add the trailer the harness
  specifies for the running model. Never add one the conventions forbid.
- Later rounds: same format, subject "address review findings (round N)" —
  same trailer rule on every commit.

## 8. Review loop — max 3 rounds

Track the round count. Round 1 reviews the whole change; rounds 2 and 3 review
only the delta.

### a. Reviewer

Spawn a **reviewer** (general-purpose Agent, `model: fable`, synchronous). If
the spawn or the run fails for ANY reason (credit/usage limit, model not
available, the agent dies mid-review), re-spawn the SAME prompt once with
`model: opus` and say in the report which model reviewed. Do not retry Fable
in the same session after it has failed. Give the
reviewer the output of `git diff <base>...HEAD` — you run the diff; it runs no
git, but it may read repo files. Prompt it to be a genuine adversary, not a rubber
stamp:

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

Send the **fix** findings to the coder (resume the same coder via SendMessage so
it keeps its context; spawn fresh only if it died). Give it your triage, not the
raw review — including which findings you declined, so it does not re-add them.

Re-run the gates (step 7).

### d. Re-review the delta

Resume the **same reviewer** (SendMessage; spawn fresh only if it died) with
the delta, `git diff <prev-sha>..HEAD` — `<prev-sha>` is the commit it last
reviewed. Ask it to confirm each finding is closed and that nothing new was
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

**Pushing publishes the branch.** If the recorded conventions say "ask before
the first push", stop here, print the push and PR commands, and wait.
Otherwise `git push -u origin <branch>`.

Then open the PR: `gh pr create` [`glab mr create`]. Open it as a **draft**
(`--draft` on both CLIs) when the conventions ask for drafts. Title: the lead
commit's subject. Body:
- what changed and why,
- the closing reference — **`Fixes #N`** (GitHub) / **`Closes #N`** (GitLab)
  when the input was a forge issue, or the Jira key when it was a Jira issue,
- what the review caught and you fixed,
- declined / deferred / unresolved findings,
- how it was tested — the gates that ran, and any you had to skip.

Apply the same attribution rule as commits (step 7) to the PR body.

**Do not merge.** The PR stays open. Merging is the human's call.

If there is no authenticated forge (step 0), stop after the last commit and
say the branch name.

## 10. Report

Give a concise summary:
- **Issue** → class → PR link (or branch name).
- **What changed** — one line.
- **What the review caught** and you fixed before the PR. This is the payoff —
  surface it.
- **Declined / deferred / unresolved**, each with the reason.
- **Non-goals** you named in the plan.
- **Escalation**, if you flagged one in triage — what the human must decide.

## Hard rules (never violate)

- **Never push to the default branch.** Feature branch always. One issue per
  branch/PR.
- **Never merge.** The PR is the deliverable.
- **You own all git and forge state.** Subagents never run `git`, `gh` or `glab`.
- **Never chain git in parallel tool calls** — they race on `.git/index.lock`;
  chain with `&&`.
- **Stage by name.** Never `git add -A`/`.` — the shared checkout has strays.
- **Max 3 review rounds.** Report the remainder instead of looping.
- **Surgical edits** — change only what the issue requires; don't "improve"
  adjacent code. Clean up orphans *you* created; leave pre-existing dead code.
- **Destructive ops** (force-push, history rewrite, deleting others' work) — hand
  to the human, don't run them.
