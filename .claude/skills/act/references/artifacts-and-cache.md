# Artifacts and caching

## Contents
- [Artifacts (upload/download-artifact)](#artifacts)
- [actions/cache and setup-* caching](#actionscache)
- [Tool cache](#tool-cache)
- [Action cache vs actions/cache](#action-cache-vs-actionscache)

## Artifacts

The artifact server is **off by default**: `ACTIONS_RUNTIME_URL`, `ACTIONS_RUNTIME_TOKEN`, and `ACTIONS_RESULTS_URL` are blank, and `actions/upload-artifact` fails. Enable it:

```sh
act --artifact-server-path "$PWD/.artifacts"      # or a dir outside the repo, e.g. /tmp/act-artifacts
```

- Supported: `actions/upload-artifact@v3/v4` and `actions/download-artifact@v3/v4` **within the same act run** (pass artifacts between jobs via `needs`). Verified with v4: upload in job A, download in a dependent job B.
- Not supported: downloading artifacts from another run, workflow, or repository (v4 `github-token` / `run-id` inputs).
- Files are stored under `<path>/<run id>/<artifact name>/` (run id `1` unless `--env GITHUB_RUN_ID=n`). Inspect or collect them from the host after the run. v4 uploads are stored zipped.
- Reusing the same path across runs: artifacts with the same name and run id may collide, so delete the dir or vary `GITHUB_RUN_ID` between runs.
- While enabled, the `ACTIONS_*` runtime vars are visible to `run:` steps too (unlike GitHub).
- `--artifact-server-addr` (default: host outbound IP) and `--artifact-server-port` (default `34567`) control binding. Change the port if two act runs execute concurrently.
- Add the dir to `.gitignore` if it's inside the repo, or the next checkout copy includes it.

## actions/cache

A built-in cache server is **on by default**. act sets `ACTIONS_CACHE_URL` for every job, so `actions/cache@v3/v4`, `actions/cache/save` and `restore`, and the built-in `cache:` option of `actions/setup-node`, `setup-python`, `setup-go`, `setup-java` work locally. Verified: cache miss, then `Cache saved with key: ...` on the first run, restored on the next.

| Flag | Default |
|---|---|
| `--cache-server-path` | `~/.cache/actcache` (persists across runs and repos) |
| `--cache-server-addr` | host outbound IP |
| `--cache-server-port` | random free port |
| `--cache-server-external-url` | – (for proxies, no trailing slash) |
| `--no-cache-server` | disable |

- Setting `ACTIONS_CACHE_URL` yourself via `--env` makes act skip starting its server (point it at a shared cache server).
- Cache keys commonly use `hashFiles()`, which works in act and hashes files in the workspace. Make sure the files exist there (checkout first).
- To force a cache miss, change the key or `rm -rf ~/.cache/actcache`.
- If restore/save hangs or times out: the container can't reach the host IP (VPN, firewall, changed network). Set `--cache-server-addr` to an address reachable from containers, or use `--no-cache-server`.

## Tool cache

`/opt/hostedtoolcache` is a persistent Docker volume `act-toolcache` shared by all runs. `setup-node`, `setup-python` and similar download toolchains there once. `docker volume rm act-toolcache` resets it. Host mode uses `~/.cache/act/tool_cache`.

## Action cache vs actions/cache

- **Action cache** (`~/.cache/act`, `--action-cache-path`): clones of the *actions themselves* (`uses: org/repo@ref`) and remote reusable workflows. Controlled by `--action-offline-mode`, `--use-new-action-cache`, `--local-repository`. See [actions-and-reusable-workflows.md](actions-and-reusable-workflows.md).
- **Cache server** (`~/.cache/actcache`): what your workflow stores with `actions/cache`.
