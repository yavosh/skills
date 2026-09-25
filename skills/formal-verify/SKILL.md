---
name: formal-verify
description: >-
  Find concurrency, state, and data-flow bugs by formally modeling the code in
  TLA+ (interleavings) and Lean 4 (state-machine proofs), checking each model
  against real execution traces, confirming each violation with a failing test
  against the real code, fixing it, and leaving a rerunnable before/after proof
  (specs/check.sh). Use when the user asks to formally verify a project, model
  it in TLA+/Lean, hunt race conditions, deadlocks, or lost updates, or prove a
  fix. Language-agnostic, with bug shapes for Go, Java, .NET, async
  TypeScript/Python, and databases. Invoke as /yavosh:formal-verify [target],
  where target is a component, file, or bug hypothesis; with no target it
  surveys the repo and works every ranked target, one PR per module.
---

# formal-verify

Model the code, check the model against real runs, and let the model checker or
prover find the bug. Then prove the bug in real code, fix it, and prove the fix.
The output is one fix per module plus a proof that anyone can rerun.

Work without constant check-ins. Ask only when the answer changes scope or risk.
Examples: which area when two are equally risky, or anything that touches prod or
shared state. Otherwise pick the top-ranked option, say which one, and proceed.

**Scope:**
- `/yavosh:formal-verify <target>`: work only that target.
- `/yavosh:formal-verify` with no target: survey the repo, then work every
  ranked target (at most 5). Each module gets its own branch and PR.

## 0. Preconditions

- Read the repo's `CLAUDE.md` / `AGENTS.md` / style docs, and `~/.claude/CLAUDE.md`.
  They set commit, branch, PR, and attribution rules. Follow them over anything here.
- `git status`. If the tree has someone else's uncommitted work, use a worktree.
  Each target gets one branch from the default branch: `formal/<target>`.
  You own all git state. Subagents never run `git` or forge commands.
- Install the tools only if they are missing:

  ```bash
  command -v java || brew install openjdk        # use "$(brew --prefix openjdk)/bin/java"
  test -f ~/.local/share/tla/tla2tools.jar || { mkdir -p ~/.local/share/tla && \
    curl -sSLo ~/.local/share/tla/tla2tools.jar \
    https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar; }
  # Lean only when a target needs it:
  command -v lake || { curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    | sh -s -- -y && source ~/.elan/env; }
  ```

## 1. Survey

Find where state is shared and written by more than one actor, or where one
actor runs a state machine with many exits. Search for the
[bug shapes](#bug-shapes) that match the repo's languages and storage.

Rank the top 3–5 targets by risk. For each target, list the actors, the shared
state, and the invariants that must hold. Tell the user the ranking in a short
table. Then work the given target, or every ranked target when none was given.

Pick the tool by target:
- **TLA+**: several actors, interleavings, crashes, retries, leases. TLC checks
  every interleaving at a small size. The default for multi-actor state.
- **Lean 4**: one actor's state machine (a stream, a retry loop, a turn loop, a
  session phase, a protocol handler), and pure functions with a clear property,
  such as round-trip encode/decode or parser totality. Lean proves the property
  for every size and every event sequence.
- **Both**: a state machine that several actors drive. Use TLA+ for the
  interleavings and Lean for the step invariants at any size.

With more than one target, write the models in parallel: one subagent per
target. Give each subagent the target's files, its actors and invariants, and
section 2 or 3 of this skill. Subagents write only under `specs/`.

## 2. Model in TLA+

Write `specs/<Name>.tla` and `specs/<Name>.cfg` in the repo.

- Model the **real** code, not an ideal version. Add a comment beside each action
  that names the source `file:line` it models.
- **Atomicity.** One step is one indivisible unit of the real runtime:
  - One SQL statement, or one lock-held section: Go `mu.Lock()`…`Unlock()`,
    Java `synchronized` or `lock()`…`unlock()`, .NET `lock` or
    `SemaphoreSlim` held.
  - One atomic operation: Go `sync/atomic`, Java `Atomic*`, .NET `Interlocked`.
    An atomic load followed by an atomic store is two steps.
  - An unbuffered Go channel send and its receive form one joint step. Model a
    buffered channel or a queue as a sequence with a capacity.
  - On a single-threaded event loop (JavaScript, Python asyncio), the code
    between two `await`s is one step. On a thread pool (.NET, Java, Go), only
    locked sections and atomics are steps. Every other shared read or write is
    its own step.
  - A "list, then act" loop is two steps: a snapshot, then a write.
- Model the environment as nondeterministic actions. Examples: backoff turning on,
  a message aging past its limit, a store write failing, a process crash plus boot
  recovery, a context being cancelled.
- Make each **assumption** a `CONSTANT` (for example `TimingHolds`) rather than
  hard-coding it. That way the model can show what breaks without it.
- Add a **before/after switch** constant (for example `Guarded`, `Atomic`) once
  you know the fix. One spec then proves both that the old code fails and that
  the new code passes.
- Keep it small: 1 row, 2 workers, bounded counters. Most bugs show at size 2.
- Define properties as invariants (`AtMostOneSending`, `NoLostRow`) and action
  properties (`[][(s \in Terminal) => (s' = s)]_s`). For deadlocks, leave
  deadlock checking on. For "every path ends in a terminal state", use a
  temporal property with fairness.
- For a model whose loops can legitimately stop, add `CHECK_DEADLOCK FALSE` to
  the `.cfg`.

Run TLC:

```bash
"$(brew --prefix openjdk)/bin/java" -XX:+UseParallelGC -cp ~/.local/share/tla/tla2tools.jar \
  tlc2.TLC -workers auto -metadir "$TMPDIR/tlc" -config specs/<Name>.cfg specs/<Name>
```

TLA+ pitfalls:
- Parenthesize inside `[][…]_v`: write `[][(a) => (b)]_v`.
- Undeclared names in a `.cfg` set become model values (`Workers = {w1, w2}`).
- Don't pass `-deadlock`. It overrides `CHECK_DEADLOCK` in the `.cfg`, and
  trace replays (section 4) rely on deadlock checking.
- Declare a `CONSTANT` before any definition that uses it.
- Keep `-metadir` outside the repo.

## 3. Model in Lean 4

Write one Lake project per target in `specs/lean/<Name>/` (`lake new <Name>`).
Don't add Mathlib unless a proof needs it.

- **State** is a structure. **Events** are an inductive type, one constructor per
  code path. **Step** is `step : State → Event → Option State`, where `none`
  means the event is not enabled. Comment each constructor with the source
  `file:line` it models.
- Model the **real** code, including its flags and copy-pasted branches. Make
  each assumption a hypothesis or a parameter.
- Add a **before/after switch**: a `fixed : Bool` parameter on `step`.
- Prove these properties:
  - **Invariants:** `Inv : State → Prop` with `inv_init` and
    `inv_step : Inv s → step s e = some s' → Inv s'`. Strengthen `Inv` with
    lemmas until it is inductive.
  - **Counterexamples:** a concrete event list that reaches a bad state when
    `fixed := false`, proved `by decide`. This is the Lean version of a TLC
    trace, and it becomes the failing test in section 7.
  - **Fix proofs:** *sufficiency*, meaning the invariant holds when
    `fixed := true`. *Agreement*, meaning that on every step where the old code
    keeps the invariant, the fixed step gives the same result. Agreement shows
    that the fix changes nothing else.
  - **Termination:** for a loop that must stop, prove that a measure decreases,
    for example the turns left under `--max-turns`.
- No `sorry`. No `native_decide`, because it adds an axiom that the audit rejects.
- Write `Audit.lean` in the project root. It imports the model and runs
  `#print axioms` on every main theorem. The allowed axioms are `propext`,
  `Quot.sound`, and `Classical.choice`.

Build and audit:

```bash
cd specs/lean/<Name> && lake build && lake env lean Audit.lean
```

## 4. Check the model against real runs

A model that rejects real behavior proves nothing about the code. Before you
trust any result, replay real traces through the model.

1. Add temporary logging at each modeled transition. Log every model variable,
   one line per transition.
2. Run the existing tests, and a real run if it is cheap. Collect the logs.
3. Convert each log into a trace of model states, and replay the traces
   (patterns below).
4. Remove the logging. Commit the replays, not the logging.

Every trace must be accepted. A rejected trace means the model is wrong: a
missing action, a wrong guard, or the wrong atomicity. Fix the model and replay
again. If you can't reach 100%, report "N of M accepted" and treat the model's
results as provisional.

**TLA+ replay.** Write `specs/<Name>Traces.tla` and a `.cfg` with
`INIT TraceInit`, `NEXT TraceNext`, and the main model's constants. Keep
deadlock checking on. A rejected trace stops as `Deadlock reached`, and the
error state's `t` and `i` name the trace and the step.

```tla
---- MODULE <Name>Traces ----
EXTENDS <Name>, Sequences
VARIABLES t, i
Traces == << << [s |-> "idle", n |-> 0], [s |-> "busy", n |-> 0] >>,
             << [s |-> "idle", n |-> 0] >> >>
Matches(k) == s = Traces[t][k].s /\ n = Traces[t][k].n
TraceInit == t \in 1..Len(Traces) /\ i = 1 /\ Init /\ Matches(1)
TraceNext == \/ /\ i < Len(Traces[t])
                /\ Next /\ i' = i + 1 /\ t' = t
                /\ s' = Traces[t][i+1].s /\ n' = Traces[t][i+1].n
             \/ i = Len(Traces[t]) /\ UNCHANGED <<s, n, t, i>>
====
```

Pin every variable in every trace state. A variable the trace leaves free lets
TLC take a wrong branch and report a false deadlock.

**Lean replay.** Write `replay : State → List (Event × State) → Bool`. It
checks that each event is enabled and that the step reaches the observed state.
Prove each trace with `example : replay init trace7 = true := by decide`.

## 5. Review each model independently

For each model, spawn a fresh reviewer (general-purpose Agent, `model: fable`;
if Fable is unavailable, use `model: opus`). Give it the source files, the model,
and the replay results, but not your reasoning. It checks that:

- Each action or step matches its cited `file:line`: guards, writes, atomicity.
- No real code path is missing from the model, and the model has no path that
  the code can't take.
- Each counterexample can happen in the real code.
- Each assumption is stated, and each theorem proves what its name claims.

Fix what the reviewer confirms, and rerun the checks. Note what you rejected
and why.

## 6. Triage every violation

TLC stops at the **first** violation. In Lean, each counterexample theorem is one
candidate. For each one, decide:

- **Modeling mistake.** The trace can't happen in real code, for example a
  message aged 48 h before its first dispatch. Constrain the model, say so to the
  user in one line, and rerun.
- **Real candidate.** Map each step to `file:line` and write down the concrete
  interleaving or event sequence. Go to step 7.

After fixing a bug in the model, rerun it. The next violation may have been hidden.

## 7. Confirm in real code

No fix without a failing test. Write a **deterministic** test that forces the
exact interleaving from the trace:

- Use gated fakes that block until released, and call the internal steps
  directly, in trace order. No sleeps. Gates by language: Go channels, Java
  `CountDownLatch`, .NET `TaskCompletionSource` or `SemaphoreSlim`, a
  JavaScript promise with its `resolve` held by the test.
- For fault paths, wrap the store in a type that embeds the real store and
  fails one call.
- Assert the model's property (for example "sends == 1", or "rows is 0 or all").
- Run it with the race detector where one exists (`go test -race`).

Run the test on the current code. **It must fail.** If it passes, the model was
too pessimistic, for example because it omitted a guard the code has. Say so,
refine the model, and drop that finding.

## 8. Fix

- Fix every confirmed bug in a module on that module's branch.
- Make the smallest change that restores the property. Common fixes:
  - A compare-and-swap write guarded by the status the writer saw.
  - One transaction for a whole plan.
  - Retiring the state before the side effect.
  - One lock order, or no callback or channel send while holding a lock.
  - Passing the cancellation signal through, and handling it on every exit.
- Match the surrounding code. Regenerate generated code (sqlc, protobuf) with
  the project's own command.
- Gates: the new tests pass, the full test suite passes (with a race detector
  where one exists), and the linter passes. Test every backend the code supports,
  using a throwaway container if a backend needs a server. Remove the container
  afterwards.
- Update the model to the fixed code. Rerun TLC, the Lean proofs, and the
  replays until all pass.

## 9. Leave the proof

Copy `check.sh` from this skill's directory into `specs/check.sh` (make it
executable). Give each target its own checks file, `specs/<Name>.checks`, so
parallel PRs don't conflict. Write one line per check:

```
# spec              config                        expect  note
DeliveryLifecycle   DeliveryLifecycle.cfg         pass    guarded writes (fix)
DeliveryLifecycle   DeliveryLifecycleBefore.cfg   fail    unguarded writes (before the fix)
DeliveryLifecycle   DeliveryLifecycleNoTiming.cfg fail    known limit: timing assumption off
DeliveryTraces      DeliveryTraces.cfg            pass    42 real traces replayed
lean                lean/SessionPhase             pass    proofs, replays, audit
```

`./specs/check.sh` fails if any result differs. A `fail` expectation passes only
on a real property violation or a deadlock, never on a parse error. A `lean`
line passes only when the project builds, and `Audit.lean` shows no `sorry` and
only the standard axioms.

Also:
- **Enforce each assumption in code.** Add a cheap test that fails when an
  assumption breaks, for example `attemptTimeout + persistTimeout < staleAge`.
- **Prove the regression test.** Run it against the code before the fix (check
  out `<fix>~1` in a temporary worktree and copy in the test file). Show that it
  fails there and passes on the fix.
- Write a short `specs/<Name>.md`. It lists what the model covers, its
  properties, the check table, the replay result (N of M traces), its
  assumptions, and what it does not prove.

## 10. Deliver

- One branch and one PR per module, each from the default branch. Commit in two
  parts, following the repo's conventions: the spec, then the fix plus tests.
  Stage only that target's files.
- Open PRs only when the user asked for them, or the repo's workflow expects
  them. In batch mode, open them as drafts. The PR body covers the interleaving,
  the fix, the check table, and the before/after test results. Merging and
  deploying are the user's call.
- If CI can't run, run CI's jobs locally (tests, backend variants, lint) and say so.
- Report to the user in 3 parts: the bugs (the concrete interleavings), the
  proof table, and anything left open (assumptions, known limits, residual risk).
  In batch mode, add totals: PRs, bugs, checks and theorems, traces accepted,
  non-test lines added and removed, and tests added.
- Offer section 11.

## 11. Simplify from the proofs (optional)

Do this only when the user asks.

- Open one PR per module, stacked on its fix branch.
- The proofs show which branches are reachable. Don't delete a reachable branch.
  Merge copies of the same logic into one: duplicate cleanup paths, state rebuilt
  by hand in many places, two trackers of the same fact.
- Keep the tests unchanged. Update the model only where the structure changed.
  All its checks, replays included, must still pass.
- When a fix PR merges, rebase the simplification PR stacked on it.

## Bug shapes

### Storage and durable state machines

- Durable state: `status` columns, claims, leases, `locked_until`,
  `next_attempt`, retries, sweepers, reapers, reconcilers.
- An unguarded write (`UPDATE … WHERE id = ?`) next to a guarded claim.
- List-then-act loops that write from a stale snapshot.
- A fan-out saved one row per statement instead of in one transaction.
- A side effect done before the status write that retires it.
- Leases or timeouts whose correctness depends on timing.
- Errors ignored on status writes (`_ = …`).

### Go

- Check-then-act across a lock release: read under `RLock`, then write under
  `Lock` without checking again.
- A map shared across goroutines without a lock. `sync.Map` `Load` then `Store`
  instead of `LoadOrStore` or `CompareAndSwap`.
- Sending on a closed channel, closing twice, or several possible closers
  without `sync.Once`.
- Goroutine leaks: a send or receive with no `ctx.Done()` case, so the goroutine
  blocks forever after its peer gives up.
- A `select` that assumes an order. When several cases are ready, Go picks one
  at random, so work can run after `done` fired.
- `wg.Add` inside the goroutine instead of before `go`.
- A struct holding a mutex copied by value (value receivers, range copies).
- Two mutexes taken in different orders, or a lock held while sending on a
  channel or calling a callback.
- `atomic` reads mixed with plain writes, or an atomic load then store where a
  compare-and-swap is needed.

### Java

- Check-then-act on a `ConcurrentHashMap` (`containsKey` then `put`) instead of
  `computeIfAbsent`, `putIfAbsent`, or `merge`.
- Double-checked locking without `volatile`, and non-`volatile` flags polled in
  a loop.
- One field guarded by different monitors in different methods, or locks taken
  in different orders.
- `wait()` outside a `while` loop, and `notify()` where `notifyAll()` is needed.
- `lock()` without `unlock()` in a `finally`.
- Exceptions lost in executor tasks whose `Future` is never read, and
  `CompletableFuture` callbacks running on an unexpected thread.
- Iterating a shared collection while another thread changes it.
- Virtual threads pinned inside `synchronized` while blocking.

### .NET

- `async void` methods: callers can't await them, and their exceptions crash
  the process or disappear.
- Sync over async (`.Result`, `.Wait()`), which deadlocks under a
  `SynchronizationContext` and starves the thread pool.
- `SemaphoreSlim` used as an async lock without `Release()` in a `finally`, or
  entered again by the same flow (it is not reentrant).
- `ConcurrentDictionary.GetOrAdd` and `AddOrUpdate` factories with side effects.
  The factory can run more than once.
- A plain `Dictionary` or `List` shared across tasks, or check-then-act on one.
- `TaskCompletionSource` without `RunContinuationsAsynchronously`, so
  continuations run inline, sometimes under the caller's lock.
- Fire-and-forget tasks (`_ = DoAsync()`) with unobserved exceptions or an
  assumed order.
- A `CancellationToken` not passed down, or cancellation that skips cleanup.
- `System.Threading.Timer` callbacks that overlap when one runs long.
- One `DbContext` used by concurrent tasks.

### Async TypeScript, JavaScript, and Python

- State checked before an `await` and acted on after it.
- Async generators and iterators: `return()` before the first `next()`, a
  consumer that breaks out during a flush, or a `send()` after abandonment.
- Promises that are never awaited, so their errors and their order are lost.
- Abort or cancel signals that some exit paths don't handle, so the turn or
  request never reaches a terminal state.
- Retry loops whose guards reset each other, so the loop never ends.

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
- The TLC exit code is unreliable. Grep the output for `No error has been found`,
  `is violated`, or `Deadlock reached`.
