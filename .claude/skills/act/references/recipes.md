# act recipes (end-to-end)

All examples assume `IMG="-P ubuntu-latest=catthehacker/ubuntu:act-latest"` (or an `.actrc` with `-P` lines).

## Contents
1. [Reproduce a failing CI job locally](#1-reproduce-a-failing-ci-job-locally)
2. [Validate a workflow edit before pushing](#2-validate-a-workflow-edit-before-pushing)
3. [Test a pull_request workflow](#3-test-a-pull_request-workflow)
4. [Test tag / release workflows](#4-test-tag--release-workflows)
5. [Run a subset of a matrix](#5-run-a-subset-of-a-matrix)
6. [Manual (workflow_dispatch) workflows with inputs](#6-workflow_dispatch-with-inputs)
7. [Integration tests with service containers](#7-integration-tests-with-service-containers)
8. [Fast iteration loop](#8-fast-iteration-loop)
9. [Machine-readable results with --json](#9-machine-readable-results)
10. [Project setup for act](#10-project-setup-for-act)
11. [act as a local task runner](#11-act-as-a-local-task-runner)
12. [Test workflows in CI with act](#12-test-workflows-in-ci-with-act)
13. [Safely running workflows that deploy/publish](#13-guarding-side-effects)
14. [Running long act jobs from an agent](#14-running-long-act-jobs-from-an-agent)

## 1. Reproduce a failing CI job locally

```sh
gh run list --limit 5                       # find the failed run (optional)
gh run view <run-id> --log-failed | tail -50
act -l                                      # map the GitHub job to a job id + workflow file
act push -W .github/workflows/ci.yml -j test $IMG -s GITHUB_TOKEN="$(gh auth token)" \
  > /tmp/act.log 2>&1; echo "exit=$?"
grep -nE "❌|Failure|exitcode|Error" /tmp/act.log | head
docker ps --filter name=act- --format '{{.Names}}'   # failed container is still running
docker exec -it <name> bash                          # poke around; scripts at /var/run/act/workflow/
```
If the failure only happens on GitHub: compare images (try `catthehacker/ubuntu:full-latest` or `runner-latest`), arch (`--container-architecture linux/amd64`), and the event context (supply the real payload with `-e`).

## 2. Validate a workflow edit before pushing

```sh
act --validate --strict                      # schema check all workflows (exit 0 = ok)
act -l pull_request                          # does my change trigger what I expect?
act -g pull_request                          # dependency stages
act -n pull_request $IMG                     # dry-run (expressions/plan without containers)
act pull_request -W .github/workflows/changed.yml $IMG   # real run of just that file
```
Also run `actionlint` if available. It catches expression/type errors that act's schema misses.

## 3. Test a pull_request workflow

```sh
cp <skill>/assets/events/pull_request.json .github/act/pr.json   # edit refs/number/labels
act pull_request -e .github/act/pr.json $IMG
```
Workflows using `github.event.pull_request.head.sha`, labels, `github.base_ref`, or `github.head_ref` need those fields in the payload. Without `number`, `github.ref` renders as `refs/pull/%!f(<nil>)/merge`.

## 4. Test tag / release workflows

```sh
echo '{"ref":"refs/tags/v1.2.3"}' > /tmp/tag.json
act push -e /tmp/tag.json -W .github/workflows/release.yml $IMG     # on: push: tags: [...]
act release -e <skill>/assets/events/release.json $IMG              # on: release
```
Guard the actual publish step with `if: ${{ !env.ACT }}` (see 13), or point it at a dry-run mode.

## 5. Run a subset of a matrix

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, ubuntu-22.04]
    node: [18, 20, 22]
```
```sh
act -j test --matrix node:20 $IMG -P ubuntu-22.04=catthehacker/ubuntu:act-22.04          # 2 combos
act -j test --matrix node:20 --matrix os:ubuntu-latest $IMG                                # 1 combo
act -j test --matrix node:20 --matrix node:22 $IMG                                         # node 20 OR 22
```
`runs-on: ${{ matrix.os }}` with `macos-latest`/`windows-latest` entries is skipped unless those labels are mapped. Filter them out with `--matrix os:ubuntu-latest`.

## 6. workflow_dispatch with inputs

```sh
act workflow_dispatch -W .github/workflows/deploy.yml --input environment=staging --input dry_run=true $IMG
# or
printf '{"inputs":{"environment":"staging","dry_run":"true"}}' > /tmp/dispatch.json
act workflow_dispatch -e /tmp/dispatch.json $IMG
```

## 7. Integration tests with service containers

```yaml
jobs:
  it:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: pw, POSTGRES_DB: app }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 5s --health-retries 10
    env:
      DATABASE_URL: postgres://postgres:pw@localhost:5432/app
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run test:integration
```
`act -j it $IMG`. If 5432 is busy locally, override the URL for act runs: change the port mapping, or run the job in `container:` and use host `postgres`.

## 8. Fast iteration loop

```sh
act -j test $IMG --pull=false --action-offline-mode --reuse     # no re-pull/re-fetch; keep container state
act -j lint $IMG --bind --pull=false                             # bind repo (no copy); outputs land locally
act -j test $IMG --watch                                         # rerun on file changes (respects .gitignore)
act -j unit -P ubuntu-latest=-self-hosted                        # no Docker at all (host mode, not isolated)
```
Clean up after `--reuse`: `docker ps -a --filter name=act- -q | xargs -r docker rm -f`.

## 9. Machine-readable results

```sh
act -j test $IMG --json > /tmp/act.jsonl 2>&1; echo "exit=$?"
J() { jq -R 'fromjson? // empty' /tmp/act.jsonl | jq -r "$1"; }   # skips non-JSON lines
J 'select(.stepResult=="failure") | "\(.job) :: \(.step)"'        # failed steps
J 'select(.jobResult) | "\(.job): \(.jobResult)"'                 # job results
J 'select(.jobID=="test" and .raw_output==true) | .msg'           # raw step output of job "test"
grep -v '^{' /tmp/act.jsonl                                       # non-JSON lines (warnings, "Error: Job 'x' failed")
```
(Verified against real act v0.2.89 `--json` output. The Apple Silicon warning and the final `Error:` line aren't JSON.)

## 10. Project setup for act

```
.actrc                       # -P mappings, --artifact-server-path, -e .github/act/event.json, etc.
.github/act/event.json       # {"act": true, ...} default payload (enables job-level skipping)
.secrets                     # GITHUB_TOKEN=..., other secrets  (gitignored!)
.secrets.example             # documented keys, no values (committed)
.vars                        # repository variables
.env                         # env overrides for local runs
```
`.gitignore`:
```
.secrets
.vars
.env
.input
.artifacts/
```
`.actrc` example:
```
-P ubuntu-latest=catthehacker/ubuntu:act-latest
-P ubuntu-24.04=catthehacker/ubuntu:act-24.04
-P ubuntu-22.04=catthehacker/ubuntu:act-22.04
--artifact-server-path=/tmp/act-artifacts
-e .github/act/event.json
```

## 11. act as a local task runner

```yaml
# .github/workflows/tasks.yml
name: tasks
on: workflow_dispatch
jobs:
  fmt:   { runs-on: ubuntu-latest, steps: [ {uses: actions/checkout@v4}, {run: make fmt} ] }
  test:  { runs-on: ubuntu-latest, steps: [ {uses: actions/checkout@v4}, {run: make test} ] }
```
`act workflow_dispatch -W .github/workflows/tasks.yml -j test` (add `--bind` to keep formatter changes locally).

## 12. Test workflows in CI with act

```yaml
jobs:
  act-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: curl -sSfL https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash -s -- -b /usr/local/bin
      - run: act -W .github/workflows/my-action-test.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest -s GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}
```
Running this workflow itself under act (act inside act) also works because the Docker socket is mounted, but workspace paths must line up, so it's usually not worth it.

## 13. Guarding side effects

Workflows can hit real systems (releases, package publishes, deploys, PR comments) because act passes real tokens. Before running a workflow you didn't write:
1. Read the workflow. Look for `gh release`, `npm publish`, `docker push`, `kubectl`, `terraform apply`, `curl -X POST`, actions like `softprops/action-gh-release` or `peter-evans/create-pull-request`.
2. Guard them: `if: ${{ !env.ACT }}` (steps) or `if: ${{ !github.event.act }}` + `-e` payload with `{"act": true}` (jobs).
3. Or run only the safe jobs with `-j`, and don't pass write-scoped tokens.

## 14. Running long act jobs from an agent

- First run pulls images (~2GB for medium), which can take minutes. Use a generous tool timeout or run in the background and poll the log file.
- Always redirect output: `act ... > /tmp/act.log 2>&1; echo "exit=$?"`. Read the tail and grep for `❌`, `Error`, `🏁`.
- macOS lacks GNU `timeout`. Use `gtimeout` (coreutils) or the agent tool's own timeout.
- Prefer `-j` and `-W` to keep runs small. Run `act -l` before each run.
- Clean up containers that failed jobs leave behind when done.
