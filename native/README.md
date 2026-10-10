# Frozen production native maintenance

This is the exact approved eight-translation-unit production source closure: five patched Dear ImGui TUs, generated wrappers, owned manual bridges and accessors. Relative manual/../api includes and all captured source bytes are preserved. `frozen-inputs.json` binds copied source/evidence/resource files; `provenance/` preserves original source record, six declaration patches and production compile/link/ownership/export receipts. Historical records retain original paths as frozen evidence; they are not active recipes or package metadata.

```sh
python3 -m scripts.verify
python3 -m scripts.rebuild_native --rid osx-arm64 --out artifacts/rebuild-osx-new
python3 -m scripts.rebuild_native --rid linux-x64 --out artifacts/rebuild-linux-new
python3 -m scripts.rebuild_native --rid win-x64 --out artifacts/rebuild-win-new
```

Use recorded Zig **0.17.0**. macOS requires a selected SDK (`--sdk`, otherwise xcrun); each TU force-includes the original config. Required flags/targets are recorded in `manifest.json`, including `-fno-strict-aliasing`, WCHAR32 and a single imgui.cpp owner. No fixture TU/include machinery is needed. Output must be fresh scratch outside protected source/pins. Rebuild records exact commands/logs, checks architecture/dependencies/complete dynamic exports and kinds, and records its hash separately. A relocated rebuild is **new evidence**, not assumed byte-identical reproduction or permission to replace approved pins. .NET restore/build/pack never compiles native code.

Production has exactly 1,175 **API** exports: 1,172 executable functions and three aligned, nonoverlapping writable eight-byte callback slots. macOS additionally has exactly two writable non-code same-address linker bookkeeping exports, `__dso_handle` and `_mh_dylib_header` (1,177 raw names). Those names alone are classified separately; every other extra/missing/fixture export is rejected. The section inspector is derived from the source baseline's bounded manual binary inspector; dynamic inventory uses Mach-O export trie, ELF dynsym and PE export directory rather than just a filtered name list.

## Historical qualification boundary

Full generation/full-fixture qualification is archived in the read-only purrtty baseline `5d71c50943c13310d02066eb56b6fd4abc914790`, bundle `sol-delivery-20261008T144358Z-33442-combined-final3`, independent qualification bundle SHA-256 `b0c089d45a6aeac64e8affa9ddbc2fb48675ec1c00d23e805f346be98cd5fd39`. Old source.lock lists an obsolete prototype adapter and is **historical evidence only**, not this production build recipe. We deliberately do not relocate anchored generator/fixture harnesses, whole scratch trees, compiler caches, proprietary metadata snapshots, or game binaries. Future ABI regeneration/full fixture requalification is an explicit separate maintenance task.

Current library checks cover renderer/input/PNG/lifecycle/package loading and representative production helpers/bridges. They are not a replacement for exhaustive historical fixture qualification. Foreign-RID static checks/cross-publish do not certify foreign runtime execution, desktop interaction or oldest-OS behavior.

The exact promoted native images retain historical build/source-path strings. These are embedded provenance, not runtime path dependencies. They are intentionally not stripped or repinned. New managed builds map source/PDB paths to a neutral root; nuspec, targets and public package documentation must not depend on private machine paths.
