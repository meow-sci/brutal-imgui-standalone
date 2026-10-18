#!/usr/bin/env bash
# Run the GitHub Actions workflows locally with nektos/act (every job runs on ubuntu-latest;
# no Windows/macOS jobs). A local clone of the private ksa-game-assemblies repo (keep it pulled to
# the latest main, like CI) stands in for the CI checkout.
#
#   KSA_GAME_ASSEMBLIES_ROOT=/path/to/ksa-game-assemblies scripts/act_local.sh ci
#   KSA_GAME_ASSEMBLIES_ROOT=/path/to/ksa-game-assemblies scripts/act_local.sh release [tag]
#
# Extra arguments after the mode/tag are passed to act (e.g. -j pack).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
mode="${1:?usage: act_local.sh ci|release [tag] [act args...]}"
shift
: "${KSA_GAME_ASSEMBLIES_ROOT:?set KSA_GAME_ASSEMBLIES_ROOT to a local ksa-game-assemblies clone}"
out="${ACT_OUT:-$root/artifacts/act}"
mkdir -p "$out"

# Package checks need a linux-x64 process, so containers run amd64 (emulated on Apple Silicon).
# act rebuilds PATH from the *local* image metadata, which for a multi-arch tag is the host
# (arm64) variant and loses node; a single-arch amd64 image avoids that.
image=local/act-ubuntu:amd64
if ! docker image inspect "$image" >/dev/null 2>&1; then
  echo 'FROM catthehacker/ubuntu:act-latest' | docker build --platform linux/amd64 -t "$image" -
fi

args=(
  -P "ubuntu-latest=$image" --pull=false
  --container-architecture linux/amd64
  --container-options "-v $KSA_GAME_ASSEMBLIES_ROOT:/ksa-game-assemblies:ro"
  --env KSA_ASSEMBLIES_LOCAL=/ksa-game-assemblies
  --artifact-server-path "$out/artifacts"
)
if command -v gh >/dev/null && token="$(gh auth token 2>/dev/null)"; then
  args+=(-s "GITHUB_TOKEN=$token")   # avoids anonymous rate limits when act clones actions
fi

case "$mode" in
  ci)
    exec act push -W "$root/.github/workflows/ci.yml" "${args[@]}" "$@"
    ;;
  release)
    tag="${1:-v0.0.1-act.1}"
    [ $# -gt 0 ] && shift
    event="$out/release-event.json"
    printf '{"ref": "refs/tags/%s", "ref_name": "%s", "act": true}\n' "$tag" "$tag" > "$event"
    exec act push -W "$root/.github/workflows/release.yml" -e "$event" "${args[@]}" "$@"
    ;;
  *)
    echo "unknown mode: $mode (expected ci or release)" >&2
    exit 2
    ;;
esac
