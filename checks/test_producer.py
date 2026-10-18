"""Source-named negative regression checks for the bounded producer verifiers."""
import contextlib
import io
import json
import os
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.binary_symbols import inspect
from scripts.verify import ROOT, verify_image, verify_package, verify_sources


class NativeExportKindChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'native/manifest.json').read_text())
        cls.exports = {e['name'] for e in json.loads((ROOT / 'native/provenance/exports.json').read_text()) if e['surface'] == 'production'}

    def test_frozen_source_bytes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            verify_sources()

    def test_complete_dynamic_inventory_and_kinds_for_each_rid(self):
        for asset in self.manifest['assets']:
            with self.subTest(rid=asset['rid']), contextlib.redirect_stdout(io.StringIO()):
                found = verify_image((ROOT / asset['path']).read_bytes(), asset, self.exports)
                self.assertEqual(len(found['exports']), asset['rawExports'])
                self.assertEqual(set(found['exports']) - self.exports, set(asset['linkerInfrastructure']))

    def test_readonly_non_executable_function_sections_rejected_each_rid(self):
        for asset in self.manifest['assets']:
            data = bytearray((ROOT / asset['path']).read_bytes())
            rid = asset['rid']
            if rid == 'osx-arm64':
                offset = 32
                for _ in range(struct.unpack_from('<I', data, 16)[0]):
                    command, size = struct.unpack_from('<II', data, offset)
                    if command == 0x19 and bytes(data[offset + 8:offset + 24]).rstrip(b'\0') == b'__TEXT':
                        flags = struct.unpack_from('<I', data, offset + 60)[0]
                        struct.pack_into('<I', data, offset + 60, flags & ~4)
                    offset += size
            elif rid == 'linux-x64':
                shoff = struct.unpack_from('<Q', data, 40)[0]
                stride, count = struct.unpack_from('<HH', data, 58)
                for i in range(count):
                    offset = shoff + i * stride
                    flags = struct.unpack_from('<Q', data, offset + 8)[0]
                    struct.pack_into('<Q', data, offset + 8, flags & ~4)
            else:
                pe = struct.unpack_from('<I', data, 0x3c)[0]
                count = struct.unpack_from('<H', data, pe + 6)[0]
                opt_size = struct.unpack_from('<H', data, pe + 20)[0]
                for i in range(count):
                    offset = pe + 24 + opt_size + i * 40 + 36
                    flags = struct.unpack_from('<I', data, offset)[0]
                    struct.pack_into('<I', data, offset, flags & ~0x20000000)
            with self.subTest(rid=rid), self.assertRaisesRegex(ValueError, 'executable function'):
                inspect(data, rid, self.exports | set(asset['linkerInfrastructure']))

    def test_elf_slot_size_type_alignment_overlap_and_writability_rejected(self):
        asset = next(a for a in self.manifest['assets'] if a['rid'] == 'linux-x64')
        source = (ROOT / asset['path']).read_bytes()
        shoff = struct.unpack_from('<Q', source, 40)[0]
        stride, count = struct.unpack_from('<HH', source, 58)
        sections = [struct.unpack_from('<IIQQQQIIQQ', source, shoff + i * stride) for i in range(count)]
        slots = []
        for section in sections:
            if section[1] != 11:
                continue
            strings = sections[section[6]][4]
            for offset in range(section[4], section[4] + section[5], section[9]):
                name, _, _, index, address, _ = struct.unpack_from('<IBBHQQ', source, offset)
                label = source[strings + name:source.index(b'\0', strings + name)].decode()
                if label.startswith('Platform_'):
                    slots.append((offset, index, address))
        self.assertEqual(len(slots), 3)
        offset, index, address = slots[0]
        for mutation in ['size', 'type', 'alignment', 'overlap', 'readonly']:
            data = bytearray(source)
            if mutation == 'size':
                struct.pack_into('<Q', data, offset + 16, 16)
            elif mutation == 'type':
                data[offset + 4] = (data[offset + 4] & 0xf0) | 2
            elif mutation == 'alignment':
                struct.pack_into('<Q', data, offset + 8, address + 1)
            elif mutation == 'overlap':
                struct.pack_into('<Q', data, offset + 8, slots[1][2])
            else:
                struct.pack_into('<Q', data, shoff + index * stride + 8, sections[index][2] & ~1)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                inspect(data, 'linux-x64', self.exports)

    def test_extra_or_missing_production_export_rejected(self):
        asset = next(a for a in self.manifest['assets'] if a['rid'] == 'linux-x64')
        data = (ROOT / asset['path']).read_bytes().replace(b'GetVersion\0', b'SetVersion\0')
        with self.assertRaisesRegex(ValueError, 'extra/missing/fixture exports'):
            verify_image(data, asset, self.exports, pinned=False)

    def test_native_byte_pin_tamper_rejected(self):
        asset = self.manifest['assets'][0]
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify_image((ROOT / asset['path']).read_bytes() + b'\0', asset, self.exports)


class PackageArchiveHygieneChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'native/manifest.json').read_text())
        cls.exports = {e['name'] for e in json.loads((ROOT / 'native/provenance/exports.json').read_text()) if e['surface'] == 'production'}
        # Archive checks inspect an actual packed nupkg (CI sets this after `dotnet pack`).
        package = os.environ.get('XBRUTAL_TEST_PACKAGE')
        if not package:
            raise unittest.SkipTest('set XBRUTAL_TEST_PACKAGE to a packed XBrutal.ImGuiStandalone .nupkg')
        cls.package = Path(package)

    def reject_archive(self, added=None, removed=None, changed=None, diagnostic='archive hygiene'):
        with tempfile.TemporaryDirectory(prefix='xbrutal-archive-check-') as temporary:
            path = Path(temporary) / 'negative.nupkg'
            with zipfile.ZipFile(self.package) as original, zipfile.ZipFile(path, 'w') as modified:
                for entry in original.namelist():
                    if entry != removed:
                        modified.writestr(entry, changed[1] if changed and entry == changed[0] else original.read(entry))
                if added:
                    modified.writestr(added, b'owned synthetic negative marker, not proprietary bytes')
            with self.assertRaisesRegex(ValueError, diagnostic), contextlib.redirect_stdout(io.StringIO()):
                verify_package(path, self.manifest, self.exports)

    def test_licensed_immutable_archive_passes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            verify_package(self.package, self.manifest, self.exports)

    def test_forbidden_glfw_proprietary_fixture_and_test_payload_rejected(self):
        for forbidden in ['runtimes/osx-arm64/native/libglfw.dylib', 'lib/net10.0/Brutal.ImGui.dll', 'runtimes/osx-arm64/native/libfixture.dylib', 'checks/Program.cs']:
            with self.subTest(path=forbidden):
                self.reject_archive(added=forbidden)

    def test_missing_automatic_font_rejected(self):
        self.reject_archive(removed='contentFiles/any/net10.0/fonts/JetBrainsMono-Regular.ttf')

    def test_changed_license_rejected(self):
        self.reject_archive(changed=('licenses/LICENSE.imgui.txt', b'changed notice'), diagnostic='license drift')

    def test_proprietary_dependency_rejected(self):
        with zipfile.ZipFile(self.package) as archive:
            data = archive.read('XBrutal.ImGuiStandalone.nuspec').replace(b'<dependencies>', b'<dependencies><dependency id="Brutal.ImGui" version="1.0"/>')
        self.reject_archive(changed=('XBrutal.ImGuiStandalone.nuspec', data), diagnostic='unexpected package dependencies')

    def test_nuspec_entity_declaration_rejected(self):
        with zipfile.ZipFile(self.package) as archive:
            data = archive.read('XBrutal.ImGuiStandalone.nuspec').decode('utf-8-sig')
        data = data.replace('<package ', '<!DOCTYPE package [<!ENTITY x "unsafe">]><package ', 1).encode()
        self.reject_archive(changed=('XBrutal.ImGuiStandalone.nuspec', data), diagnostic='DTD/entities')


if __name__ == '__main__':
    unittest.main()
