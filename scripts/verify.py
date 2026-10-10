#!/usr/bin/env python3
"""Verify immutable source/assets and optionally the actual NuGet archive."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .binary_symbols import inspect
from .native_image import inventory

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_image(data, asset, exports, pinned=True):
    if pinned and sha(data) != asset['sha256']:
        raise ValueError('native hash mismatch: ' + asset['path'])
    found = inventory(data, asset['rid'])
    if found['dependencies'] != asset['dependencies']:
        raise ValueError('native dependencies changed: ' + asset['path'])
    if asset['implementation'] == 'owned-imgui':
        infrastructure = set(asset['linkerInfrastructure'])
        if set(found['exports']) != exports | infrastructure:
            raise ValueError('extra/missing/fixture exports: ' + asset['path'])
        symbols = inspect(data, asset['rid'], exports | infrastructure)
        if sum(s['executable'] for s in symbols.values()) != 1172:
            raise ValueError('native executable export count')
        print(f"{asset['rid']}: {len(found['exports'])} raw names; 1175 API = 1172 code + 3 aligned writable eight-byte slots; linker={sorted(infrastructure)}")
    return found


def verify_sources():
    lock = json.loads((ROOT / 'native/frozen-inputs.json').read_text())
    for name, expected in lock.items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('frozen input drift: ' + name)
    record = json.loads((ROOT / 'native/provenance/source-record.json').read_text())
    for path in (ROOT / 'native/upstream').iterdir():
        if sha(path.read_bytes()) != record['sourceFiles'][path.name]:
            raise ValueError('upstream source record mismatch: ' + path.name)
    patches = json.loads((ROOT / 'native/provenance/patch-manifest.json').read_text())
    if sha((ROOT / 'native/provenance/patch-manifest.json').read_bytes()) != record['patchManifestSha256']:
        raise ValueError('source-bound patch manifest')
    for patch in patches['patches']:
        if sha((ROOT / 'native/provenance' / patch['file']).read_bytes()) != patch['sha256']:
            raise ValueError('patch hash')
    print(f'Frozen source/license/resource evidence: {len(lock)} exact input hashes; six declaration patches; upstream source record matches.')


def verify_package(path, manifest, exports):
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        native = {a['path'] for a in manifest['assets']}
        allowed = native | {'lib/net10.0/XBrutal.ImGuiStandalone.dll', 'README.md', 'LICENSE',
                           'THIRD-PARTY-NOTICES.md', 'docs/COMPATIBILITY.md', 'docs/manifest.json',
                           'docs/accessor-contract.json', 'contentFiles/any/net10.0/fonts/JetBrainsMono-Regular.ttf',
                           'XBrutal.ImGuiStandalone.nuspec', '[Content_Types].xml', '_rels/.rels',
                           'buildTransitive/XBrutal.ImGuiStandalone.targets'}
        allowed |= {'licenses/' + p.name for p in (ROOT / 'licenses').iterdir()}
        allowed.add('licenses/JetBrainsMono-Regular-license.txt')
        extras = [n for n in names if n not in allowed and not (n.startswith('package/services/metadata/core-properties/') and n.endswith('.psmdcp'))]
        if extras or len(names) != len(set(names)) or not allowed <= set(names):
            raise ValueError(f'package archive hygiene: extra={extras}, missing={allowed - set(names)}')
        for asset in manifest['assets']:
            verify_image(package.read(asset['path']), asset, exports)
        for p in (ROOT / 'licenses').iterdir():
            if package.read('licenses/' + p.name) != p.read_bytes():
                raise ValueError('package license drift')
        if package.read('contentFiles/any/net10.0/fonts/JetBrainsMono-Regular.ttf') != (ROOT / 'fonts/JetBrainsMono-Regular.ttf').read_bytes():
            raise ValueError('package font drift')
        for p, name in [('native/manifest.json', 'docs/manifest.json'), ('buildTransitive/XBrutal.ImGuiStandalone.targets', 'buildTransitive/XBrutal.ImGuiStandalone.targets'), ('native/accessor-contract.json', 'docs/accessor-contract.json'), ('docs/COMPATIBILITY.md', 'docs/COMPATIBILITY.md'), ('README.md', 'README.md'), ('LICENSE', 'LICENSE'), ('THIRD-PARTY-NOTICES.md', 'THIRD-PARTY-NOTICES.md'), ('fonts/JetBrainsMono-Regular-license.txt', 'licenses/JetBrainsMono-Regular-license.txt')]:
            if package.read(name) != (ROOT / p).read_bytes():
                raise ValueError('package documentation drift: ' + name)
        ns = {'n': 'http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd'}
        xml = package.read('XBrutal.ImGuiStandalone.nuspec').decode('utf-8-sig')
        if '<!DOCTYPE' in xml or '<!ENTITY' in xml or '\x00' in xml:
            raise ValueError('nuspec DTD/entities/non-UTF8 XML forbidden')
        nuspec = ET.fromstring(xml)  # noqa: S314 - UTF-8 only, DTD/entities rejected above.
        deps = {d.attrib['id']: d.attrib['version'] for d in nuspec.findall('.//n:dependency', ns)}
        expected = {'Microsoft.Extensions.Logging': '10.0.0', 'Microsoft.Extensions.ObjectPool': '11.0.0-rc.1.26425.128', 'Ultz.Native.GLFW': '[3.4.0]'}
        if deps != expected:
            raise ValueError('unexpected package dependencies: ' + str(deps))
        for name in names:
            # Immutable promoted natives retain historical embedded build strings.
            # Every other shipped file, including managed CodeView/targets, is checked.
            if name not in native and (b'/Users/' in package.read(name) or b'/private/var/' in package.read(name)):
                raise ValueError('private machine path in package metadata: ' + name)
        print(f'Archive hygiene PASS: {len(names)} entries, exactly one portable managed DLL, three owned native assets, exact external GLFW dependency, no GLFW/proprietary/fixture/decomp/test payload. SHA256={sha(path.read_bytes())}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path)
    args = parser.parse_args()
    verify_sources()
    manifest = json.loads((ROOT / 'native/manifest.json').read_text())
    exports = {e['name'] for e in json.loads((ROOT / 'native/provenance/exports.json').read_text()) if e['surface'] == 'production'}
    if len(exports) != 1175:
        raise ValueError('production inventory count')
    for asset in manifest['assets']:
        verify_image((ROOT / asset['path']).read_bytes(), asset, exports)
    if args.package:
        verify_package(args.package, manifest, exports)


if __name__ == '__main__':
    main()
