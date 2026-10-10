# Secrets, variables, environment and inputs

## Contents
- [Summary table](#summary-table)
- [Secrets](#secrets)
- [GITHUB_TOKEN](#github_token)
- [Variables (vars context)](#variables-vars-context)
- [Environment variables](#environment-variables)
- [Inputs](#inputs)
- [File formats (.env / .secrets / .vars / .input)](#file-formats)
- [Environment variables act injects](#environment-variables-act-injects)
- [Security notes](#security-notes)

## Summary table

| Context in workflow | CLI | File flag | Auto-loaded default file | Case |
|---|---|---|---|---|
| `secrets.X` | `-s X=v`, `-s X` (env/prompt) | `--secret-file` | `.secrets` | upper-cased (case-insensitive) |
| `vars.X` | `--var X=v`, `--var X` (env/prompt) | `--var-file` | `.vars` | upper-cased |
| `env.X` / `$X` | `--env X=v`, `--env X` (empty) | `--env-file` | `.env` | as written |
| `inputs.X` (workflow_dispatch) | `--input X=v` | `--input-file` | `.input` | as written |

Default files resolve relative to `-C` (default cwd) and are silently skipped when missing. For the same key, CLI flags win over file values.

## Secrets

```sh
act -s MY_SECRET=value                 # literal (lands in shell history; prefix the command with a space or use a file)
act -s MY_SECRET                       # takes $MY_SECRET from the environment; if unset/empty → interactive hidden prompt
act --secret-file .secrets             # dotenv or YAML file
MY_SECRET=$(op read op://vault/item) act -s MY_SECRET   # agent-safe pattern: env var + name-only flag
```

- **Agents:** never use `-s NAME` without `=value` unless `NAME` is exported and non-empty, or act blocks on `Provide value for 'NAME':`.
- Names are upper-cased, so `secrets.my_secret` and `secrets.MY_SECRET` both resolve.
- Values are masked as `***` in logs (disable with `--insecure-secrets`). Values registered with `::add-mask::` are masked too.
- An undefined secret evaluates to an empty string. It doesn't cause an error.
- Special secrets: `DOCKER_USERNAME` / `DOCKER_PASSWORD` are used as registry credentials when pulling the job image, if the job has no `container.credentials`.
- Reusable workflows get their secrets via `secrets:` mapping or `secrets: inherit` (see [actions-and-reusable-workflows.md](actions-and-reusable-workflows.md)).
- Deployment-environment scoping (`environment:` secrets) isn't supported. All secrets are global.

## GITHUB_TOKEN

GitHub auto-provides `GITHUB_TOKEN`. act does not mint one. Resolution order:
1. `-s GITHUB_TOKEN=...` or `GITHUB_TOKEN` in the secret file.
2. Otherwise act runs `gh auth token` (if the GitHub CLI is installed and logged in) and uses its output.
3. Otherwise empty. Workflows that call the API or `actions/checkout` with `--no-skip-checkout` then fail with auth/token errors.

```sh
act -s GITHUB_TOKEN="$(gh auth token)"   # explicit
act -s GITHUB_TOKEN                      # from env $GITHUB_TOKEN (prompts if unset!)
```

The token is also exposed as `github.token`. act uses it to clone remote actions and reusable workflows (private repos, rate limits) and, on GHES, against `--github-instance`. Permissions declared in `permissions:` are ignored, so the token has whatever scopes your PAT/gh login has. Be careful with workflows that write (releases, comments, pushes): they'll act on the real repo.

## Variables (vars context)

```sh
act --var ENVIRONMENT=staging --var-file .vars
```
Repository/organization/environment `vars` aren't fetched from GitHub. Supply every one you need. Missing vars evaluate to empty string. Same parsing as secrets: upper-cased names, and a name-only flag reads the env var or prompts.

## Environment variables

```sh
act --env NODE_ENV=test --env-file .env.act
```
Precedence (later wins): workflow `env:` → job `env:` → **CLI/.env (`--env`, `--env-file`)** → job `container.env` → step `env:` (+ `INPUT_*` from `with:`). Then act overwrites the `GITHUB_*`, `CI`, `RUNNER_*` defaults it computes.

So `--env` can override workflow- and job-level env (handy for pointing at test endpoints) but not step-level env.

Env vars from the host aren't passed into containers (except in `-self-hosted` host mode, where the host environment is inherited).

Also see `GITHUB_*` overrides read from `--env` in [cli-reference.md](cli-reference.md#environment-variables-that-affect-act-itself).

## Inputs

workflow_dispatch:
```sh
act workflow_dispatch --input name=alex --input debug=true
act workflow_dispatch --input-file .input
act workflow_dispatch -e payload.json     # {"inputs": {"name": "alex", "debug": "true"}}
```
- `--input` values are ignored if `-e` is also given. Put them in the JSON instead.
- Missing inputs use the workflow's `default:`. `required:` isn't enforced, and `choice` options aren't validated.
- `type: boolean` inputs: pass `"true"`/`"false"` **strings** (JSON booleans are evaluated as false).

Actions (`with:`) inputs become `INPUT_<NAME>` env vars inside the action (upper-cased, spaces → `_`), the same as on GitHub.

## File formats

**dotenv** (any extension except `.yml`/`.yaml`), parsed by godotenv (Ruby dotenv compatible):
```sh
export MY_ENV='value'            # "export " prefix allowed
SOME_VAR=SOME_VALUE
QUOTED="spaces and $NOT_EXPANDED_IN_SINGLE_QUOTES"
PRIV_KEY="-----BEGIN KEY-----\nline2\n-----END KEY-----"   # \n in double quotes → newline
JSON="{\n\"name\": \"value\"\n}"
# comments are allowed in dotenv files
```
Multi-line values: use double quotes with `\n` escapes, or a real multi-line double-quoted value.

**YAML** (`.yml`/`.yaml` extension): a flat `key: value` string map.
```yaml
MY_SECRET: abc
MULTI: |
  line 1
  line 2
```

A file that fails to parse is fatal: `Error loading from <path>: ...`.

## Environment variables act injects

Every step gets:

| Var | Value under act |
|---|---|
| `ACT` | `true` |
| `CI`, `GITHUB_ACTIONS` | `true` |
| `GITHUB_WORKFLOW`, `GITHUB_JOB`, `GITHUB_ACTION`, `GITHUB_ACTION_PATH`, `GITHUB_ACTION_REPOSITORY`, `GITHUB_ACTION_REF` | from plan/step |
| `GITHUB_RUN_ID`, `GITHUB_RUN_NUMBER`, `GITHUB_RUN_ATTEMPT` | `1` unless overridden with `--env` |
| `GITHUB_ACTOR` | `--actor` (default `nektos/act`) |
| `GITHUB_REPOSITORY`, `GITHUB_REPOSITORY_OWNER` | from git remote, else `nektos/act` |
| `GITHUB_EVENT_NAME`, `GITHUB_EVENT_PATH` | event; `/var/run/act/workflow/event.json` |
| `GITHUB_SHA`, `GITHUB_REF`, `GITHUB_REF_NAME`, `GITHUB_REF_TYPE`, `GITHUB_BASE_REF`, `GITHUB_HEAD_REF` | see [events-and-payloads.md](events-and-payloads.md#how-githubref--sha--repository-are-derived) |
| `GITHUB_WORKSPACE` | container: the **same absolute path as the host repo** (Windows host: `/mnt/<drive>/...`). Host mode: a temp dir |
| `GITHUB_SERVER_URL`, `GITHUB_API_URL`, `GITHUB_GRAPHQL_URL` | github.com URLs or `--github-instance` based |
| `GITHUB_RETENTION_DAYS` | `0` |
| `GITHUB_ENV`, `GITHUB_OUTPUT`, `GITHUB_PATH`, `GITHUB_STATE`, `GITHUB_STEP_SUMMARY` | files under `/var/run/act/workflow/` |
| `RUNNER_OS`, `RUNNER_ARCH`, `RUNNER_TEMP`, `RUNNER_TOOL_CACHE` | container: `Linux`, `X64`/`ARM64`, `/tmp`, `/opt/hostedtoolcache` |
| `ImageOS` | derived from `runs-on`: `ubuntu-latest` → `ubuntu20` (hard-coded), `ubuntu-22.04` → `ubuntu22` |
| `LANG` | `C.UTF-8` |
| `ACTIONS_CACHE_URL` | built-in cache server URL (unless `--no-cache-server`) |
| `ACTIONS_RUNTIME_URL`, `ACTIONS_RESULTS_URL`, `ACTIONS_RUNTIME_TOKEN` | only when `--artifact-server-path` is set (and then also visible in `run:` steps, unlike GitHub) |

`ImageOS=ubuntu20` for `ubuntu-latest` can confuse `setup-*` actions that key tool caches on ImageOS. Override with `--env ImageOS=ubuntu24` if needed.

## Security notes

- `actions/checkout` substitution copies your working tree into the container, **including untracked files that aren't gitignored**. Put `.secrets`, `.vars`, `.env`, `.input` in `.gitignore` (or use `--secret-file` paths outside the repo).
- `--bind` mounts your repo read-write: the workflow can modify or delete local files.
- By default the host Docker socket is mounted into job containers (`/var/run/docker.sock`), which gives workflows root-equivalent control of the host's Docker. Use `--container-daemon-socket -` to disable that.
- Prefer secrets files with restricted permissions (`chmod 600`) over CLI literals.
