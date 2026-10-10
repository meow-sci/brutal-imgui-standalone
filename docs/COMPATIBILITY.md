# Compatibility and safety boundary

Qualified loaded ABI contributors (SHA-256 and loaded module MVID are checked **before** assertion-capable native calls):

| Assembly | SHA-256 | MVID |
| --- | --- | --- |
| Brutal.ImGui | b76777a4ef3399d6353b9dba1982e3afb84b5da2aa2500da1c062db0bfad827c | be72af36-f552-460e-ab1c-cc0018ebd574 |
| Brutal.Core.Common | 4cbae1473d6a3759345f1eec8e62e6c7da1e19f8d10db8d13c005203ec590de4 | d0a4e4ad-480c-4cc8-a9bf-687b26cb8963 |
| Brutal.Core.Numerics | a217a6098116a1895e965b3a1d4fdee931e59a7a55f326c7d710b0d7eeccd17a | e4190ee6-8291-49aa-9721-88111e32f2ba |

Files must remain available at the actual loaded assembly locations. In-memory/dynamic/single-file inputs and unqualified BRUTAL builds are rejected. Exact identities are intentional, not a promise that arbitrary future assemblies with the same version/import names work. To add a compatible input: explicitly requalify its native/CLR layouts, callbacks, imports and helper domains against source-owned production/native evidence, review the resulting contract, and publish a new immutable version. Do not simply regenerate expected hashes.

Native: Dear ImGui 1.92.2 docking, `IMGUI_USE_WCHAR32`, 16-bit draw indices, little-endian eight-byte pointers; OpenGL 3.2 core/GLSL150. Process architecture (not machine architecture) selects win-x64, linux-x64 or osx-arm64. Intel macOS, ARM Windows/Linux, musl Linux and 32-bit are unsupported. Native target baselines (macOS 11/glibc 2.17/Windows GNU target) are build contracts, **not** oldest-OS runtime certification.

Complete production API export coverage is **not unrestricted raw layout compatibility**. Historical qualification retains 57 classified layout conflicts and 44 unsafe raw aliases, including packed fields, overlapping records, differing CLR 6/7/13-byte strides, Size1/static-member hazards and opaque storage. Do not use managed pointer arithmetic/spans over native records with differing strides, or directly read/write packed aliases. Helpers use actual native member access/indexing with checked representation and closed shape IDs. They do not repair proprietary structures, detect arbitrary stale/wrong pointers, validate live engine domains, or make native OOM safe.

The frozen accessor contract (`docs/accessor-contract.json` in the package, `native/accessor-contract.json` in source) records 47 fields, 12 records, 13 opaque shapes, bounds/domain/lifetime notes and source identity `e86ced3fb638c94c285378697c77e6e723bd75864c337e2b557449b4e4677f72`. Its embedded historical semantic-evidence references are archival, not newly rerun fixture certification. Borrow tokens require explicit invalidation before external mutation/destruction; address extraction is an unsafe lifetime escape. Dispose helpers/scopes on their creating thread. Production APIs never allocate/free an injected library handle.

The host supports keyboard/mouse/Unicode/clipboard and DPI coordinate mapping, not gamepads, OS multiviewport windows, cursor shapes/warping, complete IME or arbitrary game texture handles. Linux invisible capture still requires a graphical session (Xvfb/Mesa can be provided externally; not certified here). Windows/Linux execution and manual desktop interaction must be qualified separately on suitable systems.
