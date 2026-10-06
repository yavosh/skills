# yavosh skills

Claude Code skills, packaged as one plugin. The `work` skill also runs in Codex.

| Skill | What it does |
|---|---|
| `/yavosh:work` or `$work` in Codex | Takes one issue or problem statement to an open, reviewed PR or MR. A coordinator plans the fix, delegates coding and review when agents are available, and triages findings for up to 3 rounds. |
| `/yavosh:snapshot` | Saves the working state of a session to a file. After `/clear` or `/compact`, it briefs the fresh session from that file. |
| `/yavosh:formal-verify` | Models risky code in TLA+ and Lean 4 to find concurrency, state, and data-flow bugs. It replays real traces through each model, confirms each bug with a failing test, fixes it, and leaves a rerunnable before/after proof in `specs/check.sh`. With no target, it works every ranked module, one PR each. |

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

To use `work` in Codex, run this from the cloned repository:

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/work"
cp skills/work/SKILL.md "${CODEX_HOME:-$HOME/.codex}/skills/work/SKILL.md"
```

Invoke it as `$work` in Codex.

## Update

```sh
claude plugin marketplace update yavosh-skills
claude plugin update yavosh@yavosh-skills
```

Restart Claude Code to apply the update.

## Usage

```
/yavosh:work #142
/yavosh:work the login form accepts empty passwords
/yavosh:snapshot save indent-fix
/yavosh:snapshot resume
/yavosh:snapshot list
/yavosh:formal-verify
/yavosh:formal-verify the outbox dispatcher
```

## Requirements

- `work`:
  - git and an authenticated [GitHub CLI](https://cli.github.com/) (`gh`) for GitHub PRs. GitLab MRs use git push options.
  - Agent delegation is optional. Without it, the coordinator codes and reviews directly.
- `snapshot`: git and a POSIX shell. It stores snapshots in `~/.claude/projects/<project>/snapshots/`, or under `$CLAUDE_CONFIG_DIR` when that variable is set.
- `formal-verify`: git, Java, and `tla2tools.jar`. If Java or the jar is missing, the skill installs it (Java through Homebrew, the jar into `~/.local/share/tla/`). Lean (through `elan`) is installed only when a target needs it.

## License

[MIT](LICENSE)
