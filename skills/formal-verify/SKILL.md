---
name: formal-verify
description: >-
  Find concurrency, state, and data-flow bugs by formally modeling the code in
  TLA+ (or Lean for pure logic), confirming each model violation with a failing
  test against the real code, fixing it, and leaving a rerunnable before/after
  proof (specs/check.sh). Use when the user asks to formally verify a project,
  model it in TLA+/Lean, hunt race conditions or lost updates, or prove a fix.
  Language-agnostic. Invoke as /yavosh:formal-verify [target], where target is a
  component, file, or bug hypothesis; with no target it surveys the repo and
  picks the riskiest area.
---

# formal-verify

Model the code, let the model checker find the bug, prove the bug in real code,
fix it, and prove the fix. The output is a fix plus a proof that anyone can rerun.

Work without constant check-ins. Ask only when the answer changes scope or risk.
Examples: which area when two are equally risky, or anything that touches prod or
shared state. Otherwise pick the top-ranked option, say which one, and proceed.

## 0. Preconditions

- Read the repo's `CLAUDE.md` / `AGENTS.md` / style docs, and `~/.claude/CLAUDE.md`.
  They set commit, branch, PR, and attribution rules. Follow them over anything here.
- `git status`. On a clean default branch, create one branch for the work
  (`formal/<target>`). If the tree has someone else's uncommitted work, use a
  worktree. Otherwise keep git simple: no worktree choreography.
- Install the tools only if they are missing:

  ```bash
  command -v java || brew install openjdk        # use "$(brew --prefix openjdk)/bin/java"
  test -f ~/.local/share/tla/tla2tools.jar || { mkdir -p ~/.local/share/tla && \
    curl -sSLo ~/.local/share/tla/tla2tools.jar \
    https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar; }
  # Lean only when needed: curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
  ```

## 1. Survey

Find where state is shared and written by more than one actor. Search for:

- Concurrency primitives: goroutines, threads, async tasks, locks, channels,
  semaphores, atomics, worker pools, tickers.
- Durable state machines: `status` columns, claims, leases, `locked_until`,
  `next_attempt`, retries, sweepers, reapers, reconcilers.
- **The recurring bug shapes:**
  - An unguarded write (`UPDATE … WHERE id = ?`) next to a guarded claim.
  - List-then-act loops that write from a stale snapshot.
  - A fan-out saved one row per statement instead of in one transaction.
  - A side effect done before the status write that retires it.
  - Leases or timeouts whose correctness depends on timing.
  - Errors ignored on status writes (`_ = …`).

Rank the top 3–5 targets by risk. For each target, list the actors, the shared
state, and the invariants that must hold. Tell the user the ranking in a short
table, then start on the top one.

Pick the tool by target:
- **TLA+**: interleavings, crashes, retries, leases, and multi-actor state. The default.
- **Lean**: pure functions with a clear property, such as round-trip encode/decode,
  bounds, or parser totality.

## 2. Model (TLA+)

Write `specs/<Name>.tla` and `specs/<Name>.cfg` in the repo.

- Model the **real** code, not an ideal version. Add a comment beside each action
  that names the source `file:line` it models.
- **Atomicity:** each SQL statement or lock-held section is one step. A
  "list, then act" loop is two steps: a snapshot, then a write.
- Model the environment as nondeterministic actions. Examples: backoff turning on,
  a message aging past its limit, a store write failing, a process crash plus boot
  recovery.
- Make each **assumption** a `CONSTANT` (for example `TimingHolds`) rather than
  hard-coding it. That way the model can show what breaks without it.
- Add a **before/after switch** constant (for example `Guarded`, `Atomic`) once
  you know the fix. One spec then proves both that the old code fails and that
  the new code passes.
- Keep it small: 1 row, 2 workers, bounded counters. Most bugs show at size 2.
- Define properties as invariants (`AtMostOneSending`, `NoLostRow`) and action
  properties (`[][(s \in Terminal) => (s' = s)]_s`).

Run TLC:

```bash
"$(brew --prefix openjdk)/bin/java" -XX:+UseParallelGC -cp ~/.local/share/tla/tla2tools.jar \
  tlc2.TLC -workers auto -deadlock -metadir "$TMPDIR/tlc" -config specs/<Name>.cfg specs/<Name>
```

TLA+ pitfalls:
- Parenthesize inside `[][…]_v`: write `[][(a) => (b)]_v`.
- Undeclared names in a `.cfg` set become model values (`Workers = {w1, w2}`).
- Use `-deadlock` for models whose loops can legitimately stop.
- Keep `-metadir` outside the repo.

## 3. Triage every trace

TLC stops at the **first** violation. For each trace, decide:

- **Modeling mistake.** The trace can't happen in real code, for example a
  message aged 48 h before its first dispatch. Constrain the model, say so to the
  user in one line, and rerun.
- **Real candidate.** Map each step to `file:line` and write down the concrete
  interleaving. Go to step 4.

After fixing a bug in the model, rerun it. The next violation may have been hidden.

## 4. Confirm in real code

No fix without a failing test. Write a **deterministic** test that forces the
exact interleaving from the trace:

- Use gated fakes (a deliverer or client that blocks on a channel until
  released) and call the internal steps directly, in trace order. No sleeps.
- For fault paths, wrap the store in a type that embeds the real store and
  fails one call.
- Assert the model's property (for example "sends == 1", or "rows is 0 or all").

Run the test on the current code. **It must fail.** If it passes, the model was
too pessimistic, for example because it omitted a guard the code has. Say so,
refine the model, and drop that finding.

## 5. Fix

- Make the smallest change that restores the property. Common fixes:
  - A compare-and-swap write guarded by the status the writer saw.
  - One transaction for a whole plan.
  - Retiring the state before the side effect.
- Match the surrounding code. Regenerate generated code (sqlc, protobuf) with
  the project's own command.
- Gates: the new tests pass, the full test suite passes (with a race detector
  where one exists), and the linter passes. Test every backend the code supports,
  using a throwaway container if a backend needs a server. Remove the container
  afterwards.
- Update the model to the fixed code and rerun TLC until it reports no error.

## 6. Leave the proof

Copy `check.sh` from this skill's directory into `specs/check.sh` (make it
executable). Then write `specs/checks.txt`, one line per configuration:

```
# spec              config                       expect  note
DeliveryLifecycle   DeliveryLifecycle.cfg        pass    guarded writes (fix)
DeliveryLifecycle   DeliveryLifecycleBefore.cfg  fail    unguarded writes (before the fix)
DeliveryLifecycle   DeliveryLifecycleNoTiming.cfg fail   known limit: timing assumption off
```

`./specs/check.sh` fails if any result differs. A `fail` expectation passes only
on a real property violation, never on a parse error.

Also:
- **Enforce each assumption in code.** Add a cheap test that fails when an
  assumption breaks, for example `attemptTimeout + persistTimeout < staleAge`.
- **Prove the regression test.** Run it against the code before the fix (check
  out `<fix>~1` in a temporary worktree and copy in the test file). Show that it
  fails there and passes on the fix.
- Write a short `specs/README.md`. It lists each spec, what it models, its
  properties, the check table, and its assumptions.

## 7. Deliver

- Commit in two parts, following the repo's conventions: the spec, then the fix
  plus tests.
- Open a PR only when the user asked for one, or the repo's workflow expects one.
  The PR body covers the interleaving, the fix, the TLC before/after table, and
  the before/after test results. Merging and deploying are the user's call.
- If CI can't run, run CI's jobs locally (tests, backend variants, lint) and say so.
- Report to the user in 3 parts: the bug (the concrete interleaving), the proof
  table, and anything left open (assumptions, known limits, residual risk).

## Production evidence (optional)

The goal is to measure exposure, never to reproduce a race in prod.

- **Read-only only.** Never trigger the race, restart services, or write to prod.
  Prefer a restored copy or backup of the prod database over live queries.
- Give the user **bare commands** to run. Don't send them through `ssh` wrappers
  unless asked. Hosts often lack `rg`, so use `grep -F` for literal matches (in
  basic regex, `\(` starts a group).
- **Validate the detector first.** Replay the failing test into a kept database,
  and run the same query on it. The query must catch the bug before a zero on
  prod means anything.
- Keep personal data out of results: select IDs, counts, and timestamps, not
  addresses or bodies. Remind the user to delete any prod DB copy afterwards.
- Treat low traffic as "not yet exposed", not "safe". The failing test is the proof.

## Shell pitfalls

- zsh: `echo ====` fails (`=` expansion), so use `echo '---'`. An unmatched glob
  aborts the command (`rm -f x*`).
- `sqlite3 -readonly` fails on a WAL database without its `-shm` file. Copy the
  file first.
- The TLC exit code is unreliable. Grep the output for `No error has been found`
  or `is violated`.
