# yavosh skills

Agent skills for Claude Code and Codex, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `/yavosh:work` or `$work` in Codex | Takes one issue or problem statement to an open, reviewed PR or MR. A coordinator plans the fix, delegates coding and review when agents are available, and triages findings for up to 3 rounds. |
| `/yavosh:snapshot` or `$snapshot` in Codex | Saves session state to a unique file. It resumes a selected task or the latest snapshot in a fresh session. |
| `/yavosh:formal-verify` or `$formal-verify` in Codex | Models risky code in TLA+ and Lean 4. It replays real traces, confirms bugs with failing tests, fixes them, and leaves checks in `specs/check.sh`. With no target, it reports ranked targets without changing code. |

## Install

In Claude Code, run:

```
/plugin marketplace add yavosh/skills
/plugin install yavosh@yavosh-skills
```

From a shell, run:

```sh
claude plugin marketplace add yavosh/skills
claude plugin install yavosh@yavosh-skills
```

To install the skills in Codex, run this from the cloned repository:

```sh
mkdir -p "$HOME/.agents/skills"
cp -R skills/work skills/snapshot skills/formal-verify "$HOME/.agents/skills/"
```

Copy whole skill directories so `formal-verify/check.sh` is included.
Invoke them as `$work`, `$snapshot`, or `$formal-verify` in Codex.
For repository-scoped installation, use `.agents/skills/` in that repository.
These are the [currently documented Codex skill locations](https://learn.chatgpt.com/docs/build-skills).
Older installations under `~/.codex/skills` may still work. Avoid keeping duplicate copies with the same skill names.

## Update

```sh
claude plugin marketplace update yavosh-skills
claude plugin update yavosh@yavosh-skills
```

Restart Claude Code to apply the update.

For Codex, run these commands from the clone's default branch:

```sh
git pull --ff-only
mkdir -p "$HOME/.agents/skills"
cp -R skills/work skills/snapshot skills/formal-verify "$HOME/.agents/skills/"
```

Restart Codex if the updated skill does not appear.

## Usage

```
/yavosh:work #142
/yavosh:work the login form accepts empty passwords
/yavosh:snapshot save indent-fix
/yavosh:snapshot resume
/yavosh:snapshot resume indent-fix
/yavosh:snapshot list
/yavosh:formal-verify
/yavosh:formal-verify the outbox dispatcher
```

In Codex:

```
$work #142
$snapshot save indent-fix
$snapshot resume indent-fix
$formal-verify
$formal-verify the outbox dispatcher
```

Request a batch explicitly to verify multiple targets, with one branch and PR per module.

## Requirements

- `work`:
  - git and an authenticated [GitHub CLI](https://cli.github.com/) (`gh`) for GitHub PRs. GitLab MRs use git push options.
  - Agent delegation is optional. Without it, the coordinator codes and reviews directly.
- `snapshot`: git, a POSIX shell, and `mktemp`. It stores snapshots under `~/.local/state/agent-snapshots/`, shared across worktrees. Set `SNAPSHOT_DIR` to override the directory or resume existing Claude snapshots.
- `formal-verify`: git, Java, and `tla2tools.jar`. Missing Java uses the host's package manager. The jar download uses TLA+ v1.7.4. Lean (through `elan`) is installed only when a target needs it. Set `JAVA` or `TLA2TOOLS` for custom paths.

## Validation

Run the verification runner's regression tests:

```sh
python3 -B -m unittest discover -s tests -v
bash -n skills/formal-verify/check.sh
```

The tests use tool fixtures and require no Java, TLA+, or Lean installation.
They validate runner behavior. Complete Codex and Claude Code workflows require separate validation.
Model proofs and trace replays do not prove complete correspondence with the implementation.

## License

[MIT](LICENSE)
