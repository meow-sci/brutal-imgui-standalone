# Actions and reusable workflows

## Contents
- [Kinds of `uses:` act supports](#kinds-of-uses-act-supports)
- [How remote actions are fetched and cached](#how-remote-actions-are-fetched-and-cached)
- [Offline mode](#offline-mode)
- [Testing a local action you're developing](#testing-a-local-action-youre-developing)
- [Overriding a remote action/workflow with a local checkout (--local-repository)](#--local-repository)
- [Reusable workflows](#reusable-workflows)
- [GitHub Enterprise Server](#github-enterprise-server)

## Kinds of `uses:` act supports

| Form | Example | Notes |
|---|---|---|
| Remote action | `actions/setup-node@v4`, `org/repo/sub/path@sha` | Cloned from `github.com` (or `--github-instance`). Full SHA, short SHA, tag, and branch refs work |
| Local action | `./.github/actions/my-action` | Read **from the job's workspace**, so you need `actions/checkout` first (or `--bind`), same as GitHub |
| Docker image | `docker://alpine:3.20` | `with.args` / `with.entrypoint` are passed to the container |
| Reusable workflow (job-level) | `uses: ./.github/workflows/build.yml` or `org/repo/.github/workflows/build.yml@v1` | See below |

Action `runs.using` support: `node12`, `node16`, `node20`, `node24`, `docker` (image or `Dockerfile`), `composite` (nested composites too). Pre/post steps (`runs.pre`, `runs.post`, `pre-if`, `post-if`) run.

- **Node actions run with whatever `node` is on the container's `PATH`.** The `nodeXX` version in `action.yml` isn't enforced (GitHub ships its own node runtime). The catthehacker act images ship a recent Node (v24 at the time of writing). Images without node (alpine, distroless, `ubuntu:24.04`) fail JS actions with errors like `exec: "node": executable file not found`.
- **Dockerfile actions** are built locally each run (`--rebuild` default true; `--rebuild=false` reuses the image). Image-based docker actions are pulled (`--pull`).
- Docker actions run in a separate container with the **same mounts as the job container** (workspace at the host-absolute repo path, `/var/run/act`, toolcache, docker socket) and the job container's network namespace. Working dir is the workspace. This differs from GitHub, which uses `/github/workspace`, so actions that hard-code `/github/workspace` may break. `INPUT_*` env and `args` are interpolated.

## How remote actions are fetched and cached

- Default cache dir: `~/.cache/act/` (`--action-cache-path`). Each `uses:` string gets a directory named after it with `/` and `:` replaced by `-` (e.g. `actions-checkout@v4`).
- Every run does a `git fetch`/checkout of the ref (network). A `GITHUB_TOKEN` secret (or `gh auth token`) is used for private repos and to avoid rate limits.
- `--use-new-action-cache` switches to a go-git store that keeps one bare repo per action and extracts trees per resolved sha. It's more robust for many refs of the same repo and is enabled automatically by `--local-repository`.
- Corrupt or odd cache state: `rm -rf ~/.cache/act/<dir>`, or the whole `~/.cache/act`.
- `actions/checkout` is special-cased (local copy). See [workspace-and-containers.md](workspace-and-containers.md#where-your-code-is-inside-the-job).

## Offline mode

```sh
act --action-offline-mode        # or put it in .actrc
```
- Uses cached action clones and existing images without fetching or pulling. Missing ones are still fetched.
- Turns off force-pull of images.
- Avoids GitHub rate limits and flaky networks. Requires at least one online run first.

## Testing a local action you're developing

Composite/JS/Docker action in this repo:
```yaml
# .github/workflows/test-action.yml
on: [push, workflow_dispatch]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: run
        uses: ./                     # or ./path/to/action
        with:
          who-to-greet: act
      - run: test "${{ steps.run.outputs.greeting }}" = "Hello act"
```
`act -W .github/workflows/test-action.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest`

Known issue `MODULE_NOT_FOUND` during `docker cp` (old act, nektos/act#228): when an action uses `uses: ./` and relies on unpushed local changes, check out with `path:` equal to the repository name:
```yaml
- uses: actions/checkout@v4
  with:
    path: "my-action"      # must equal the repo name
```
For JS actions, make sure `dist/` (or `node_modules`) is present in the working tree, since act copies the tree minus gitignored files. If `node_modules` is gitignored but needed, run `npm ci` in a step first, or use `--use-gitignore=false`.

## --local-repository

Point a remote `uses:` (action or reusable workflow) at a local directory, e.g. to test an unreleased change to a shared action:

```sh
act --local-repository my-org/shared-actions@v2=/home/me/src/shared-actions
act --local-repository https://github.com/my-org/shared-actions@v2=/home/me/src/shared-actions   # host-specific key
```
- Key must match `org/repo@ref` exactly as written in `uses:` (the `@ref` part too). The local directory's **working tree** is used as is (uncommitted changes included), regardless of ref.
- Repeat the flag for several repos.

## Reusable workflows

Supported: local and remote `jobs.<id>.uses`, `with` inputs (string/number/boolean, evaluated in the caller), `secrets:` mapping, `secrets: inherit`, `outputs` (via `on.workflow_call.outputs`), `needs` on reusable jobs, nested calls, matrix-calling (`strategy.matrix` with `uses`).

```yaml
jobs:
  build:
    uses: ./.github/workflows/build.yml          # must start with ./ (relative to repo root)
    with:
      target: linux
      debug: ${{ true }}
    secrets:
      token: ${{ secrets.NPM_TOKEN }}
  shared:
    uses: my-org/ci/.github/workflows/lint.yml@v3   # {owner}/{repo}/.github/workflows/{file}@{ref}
    secrets: inherit
  after:
    needs: [build]
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ needs.build.outputs.artifact-name }}"
```

- The called workflow runs its own jobs (each still needs `-P` mappings for its `runs-on`). Log prefix: `<caller job>/<called workflow>/<job>`.
- **Local** reusable workflows are read from the host repo directory (no checkout needed).
- **Remote** reusable workflows are cloned into the action cache (token used for private repos). They're re-fetched each run unless offline mode is on or `--local-repository` overrides them.
- Invalid `uses` format gives: ``uses` key references invalid workflow path '...'. Must start with './' if it's a local workflow, or must start with '<org>/<repo>/' and include an '@' if it's a remote workflow``.
- A reusable workflow file must have `on: workflow_call` (any `on` form containing it).
- Run a reusable workflow directly: `act workflow_call -W .github/workflows/build.yml --input target=linux` (or `-e` with `{"inputs": {...}}`). Boolean inputs must be strings `"true"`.
- `-j <caller-job>` runs the caller job, which runs the whole called workflow.

## GitHub Enterprise Server

```sh
act --github-instance github.mycompany.com -s GITHUB_TOKEN=$GHES_TOKEN
```
- Remote actions and reusable workflows are cloned from the GHES host using `GITHUB_TOKEN`. `github.server_url` becomes `https://<host>`, `api_url` becomes `https://<host>/api/v3`, and `graphql_url` becomes `https://<host>/api/graphql`.
- Some actions only exist on github.com. Fetch those from there:
  ```sh
  act --github-instance github.mycompany.com \
      --replace-ghe-action-with-github-com actions/setup-node \
      --replace-ghe-action-with-github-com github/super-linter \
      --replace-ghe-action-token-with-github-com "$GITHUB_COM_PAT"   # only needed for private github.com actions
  ```
- `github.repository` is derived from the `origin` remote matching the GHES host.
