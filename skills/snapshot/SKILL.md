---
name: snapshot
description: >-
  Save the working state of a session to a file, then brief a fresh session from
  that file after /clear or /compact. Use when context is about to run out,
  before clearing, when handing work to a new session, or when the user asks to
  save, checkpoint, resume, or restore progress. Invoke as
  /yavosh:snapshot [save|resume|list] [label].
---

# snapshot

A `/clear` throws away everything the model learned: which approach already
failed, which file holds the real bug, what "done" means for this task. The
code and the git history survive; the reasoning does not. This skill writes
that reasoning to a file and reads it back.

## Where snapshots live

Outside the repo, one directory per project:

```sh
SNAPDIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(pwd | sed 's|/|-|g')/snapshots"
```

Keeping them out of the working tree means a snapshot never shows up in
`git status`, never lands in a commit, and never needs a `.gitignore` entry.
Files are named `YYYY-MM-DD-HHMM-<label>.md`, so sorting by name gives the
newest last.

## Mode

| Argument | Action |
|---|---|
| none | Save. But if the session has no work in context yet — a fresh window — resume instead. |
| `save`, `s` | Save, always |
| `resume`, `r`, `restore` | Read the newest snapshot and brief |
| `list`, `l` | List snapshots with their goal lines |

Extra words are the label: `/yavosh:snapshot save indent-fix` → `...-indent-fix.md`.

## Save

### 1. Collect the mechanical facts

```sh
SNAPDIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(pwd | sed 's|/|-|g')/snapshots"
mkdir -p "$SNAPDIR"
git branch --show-current; git status --short; git log --oneline -5; git diff --stat
```

Cheap, and it anchors everything else. Include untracked files — a new test
file the next session cannot see is the classic lost thread.

### 2. Write the file

```sh
cat > "$SNAPDIR/$(date +%Y-%m-%d-%H%M)-<label>.md" <<'EOF'
# <one-line goal>

- **Branch:** <branch>  **Base:** <commit sha + subject>
- **Issue/PR:** <#nnn or none>

## Goal
What the user asked for, in their terms. One or two sentences.

## State
What is done and how it was verified — a passing test name, a command and its
output, a render that was actually looked at. Then what is half-done, and where
exactly it stops.

## Files
`path:line` for each place that matters, one line of why each.

## Next steps
1. Concrete and actionable. Verbs, not topics.
2. ...

## Decisions and dead ends
Approaches already ruled out and the reason. This is the part a fresh session
cannot rediscover and will otherwise retry.

## Resume commands
The exact build/test/run invocation, including any env setup.

## Open questions
Anything waiting on the user.
EOF
```

Write it yourself from the conversation — do not shell out to summarise. Rules:

- **Facts, not vibes.** "108 of 219 lines match, measured by X" beats "close".
- **Absolute over relative.** "before the fix" means nothing later; name the sha.
- **A dead end is worth more than a success.** Successes are in the diff.
- **No secrets.** Reference an env var by name; never paste its value.
- Aim for one screen. A snapshot nobody reads is worse than none.

### 3. Confirm

Print the path and the next steps. Then tell the user they can `/clear`.

## Resume

### 1. Find and read the newest snapshot

```sh
SNAPDIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(pwd | sed 's|/|-|g')/snapshots"
ls -1 "$SNAPDIR" | tail -1
cat "$SNAPDIR/$(ls -1 "$SNAPDIR" | tail -1)"
```

If the directory is empty, say so and ask what to work on. Do not guess.

### 2. Check for drift

The tree may have moved since the snapshot — another session, a merge, the
user's own edits.

```sh
git branch --show-current && git status --short && git log --oneline -5
```

Compare against the snapshot's branch and base sha. If they differ, say so in
the brief and treat the snapshot as a lead, not as truth.

### 3. Brief, then continue

Six to ten lines, no more:

- The goal, in one line
- Where the work stopped
- Drift since the snapshot, if any
- The next step you are about to take

Then start on it. Do not wait for permission the user has already given —
`/yavosh:snapshot resume` is the go-ahead. Stop only if the snapshot has an open
question that blocks the next step.

Re-read the files the snapshot names before you act on them. The snapshot says
what was true when it was written; the file says what is true now.

## Notes

- Snapshots accumulate. `/yavosh:snapshot list` shows them; delete stale ones by hand.
- This is not project memory. Durable facts about the user or the project belong
  in the memory directory. A snapshot is disposable — it describes one piece of
  in-flight work and stops being true the moment that work lands.
