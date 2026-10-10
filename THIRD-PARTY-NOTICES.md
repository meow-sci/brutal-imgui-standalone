# Third-party notices and provenance

- Extracted host/input/renderer/capture/helper and owned native adapter code originate in Alex Sherwin's MIT ImGuiPlayground at purrtty commit `5d71c50943c13310d02066eb56b6fd4abc914790`; original notice is preserved in `licenses/LICENSE.original.txt`. New work is covered by the repository MIT license.
- Dear ImGui 1.92.2 docking is MIT (Omar Cornut); `licenses/LICENSE.imgui.txt` and `native/upstream/LICENSE.txt` preserve its notice. Upstream commit/archive and production configuration/source/patch/binary identities are in `docs/manifest.json` in the package (`native/manifest.json` in source). Promoted images contain owned generated/manual/accessor implementation, not game-derived wrappers.
- GLFW is Zlib licensed; `licenses/LICENSE.glfw.txt` is preserved. Native files are obtained exclusively through the exact external NuGet dependency `Ultz.Native.GLFW` 3.4.0. **No GLFW binaries are vendored or embedded in XBrutal.** Its dependency runtime assets are aliased automatically for the external BRUTAL loader.
- JetBrains Mono Regular is OFL 1.1; its exact font bytes and `licenses/JetBrainsMono-Regular-license.txt` are included. ImGui's file-font loading owns native allocations; no managed buffer is transferred to the native allocator.
- Microsoft.Extensions.Logging 10.0.0 and Microsoft.Extensions.ObjectPool 11.0.0-rc.1.26425.128 are MIT; the .NET notice is in `licenses/LICENSE.dotnet.txt`. ObjectPool's prerelease is intentional for the audited external closure.

Proprietary BRUTAL managed bindings and their supporting closure are supplied independently by licensed consumers. They are not shipped, not NuGet dependencies of this package, and not reconstructed from decompilation. No game-derived native content or native fixture/test images ship.

The approved native images preserve their original embedded historical build/source-path strings; these are not required runtime paths. Removing those strings would change the approved image hashes. Managed builds use a neutral source/PDB path map, and NuGet metadata/targets/public documentation do not depend on private machine paths.
