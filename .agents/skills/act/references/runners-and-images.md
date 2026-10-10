# Runners, platforms and images

## Contents
- [How runs-on maps to an image](#how-runs-on-maps-to-an-image)
- [Image choices](#image-choices)
- [Picking an image for a workflow](#picking-an-image-for-a-workflow)
- [Host mode (-self-hosted)](#host-mode--self-hosted)
- [Architecture / Apple Silicon](#architecture--apple-silicon)
- [Pulling, local images, private registries](#pulling-local-images-private-registries)
- [Fidelity limits](#fidelity-limits)

## How runs-on maps to an image

Each job's `runs-on` labels are evaluated (expressions allowed, e.g. `${{ matrix.os }}`) and lower-cased. The **first label with a `-P` mapping** chooses the image. `runs-on: {group: x, labels: [...]}` uses the labels plus the group name.

- If the job has `container:` (image), that image is used instead and `-P` only matters for host detection.
- If no label is mapped, the job is **skipped** with `🚧  Skipping unsupported platform -- Try running with -P <label>=...`, and act still exits 0. Always map every label your jobs use (`self-hosted`, `macos-latest`, custom labels, …).

Built-in default mappings (micro images, used only when no survey/actrc/`-P` overrides them):

| Label | Default image |
|---|---|
| `ubuntu-latest` | `node:16-buster-slim` |
| `ubuntu-22.04` | `node:16-bullseye-slim` |
| `ubuntu-20.04` | `node:16-buster-slim` |
| `ubuntu-18.04` | `node:16-buster-slim` |

These are tiny and outdated (Node 16, no git/docker CLI, etc.). Override them.

```sh
act -P ubuntu-latest=catthehacker/ubuntu:act-latest
act -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 -P ubuntu-22.04=catthehacker/ubuntu:act-22.04
act -P self-hosted=catthehacker/ubuntu:act-latest -P my-gpu-runner=nvidia/cuda:12.4.1-runtime-ubuntu22.04
act -P ubuntu-latest=ubuntu:24.04            # any image works if it has what your steps need (node for JS actions!)
```

## Image choices

| Size (survey name) | Image | Notes |
|---|---|---|
| Micro | `node:16-*-slim` | <200MB. Node only. Many actions fail. |
| **Medium (recommended)** | `catthehacker/ubuntu:act-latest`, `act-24.04`, `act-22.04`, `act-20.04` | ~2.3GB unpacked. Ubuntu 24.04 (latest), root user, node, npm, python3, git, docker CLI, jq, curl, zstd. **No `gh`**. Compatible with most actions. Multi-arch (amd64/arm64/arm). |
| Large | `catthehacker/ubuntu:full-latest`, `full-24.04`, `full-22.04` | ~17GB download / ~53GB on disk (needs ~75GB free). Filesystem dump of GitHub's hosted runner (minus snap and pre-pulled images). amd64 + arm64. |
| Runner-user variants | `catthehacker/ubuntu:runner-latest`, `runner-24.04`, … | Like `act-*` but runs as non-root user `runner` with sudo, closer to GitHub (catches permission bugs). |
| Language variants | `catthehacker/ubuntu:js-latest`, `go-latest`, `rust-latest`, `pwsh-latest`, `custom-latest` | Medium plus that toolchain preinstalled. |
| Legacy | `nektos/act-environments-ubuntu:18.04` | >18GB, built from GitHub's Packer files. Obsolete. |

Images are also published at `ghcr.io/catthehacker/ubuntu:<tag>`. Source and issues: <https://github.com/catthehacker/docker_images>. Runner image blobs: <https://github.com/ChristopherHX/runner-image-blobs>.

## Picking an image for a workflow

1. Default to `catthehacker/ubuntu:act-latest` for `ubuntu-latest`/`ubuntu-24.04`, and the matching `act-22.04` for `ubuntu-22.04`.
2. A step fails with `command not found` for a tool GitHub runners preinstall: either add an install step guarded by `if: ${{ env.ACT }}`, switch that label to `full-*`, or build a custom image:
   ```dockerfile
   FROM catthehacker/ubuntu:act-latest
   RUN apt-get update && apt-get install -y --no-install-recommends gh postgresql-client && rm -rf /var/lib/apt/lists/*
   ```
   `docker build -t my-act-image .` then `act -P ubuntu-latest=my-act-image --pull=false`.
3. Need Windows/macOS jobs: only possible in host mode on a matching host (below). act's containers are Linux-only.

## Host mode (-self-hosted)

```sh
act -P macos-latest=-self-hosted
act -P windows-latest=-self-hosted
act -P ubuntu-latest=-self-hosted      # run Linux jobs directly on this Linux/macOS machine, no Docker needed
```

Behavior (verified):
- Steps run as host processes. **The host environment is inherited**. `RUNNER_OS` is the real OS (`macOS`, `Windows`, `Linux`).
- Each job gets a fresh temp dir `~/.cache/act/<random>/hostexecutor` as `GITHUB_WORKSPACE`/cwd. It starts **empty**. `actions/checkout` (same repo) copies your working tree (including `.git` and uncommitted files, excluding gitignored paths) into it. The dir is deleted after the job.
- `--bind` doesn't apply. Steps can still touch anything on the host using absolute paths.
- Tool cache: `~/.cache/act/tool_cache`.
- Default shell: `bash` (falls back to `sh`). On Windows: `pwsh` (falls back to `powershell`).
- JS actions need `node` on the host `PATH`. Docker actions and `services` still need Docker.
- A job that has `container:` still runs in Docker.
- Useful for fast lint/test loops without images, but it's **not isolated**. Don't run untrusted workflows this way.

## Architecture / Apple Silicon

- Without `--container-architecture`, containers use the host arch. On Apple Silicon act prints `⚠ You are using Apple M-series chip and you have not specified container architecture...` on every run. It's informational.
- catthehacker `act-*` images are multi-arch, so native arm64 works for most workflows and is much faster.
- Use `--container-architecture linux/amd64` when a step downloads x86_64-only binaries, a `setup-*` action lacks arm64 builds, or you need parity with GitHub's x64 runners. It runs under QEMU/Rosetta emulation: slower, occasionally flaky.
- `RUNNER_ARCH` reflects the container arch (`X64`, `ARM64`).

## Pulling, local images, private registries

- `--pull` defaults to **true**: every run checks the registry for a newer image. `--pull=false` uses the local copy (needed for locally built images that don't exist in a registry, and faster). `--action-offline-mode` also disables force-pull.
- `--rebuild` defaults to true for Dockerfile-based actions. Use `--rebuild=false` to reuse.
- Private job images: `container.credentials` in the workflow, or secrets `DOCKER_USERNAME`/`DOCKER_PASSWORD` (`act -s DOCKER_USERNAME=u -s DOCKER_PASSWORD=p`). Services use their own `credentials:`.
- Images already pulled by `docker pull` (with your `docker login`) are used directly if you pass `--pull=false`.

## Fidelity limits

- Docker containers aren't VMs: no `systemd`, limited kernel features. Some tools behave differently. Use `--container-options "--privileged"` for things like nested Docker daemons or `mount`.
- The default images intentionally lack much of GitHub's preinstalled software.
- Default user is root in `act-*` images (GitHub's runner is a non-root `runner` user with passwordless sudo). `sudo` works in act images, but file ownership differences can hide or cause bugs. Use `runner-*` images for parity.
- Report image issues to catthehacker/docker_images, act issues to nektos/act.
