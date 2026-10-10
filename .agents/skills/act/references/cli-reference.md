# act CLI reference (v0.2.89)

```
act [event name to run] [flags]
```

- At most one positional arg: the event name (`push`, `pull_request`, `workflow_dispatch`, `schedule`, `release`, …).
- If omitted: use the only event when all loaded workflows share a single event. Otherwise use the first event alphabetically if `--detect-event` is set. Otherwise `push`.
- Also usable as a GitHub CLI extension: `gh act <same args>`.

## Table of contents
- [Selecting what runs](#selecting-what-runs)
- [Inspection / no-run modes](#inspection--no-run-modes)
- [Inputs, secrets, vars, env, event](#inputs-secrets-vars-env-event)
- [Images and container runtime](#images-and-container-runtime)
- [Workspace and container lifecycle](#workspace-and-container-lifecycle)
- [Artifacts and cache servers](#artifacts-and-cache-servers)
- [Actions fetching and caching](#actions-fetching-and-caching)
- [GitHub identity and enterprise](#github-identity-and-enterprise)
- [Logging and output](#logging-and-output)
- [Configuration file (.actrc)](#configuration-file-actrc)
- [Environment variables that affect act itself](#environment-variables-that-affect-act-itself)
- [Exit codes](#exit-codes)

## Selecting what runs

| Flag | Default | Meaning |
|---|---|---|
| `[event]` (positional) | see above | Run every workflow whose `on:` includes this event. Branch/tag/path/`types` filters are **not** evaluated. |
| `-W, --workflows <path>` | `./.github/workflows/` | Directory (recursed) or a single workflow file. Only `.yml` / `.yaml` files are loaded. |
| `--no-recurse` | false | Don't descend into subdirectories of the `-W` directory. |
| `-j, --job <id>` | – | Run the job with this **job id** (the YAML key, not `name:`) in every loaded workflow, **plus its transitive `needs`**. The event filter is not applied. Combine with `-W` when job ids collide across files. |
| `--matrix key:value` (repeatable) | – | Keep only matrix combinations whose `key` equals one of the given values. Several values for the same key are OR'ed, different keys are AND'ed. Can't add combinations. `exclude` still wins. Values are compared as strings. |
| `--detect-event` | false | With no positional event, use the first (alphabetical) event found in the workflows. |
| `-C, --directory <dir>` | `.` | Repo/working directory. Relative paths for `-W`, `-e`, and the `.env`/`.secrets`/`.vars`/`.input` files resolve against it. |
| `--concurrent-jobs <n>` | #CPUs | Max jobs run in parallel within a stage. |

Matrix jobs within one job run up to `strategy.max-parallel` at a time (act defaults to 4).

## Inspection / no-run modes

| Flag | Effect |
|---|---|
| `-l, --list` | Table: `Stage  Job ID  Job name  Workflow name  Workflow file  Events`. With an event or `-j`, the list is filtered. Prints a warning when job ids are duplicated across files. No Docker needed. |
| `-g, --graph` | ASCII graph of stages/needs for the selected plan. |
| `--validate` | Load and schema-check workflows, then exit (0 = valid). |
| `--strict` | Use the strict workflow schema (catches more mistakes) for validate and run. |
| `-n, --dryrun` | Plan and evaluate without creating containers. Doesn't execute steps, so it won't catch runtime errors. |
| `--list-options` | JSON array of every flag (`name`, `default`, `description`, `type`). |
| `--bug-report` | Prints act version, OS/arch, DOCKER_HOST, detected sockets, config files and their contents, and Docker engine info. Best first step for environment problems. |
| `--man-page` | Print a man page. |
| `--version`, `-h/--help` | |

## Inputs, secrets, vars, env, event

| Flag | Default | Meaning |
|---|---|---|
| `-e, --eventpath <file>` | – | JSON event payload, exposed as `github.event` and `$GITHUB_EVENT_PATH`. |
| `--input k=v` (repeatable) | – | `workflow_dispatch` inputs (`inputs.k` / `github.event.inputs.k`). **Ignored for the event payload when `-e` is given**: put `"inputs"` in the JSON instead. |
| `--input-file <f>` | `.input` | dotenv/YAML file of inputs. |
| `-s, --secret k[=v]` (repeatable) | – | Secret. Without `=v`, act reads env var `k`, or **prompts interactively** (blocks agents). Names are upper-cased. |
| `--secret-file <f>` | `.secrets` | dotenv/YAML file of secrets. |
| `--var k[=v]` (repeatable) | – | Repository/org variable (`vars.k`). Same prompting rules as `-s`. Names upper-cased. |
| `--var-file <f>` | `.vars` | dotenv/YAML file of vars. |
| `--env k[=v]` (repeatable) | – | Env var for every step. Overrides workflow- and job-level `env:` (step-level `env:` still wins). |
| `--env-file <f>` | `.env` | dotenv/YAML file of env vars. |
| `--insecure-secrets` | false | Don't mask secrets in logs. Not recommended. |

Default files are loaded only if they exist. Values passed on the CLI take precedence over file values with the same key.

## Images and container runtime

| Flag | Default | Meaning |
|---|---|---|
| `-P, --platform label=image` (repeatable) | built-in micro images | Map a `runs-on` label to a Docker image. `label=-self-hosted` runs the job directly on the host (no container). Labels are case-insensitive. |
| `-p, --pull` | **true** | Pull images even if they're present. `--pull=false` uses local images. |
| `--rebuild` | **true** | Rebuild Dockerfile-based actions each run. `--rebuild=false` reuses built images. |
| `--container-architecture <os/arch>` | host arch | e.g. `linux/amd64` (emulated on ARM hosts). Needs Docker API ≥ 1.41. |
| `--container-daemon-socket <uri>` | auto (DOCKER_HOST/socket) | Socket bind-mounted into job containers as `/var/run/docker.sock`. Use `-` to **not** mount any socket. |
| `--container-options "<docker run flags>"` | – | Extra `docker run`-style flags for job containers whose job has no `container.options`. e.g. `"--cpus 2 --memory 4g -v /data:/data"`. |
| `--network <name>` | `host` | Docker network for job containers (jobs with `services` get their own network instead). |
| `--privileged` | false | **Deprecated**: use `--container-options "--privileged"`. |
| `--userns <mode>` | – | **Deprecated**: use `--container-options "--userns=<mode>"`. |
| `--container-cap-add CAP` / `--container-cap-drop CAP` | – | **Deprecated**: use `--container-options "--cap-add=CAP"`. |

## Workspace and container lifecycle

| Flag | Default | Meaning |
|---|---|---|
| `-b, --bind` | false | Bind-mount the working directory into containers instead of copying. Writes from the job **change your local files**. `actions/checkout` becomes a no-op. |
| `--use-gitignore` | **true** | When copying the workspace (checkout substitution), skip `.gitignore`d paths. `--use-gitignore=false` copies everything. |
| `--no-skip-checkout` | false | Really run `actions/checkout` (clones from GitHub at the event ref/sha) instead of copying the local tree. |
| `-r, --reuse` | false | Keep containers and volumes after successful runs and reuse them (state persists between runs). |
| `--rm` | false | Remove containers and volumes even when the job **fails** (by default failed job containers are left for inspection). |
| `-w, --watch` | false | Run once, then re-run whenever files in the cwd change (respects `.gitignore`, polls every 2s). |

## Artifacts and cache servers

| Flag | Default | Meaning |
|---|---|---|
| `--artifact-server-path <dir>` | – (server off) | Start the built-in artifact server storing files in `<dir>`. Required for `actions/upload-artifact` / `download-artifact` (v3 and v4). |
| `--artifact-server-addr <ip>` | outbound host IP | Bind address. |
| `--artifact-server-port <port>` | `34567` | |
| `--no-cache-server` | false | Disable the built-in `actions/cache` server (it's **on by default**). |
| `--cache-server-path <dir>` | `~/.cache/actcache` | Cache storage. |
| `--cache-server-addr <ip>` | outbound host IP | |
| `--cache-server-port <port>` | `0` (random) | |
| `--cache-server-external-url <url>` | – | Public URL if the cache server is behind a proxy (no trailing slash). |

## Actions fetching and caching

| Flag | Default | Meaning |
|---|---|---|
| `--action-cache-path <dir>` | `~/.cache/act` (`$XDG_CACHE_HOME/act`) | Where remote actions/reusable workflows are cloned and host-mode workspaces are created. |
| `--action-offline-mode` | false | Use cached actions and images without re-fetching or pulling. Still fetches anything missing. Implies no force-pull. |
| `--use-new-action-cache` | false | go-git based action cache (stores repos and extracts tar archives per sha). Enabled automatically with `--local-repository`. |
| `--local-repository repo@ref=/local/path` (repeatable) | – | Replace a remote action/reusable-workflow repo at a ref with a local directory. Key is `https://github.com/org/repo@ref` (exact) or `org/repo@ref` (any host). |
| `--replace-ghe-action-with-github-com org/repo` (repeatable) | – | On GHES: fetch these actions from github.com instead. |
| `--replace-ghe-action-token-with-github-com <token>` | – | Token used for those github.com actions (private repos). |

## GitHub identity and enterprise

| Flag | Default | Meaning |
|---|---|---|
| `-a, --actor <user>` | `nektos/act` | `github.actor` / `GITHUB_ACTOR`. |
| `--remote-name <name>` | `origin` | Git remote used to derive `github.repository` (owner/repo). |
| `--defaultbranch <name>` | – (falls back to `master`) | Sets `github.event.repository.default_branch`, used when the ref can't be derived. |
| `--github-instance <host>` | `github.com` | GHES hostname. Sets server/API/GraphQL URLs, used for cloning actions with `GITHUB_TOKEN`. |

## Logging and output

| Flag | Meaning |
|---|---|
| `-v, --verbose` | Debug logging (expression evaluation, skip reasons, docker operations). |
| `-q, --quiet` | Hide step output (status lines remain). |
| `--json` | Logs as JSON lines. Useful fields: `job`, `jobID`, `step`, `stepid`, `stepResult`, `jobResult`, `matrix`, `msg`, `level`, `raw_output`. |
| `--log-prefix-job-id` | Prefix lines with the job id instead of `workflow/job name`. |

## Configuration file (.actrc)

Arguments are read from these files **in order**, then the real CLI args are appended. Later values win for scalar flags, and repeatable flags (`-P`, `-s`, `--env`, …) accumulate:

1. XDG config file `act/actrc`:
   - Linux: `$XDG_CONFIG_HOME/act/actrc` (default `~/.config/act/actrc`)
   - macOS: `~/Library/Application Support/act/actrc` (or `$XDG_CONFIG_HOME/act/actrc` if set)
   - Windows: `%LOCALAPPDATA%\act\actrc`
2. `~/.actrc`
3. `./.actrc` (the **invocation** directory, not `-C`)

Format: one argument per line. A line starting with `-` is split at its first whitespace into flag + value. `--flag=value` also works. Lines that don't start with `-` are ignored, so `#` comments are effectively skipped (officially "no comments supported"). `$VARS` are expanded from the environment.

```
-P ubuntu-latest=catthehacker/ubuntu:act-latest
-P ubuntu-24.04=catthehacker/ubuntu:act-24.04
-P ubuntu-22.04=catthehacker/ubuntu:act-22.04
--container-architecture=linux/amd64
--action-offline-mode
--artifact-server-path=$HOME/.cache/act-artifacts
-e .github/act-event.json
```

**First-run image survey:** if no `-P` is present anywhere, act interactively asks you to choose Large, Medium, or Micro and **writes the choice to the XDG actrc** (file #1). With no TTY this fails with `fatal msg=EOF`. Answers write:
- Large: `-P ubuntu-latest=catthehacker/ubuntu:full-latest` (+ `full-22.04`, `full-20.04`, `full-18.04`)
- Medium: `-P ubuntu-latest=catthehacker/ubuntu:act-latest` (+ `act-22.04`, `act-20.04`, `act-18.04`)
- Micro: `-P ubuntu-latest=node:16-buster-slim` (+ `ubuntu-22.04=node:16-bullseye-slim`, …)

To pre-seed it non-interactively:

```sh
if [ -n "$XDG_CONFIG_HOME" ]; then cfg="$XDG_CONFIG_HOME/act"
elif [ "$(uname)" = Darwin ]; then cfg="$HOME/Library/Application Support/act"
else cfg="$HOME/.config/act"; fi
mkdir -p "$cfg" && printf '%s\n' \
  '-P ubuntu-latest=catthehacker/ubuntu:act-latest' \
  '-P ubuntu-24.04=catthehacker/ubuntu:act-24.04' \
  '-P ubuntu-22.04=catthehacker/ubuntu:act-22.04' >> "$cfg/actrc"
act --bug-report | sed -n '/Config files/,/Build info/p'   # confirm act sees it
```

(Or simply create `./.actrc` / `~/.actrc` containing `-P` lines. Don't modify a user's global config without asking. Prefer passing `-P` on the command line or a project `./.actrc`.)

## Environment variables that affect act itself

| Var | Effect |
|---|---|
| `DOCKER_HOST` | Docker API endpoint (`unix://…`, `tcp://…`, `ssh://user@host`, `npipe://…`). Takes precedence over socket auto-detection. |
| `DOCKER_CERT_PATH`, `DOCKER_TLS_VERIFY` | TLS for remote engines (respected). |
| `XDG_CACHE_HOME` | Base for `act` action cache and `actcache` cache server dirs. |
| `XDG_CONFIG_HOME` | Location of the XDG `act/actrc`. |
| `ACTIONS_RUNTIME_URL`, `ACTIONS_RUNTIME_TOKEN` | If set in act's environment, passed to jobs instead of the built-in artifact server values. |
| Any `NAME` used by `-s NAME` / `--var NAME` without value | Supplies that secret/var value without prompting. |

GitHub-context overrides via `--env` (read by act when it builds `github.*`): `GITHUB_RUN_ID`, `GITHUB_RUN_NUMBER`, `GITHUB_RUN_ATTEMPT`, `GITHUB_REPOSITORY`, `GITHUB_REPOSITORY_OWNER`, `GITHUB_REF`, `GITHUB_REF_NAME`, `GITHUB_REF_TYPE`, `GITHUB_BASE_REF`, `GITHUB_HEAD_REF`, `GITHUB_SERVER_URL`, `GITHUB_API_URL`, `GITHUB_GRAPHQL_URL`, `GITHUB_RETENTION_DAYS`, `RUNNER_PERFLOG`, `RUNNER_TRACKING_ID`. Example: `act --env GITHUB_RUN_NUMBER=42 --env GITHUB_REPOSITORY=acme/app`.

## Exit codes

- `0`: all planned jobs succeeded, or were skipped by `if:` or an unmapped platform.
- `1`: a job failed (`Error: Job '<name>' failed`), workflow parse/schema error, `Could not find any stages to run`, Docker errors, etc.
- Step exit codes are not propagated as act's exit code. Inspect the logs (`❌  Failure - Main <step>` followed by `exitcode '<n>': failure`).
