# Troubleshooting act

First steps for any problem:
1. `act --bug-report` (versions, docker host, sockets, actrc contents, engine info).
2. Re-run with `-v` and save logs: `act ... -v > /tmp/act.log 2>&1; echo $?`, then grep `level=error|Failure|fatal|Skipping`.
3. `act -l <event>` to confirm which jobs are planned.

## Contents
- [Startup / configuration](#startup--configuration)
- [Docker connectivity](#docker-connectivity)
- [Planning: jobs not running or the wrong jobs running](#planning)
- [Workflow parse errors](#workflow-parse-errors)
- [Step failures that pass on GitHub](#step-failures-that-pass-on-github)
- [Actions fetching / auth](#actions-fetching--auth)
- [Artifacts / cache / services](#artifacts--cache--services)
- [Containers left behind / conflicts](#containers-left-behind--conflicts)
- [Known issue: MODULE_NOT_FOUND](#module_not_found)

## Startup / configuration

| Symptom | Cause → fix |
|---|---|
| `? Please choose the default image you want to use with act` and then `level=fatal msg=EOF` | No `-P` anywhere, no TTY. Pass `-P ubuntu-latest=catthehacker/ubuntu:act-latest` or add `-P` lines to `./.actrc`/`~/.actrc` |
| Hangs at `Provide value for 'NAME':` | `-s NAME`/`--var NAME` without value and env var unset. Use `NAME=value` or export it. Kill the hung process |
| `⚠ You are using Apple M-series chip and you have not specified container architecture` | Informational. Add `--container-architecture linux/amd64` only if x86-only binaries/actions fail |
| `Error loading from .secrets: ...` | Malformed dotenv/YAML file. Check quoting and multi-line values |
| Flags in `.actrc` ignored | Lines must start with `-`. The file must be in the **invocation** dir (not `-C`), `~/.actrc`, or the XDG path. Confirm with `act --bug-report` |
| Warnings `--privileged is deprecated` (also userns/cap-add/cap-drop) | Use `--container-options "--privileged"` etc. |

## Docker connectivity

| Symptom | Fix |
|---|---|
| `Couldn't get a valid docker connection` / `failed to connect to the docker API at unix://...docker.sock ... no such file or directory` / `Cannot connect to the Docker daemon` | Start the engine (Docker Desktop: `open -a Docker`; Linux: `sudo systemctl start docker`; `colima start`), check `docker info`, or set `DOCKER_HOST` |
| Works with `docker` CLI but not act (non-default context) | `export DOCKER_HOST=$(docker context inspect --format '{{.Endpoints.docker.Host}}')` |
| `permission denied ... docker.sock` | Add the user to the docker group, or use rootless `DOCKER_HOST` |
| `toomanyrequests: You have reached your pull rate limit` | `docker login`, then `--pull=false` / `--action-offline-mode` for repeat runs |
| `no space left on device` | `full-*` images need ~75GB. `docker system prune`, use `act-*` images |
| `no matching manifest for linux/arm64` | Image lacks arm64. Use `--container-architecture linux/amd64` or a multi-arch image |
| `invalid reference format` | Image name in `-P`/`container:` has uppercase letters or bad characters, or an expression evaluated to empty |

## Planning

| Symptom | Cause → fix |
|---|---|
| `Could not find any stages to run. View the valid jobs with act --list` | Event not in any workflow's `on:` (e.g. ran `act` = `push` for a PR-only workflow), or `-j` id typo (use the job **id**, not `name:`). Run `act -l` and pass the right event/`-j`/`-W` |
| Job silently not run, log shows `🚧  Skipping unsupported platform -- Try running with -P <label>=...` | `runs-on` label unmapped (`self-hosted`, `macos-*`, `windows-*`, custom). Add `-P label=image` or `-P label=-self-hosted` |
| Job skipped with no output | Job `if:` false. `-v` shows `Skipping job '<name>' due to '<expr>'`. Check simulated `github.ref`/`event_name` (supply `-e` payload) |
| Too many workflows run | Branch/path/type filters are ignored. Narrow with `-W file` and `-j job` |
| `Detected multiple jobs with the same job name, use -W` | Same job id in several files. Add `-W` |
| A `needs` dependency runs when using `-j` | Expected: `-j` includes transitive needs. Use a separate test workflow, or guard with `if:` |
| `--input` values not seen | `-e` given (inputs then come only from JSON), or event isn't `workflow_dispatch` |
| Boolean input is false though passed `true` in JSON | Use the string `"true"` in event JSON |
| `--matrix` selects nothing | Values are compared as strings against the matrix values, and `exclude` wins. Check with `-l`/`-v` (`Final matrix after applying user inclusions`) |

## Workflow parse errors

| Message | Fix |
|---|---|
| `workflow is not valid. '<file>': ... Actions YAML Schema Validation Error detected` | act's schema is strict and its errors are cryptic. Check with the GitHub Actions VS Code extension or `actionlint`. Common causes: unknown keys, wrong types, `if` with stray `${{`, newer GitHub syntax act doesn't know yet |
| `yaml: line N: did not find expected ',' or '}'` | A `${{ ... }}` expression inside a YAML **flow mapping** `{ key: ${{ x }} }`. Use block style or quote the value |
| `Job name 'x' is invalid. Names must start with a letter or '_'...` | Job ids must match `^[A-Za-z_][A-Za-z0-9_-]*$` |
| `unable to read workflow '<f>': file is empty` | Empty yml in the workflows dir. Remove it or use `-W` |
| `Matrix exclude key "k" does not match any key within the matrix` | Fix the exclude keys |
| `` `uses` key references invalid workflow path `` | Reusable workflow must be `./.github/workflows/x.yml` or `owner/repo/.github/workflows/x.yml@ref` |

## Step failures that pass on GitHub

| Symptom | Fix |
|---|---|
| `command not found` (`gh`, `aws`, `az`, `kubectl`, `yarn`, browsers, …) | Medium image lacks it. Install it in a step guarded by `if: ${{ env.ACT }}`, use a `full-*` or custom image |
| `exec: "node": executable file not found` / JS action fails immediately | Job image or `container:` lacks node. Use catthehacker images or install node |
| Files missing in workspace (`No such file or directory`, `package.json not found`) | No `actions/checkout` step (workspace is empty), or the files are gitignored (`--use-gitignore=false`), or checkout has `ref:`/`repository:` and so cloned the remote instead (see [workspace-and-containers.md](workspace-and-containers.md)) |
| `fatal: not a git repository` | Same as above. Checkout substitution includes `.git` |
| Bash syntax errors in a `container:` job | Default shell is `sh`. Set `shell: bash` |
| `sudo: command not found` or permission errors | `act-*` images run as root (no sudo needed). `runner-*` images run as `runner`. Choose based on what the workflow expects |
| systemd/service manager errors (`systemctl`) | Not available in containers. Guard or replace |
| OIDC: `Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env variable` | Not supported. Use static credentials secrets when `env.ACT` |
| Token errors (`Bad credentials`, `Resource not accessible`, `GITHUB_TOKEN` empty) | Pass `-s GITHUB_TOKEN="$(gh auth token)"` |
| x86-only binary fails (`exec format error`) | `--container-architecture linux/amd64` |
| Different results from setup-* caches | `ImageOS=ubuntu20` for `ubuntu-latest`. Try `--env ImageOS=ubuntu24` |
| Network calls to `localhost` services fail | See [services-and-networking.md](services-and-networking.md#how-to-reach-a-service-verified) |

## Actions fetching / auth

| Symptom | Fix |
|---|---|
| `authentication required` / `repository not found` cloning an action or reusable workflow | Private repo. Pass `GITHUB_TOKEN` with access |
| GitHub `API rate limit exceeded` / slow fetches | Pass a token. Use `--action-offline-mode` after the first run |
| `Unable to resolve <ref>` / `couldn't find remote ref` | Tag/branch/sha doesn't exist on the remote (local-only commits of an action repo: use `--local-repository`) |
| Stale action code after a tag moved | `rm -rf ~/.cache/act/<org>-<repo>@<ref>` |
| `--local-repository` not applied | Key must exactly match `org/repo@ref` from `uses:` |

## Artifacts / cache / services

| Symptom | Fix |
|---|---|
| upload-artifact: `Unable to get the ACTIONS_RUNTIME_TOKEN env variable` / `ACTIONS_RUNTIME_URL` missing | Add `--artifact-server-path /tmp/act-artifacts` |
| download-artifact from another run/repo fails | Not supported |
| actions/cache hangs/times out (`ECONNREFUSED`, `ETIMEDOUT` to `172.x/192.168.x`) | Container can't reach the host IP act bound to (VPN/firewall). Set `--cache-server-addr` (and `--artifact-server-addr`) to a reachable IP, or `--no-cache-server` |
| `bind: address already in use` for artifact port 34567 | Another act run. Use `--artifact-server-port 34568` |
| `service container failed to start` | Service healthcheck never became healthy within ~5 min. Check `docker logs <service container>`, env vars (e.g. `POSTGRES_PASSWORD`), image arch |
| `port is already allocated` | Host port in `services.*.ports` in use (local DB, parallel matrix job). Change the host port or stop the conflicting process |
| Service hostname doesn't resolve | Plain `runs-on` jobs must use `localhost:<published port>`. Only `container:` jobs resolve service ids |

## Containers left behind / conflicts

- Failed jobs leave containers on purpose. Clean up: `docker ps -a --filter name=act- -q | xargs -r docker rm -f` (and volumes: `docker volume ls -q | grep '^act-' | grep -v act-toolcache | xargs -r docker volume rm`).
- `Conflict. The container name "/act-..." is already in use`: remove the old container (above). This is rare, since act removes same-named containers before starting.
- `--reuse` state is stale: remove the containers and volumes, then run without `-r`.

## MODULE_NOT_FOUND

`MODULE_NOT_FOUND` during `docker cp` (nektos/act#228) can happen when relying on unpushed local changes with `uses: ./`. The checkout path must equal the repository name:
```yaml
steps:
  - uses: actions/checkout@v4
    with:
      path: "my-action"     # == repository name
```
Also make sure the action's `dist/`/`node_modules` exist in the working tree and aren't excluded by `.gitignore` (or pass `--use-gitignore=false`).

## Reporting bugs

Search <https://github.com/nektos/act/issues>. Include `act --bug-report` output, a minimal workflow, and `-v` logs. Image problems go to <https://github.com/catthehacker/docker_images>.
