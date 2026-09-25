#!/usr/bin/env bash
# Rerun every TLC model listed in checks.txt and compare each result with its
# expected outcome. checks.txt lines: <spec> <config> <pass|fail> [note...].
# A "fail" expectation passes only on a real property violation, never on a
# parse or setup error. Exits non-zero if any result differs.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -z "${JAVA:-}" ]]; then
  if command -v brew >/dev/null && [[ -x "$(brew --prefix openjdk 2>/dev/null)/bin/java" ]]; then
    JAVA="$(brew --prefix openjdk)/bin/java"
  else
    JAVA=java
  fi
fi
JAR="${TLA2TOOLS:-$HOME/.local/share/tla/tla2tools.jar}"
[[ -f "$JAR" ]] || { echo "tla2tools.jar not found at $JAR (set TLA2TOOLS)" >&2; exit 2; }
[[ -f checks.txt ]] || { echo "checks.txt not found next to check.sh" >&2; exit 2; }

meta="$(mktemp -d)"
trap 'rm -rf "$meta"' EXIT
status=0

while read -r spec cfg expect note; do
  [[ -z "${spec:-}" || "$spec" == \#* ]] && continue
  out="$("$JAVA" -XX:+UseParallelGC -cp "$JAR" tlc2.TLC -workers auto -deadlock \
    -metadir "$meta/$cfg" -config "$cfg" "$spec" 2>&1 || true)"
  violated="$(grep -oE '(Invariant|Action property|Temporal properties) [A-Za-z0-9_]* ?(is|were) violated' <<<"$out" | head -1 || true)"
  if grep -q 'No error has been found' <<<"$out"; then got=pass
  elif [[ -n "$violated" ]]; then got=fail
  else got=error
  fi
  mark=ok
  [[ "$got" == "$expect" ]] || { mark=BAD; status=1; }
  printf '%-3s  %-36s expect=%-4s got=%-5s %s\n' "$mark" "$cfg" "$expect" "$got" "${violated:-${note:-}}"
  if [[ "$got" == error ]]; then grep -m3 -iE 'error|exception' <<<"$out" | sed 's/^/     /' || true; fi
done < checks.txt
exit "$status"
