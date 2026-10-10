# Installing act

Prerequisite: a Docker Engine API (Docker Desktop on macOS/Windows, Docker Engine on Linux, or an alternative; see [container-engines.md](container-engines.md)). It's not needed if you only use host mode (`-P <label>=-self-hosted`) or `act -l/-g/--validate`.

Check: `act --version` (this skill was verified against `act version 0.2.89`).

## Package managers

| Platform | Command |
|---|---|
| macOS / Linux (Homebrew) | `brew install act` (latest commit: `brew install act --HEAD`) |
| macOS (MacPorts) | `sudo port install act` |
| Arch Linux | `pacman -Syu act` |
| Fedora/RHEL (COPR) | `dnf copr enable goncalossilva/act && dnf install act-cli` |
| Nix / NixOS | `nix-env -iA nixpkgs.act` · `nix-shell -p act` · `nix run nixpkgs#act` |
| Windows (Chocolatey) | `choco install act-cli` |
| Windows (Scoop) | `scoop install act` |
| Windows (WinGet) | `winget install nektos.act` |
| GitHub CLI extension (any OS) | `gh extension install https://github.com/nektos/gh-act`, then use `gh act ...` |

Packaging status across distros: <https://repology.org/project/act-run-github-actions/versions>

## Install script (any OS with bash)

```sh
# Default install dir is ./bin (relative to cwd!). Pass -b to choose:
curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash -s -- -b /usr/local/bin
# specific version:
curl ... | bash -s -- -b "$HOME/.local/bin" v0.2.89
```
Flags: `-b <bindir>`, `-d` debug, `-f` force, optional tag. It can't install unreleased versions.

## Prebuilt binaries

From <https://github.com/nektos/act/releases/latest>: `act_Darwin_arm64.tar.gz`, `act_Darwin_x86_64.tar.gz`, `act_Linux_x86_64.tar.gz`, `act_Linux_arm64.tar.gz`, `act_Linux_armv6.tar.gz`, `act_Linux_armv7.tar.gz`, `act_Linux_i386.tar.gz`, `act_Windows_x86_64.zip`, `act_Windows_arm64.zip`, `act_Windows_armv7.zip`, `act_Windows_i386.zip`.

```sh
curl -sSL https://github.com/nektos/act/releases/latest/download/act_Linux_x86_64.tar.gz | tar -xz -C ~/.local/bin act
```

## From source (Go)

```sh
git clone https://github.com/nektos/act.git && cd act
make build      # or:
go build -ldflags "-X main.version=$(git describe --tags --dirty --always | sed -e 's/^v//')" -o dist/local/act main.go
# or simply:
go install github.com/nektos/act@latest
```

## Editor / ecosystem integrations

- VS Code extension "GitHub Local Actions" (runs act from the editor): <https://sanjulaganepola.github.io/github-local-actions-docs/>
- Gitea Actions runner (`act_runner`), built on an act fork: <https://gitea.com/gitea/act_runner>
- `github-act-runner` (self-hosted runner implementation using act): <https://github.com/ChristopherHX/github-act-runner>
- `act-test-runner` (test workflows from JVM tests): <https://github.com/pshevche/act-test-runner>
- Recommended for workflow authoring: the official GitHub Actions VS Code extension (schema validation shows clearer errors than act's).

## After installing

1. Make sure Docker works: `docker info`.
2. Avoid the interactive first-run image prompt: pass `-P ubuntu-latest=catthehacker/ubuntu:act-latest`, or create `./.actrc` / `~/.actrc` with `-P` lines (see [cli-reference.md](cli-reference.md#configuration-file-actrc)).
3. `act -l` in a repo with `.github/workflows/`.
