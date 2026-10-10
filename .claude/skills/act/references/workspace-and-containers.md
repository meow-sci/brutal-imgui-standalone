# Workspace, filesystem and container lifecycle

## Contents
- [Where your code is inside the job](#where-your-code-is-inside-the-job)
- [Copy vs bind](#copy-vs-bind)
- [Paths inside the job container](#paths-inside-the-job-container)
- [Container naming, volumes, reuse, cleanup](#container-naming-volumes-reuse-cleanup)
- [Debugging inside a job container](#debugging-inside-a-job-container)

## Where your code is inside the job

Verified behavior (container mode):

| Situation | Contents of `$GITHUB_WORKSPACE` |
|---|---|
| No checkout step, no `--bind` | **Empty** (a fresh Docker volume) |
| `uses: actions/checkout@vN` (same repo, no different `ref`) | act **does not clone**. It copies your local working tree there, **including `.git`, uncommitted changes and untracked files**, excluding `.gitignore`d paths (`--use-gitignore=false` includes them) |
| checkout `with: path: sub` | Local tree copied into `$GITHUB_WORKSPACE/sub` |
| checkout with a `repository:` or `ref:` that isn't **literally** equal to `github.repository` / `github.ref` | Real `actions/checkout` runs (clones from GitHub, needs `GITHUB_TOKEN`, commit must be pushed). The comparison uses the **raw, un-interpolated** string, so `ref: ${{ github.ref }}`, `ref: ${{ github.head_ref }}`, `ref: main` (vs `refs/heads/main`) or `repository: ${{ github.repository }}` all trigger a real clone (verified) |
| `--no-skip-checkout` | Real `actions/checkout` always runs: clones `github.repository` at `github.sha`/`ref` from GitHub, so your **local uncommitted changes are not used** and the commit must be pushed |
| `--bind` | Host repo is bind-mounted at the same path. Checkout is a no-op. Writes affect your real files |

Practical consequence: act tests **your current local edits** by default, with no commit or push needed.

Only `actions/checkout` is substituted. Third-party checkout wrappers clone for real.

If a workflow's checkout has `ref:`/`repository:` and you want to test local changes, either:
- temporarily drop those keys under act: use two steps, `if: ${{ env.ACT }}` (plain checkout) and `if: ${{ !env.ACT }}` (original), or
- run with `--bind` and remove/guard the checkout step, or
- push your branch and let the real checkout clone it (`-s GITHUB_TOKEN=...` for private repos).

## Copy vs bind

| | Copy (default) | `--bind` / `-b` |
|---|---|---|
| Speed | Copies the tree each job (slow for huge repos / node_modules unless gitignored) | Instant |
| Isolation | Job writes stay in the container volume | Job writes (build outputs, formatter changes, `git` operations) land in your repo |
| Root-owned files | n/a | Files created by root in the container may end up root-owned on Linux hosts |
| macOS | | Mounted with `:delegated`. Large trees may be slower on Docker Desktop file sharing |
| SELinux hosts | | Mounted with `:z` |

Use `--bind` when you want build artifacts locally, or for very large repos. Use copy mode when you want a clean, disposable run.

## Paths inside the job container

| Path | Purpose |
|---|---|
| `<same absolute path as host repo>` | Working directory / `GITHUB_WORKSPACE` (Windows hosts: `C:\x\y` → `/mnt/c/x/y`) |
| `/var/run/act/` | act internal dir (volume `<container>-env`): `workflow/event.json`, `workflow/envs.txt` (GITHUB_ENV), `outputcmd.txt`, `statecmd.txt`, `pathcmd.txt`, `SUMMARY.md`, and generated step scripts (`workflow/<n>.sh`) |
| `/var/run/act/actions/<action>` | Copied remote/local action sources |
| `/opt/hostedtoolcache` | `RUNNER_TOOL_CACHE`, a persistent named volume `act-toolcache` shared across all runs (setup-node/python/go downloads survive) |
| `/tmp` | `RUNNER_TEMP` |
| `/var/run/docker.sock` | Host Docker socket (unless `--container-daemon-socket -`) |
| `/github/workspace`, `/github/home`, … | **Not used** by act, not even for Docker actions (they get the same mounts as the job container) |

Host-side directories:

| Path | Purpose |
|---|---|
| `~/.cache/act/` (`--action-cache-path`, `$XDG_CACHE_HOME/act`) | Cloned remote actions (`<org>-<repo>@<ref>`), reusable workflows, host-mode temp workspaces, host tool cache |
| `~/.cache/actcache/` (`--cache-server-path`) | `actions/cache` storage |
| `--artifact-server-path` dir | Uploaded artifacts |

## Container naming, volumes, reuse, cleanup

- Job container: `act-<workflow name>-<job name>[-<matrix index>]-<sha256>`, with non-alphanumerics turned into `-`. Volumes: same name (workspace) and `<name>-env` (`/var/run/act`).
- Service containers: `<job container name>-<service id>-<hash>`. Network: `<job container name>-<job id>-network`.
- Lifecycle:
  - **Success:** container, volumes, services and network are removed.
  - **Failure:** job container and volumes are **left in place** (container still running `tail -f /dev/null`) for debugging. `--rm` removes them anyway.
  - `-r/--reuse`: never remove. The next run reuses the same container and workspace (state persists, e.g. installed packages and node_modules). Useful for fast iteration. Remember to clean up.
- Before starting a job, act removes any old container with the same name (unless reusing).

Cleanup commands:
```sh
docker ps -a --filter name=act- --format '{{.Names}}\t{{.Status}}'
docker ps -a --filter name=act- -q | xargs -r docker rm -f
docker volume ls -q | grep '^act-' | grep -v '^act-toolcache$' | xargs -r docker volume rm
docker network ls -q --filter name=act- | xargs -r docker network rm
docker volume rm act-toolcache            # only to reset cached tool downloads
rm -rf ~/.cache/act                       # re-download all actions next run
```

## Debugging inside a job container

1. Run the failing job: `act -j build -P ubuntu-latest=catthehacker/ubuntu:act-latest` (fails and leaves its container).
2. `docker ps --filter name=act- --format '{{.Names}}'`
3. `docker exec -it <name> bash` and `cd` to the repo path. Inspect files, rerun commands, check `/var/run/act/workflow/*.sh` (exact scripts act ran) and `/var/run/act/workflow/event.json`.
4. Alternatively, insert a temporary step `run: sleep 3600` before the failing step (guard it with `if: ${{ env.ACT }}`), then exec in while it waits.
5. `-v` shows evaluated expressions, env, and docker exec commands.
