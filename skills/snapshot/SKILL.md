---
name: snapshot
description: >-
  Save the working state of a session to a file, then brief a fresh session from
  that file after resetting or compacting context. Use when context is about to run out,
  before clearing, when handing work to a new session, or when the user asks to
  save, checkpoint, resume, or restore progress. Invoke as
  $snapshot in Codex or /yavosh:snapshot in Claude Code, with
  [save|resume|list] [label or filename].
---

# snapshot

A fresh session loses what the model learned: which approach already
failed, which file holds the real bug, what "done" means for this task. The
code and the git history survive; the reasoning does not. This skill writes
that reasoning to a file and reads it back.

## Where snapshots live

Outside the repo, one directory per project:

```sh
PROJECT_DIR="$(git rev-parse --git-common-dir)"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd -P)"
SNAPDIR="${SNAPSHOT_DIR:-$HOME/.local/state/agent-snapshots/$(printf '%s' "$PROJECT_DIR" | sed 's|/|-|g')}"
```

Keeping them out of the working tree means a snapshot never shows up in
`git status`, never lands in a commit, and never needs a `.gitignore` entry.
Worktrees share the repository's common Git directory, so they share snapshots.
Set `SNAPSHOT_DIR` to use another directory outside the working tree.
Existing Claude snapshots can be read by setting it to their current directory.
Files contain Markdown and use `YYYY-MM-DD-HHMMSS-<label>.<random>` names.
The random suffix prevents repeated saves from overwriting an existing snapshot.

## Mode

| Argument | Action |
|---|---|
| none | Save. But if the session has no work in context yet — a fresh window — resume instead. |
| `save`, `s` | Save, always |
| `resume`, `r`, `restore` | Read the selected snapshot, or the newest when no selector is given, and brief |
| `list`, `l` | List snapshots with their goal lines |

For save, convert extra words to a lowercase label containing only letters, digits, and hyphens.
For resume, extra words select a label or exact filename within `SNAPDIR`.

## Save

### 1. Collect the mechanical facts

```sh
PROJECT_DIR="$(git rev-parse --git-common-dir)"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd -P)"
SNAPDIR="${SNAPSHOT_DIR:-$HOME/.local/state/agent-snapshots/$(printf '%s' "$PROJECT_DIR" | sed 's|/|-|g')}"
mkdir -p "$SNAPDIR"
git branch --show-current; git status --short; git log --oneline -5; git diff --stat
```

Cheap, and it anchors everything else. Include untracked files — a new test
file the next session cannot see is the classic lost thread.

### 2. Write the file

```sh
SNAPFILE="$(mktemp "$SNAPDIR/$(date +%Y-%m-%d-%H%M%S)-<label>.XXXXXX")"
cat > "$SNAPFILE" <<'EOF'
# <one-line goal>

- **Branch:** <branch>  **Base:** <commit sha + subject>
- **Worktree:** <absolute path>  **Saved HEAD:** <commit sha>
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

Print the path and the next steps. Tell the user how to resume in their current agent.
In Codex, invoke `$snapshot resume <filename>` in the fresh session.
In Claude Code, invoke `/yavosh:snapshot resume <filename>` after `/clear`.

## Resume

### 1. Find and read the selected snapshot

If a filename is given, read that file within `SNAPDIR`.
If a label is given, read the newest snapshot with that exact label.
If nothing matches, report that and list available snapshots; do not resume another task.
Without a selector, read the newest snapshot:

```sh
PROJECT_DIR="$(git rev-parse --git-common-dir)"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd -P)"
SNAPDIR="${SNAPSHOT_DIR:-$HOME/.local/state/agent-snapshots/$(printf '%s' "$PROJECT_DIR" | sed 's|/|-|g')}"
SNAPFILE="$(ls -1t "$SNAPDIR" | head -1)"
test -n "$SNAPFILE" && cat "$SNAPDIR/$SNAPFILE"
```

If the directory is empty, say so and ask what to work on. Do not guess.

### 2. Check for drift

The tree may have moved since the snapshot — another session, a merge, the
user's own edits.

Run repository commands in the snapshot's saved worktree when it still exists.
Verify its branch before continuing. Do not switch branches in a shared checkout.
If the worktree is missing or its branch changed, report that and ask which worktree to use.
Do not apply next steps to another branch or assume saved uncommitted files exist there.
Older snapshots without a worktree path require selecting a worktree before continuing.

```sh
git branch --show-current && git status --short && git log --oneline -5
```

Compare against the snapshot's branch and saved HEAD in the selected worktree.
Report commit drift in the brief and treat the snapshot as a lead, not as truth.

### 3. Brief, then continue

Six to ten lines, no more:

- The goal, in one line
- Where the work stopped
- Drift since the snapshot, if any
- The next step you are about to take

Then start on it. Do not wait for permission the user has already given —
an explicit snapshot resume is the go-ahead. Stop if worktree selection or an open question blocks the next step.

Re-read the files the snapshot names before you act on them. The snapshot says
what was true when it was written; the file says what is true now.

## Notes

- Snapshots accumulate. The `list` mode shows them; delete stale ones by hand.
- Resuming is explicit. Installing this skill does not restore snapshots automatically in every new session.
- This is not project memory. Durable facts about the user or the project belong
  in the memory directory. A snapshot is disposable — it describes one piece of
  in-flight work and stops being true the moment that work lands.
