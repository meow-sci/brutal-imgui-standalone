---
name: act
description: Run, test, and debug GitHub Actions workflows locally with nektos/act (the `act` CLI, also `gh act`), which executes .github/workflows jobs in Docker containers or directly on the host. Use when asked to run CI locally, test or debug a workflow/job/matrix before pushing, simulate events (push, pull_request, workflow_dispatch, tags, releases, schedule), pass secrets/vars/inputs, use service containers, artifacts or actions/cache locally, test a custom/composite/docker action or reusable workflow, or troubleshoot act errors and incompatibilities with GitHub-hosted runners.
license: MIT
compatibility: Requires the act CLI (verified against v0.2.89) and, for container mode, a running Docker Engine API (Docker Desktop, colima, podman socket, or remote DOCKER_HOST). Network access is needed to pull images and remote actions unless --action-offline-mode caches are warm.
metadata:
  author: synthesized from nektos/act docs + source (v0.2.89)
  version: "1.0"
---

# act — run GitHub Actions locally

`act` reads `.github/workflows/*.yml`, builds a job dependency plan for an event, and runs each job in a Docker container (or on the host) with GitHub-like env vars, contexts, and filesystem. It is a **simulation**: images are not identical to GitHub runners and some features are ignored (see [workflow-support.md](references/workflow-support.md)).

## Agent golden rules (read first)

act has several behaviors that hang or mislead a non-interactive agent:

1. **Always provide a platform image.** If no `-P` flag is found on the CLI or in any `.actrc`, act opens an interactive image picker. Without a TTY it dies with `level=fatal msg=EOF`. Always pass `-P ubuntu-latest=catthehacker/ubuntu:act-latest` (or make sure an actrc has `-P` lines).
2. **Never pass `-s NAME` or `--var NAME` without `=value`** unless `NAME` is exported in the environment. Otherwise act prompts for hidden input and blocks. Prefer `--secret-file`.
3. **Run `act -l` before running anything.** It shows which jobs and workflows match the event, at no cost.
4. **Check the exit code.** `0` means every job succeeded. `1` means a job failed (`Error: Job '<name>' failed`) or there was a config/parse error.
5. **The workspace is empty unless the job uses `actions/checkout`** (act replaces it with a copy of your local working tree, `.git` and uncommitted changes included, gitignored files excluded) or you pass `--bind`. If that checkout has any `ref:` or `repository:` key (even `${{ github.ref }}`), act does a **real clone from GitHub** instead, and your local changes aren't tested.
6. **On Apple Silicon**, act warns about architecture on every run. Native arm64 images (catthehacker images are multi-arch) usually work. Add `--container-architecture linux/amd64` only when a tool or action needs x86_64.
7. **No branch or path filtering.** `on.push.branches`, `paths`, and `types` are ignored. Every workflow whose `on:` lists the event will run. Use `-W <file>` and `-j <job>` to narrow it down.
8. Logs are long. Redirect to a file and grep (`act ... > /tmp/act.log 2>&1; echo $?`), or use `--json` for machine parsing.

## Preflight

```sh
act --version                 # installed? (brew install act | gh extension install nektos/gh-act)
docker info >/dev/null && echo docker-ok   # container mode needs a Docker API
act -l                        # parses workflows, lists jobs (no Docker needed)
```

Or run the bundled check: `bash scripts/act-preflight.sh [repo-dir]`. It reports install state, the Docker socket, any actrc platform config, and suggested flags.

## Core commands

```sh
act -l                                   # list ALL jobs (stage, job id, workflow, file, events)
act -l pull_request                      # list jobs that a pull_request event would run
act -g push                              # draw the job dependency graph
act --validate                           # parse/schema-check workflows only (add --strict for strict schema)
act -n push -P ubuntu-latest=...         # dry run: plan + validate without creating containers

act push                                 # run every workflow triggered by push (default event)
act pull_request -e event.json           # simulate PR with a payload
act workflow_dispatch --input name=val   # manual trigger with inputs
act -j test                              # run job id "test" (+ the jobs it `needs`) from ALL workflows
act -W .github/workflows/ci.yml -j test  # one job from one file
act --matrix node:20 --matrix os:ubuntu-latest   # only matching matrix combinations
```

Event selection: positional arg if given. Otherwise, if the loaded workflows have exactly one event, that event. Otherwise `--detect-event` picks the first one alphabetically. Otherwise `push`.

## Recommended baseline invocation

```sh
act <event> \
  -P ubuntu-latest=catthehacker/ubuntu:act-latest \
  -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 \
  -P ubuntu-22.04=catthehacker/ubuntu:act-22.04 \
  -W .github/workflows/<file>.yml -j <job> \
  --secret-file .secrets --var-file .vars \
  --artifact-server-path /tmp/act-artifacts \
  > /tmp/act.log 2>&1; echo "exit=$?"
```

Persist defaults in `./.actrc` (one flag per line), e.g.:

```
-P ubuntu-latest=catthehacker/ubuntu:act-latest
--artifact-server-path=/tmp/act-artifacts
--container-architecture=linux/amd64
```

`--pull=false` (or `--action-offline-mode`) skips re-pulling images you already have, which saves a lot of time on repeated runs.

## Secrets, vars, env, inputs (quick)

| Need | Flag | Default file (auto-loaded from `-C` dir if it exists) |
|---|---|---|
| `${{ secrets.X }}` | `-s X=val` / `--secret-file f` | `.secrets` |
| `${{ vars.X }}` | `--var X=val` / `--var-file f` | `.vars` |
| `env` for every step | `--env X=val` / `--env-file f` | `.env` |
| `inputs.X` for workflow_dispatch | `--input X=val` / `--input-file f` | `.input` |

Files use dotenv format (`KEY=value`). Files ending `.yml`/`.yaml` are read as YAML maps. Secret and var names are upper-cased. CLI values beat file values. If `GITHUB_TOKEN` isn't supplied, act runs `gh auth token` automatically when `gh` is installed. Explicit form: `-s GITHUB_TOKEN="$(gh auth token)"`. Add `.secrets`, `.vars`, and `.env` to `.gitignore`: checkout copies the working tree, minus gitignored files, into the container. Details: [secrets-vars-env-inputs.md](references/secrets-vars-env-inputs.md).

## Behaviors that differ from GitHub (verified)

- `services:` work. From a plain `runs-on` job, reach them at `localhost:<published port>` (needs `ports:`). From a `container:` job, use the service id as hostname.
- Default shell in a `container:` job is `sh`. Add `shell: bash` for bash syntax.
- Step `continue-on-error` and `timeout-minutes` work. Job-level `timeout-minutes`, `continue-on-error`, `concurrency`, `permissions`, `environment`, and OIDC are ignored or unsupported.
- `$GITHUB_STEP_SUMMARY` content is just printed into the log. Annotations and problem matchers are ignored.
- `actions/cache` works out of the box (built-in cache server). Artifacts need `--artifact-server-path`.
- Event-JSON `inputs` booleans must be strings (`"true"`). JSON `true` evaluates as false.
- JS actions use the image's `node` (catthehacker `act-*` images ship one). Docker actions see the workspace at the host-absolute path, not `/github/workspace`.

## Detecting act inside a workflow

act sets env `ACT=true` (and `CI=true`, `GITHUB_ACTIONS=true`). It defaults to actor `nektos/act` and run id/number `1`.

```yaml
- name: Publish
  if: ${{ !env.ACT }}          # step-level: skip under act
  run: ./publish.sh
jobs:
  deploy:
    if: ${{ !github.event.act }}   # job-level: env context unavailable; pass -e with {"act": true}
```

## Typical agent tasks → where to look

| Task | Reference |
|---|---|
| All flags, defaults, `.actrc` locations and syntax | [cli-reference.md](references/cli-reference.md) |
| Event payloads (PR, tag push, release, schedule, dispatch, workflow_call), ref/sha rules | [events-and-payloads.md](references/events-and-payloads.md) |
| Secrets/vars/env/inputs/GITHUB_TOKEN, file formats, precedence, masking | [secrets-vars-env-inputs.md](references/secrets-vars-env-inputs.md) |
| Runner images, `-P`, host mode (`-self-hosted`), arch, private registries | [runners-and-images.md](references/runners-and-images.md) |
| Workspace/checkout/`--bind`, paths, container reuse and cleanup | [workspace-and-containers.md](references/workspace-and-containers.md) |
| Service containers, `container:` jobs, networking, docker socket, options | [services-and-networking.md](references/services-and-networking.md) |
| upload/download-artifact, actions/cache, cache server | [artifacts-and-cache.md](references/artifacts-and-cache.md) |
| Remote/local/composite/docker actions, reusable workflows, `--local-repository`, offline mode, GHE | [actions-and-reusable-workflows.md](references/actions-and-reusable-workflows.md) |
| What is / isn't supported, expression functions, workflow commands, env files | [workflow-support.md](references/workflow-support.md) |
| Podman, colima, remote Docker, docker context, socket detection | [container-engines.md](references/container-engines.md) |
| Error messages → fixes | [troubleshooting.md](references/troubleshooting.md) |
| End-to-end recipes (debug failing CI, test an action, matrix subset, Makefile replacement, CI-in-CI) | [recipes.md](references/recipes.md) |
| Installing act on any OS | [installation.md](references/installation.md) |

Ready-to-use event payloads are in [assets/events/](assets/events/) (copy one and edit it, then pass `-e path`).

## Reading act output

- Line prefix `[<workflow name>/<job name>]`. Matrix jobs get a `-1`, `-2`, … suffix.
- `⭐ Run Main <step>` starts a step. `| ...` lines are step stdout/stderr. `✅  Success` / `❌  Failure` end the step.
- `🏁  Job succeeded|failed` ends the job. The final `Error: Job 'x' failed` sets exit code 1.
- `🚧  Skipping unsupported platform -- Try running with -P <label>=...` means the job's `runs-on` label has no image mapping, so the job is **silently skipped**. Add `-P`.
- `-v` adds debug logs (expression evaluation, skip reasons). `-q` hides step output. `--json` emits one JSON object per line (`job`, `jobID`, `step`, `stepResult`, `jobResult`, `msg`, `matrix`).

## Cleanup and debugging state

- A successful job removes its container and volumes. A **failed job's container is left running** (`act-<workflow>-<job>-<hash>`) so you can `docker exec -it <name> bash` to inspect it. Use `--rm` to remove it on failure.
- `-r/--reuse` keeps containers between runs to preserve state. Clean up leftovers with `docker ps -a --filter name=act- -q | xargs docker rm -f`.
- Volume `act-toolcache` (mounted at `/opt/hostedtoolcache`) persists setup-* tool downloads between runs on purpose.
