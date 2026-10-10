# XBrutal.ImGuiStandalone extraction plan

Status: implemented and independently validated. Oracle corrections on native maintenance, early package-loading proof, and check ownership were incorporated before implementation. The local package and migrated consumer passed independent review with no P0/P1/P2 findings. Baseline runs used the old game-derived native image; final package/consumer runs use the approved source-owned image. Foreign-OS execution and manual desktop qualification remain unverified as detailed below.

## Goal and agreed boundaries

Publish a real local NuGet package named `XBrutal.ImGuiStandalone`, containing one portable `net10.0` managed assembly and owned native implementations for `win-x64`, `linux-x64`, and `osx-arm64`. Migrate `/Users/asherwin/repos/meow-sci/purrtty/ImGuiPlayground` to consume it from `/Users/asherwin/nuget-feed` while preserving the existing direct BRUTAL UI API, CLI/gallery, rendering, input, capture, and smoke behavior.

User confirmed:
- Proceed from planning through implementation and validation.
- Consumers may supply `Brutal.ImGui`, `Brutal.Glfw`, and their supporting BRUTAL managed assembly closure.
- Promote only the source-owned full production native ImGui builds, not game-derived wrappers or fixture images.
- GLFW must remain the existing `Ultz.Native.GLFW` 3.4.0 NuGet dependency. Do not vendor its binaries in this repository or embed them in this package.
- Automated test projects may live here; no demo application or tests ship in the package.
- No GitHub Packages, GitHub Actions, remote publication, commits, or pushes are part of this task.

Source baseline: purrtty `feature/standalone-imgui-test`, commit `5d71c50943c13310d02066eb56b6fd4abc914790`. Destination baseline: `main`, commit `85e385f2f27d78f31b29df53ae4ab21f32ec24de`.

## Architecture and public contract

- `src/XBrutal.ImGuiStandalone/` owns the extracted host, GLFW input, OpenGL binding/renderer, framebuffer capture/PNG encoding, and supplemental native field accessors. Keep rendering algorithms/ABI behavior unchanged except changes necessary for packaging and clear startup errors.
- Public namespace/assembly/package: `XBrutal.ImGuiStandalone`. Public entry points: `StandaloneHost.Run(Action drawUi, bool smokeTest = false)` and `StandaloneHost.Capture(Action drawUi, int width = 800, int height = 500)`, returning public `CapturedFrame`. Retain reusable accessor types; offer a host-owned accessor factory so ordinary callers need not locate/load another native image.
- A consumer callback still calls `Brutal.ImGuiApi.ImGui` directly. This library is not a replacement C# binding or a game backend. `Program.cs`, `WidgetGallery.cs`, mockups and CLI parsing stay in purrtty.
- Synchronous main-thread operation, one owned context/window at a time, safe repeated sessions, exception propagation, and process-lifetime native handle retention remain explicit constraints. No new native-only/headless API, multiple backends, trimming, NativeAOT, or single-file support is promised.
- Use external file `<Reference>` items with `Private=false` for library builds, selected explicitly by `KSA_DLL_DIR`/`KSAFolder` (optionally a clearly documented canonical property). Never copy managed game files into this repository. Consumer projects continue their own copy-local proprietary references; no automatic proprietary dependency or transitive build target injecting them.
- Retain required open-source managed package dependencies at proven versions. Do not silently downgrade ObjectPool from its required v11 prerelease. Keep `Ultz.Native.GLFW` 3.4.0 as an actual transitive NuGet dependency, as required by the user; its binaries must not be vendored or packed into XBrutal.ImGuiStandalone. Preserve the PoC's tested GLFW package source and BRUTAL-compatible filename aliases. If standard native asset probing does not supply those aliases, use minimal package-owned buildTransitive staging from NuGet-resolved assets (never machine-global paths or consumer-authored copy steps). The app must receive GLFW automatically even when XBrutal.ImGuiStandalone is a transitive reference.

## Native promotion and reproducibility

Promote exactly these source-owned production candidates from:
`/Users/asherwin/repos/meow-sci/purrtty/ImGuiPlayground/.tmp/native/combined/sol-delivery-20261008T144358Z-33442-combined-final3/`

| RID | File | SHA-256 |
| --- | --- | --- |
| osx-arm64 | `osx-arm64/production/libimgui.dylib` | `048ce8fd55b30b86f9ea3c3c4531cf8be78763002a06d0a3e8d784c4e41f9c5a` |
| linux-x64 | `linux-x64/production/libimgui.so` | `ba20d709f69b23928a1b5f7c65f47a8c5cab95e86644e3b86dd667dee16029ab` |
| win-x64 | `win-x64/production/imgui.dll` | `a57ce9a768466f99c2d3e66dd45ce0b6a5a03547aafa49217e92a9a5c2a3da08` |

- `runtimes/<rid>/native/` in this repository/package contains only the owned ImGui binaries. GLFW comes from `Ultz.Native.GLFW` 3.4.0 through NuGet, not these vendored assets. Package ImGui for all three RIDs; never build a RID-specific managed assembly.
- Record upstream Dear ImGui 1.92.2 docking commit/archive hash, WCHAR32/config, six declaration patches, generator/manual/accessor source identities, toolchain/target flags, export inventories, binary hashes and dependencies in a concise machine-readable manifest plus notices.
- Vendor the exact hash-bound production source snapshot under `native/`: five patched upstream translation units and header/license closure, generated wrappers, owned ABI/manual/accessor sources, generated `fields.inc`/`identity.h`, forced configuration, and source/patch/export/build provenance. Preserve source bytes and relative include relationships. Capture generated accessor inputs currently in temporary storage promptly. Do not copy whole `.tmp`, qualification bundles, game snapshots, proprietary decompilation, compiler caches, fixture binaries, or obsolete prototype adapters.
- Provide a focused explicit standalone native rebuild command and source/asset verifier. Eight production translation units use the recorded Zig 0.17.0 flags/target contracts; ordinary .NET build/restore/pack never invokes native compilation. A relocated rebuild is new evidence, not assumed byte-for-byte reproduction, and never silently replaces promoted pins. Do not refresh expected hashes solely to pass tests or advertise untested commands.
- Archive full historical generator/fixture qualification through the recorded purrtty baseline and bundle references. It is not relocated as active tooling or claimed rerun. New library-owned checks cover host/input/PNG/package behavior and production helper/bridge behavior. This bounded maintenance migration preserves shipped runtime functionality; future ABI regeneration/full fixture requalification is an explicit separate task.
- Verify the complete defined production API inventory for each promoted binary: 1,175 API exports, comprising 1,172 executable functions and three aligned, nonoverlapping eight-byte writable pointer slots. The approved macOS image additionally exposes exactly two historical linker bookkeeping names, `__dso_handle` and `_mh_dylib_header`, verified as writable non-code same-address aliases (1,177 raw names); Linux/Windows have 1,175 raw/API names. Preserve the approved image hashes and classify only those two macOS names separately. Reuse the bounded binary section inspector if helpful; reject every other extra/missing export and fixture leakage, not just missing names.

## Native resolution, compatibility and packaged resources

- Use NuGet-native layout and .NET probing, not a consumer manual-copy requirement. No-RID builds retain RID subdirectories; RID publishes select matching assets. Support and test both layouts.
- Startup selects OS plus **process architecture**, rejects unsupported combinations, resolves only the expected package/application native assets, validates the pinned bytes/ABI before unsafe calls, and provides actionable missing/incompatible-asset errors. Never fall back to an arbitrary system/game/Homebrew ImGui.
- Preserve the proven external `Brutal.ImGui` resolver workaround, documenting exclusive resolver ownership. Before migrating the PoC, require a fresh package-only consumer to prove ordinary P/Invoke, all three `Interop.CreateTrampoline`/explicit native-load routes, and GLFW's own loader reach the selected packaged images. Run no-RID build, no-RID publish, and osx-arm64 publish layouts on this host. Inspect actual GLFW path/hash and prove trampoline getter/slot/callback identity with rooted callbacks, neighboring-slot checks and cleanup. Do not install a competing resolver on `Brutal.Glfw`, which already owns one.
- Add an early supported-managed-input guard before assertion-capable native ABI calls. Initially support the audited ImGui/Common/Numerics identities; document the compatibility boundary and update procedure. Runtime checks must examine actual loaded assemblies, not only source files supplied during build. Version equality alone is insufficient.
- Keep JetBrains Mono automatically available without consumer copy tasks. Use standard transitive packaged content or an embedded resource, choosing the least invasive tested option. If memory-loading is chosen, prove allocator ownership/lifetime (native ImGui must not free a managed buffer). Preserve the existing font debug name, size/visuals, dynamic atlas checks and OFL notice.
- Preserve explicit raw-layout limitations (packed aliases, differing managed strides, opaque records). Complete export coverage is not unrestricted safe access to all BRUTAL fields. Preserve additive accessor safety/lifetime semantics.

## Local pack/feed/consumer workflow

1. Add standalone build settings, solution, `.gitignore`, README, compatibility/native notices, and a scoped `NuGet.Config` (no machine-wide feed edits).
2. Use an exact prerelease package version such as `0.1.0-local.1`; increment the version for changed published bytes. Do not overwrite ID/version or clear global NuGet caches.
3. Build and `dotnet pack -c Release` with explicit external managed directory; inspect the actual archive and nuspec before publishing.
4. Create `/Users/asherwin/nuget-feed`; push only this package there with `dotnet nuget push --source /Users/asherwin/nuget-feed`. Ordinary OSS dependencies may still restore from nuget.org.
5. A repeatable local publishing script accepts version/feed/managed-directory parameters, validates asset hashes and rejects reused versions. Do not bake the machine's proprietary assembly directory into shipped metadata.
6. Migrate purrtty's PoC to an exact `PackageReference`, add the local source in its isolated NuGet.Config, remove runtime/renderer/input/accessor implementations and duplicate native/font staging, and update namespace/call sites. Never use a ProjectReference to this repo or linked-source fallback.
7. Keep demo/gallery checks in purrtty. Rehome reusable implementation tests with this library, preserving meaningful renderer, input, lifecycle, capture and supplemental-ABI coverage through a narrowly named friend assembly, not public internals. Adapt flat-path assumptions to package layouts and require true WCHAR32 preservation rather than accepting old WCHAR16 fallback. Remove dead historical qualification CLI modes/current instructions; record archival references explicitly. Keep frozen historical evidence distinct from current checks.

## Execution ownership / lane board

The extraction has a producer contract and a consumer integration contract. Work is serial, with no overlapping writers. The producer is a single coupled packaging seam: native artifacts are already built/frozen and managed code is moved, not independently redesigned; splitting native resolution, project packaging and host extraction would create competing asset/ABI owners.

| Stage | Owner/model | Cwd / write boundary | Gate and durable handoff |
| --- | --- | --- | --- |
| Recon (done) | scout gpt-6.1-sol/xhigh; researcher gpt-6-luna/high | Read-only source and official docs | Saved source map/research |
| Plan review | oracle gpt-6-astra/xhigh | Read-only this plan and cited source | Parent resolves findings before any worker |
| Library producer | worker gpt-6.1-sol/xhigh | Destination repo only; read PoC; local package/feed outputs allowed | Build, nupkg hygiene, local feed package + API/native contract; no PoC edits |
| Consumer integration | worker gpt-6.1-sol/xhigh | purrtty ImGuiPlayground, relevant Checks/docs only; read destination | Exact package migration, CLI/gallery/consumer proof; escalate package defects to producer |
| Independent validation | validation-reviewer gpt-6-luna/max | Read-only product source; temporary checkouts/caches and generated outputs allowed | Compile, run tests/scripts, inspect archive/deps/RID publishes, native macOS smoke/captures; concrete findings |
| Fix/recheck if necessary | Original owning worker; reviewer | Only accepted defects within original boundaries | Bounded targeted repair and rerun affected gates |

No subagent may delegate further. Parent owns scope decisions, accepted findings and final acceptance. No commit/push is required.

## Acceptance gates

- **Package hygiene:** one AnyCPU `lib/net10.0/XBrutal.ImGuiStandalone.dll`; exactly the three owned native ImGui production images; licenses/font included; no GLFW binary payload, proprietary assemblies, decompilation, fixture images or `Brutal.*` NuGet dependency entries. Nuspec must retain `Ultz.Native.GLFW` 3.4.0 dependency; consumer restore/output must prove GLFW originates from that NuGet package.
- **Real package use:** fresh isolated `NUGET_PACKAGES` cache, local-source provenance evidence, no target ProjectReference/linked sources/manual native copy, no warm-cache success masking stale bytes. Consumer supplies real proprietary closure.
- **Packaging matrix:** no-RID build and publish plus framework-dependent publishes for all three supported RIDs. Inspect selected native names/hash/dependencies; same portable library. Missing/tampered assets, unsupported platform and incompatible managed inputs fail clearly.
- **Host lifecycle and rendering:** smoke and capture; repeat runs; callback/empty-frame failure and recovery; main-thread/reentrancy checks; renderer scissor/orientation/reset/large meshes, PNG roundtrip, dynamic font/texture behavior.
- **Input and gallery:** existing keyboard/mouse/Unicode/clipboard/DPI checks and nine gallery captures where applicable; unchanged CLI and direct BRUTAL UI code.
- **Owned native ABI:** verify complete production export/kind inventory and no fixture leakage; exercise dynamic bridge image identity plus representative manual/accessor operations. Preserve existing full-qualification restrictions and distinguish historical evidence from newly rerun gates.
- **Independent review:** exact commands, exit codes, fresh findings and residual risks from requested reviewer. Address concrete in-scope blockers and rerun affected gates.
- **Platform honesty:** actual execution is possible here on macOS ARM64. Windows/Linux cross-publish and static inspection are not runtime certification. Actual foreign-OS interactive/native execution remains explicitly unverified unless suitable existing environments are available and authorized; do not claim it passed.
- Final source/diff hygiene in both repos, no unintended purrTTY mod/game deployment changes, and no GitHub distribution/Actions setup.

## Completed delivery

- Published `XBrutal.ImGuiStandalone` **0.1.0-local.4** to `/Users/asherwin/nuget-feed/XBrutal.ImGuiStandalone.0.1.0-local.4.nupkg`.
- Package SHA-256: `1c2c4a35ba6c3004a6bbb34c1ff7bc7d53946a95b00eb5b880f305222377bd20`. Earlier local.1–local.3 are immutable development iterations; the consumer pins local.4.
- One portable `net10.0` assembly; three owned native ImGui images; no proprietary or GLFW binary payload. GLFW is the exact transitive `[3.4.0]` NuGet dependency. Package-owned transitive targets deliver aliases and the bundled font.
- `ImGuiPlayground` consumes the exact local package, with its duplicated implementation/assets removed. `WidgetGallery.cs` is unchanged. Old generator/full-fixture tools are archived at the recorded baseline revision rather than presented as current commands.
- Independent validation reran 12 Python tests, source/native/archive verification, a zero-warning/error Release solution build, and the 33-command/12-layout fresh-cache direct/true-transitive package matrix. A separate clean consumer snapshot built and passed smoke, capture, default checks, gallery and packaging checks.
- All nine independently regenerated gallery captures were pixel-identical to the pre-migration baseline on this macOS ARM64 host. Windows/Linux were cross-published and statically inspected, not executed.
- Independent review verdict: **OK with notes**, with no actionable P0/P1/P2 findings. Notes retain the explicit foreign-runtime/manual-testing gaps, historical qualification boundary, exact managed ABI restrictions, and inert historical native build-path strings.
- No GitHub Packages/Actions configuration, remote publication, commits or pushes were performed.

Repeatable verification commands are in `README.md`, `native/README.md`, and the consumer READMEs. Independent execution evidence for this delivery is retained under `/tmp/xbrutal-independent-review-f3095df5` and `/tmp/purrtty-independent-review-f3095df5`; these temporary directories are evidence, not build/runtime dependencies.
