# Workflow feature support in act (v0.2.89)

The official docs' "support matrix" is outdated (it lists services, step `continue-on-error`, `timeout-minutes`, and reusable workflows as unsupported). This table reflects the v0.2.89 source and was spot-checked by running act.

## Contents
- [Workflow level](#workflow-level)
- [Job level](#job-level)
- [Step level](#step-level)
- [Actions (action.yml)](#actions-actionyml)
- [Expressions and contexts](#expressions-and-contexts)
- [Workflow commands and environment files](#workflow-commands-and-environment-files)
- [Not supported / ignored (plan around these)](#not-supported--ignored)

Legend: ✅ supported · ⚠️ partial/different · ❌ ignored/unsupported

## Workflow level

| Key | Status | Notes |
|---|---|---|
| `name` | ✅ | Defaults to the file name |
| `run-name` | ❌ | Ignored |
| `on` (scalar/list/map) | ✅ | Only the event **name** is used for selection |
| `on.<event>.types`, `branches*`, `tags*`, `paths*` | ❌ | Not evaluated. Every workflow listing the event runs |
| `on.schedule` | ⚠️ | `act schedule` runs it. Cron ignored |
| `on.workflow_dispatch.inputs` | ✅ | Defaults applied. `required`/`choice` not validated |
| `on.workflow_call` (inputs/outputs/secrets) | ✅ | |
| `on.workflow_run` | ⚠️ | Runs by name with a payload you supply. No chaining after other workflows |
| `env` | ✅ | |
| `defaults.run.shell` / `working-directory` | ✅ | |
| `permissions` | ❌ | Ignored. Token has whatever scopes you gave it |
| `concurrency` | ❌ | Ignored |
| YAML anchors/aliases | ✅ | |

## Job level

| Key | Status | Notes |
|---|---|---|
| `name` | ✅ | Expressions allowed (matrix) |
| `needs` | ✅ | Stages built from needs. `needs.<id>.result` / `outputs` available |
| `if` | ✅ | `env` context NOT available here (use `github.event.*`, `vars.*`, `inputs.*`) |
| `runs-on` (string/list/group+labels/expression) | ✅ | Must map via `-P`, or the job is skipped |
| `outputs` | ✅ | |
| `env` | ✅ | |
| `defaults.run` | ✅ | |
| `steps` | ✅ | |
| `strategy.matrix` incl. `include`/`exclude`, expressions, `fromJSON` | ✅ | Resolution may differ from GitHub in edge cases (nektos/act#981, #573) |
| `strategy.fail-fast` | ⚠️ | Parsed and exposed as `strategy.fail-fast`, but other matrix legs are not cancelled |
| `strategy.max-parallel` | ✅ | Default 4 under act |
| `container` (image, credentials, env, volumes, options) | ✅ | `ports` ignored |
| `services` | ✅ | image, env, ports, volumes, options (healthchecks awaited), credentials |
| `uses` / `with` / `secrets` (reusable workflow) | ✅ | Local `./...` and remote `org/repo/...@ref`. `secrets: inherit` OK |
| `timeout-minutes` (job) | ❌ | Ignored |
| `continue-on-error` (job) | ❌ | Ignored. A failed job fails the run |
| `environment` | ❌ | Ignored. No environment-scoped secrets, approvals, or URLs |
| `permissions`, `concurrency` | ❌ | Ignored |

## Step level

| Key | Status | Notes |
|---|---|---|
| `id`, `name`, `if`, `env` | ✅ | `if` default is `success()` |
| `run` | ✅ | |
| `shell` | ✅ | `bash`, `sh`, `pwsh`, `powershell`, `python`, `cmd`, custom (`perl {0}`) |
| `working-directory` | ✅ | |
| `uses` (remote/local/docker://) | ✅ | |
| `with` (incl. `args`, `entrypoint` for docker) | ✅ | |
| `continue-on-error` | ✅ | Expression allowed. `steps.x.outcome` = failure, `conclusion` = success |
| `timeout-minutes` | ✅ | Expression allowed |

Default shells (same as GitHub):
- No `shell` and no defaults: `bash -e {0}` (no `pipefail`). Explicit `shell: bash` → `bash --noprofile --norc -e -o pipefail {0}`.
- Job with `container:` → `sh -e {0}` by default. Host mode → bash (fallback sh). Windows host → pwsh (fallback powershell).
- `pwsh` → `pwsh -command . '{0}'`. `python` → `python {0}`. `cmd` → `cmd /D /E:ON /V:OFF /S /C "CALL "{0}""`.

## Actions (action.yml)

| Feature | Status |
|---|---|
| `inputs` (defaults, required), `outputs` | ✅ |
| `runs.using: node12/16/20/24` | ✅ (runs with container's `node`) |
| `runs.using: docker` (image / Dockerfile, `args`, `entrypoint`, `pre-entrypoint`, `post-entrypoint`, `env`) | ✅ |
| `runs.using: composite` (nested, `if`, `env`, `shell`, `continue-on-error` in steps) | ✅ |
| `runs.pre`, `runs.post`, `pre-if`, `post-if` | ✅ |
| `branding` | n/a |

## Expressions and contexts

Functions: `contains`, `startsWith`, `endsWith`, `format`, `join`, `toJSON`, `fromJSON`, `hashFiles` (evaluated against the job's workspace, `''` when nothing matches), `success()`, `always()`, `cancelled()`, `failure()`. Literals `null`, booleans, numbers, strings, `Infinity`, `NaN`. Operators: `! < <= > >= == != && || ()`, `.`/`[]`/`*` (object filters).

Contexts:

| Context | Status / notes |
|---|---|
| `github` | ⚠️ Partial: event, event_name, event_path, ref, ref_name, ref_type, sha, head_ref, base_ref, repository, repository_owner, actor, workflow, job, run_id/number/attempt (=1), workspace, action*, token, server_url/api_url/graphql_url, retention_days. Missing fields such as `github.triggering_actor`, `github.workflow_ref`, `github.repository_id` are empty |
| `env` | ✅ (not in job-level `if`) |
| `vars` | ✅ from `--var`/`.vars` |
| `secrets` | ✅ from `-s`/`.secrets` (+ `GITHUB_TOKEN`) |
| `inputs` | ✅ workflow_dispatch / workflow_call / composite |
| `matrix` | ✅ |
| `strategy` | ⚠️ `fail-fast` and `max-parallel` only (`job-index`, `job-total` are empty) |
| `needs` | ✅ (`result`, `outputs`) |
| `steps` | ✅ (`outputs`, `outcome`, `conclusion`) |
| `job` | ⚠️ `job.status` only. `job.services`/`job.container` not populated |
| `runner` | ✅ os, arch, temp, tool_cache (`runner.name` empty) |

## Workflow commands and environment files

Environment files (preferred):

| File | Status |
|---|---|
| `$GITHUB_ENV` (`NAME=value`, heredoc `NAME<<EOF`) | ✅ Applies to later steps |
| `$GITHUB_OUTPUT` | ✅ Step outputs |
| `$GITHUB_PATH` | ✅ Prepends to PATH for later steps |
| `$GITHUB_STATE` | ✅ pre/main/post state |
| `$GITHUB_STEP_SUMMARY` | ⚠️ Not rendered anywhere. act prints each step's summary into the log as `⚙  Summary - <content>` |

Stdout commands:

| Command | Status |
|---|---|
| `::set-output name=x::v` | ✅ (deprecated on GitHub, still works) |
| `::add-mask::v` | ✅ |
| `::debug::`, `::warning::`, `::error::`, `::notice::` | ⚠️ Logged (debug only with `-v`). No annotations created, file/line params ignored |
| `::group::` / `::endgroup::` | ⚠️ Printed as plain lines |
| `::stop-commands::token` … `::token::` | ✅ |
| `::save-state name=x::v` | ✅ |
| `::set-env`, `::add-path` | ⚠️ Only with `ACTIONS_ALLOW_UNSECURE_COMMANDS=true` (same as GitHub) |
| `::add-matcher::` | ❌ Problem matchers ignored |
| `##[cmd]` (Azure-style) | ✅ parsed |

## Not supported / ignored

- `concurrency`, `run-name`, `permissions` (workflow and job), job `timeout-minutes`, job `continue-on-error`, `environment` (protection rules, environment secrets, URL).
- Event filters (`branches`, `tags`, `paths`, `types`) and cron timing.
- Annotations, problem matchers, and rendered step summaries.
- Cancelling running steps from outside (Ctrl-C stops act. Matrix fail-fast doesn't cancel siblings).
- OIDC: `ACTIONS_ID_TOKEN_REQUEST_URL` isn't set, so `aws-actions/configure-aws-credentials` with `role-to-assume`, `google-github-actions/auth` with workload identity, and Azure OIDC login fail. Use static credentials via secrets when `env.ACT`.
- macOS/Windows **containers**. Those platforms only work in host mode (`-P macos-latest=-self-hosted`) on a matching machine.
- `docker context` isn't respected. Export `DOCKER_HOST` (see [container-engines.md](container-engines.md)).
- GitHub's bundled node for JS actions: the image/host must provide `node`.
- Downloading artifacts from other runs, the GitHub Packages/Pages deploy APIs, and anything that needs real GitHub run infrastructure (`actions/deploy-pages`, `actions/attest-build-provenance`, `github/codeql-action` uploads).
