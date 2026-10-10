# Service containers, job containers and networking

## Contents
- [Service containers](#service-containers)
- [How to reach a service (verified)](#how-to-reach-a-service-verified)
- [Job containers (container:)](#job-containers-container)
- [Networking flags](#networking-flags)
- [Docker-in-workflow (docker build / compose inside steps)](#docker-in-workflow)
- [container options parsing](#container-options-parsing)

## Service containers

`jobs.<id>.services` is supported (the docs' support matrix is outdated): `image`, `env`, `ports`, `volumes`, `options`, `credentials`, all with expression interpolation.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: runner
          POSTGRES_PASSWORD: secret
          POSTGRES_DB: app
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: --health-cmd "redis-cli ping" --health-interval 2s --health-retries 10
    steps:
      - run: PGPASSWORD=secret psql -h localhost -U runner -d app -c 'select 1'
```

- act creates a dedicated network `<job-container>-<jobid>-network` and starts services on it with the service id as network alias.
- act waits until every service with a Docker `HEALTHCHECK` (from `options` or the image) reports healthy, polling with backoff for up to ~5 minutes. If the service never becomes healthy, the job fails with `service container failed to start`. Services without a healthcheck count as ready immediately, so add a wait loop in your steps for slow starters.
- `image: ''` (e.g. `${{ matrix.db == 'none' && '' || 'postgres' }}`) means the service is skipped.
- The `job.services.<id>.id/network/ports` context isn't populated by act (it evaluates to empty). Use known ports/aliases instead of reading them dynamically.
- Services are removed when the job ends (unless `--reuse`, or the job failed without `--rm`).

## How to reach a service (verified)

| Job type | Address | Requirement |
|---|---|---|
| `runs-on` job (no `container:`) | `localhost:<host port>` | Service must publish `ports:` (e.g. `5432:5432`). The job container is on the **host** network (`--network host` default), so the service alias **doesn't resolve** there |
| Job with `container:` | `<service id>:<container port>` (e.g. `redis:6379`) | Nothing extra. The job container joins the service network |

Same as GitHub's rules. On Docker Desktop (macOS/Windows), "host network" means the Docker VM's network, so published ports are reachable from the job container via `localhost`, but other host-machine services are not (use `host.docker.internal`).

Port conflicts: publishing `5432:5432` fails if something on the Docker host already uses 5432 (e.g. a local Postgres, or a parallel act job). Use a different host port (`15432:5432`) and point the step at it, or use a `container:` job and the service alias. Matrix jobs with services run in parallel and fight over host ports. Limit them with `--matrix` or `strategy.max-parallel: 1`.

## Job containers (container:)

```yaml
jobs:
  build:
    runs-on: ubuntu-latest           # still needs a -P mapping or the job is skipped as unsupported platform
    container:
      image: node:20-bookworm
      credentials: { username: ${{ secrets.REG_USER }}, password: ${{ secrets.REG_PASS }} }
      env: { NODE_ENV: test }
      volumes: [ "my_named_vol:/data", "/abs/host/path:/mnt/host" ]
      options: --cpus 2 --hostname builder
    steps: [ ... ]
```

- The container image replaces the `-P` image. `runs-on` must still resolve via `-P` (any image value) or the job is skipped.
- `container: node:20` (string form) is supported.
- Default shell inside a `container:` job is **`sh`**, not bash. Set `shell: bash` (step) or `defaults.run.shell: bash` when using bash features (`[[`, `/dev/tcp`, `pipefail`, arrays). This matches GitHub.
- JS actions need `node` in the container image's `PATH` (GitHub mounts its own node, act doesn't). Alpine/distroless images without node can't run `actions/*` JS actions.
- `volumes`: `name:/path` creates or uses a named volume. `/abs:/path` is a bind mount.
- `credentials` must contain both username and password, and both must interpolate to non-empty values.
- `ports` on the job container itself are ignored.

## Networking flags

- `--network <name>` (default `host`): network for job containers that have no services and no `container:`. Example: `docker network create devnet` with your local stack on it, then `act --network devnet` lets jobs reach `db:5432`, etc.
- Inside job containers, `localhost` is the Docker host's network namespace (in host mode). On Linux that's the real host, so jobs can reach host services directly.
- Artifact/cache servers bind to the host's outbound IP (`--artifact-server-addr`, `--cache-server-addr`) so containers can reach them. If you're on a VPN or your IP changes, set them explicitly (e.g. `--cache-server-addr 0.0.0.0 --cache-server-external-url http://host.docker.internal:PORT`).

## Docker-in-workflow

By default the host Docker socket is mounted into job containers at `/var/run/docker.sock`. Steps like `docker build`, `docker compose up`, or testcontainers talk to the **host** daemon:
- Images and containers they create persist on your host after the run. Clean them up.
- Bind mounts in `docker run -v $PWD:/x` refer to **host** paths. Since the workspace sits at the same absolute path as the host repo, that only works with `--bind`. In copy mode the files live in a Docker volume, not at that host path.
- testcontainers: set `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal` (Docker Desktop) if it can't reach mapped ports.
- Disable socket mounting with `--container-daemon-socket -`, or point it elsewhere: `--container-daemon-socket unix:///run/user/1000/podman/podman.sock`.
- Docker Desktop/colima: the mounted socket path inside the VM is handled automatically.

## container options parsing

Both `container.options` / `services.*.options` (workflow) and `--container-options` (CLI, used when the job has no `container.options`) are parsed like `docker run` flags. Common ones work: `--privileged`, `--cap-add`, `--cap-drop`, `--security-opt`, `--user`, `--memory`, `--cpus`, `--shm-size`, `--tmpfs`, `-v/--volume`, `-e/--env`, `--hostname`, `--add-host`, `--device`, `--gpus`, `--ulimit`, `--health-*`, `--entrypoint`, `--network` (job default), `--userns`. Unknown flags cause `Cannot parse container options`.

```sh
act --container-options "--privileged --add-host=api.local:host-gateway --shm-size=2g"
```
