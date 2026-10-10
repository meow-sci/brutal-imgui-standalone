#!/usr/bin/env bash
# act-preflight.sh: non-interactive environment check before running nektos/act.
# Usage: bash act-preflight.sh [repo-dir]
# Prints findings and a suggested base command. Never modifies anything.
# Exit: 0 = ready (maybe with warnings), 1 = blocker (act missing, or no workflows found).

set -u
REPO="${1:-.}"
cd "$REPO" 2>/dev/null || { echo "ERROR: cannot cd to '$REPO'"; exit 1; }

ok()   { printf '  [ok]   %s\n' "$*"; }
warn() { printf '  [warn] %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; }
blocker=0

echo "== act"
if command -v act >/dev/null 2>&1; then
  ok "$(act --version 2>/dev/null)"
else
  bad "act not installed (brew install act | gh extension install nektos/gh-act | see references/installation.md)"
  blocker=1
fi

echo "== container engine"
docker_ok=0
if [ -n "${DOCKER_HOST:-}" ]; then ok "DOCKER_HOST=$DOCKER_HOST"; fi
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    docker_ok=1
    ok "docker reachable: $(docker info --format '{{.ServerVersion}} {{.OperatingSystem}} {{.Architecture}}' 2>/dev/null)"
    ctx_host=$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)
    if [ -z "${DOCKER_HOST:-}" ] && [ -n "$ctx_host" ]; then
      case "$ctx_host" in
        unix:///var/run/docker.sock|unix://$HOME/.docker/run/docker.sock|unix://$HOME/.colima/docker.sock) ;;
        *) warn "docker context endpoint is $ctx_host; act ignores docker contexts. Consider: export DOCKER_HOST=$ctx_host" ;;
      esac
    fi
  else
    warn "docker CLI present but daemon not reachable. Container mode will fail (start Docker Desktop/colima or set DOCKER_HOST). Host mode (-P <label>=-self-hosted) and act -l still work."
  fi
else
  warn "docker CLI not found. Only host mode (-P <label>=-self-hosted) and act -l/-g/--validate will work."
fi

echo "== host"
os=$(uname -s); arch=$(uname -m)
ok "$os/$arch"
if [ "$os" = Darwin ] && [ "$arch" = arm64 ]; then
  warn "Apple Silicon: native arm64 images usually work. Add --container-architecture linux/amd64 if x86-only tools/actions fail."
fi

echo "== actrc / platform mappings"
if [ -n "${XDG_CONFIG_HOME:-}" ]; then xdg="$XDG_CONFIG_HOME/act/actrc"
elif [ "$os" = Darwin ]; then xdg="$HOME/Library/Application Support/act/actrc"
else xdg="$HOME/.config/act/actrc"; fi
has_p=0
for f in "$xdg" "$HOME/.actrc" "./.actrc"; do
  if [ -f "$f" ]; then
    n=$(grep -cE '^[[:space:]]*(-P|--platform)' "$f" 2>/dev/null || true)
    ok "$f ($n platform lines)"
    [ "${n:-0}" -gt 0 ] && has_p=1
    sed -n 's/^[[:space:]]*\(-P\|--platform\)[ =]*/      -P /p' "$f" 2>/dev/null | head -8
  fi
done
if [ "$has_p" -eq 0 ]; then
  warn "no -P mapping in any actrc: act will show an INTERACTIVE image prompt (fatal EOF without a TTY). Always pass -P on the command line."
fi

echo "== workflows"
wfdir=".github/workflows"
if [ -d "$wfdir" ]; then
  count=$(find "$wfdir" -type f \( -name '*.yml' -o -name '*.yaml' \) | wc -l | tr -d ' ')
  ok "$count workflow file(s) in $wfdir"
  [ "$count" -eq 0 ] && blocker=1
  labels=$(grep -rhoE 'runs-on:[[:space:]]*.*' "$wfdir" 2>/dev/null \
    | sed -E 's/runs-on:[[:space:]]*//; s/[][]//g; s/#.*//' | tr ',' '\n' \
    | sed -E 's/^[[:space:]"'\'']*//; s/[[:space:]"'\'']*$//' | grep -v '^$' | sort -u)
  if [ -n "$labels" ]; then
    echo "  runs-on values found (each needs a -P mapping; expressions like \${{ matrix.os }} resolve at runtime):"
    printf '%s\n' "$labels" | sed 's/^/      /'
  fi
  if grep -rqE '^[[:space:]]+(container|services):' "$wfdir" 2>/dev/null; then
    ok "uses container:/services: (needs Docker)"
  fi
  if grep -rqE 'upload-artifact|download-artifact' "$wfdir" 2>/dev/null; then
    warn "uses artifacts: add --artifact-server-path /tmp/act-artifacts"
  fi
  if grep -rqE 'id-token:[[:space:]]*write' "$wfdir" 2>/dev/null; then
    warn "uses OIDC (id-token: write): not supported by act; guard those steps with if: \${{ !env.ACT }}"
  fi
  if command -v act >/dev/null 2>&1; then
    echo "  act -l:"
    act -l 2>/dev/null | sed 's/^/      /' | head -40
  fi
else
  bad "no $wfdir directory in $(pwd)"
  blocker=1
fi

echo "== secrets / token"
for f in .secrets .vars .env .input; do
  if [ -f "$f" ]; then
    if git check-ignore -q "$f" 2>/dev/null; then ok "$f present (gitignored)"
    else warn "$f present but NOT gitignored: it will be copied into job containers by checkout"; fi
  fi
done
if command -v gh >/dev/null 2>&1 && gh auth token >/dev/null 2>&1; then
  ok "gh is logged in: act will auto-use 'gh auth token' as GITHUB_TOKEN"
else
  warn "no gh token: pass -s GITHUB_TOKEN=... if workflows call the GitHub API or use private actions"
fi

echo "== suggested base command"
if [ "$docker_ok" -eq 1 ]; then
  echo "  act <event> -P ubuntu-latest=catthehacker/ubuntu:act-latest -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 -P ubuntu-22.04=catthehacker/ubuntu:act-22.04 [-W <file>] [-j <job>] > /tmp/act.log 2>&1; echo \"exit=\$?\""
else
  echo "  act <event> -P ubuntu-latest=-self-hosted [-W <file>] [-j <job>]   # host mode, no isolation"
fi

exit "$blocker"
