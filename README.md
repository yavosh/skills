# yavosh skills

Claude Code skills, packaged as one plugin.

| Skill | What it does |
|---|---|
| `/yavosh:work` | Takes one GitHub issue or problem statement to an open, reviewed PR. An orchestrator plans the fix, a coder subagent implements it, and a reviewer subagent attacks it, for up to 3 rounds. |
| `/yavosh:snapshot` | Saves the working state of a session to a file. After `/clear` or `/compact`, it briefs the fresh session from that file. |
| `/yavosh:formal-verify` | Models risky code in TLA+ (or Lean) to find concurrency, state, and data-flow bugs. It confirms each bug with a failing test, fixes it, and leaves a rerunnable before/after proof in `specs/check.sh`. |

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
  - git and an authenticated [GitHub CLI](https://cli.github.com/) (`gh`). Without a GitHub remote, it stops at a local commit and opens no PR.
  - Access to Opus and Sonnet. The reviewer uses Fable and falls back to Opus.
- `snapshot`: git and a POSIX shell. It stores snapshots in `~/.claude/projects/<project>/snapshots/`, or under `$CLAUDE_CONFIG_DIR` when that variable is set.
- `formal-verify`: git, Java, and `tla2tools.jar`. If Java or the jar is missing, the skill installs it (Java through Homebrew, the jar into `~/.local/share/tla/`). Lean is installed only when a target needs it.

## License

[MIT](LICENSE)
