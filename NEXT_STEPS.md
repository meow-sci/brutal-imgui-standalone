# Next steps to publish XBrutal.ImGuiStandalone on nuget.org

Status as of 2026-10-09: GitHub Actions CI and a tag-driven release pipeline are in place and were
run locally with `act`. Every job runs on `ubuntu-latest`, so act covers all of them except the
real nuget.org/GitHub publishing calls (see [what act could not test](#what-act-could-not-test)).
Nothing has been committed, pushed or published. The package ID `XBrutal.ImGuiStandalone` is still
unclaimed on nuget.org.

Verified locally with act 0.2.89 (linux/amd64 containers on Apple Silicon):

- `ci.yml`: verify, pack and `Package check (linux-x64)` all green. `check_package` reported
  `status: passed`, 33 commands, 12 deployment layouts and `runtimeHost: linux-x64`. That includes the
  runtime Checks executable (smoke, capture, renderer, input, tamper/missing-asset rejections) under
  Xvfb + Mesa llvmpipe. This is the first Linux runtime execution of the package, in an emulated
  container rather than on a desktop.
- `release.yml` for a simulated tag `v0.1.0-alpha.1`: version `0.1.0-alpha.1` was resolved as a
  prerelease, the full build ran, the archive was re-verified and pushed to a dry-run folder feed.
  A malformed tag (`v1.0`) is rejected before any build work.
- `dotnet pack -p:Version=0.1.0` fails with NU5104 (see [Versioning](#versioning-and-the-objectpool-prerelease)).

## What is in place

| File | Purpose |
| --- | --- |
| `.github/workflows/build.yml` | Reusable pipeline: `verify` → `pack` → `package-check` (all Linux) |
| `.github/workflows/ci.yml` | Runs `build.yml` on push to `main`, PRs and manual dispatch (version `0.0.0-ci.<run>`, artifacts only) |
| `.github/workflows/release.yml` | On tag `vX.Y.Z[-pre]`: validate tag, run `build.yml`, re-verify the exact nupkg, push to nuget.org via Trusted Publishing, create a GitHub release with the nupkg attached |
| `.github/actions/ksa-assemblies/` | Checks out the latest default branch of private `meow-sci/ksa-game-assemblies` (`current/dll` only), logs the commit used, checks the DLLs exist and logs their versions, exports `KSA_DLL_DIR` |
| `scripts/check_managed_inputs.py` | Fails fast if a BRUTAL DLL is missing; prints versions (no hash pin) |
| `scripts/act_local.sh` | Runs `ci.yml` / `release.yml` locally with act |
| `global.json` | Pins the .NET 10 SDK band for CI and local builds |

Pipeline jobs:

- **verify** (no proprietary inputs, also runs for fork PRs): `scripts.verify` (frozen sources, licenses,
  native image hashes/exports) and `checks/test_producer.py`.
- **pack**: compiles against the licensed BRUTAL DLLs, packs with `scripts.publish_local` into a folder
  feed (archive inspection before "push"), runs the archive regression tests against the real nupkg
  (`XBRUTAL_TEST_PACKAGE`), uploads artifact `nupkg`.
- **package-check**: runs `scripts.check_package` with fresh NuGet caches, direct and
  true-transitive consumers, and portable publishes plus explicit-RID publishes for **all three**
  RIDs. It inspects the selected native names/hashes/dependencies, then runs the runtime Checks
  executable on linux-x64 under Xvfb + Mesa llvmpipe (smoke, capture, renderer, input,
  tamper/missing-asset rejections).

No Windows or macOS runners are used. The native ImGui images are prebuilt (zig cross-compiled,
hash-pinned in `native/manifest.json`) and the managed library is a single portable AnyCPU assembly,
so build and pack are platform-independent. Executing the package on real Windows/macOS desktops
stays a manual qualification step (as before: `ImGuiPlayground/VALIDATE_PLATFORMS.md`). If you ever
want automated runtime coverage there, you could add a `macos-latest` job and a `windows-latest` job
(with Mesa llvmpipe for OpenGL) that run the same `check_package` command. It is not required to publish.

Other changes: `NuGet.Config` now has package source mapping, so the optional `%HOME%/nuget-feed`
source only matters when restoring `XBrutal.ImGuiStandalone` itself. Previously, restore failed with
NU1301 on any machine without that folder, including CI runners. Also: package metadata (copyright, project/repository URLs, tags, SourceLink repository
info), `ContinuousIntegrationBuild` on GitHub Actions, csproj default version `0.0.0-dev` (real
versions always come from `-p:Version`), archive tests no longer hard-code `~/nuget-feed`, pack/push
failures print their logs, README consumer section points at nuget.org.

## Manual steps for you

### 1. Secret: `KSA_GAME_ASSEMBLIES_PAT` (required for pack/package-check)

Same pattern as gatOS/purrtty. If your existing token's repository access already includes
`meow-sci/ksa-game-assemblies`, you can reuse its value.

1. GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token.
2. Resource owner: **meow-sci**. Repository access: **Only select repositories →
   `meow-sci/ksa-game-assemblies`**. Permissions: **Contents: Read-only** (Metadata read-only is implicit).
   If meow-sci requires approval for fine-grained tokens, approve it in the org settings.
3. `meow-sci/brutal-imgui-standalone` → Settings → Secrets and variables → Actions → New repository
   secret: name `KSA_GAME_ASSEMBLIES_PAT`, value = the token.
   Or: `gh secret set KSA_GAME_ASSEMBLIES_PAT -R meow-sci/brutal-imgui-standalone`
4. Note the expiry date; CI fails with "KSA_GAME_ASSEMBLIES_PAT is not configured" or a checkout auth
   error when it lapses.

### 2. nuget.org Trusted Publishing (no long-lived API key)

1. Sign in to nuget.org with the account (or organization) that should own the package.
2. Username menu → **Trusted Publishing** → **Create policy** (GitHub Actions):
   - Repository owner: `meow-sci`
   - Repository: `brutal-imgui-standalone`
   - Workflow file: `release.yml` (file name only)
   - Environment: `nuget-org` (must match the workflow; or leave blank to allow any)
   - Policy owner: your user or the organization that will own `XBrutal.ImGuiStandalone`
3. Repository secret `NUGET_USER` = your nuget.org **profile username** (not your email address):
   `gh secret set NUGET_USER -R meow-sci/brutal-imgui-standalone`
4. Optional but recommended: request an **ID prefix reservation** for `XBrutal.` (email
   account@nuget.org from the owning account) so the package shows as verified and nobody else can
   publish `XBrutal.*` IDs.

### 3. GitHub environment `nuget-org` (optional hardening)

GitHub creates the environment automatically on the first release run. To protect it beforehand:
Settings → Environments → New environment `nuget-org` → add yourself as a required reviewer and
restrict deployment refs to tags matching `v*`. Each publish then waits for your approval after the
build has passed.

### 4. First CI run on GitHub

1. Commit and push these changes to `main` (or open a PR from a branch in this repo).
2. Watch **Actions → CI**. All three jobs should match the local act run. If `Package check` fails,
   the uploaded `package-check` artifact has every command log and `results.json`.

### 5. First release

Packing a stable version currently fails on purpose (see [Versioning](#versioning-and-the-objectpool-prerelease)),
so the first public release must be a prerelease:

```sh
git checkout main && git pull
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1
```

The tag must be on `main`. Watch **Actions → Release**; approve the `nuget-org` deployment if you added
reviewers. After nuget.org finishes validation and indexing (usually minutes, up to an hour), the
package appears at <https://www.nuget.org/packages/XBrutal.ImGuiStandalone>. nuget.org versions are
immutable: if a release fails *after* the push, fix forward with a new tag. You can only unlist a
version, not replace it.

### 6. Switch ImGuiPlayground to nuget.org

Once a version is published, in `purrtty/ImGuiPlayground`:

- `ImGuiPlayground.csproj`: `<PackageReference Include="XBrutal.ImGuiStandalone" Version="[0.1.0-alpha.1]" />`
- `NuGet.Config`: remove the `local-standalone` source and its `packageSourceMapping` entry (or keep it
  for local iteration on `-local.N` builds).
- Update the `0.1.0-local.4` references in its README/VALIDATE_PLATFORMS.md.

The library repo's own `NuGet.Config` still lists `%HOME%/nuget-feed` for the `checks/` project's local
dev loop. CI does not use it for the library, and `check_package` writes its own isolated config.

## Versioning and the ObjectPool prerelease

`Microsoft.Extensions.ObjectPool 11.0.0-rc.1.26425.128` is not an accident. The proprietary
`Brutal.Core.Strings` and `Brutal.Core.Logging` assemblies (game build 2026.10.10.5554) were compiled
against **assembly version 11.0.0.0** of ObjectPool. The current GA package (10.0.x) ships assembly
version 10.0.0.0. .NET will not bind a reference to a *lower* assembly version, so consumers would
get a `FileLoadException` when the BRUTAL string code loads. No GA package provides 11.0.0.0 yet;
ObjectPool 11.0.0 GA is expected with .NET 11 (November 2026). `Microsoft.Extensions.Logging 10.0.0`
(GA) matches what `Brutal.Core.Logging` references.

Consequences:

- NuGet warns (NU5104) when a stable package depends on a prerelease. With `TreatWarningsAsErrors`
  this fails the pack, so `v0.1.0` cannot be released yet. That guard is intentional; keep using
  `-alpha.N` / `-beta.N` tags.
- When ObjectPool 11.0.0 GA ships: bump the `PackageReference` in the csproj, the expected
  dependency map in `scripts/verify.py` (`verify_package`), and `THIRD-PARTY-NOTICES.md`; run CI;
  then stable tags work.
- If you'd rather ship a stable version before that, add `<NoWarn>$(NoWarn);NU5104</NoWarn>` to the
  csproj. Not recommended.

Release checklist for later versions: bump nothing in the csproj (the version comes from the tag),
ensure CI is green on `main`, tag `vX.Y.Z[-pre]`, push the tag.

## When the game updates

CI always builds against the **latest `main`** of `ksa-game-assemblies` (`current/dll`), and runs daily
(`schedule:` in `ci.yml`) as well as on pushes/PRs, so breakage is noticed soon after the game moves.
The game re-signs code-identical `Brutal.*` assemblies every few days; the library does **not** pin their
hashes or MVIDs, so such a rebuild passes. Only a real ABI change fails.

- `ManagedCompatibility.cs` rejects a build if any `imgui` P/Invoke in `Brutal.ImGui` is not exported by our
  native image, or if the size/field offsets of the Brutal types we touch differ from its pinned table.
  The failure is `Incompatible loaded managed ABI input '<import or type>'` from the runtime checks in the
  package-check step. The job summary records which `ksa-game-assemblies` commit was used.
- To catch up: requalify the native/CLR layouts and imports against the new assemblies (rebuild the native
  image if it must export new functions), update the pinned table in `ManagedCompatibility.cs` and the
  "last verified build" in `docs/COMPATIBILITY.md`, get CI green, and release a new version.
- Releases also build against whatever `main` is at tag time, so a release can only go out while the
  library matches the current game.

## Running the workflows locally with act

Requires Docker. Point the helper at a local clone of `ksa-game-assemblies` (`git pull` it first so it
matches CI's latest `main`); it is mounted read-only in place of the private-repo checkout:

```sh
export KSA_GAME_ASSEMBLIES_ROOT=~/repos/meow-sci/ksa-game-assemblies
scripts/act_local.sh ci                         # verify + pack + linux-x64 package check
scripts/act_local.sh release v0.1.0-alpha.1     # release dry run for a simulated tag push
scripts/act_local.sh ci -j pack                 # extra args go to act
```

Outputs (uploaded artifacts) land in `artifacts/act/`. Under act, the release workflow replaces the
nuget.org login/push and the GitHub release with a push to a temporary local folder feed (`env.ACT`).

Things the helper handles, verified on this Apple Silicon Mac with act 0.2.89:

- Containers run `linux/amd64` because `check_package` needs a linux-x64 process (Docker emulation
  is slower but works, including the runtime checks under Xvfb/llvmpipe).
- It builds a single-arch `local/act-ubuntu:amd64` image from `catthehacker/ubuntu:act-latest`.
  With the multi-arch tag, act rebuilds `PATH` from the arm64 image metadata after `setup-dotnet`
  and later node actions fail with `exec: "node": executable file not found`.
- `actions/upload-artifact` / `download-artifact` are pinned to `v5` in the workflows because
  act's artifact server rejects newer majors (`unknown field "mime_type"`, `Error unauthorized`).

To exercise the real private-repo checkout instead of the mount, run act directly without
`--container-options`/`--env KSA_ASSEMBLIES_LOCAL=...` and add
`-s KSA_GAME_ASSEMBLIES_PAT="$(gh auth token)"`.

### What act could not test

- The real private-repo checkout with `KSA_GAME_ASSEMBLIES_PAT` (the local mount stands in; see above
  to test it too).
- `environment:` protection and `permissions:` are ignored by act.
- OIDC (`NuGet/login`), the real `dotnet nuget push` to nuget.org and `gh release create`: replaced by
  the local dry run.

## Other things worth deciding

- **Repo hygiene before announcing:** `docs/IMPLEMENTATION_PLAN.md` contains local machine paths
  (`/Users/asherwin/...`, `/tmp/...`) and internal agent/model notes. It is not packed, but the repo
  is public. Consider trimming or removing it.
- **Package icon:** none set. Add a 128×128 PNG, `<PackageIcon>icon.png</PackageIcon>`, pack it, and
  add `icon.png` to the allowlist in `scripts/verify.py` `verify_package`. The allowlist is exact,
  so any new packed file needs an entry there.
- **Symbols:** no PDB or `.snupkg` is shipped (`IncludeSymbols=false`). SourceLink repository metadata
  is now stamped. Publishing a `.snupkg` would need the verifier allowlist and release push updated.
- **Naming/trademarks:** the package name and description reference BRUTAL/KSA. Confirm you are
  comfortable with that on a public registry. Nothing proprietary ships: `scripts/verify.py` rejects
  any `Brutal.*` payload or dependency in the archive.
- **Dependabot** for `github-actions` only (the NuGet dependencies are pinned on purpose) would keep
  action versions current.
