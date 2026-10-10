# XBrutal.ImGuiStandalone

A portable `net10.0`/AnyCPU library hosting the original BRUTAL ImGui UI API with GLFW and OpenGL 3.2 core. Native ImGui is source-owned Dear ImGui 1.92.2 docking, not a game-derived wrapper. Supported process RIDs: **win-x64, linux-x64, osx-arm64**.

## Consumer

Reference an exact local package version. Supply your own licensed BRUTAL managed assembly closure (`Brutal.ImGui`, `Brutal.Glfw`, Common, Numerics, Strings and their normal supporting assemblies) as copy-local file references. These proprietary files are never distributed by this package or injected by its build targets. See [compatibility](docs/COMPATIBILITY.md) for the qualified hashes; matching version numbers alone are insufficient.

```csharp
using Brutal.ImGuiApi;
using XBrutal.ImGuiStandalone;

StandaloneHost.Run(() => {
    ImGui.Begin("Standalone"u8);
    try { ImGui.Text("Direct BRUTAL calls"u8); }
    finally { ImGui.End(); }
});
// Or: StandaloneHost.Capture(DrawUi, 800, 500).SavePng("capture.png");
```

- `Run(Action drawUi, bool smokeTest = false)` synchronously owns a window/context. Smoke mode requires three nonempty frames and exits.
- `Capture(Action drawUi, int width = 800, int height = 500)` draws three frames in an invisible window and returns `CapturedFrame` (`Width`, `Height`, `Rgba`, `SavePng`). Requested size is logical; returned pixels are physical. A desktop/OpenGL driver is still required; this is not a headless backend.
- `CreateNativeFieldAccessors()` creates the existing thread-affine helper on an active callback thread. Dispose before the session ends; invalidate borrowed scopes **before** native structural mutation/destruction. Direct constructor injection remains an advanced caller-owned lifetime API.

Operate synchronously on the OS main thread (enforced on macOS), one owned context/window at a time. Callbacks must balance BRUTAL stacks even when throwing. Exceptions propagate; teardown allows repeated sessions. The host exclusively owns `Brutal.ImGui`'s external DllImport resolver before its first P/Invoke. Do not initialize competing game/UI backends or preload another ImGui/GLFW image. Native handles are retained for process lifetime because external imports/bridges cache addresses. The host does **not** install a competing GLFW resolver.

## Automatic assets

The package contains one managed library and exactly three owned native ImGui images in standard `runtimes/<rid>/native/` layout. GLFW is an **exact transitive `Ultz.Native.GLFW` 3.4.0 dependency**, not an XBrutal binary payload. A minimal `buildTransitive` target derives BRUTAL filename aliases from NuGet-resolved native item metadata; no global cache paths or consumer copy commands are used. JetBrains Mono and its OFL notice are included automatically. Native/font hashes and actual loaded-image identity are checked at startup; stale/missing/tampered assets are rejected rather than falling back to system/game libraries.

Portable builds/publishes keep RID subdirectories; explicit RID publishes flatten matching native assets. Supported foreign-RID output inspection is not foreign-OS execution certification. Trimming, NativeAOT, single-file deployment, multiple backends and arbitrary raw BRUTAL layout access are unsupported.

## Producer development

Use .NET SDK 10 and explicitly select your external inputs; there is no machine-specific fallback:

```sh
export KSA_DLL_DIR=/path/to/your/licensed/managed/dll
# Alternatively: -p:KSAFolder=/path/to/dll (takes precedence).
python3 -m scripts.verify
dotnet build src/XBrutal.ImGuiStandalone -c Release
python3 -m scripts.publish_local --version 0.1.0-local.4 --feed /path/to/local-feed --managed-dir "$KSA_DLL_DIR"
python3 -m scripts.check_package --version 0.1.0-local.4 --feed /path/to/local-feed --managed-dir "$KSA_DLL_DIR" --out artifacts/package-check-new
```

Publication rejects reused ID/version, inspects the archive before push and only supports a local directory feed. Use a new version for changed published bytes. Package checks restore into a fresh isolated cache; no global cache clearing or user-wide NuGet configuration is needed. Automated checks are not shipped; there is no shipped demo. Native compilation is explicit, never part of ordinary restore/build/pack. See the source repository’s `native/README.md` for frozen-source rebuilds and historical evidence boundaries.
