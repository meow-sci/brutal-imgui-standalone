# Container engines and Docker connectivity

act talks to the **Docker Engine API**. Anything that exposes that API works to varying degrees: Docker Desktop, Docker Engine (Linux), colima, OrbStack, Rancher Desktop (moby), podman (via its Docker-compatible socket), and remote engines over TCP or SSH. Only Docker is officially supported. Podman "might work" (nektos/act#303).

## How act finds the engine

1. `DOCKER_HOST`, if set (never overridden).
2. Otherwise the first existing socket among:
   - `/var/run/docker.sock`
   - `/run/podman/podman.sock`
   - `$HOME/.colima/docker.sock`
   - `$XDG_RUNTIME_DIR/docker.sock`
   - `$XDG_RUNTIME_DIR/podman/podman.sock`
   - `\\.\pipe\docker_engine` (Windows)
   - `$HOME/.docker/run/docker.sock` (Docker Desktop on macOS)

act logs `Using docker host '<host>', and daemon socket '<socket>'`. `act --bug-report` lists which sockets exist (and broken symlinks).

`--container-daemon-socket <uri>` changes only the socket **mounted into job containers** (default: the same as the host). Use `-` to mount nothing.

## Docker context is NOT respected

`docker context use x` has no effect on act (nektos/act#583, won't fix). Export the context's endpoint:
```sh
export DOCKER_HOST=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
# if that context uses TLS client certs:
export DOCKER_CERT_PATH=$(docker context inspect --format '{{.Storage.TLSPath}}')/docker
```
One-shot: `DOCKER_HOST=$(docker context inspect --format '{{.Endpoints.docker.Host}}') act ...`

## Recipes per engine

**Docker Desktop (macOS/Windows):** usually auto-detected (`/var/run/docker.sock` symlink or `~/.docker/run/docker.sock`). If the daemon isn't running: `failed to connect to the docker API ... no such file or directory`. Start Docker Desktop (`open -a Docker` on macOS) and wait for `docker info` to succeed.

**colima:**
```sh
colima start --cpu 4 --memory 8
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"   # or rely on auto-detect of ~/.colima/docker.sock
act ...
```

**podman (Linux rootful):**
```sh
sudo systemctl enable --now podman.socket
DOCKER_HOST='unix:///var/run/podman/podman.sock' act ...
```
**podman (rootless Linux):**
```sh
systemctl --user enable --now podman.socket
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
act --container-daemon-socket - ...     # avoid mounting the rootless socket into containers if it causes permission errors
```
**podman (macOS, podman machine):**
```sh
podman machine start
export DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')"
```
Podman caveats: health checks, `--network host` and service networking may behave differently. If services fail, try `--network` with a podman network, or run jobs in `container:`.

**Remote engine over SSH:**
```sh
DOCKER_HOST='ssh://user@build-host' act ...
```
PowerShell: `$env:DOCKER_HOST = 'ssh://user@host'; act ...`
With a remote engine, the workspace is copied over the API (works), but `--bind` mounts **remote** paths (usually wrong), and `localhost` service ports are on the remote host.

**Remote TCP/TLS:** `DOCKER_HOST=tcp://host:2376 DOCKER_TLS_VERIFY=1 DOCKER_CERT_PATH=~/.docker/certs act ...`

## Permissions (Linux)

`permission denied while trying to connect to the Docker daemon socket`: add the user to the `docker` group (`sudo usermod -aG docker $USER`, then re-login), or run rootless Docker and set `DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock`. Avoid `sudo act`: caches and configs end up under root's HOME.

## Running act inside CI or another container

- act inside a GitHub Actions job (`ubuntu-latest` has Docker): install act (`curl -sSfL https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash -s -- -b /usr/local/bin`) and run `act -P ubuntu-latest=catthehacker/ubuntu:act-latest ...`. This is useful for testing workflows/actions as part of CI.
- act inside a dev container: mount the host socket (`-v /var/run/docker.sock:/var/run/docker.sock`). Workspace paths differ between the container and the host, so use copy mode (not `--bind`) unless the paths match.
