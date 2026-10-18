"""Pack, inspect, then publish an immutable version to a local folder only."""
import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path

from .verify import ROOT, sha, verify_package, verify_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--feed', required=True, type=Path)
    parser.add_argument('--managed-dir', required=True, type=Path)
    args = parser.parse_args()
    if not args.version or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in args.version):
        raise ValueError('invalid package version')
    feed = args.feed.expanduser().resolve()
    if '://' in str(args.feed) or not args.managed_dir.is_dir():
        raise ValueError('local directory feed and existing external managed directory required')
    expected_name = f'xbrutal.imguistandalone.{args.version}.nupkg'.lower()
    if feed.exists() and any(p.name.lower() == expected_name for p in feed.rglob('*.nupkg')):
        raise ValueError('immutable package ID/version already published; increment version')
    verify_sources()
    out = ROOT / 'artifacts' / ('publish-' + args.version + '-' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    environment = os.environ.copy()
    environment.pop('KSAFolder', None)
    environment['KSA_DLL_DIR'] = str(args.managed_dir.resolve())
    command = ['dotnet', 'pack', str(ROOT / 'src/XBrutal.ImGuiStandalone/XBrutal.ImGuiStandalone.csproj'), '-c', 'Release', '-p:Version=' + args.version, '-p:KSAFolder=' + str(args.managed_dir.resolve()), '-o', str(out), '--nologo', '-v', 'quiet']
    result = subprocess.run(command, env=environment, capture_output=True, text=True, check=False)
    (out / 'pack.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        print(result.stdout + result.stderr)
    result.check_returncode()
    package = out / f'XBrutal.ImGuiStandalone.{args.version}.nupkg'
    manifest = json.loads((ROOT / 'native/manifest.json').read_text())
    exports = {e['name'] for e in json.loads((ROOT / 'native/provenance/exports.json').read_text()) if e['surface'] == 'production'}
    verify_package(package, manifest, exports)
    feed.mkdir(parents=True, exist_ok=True)
    push = subprocess.run(['dotnet', 'nuget', 'push', str(package), '--source', str(feed)], env=environment, capture_output=True, text=True, check=False)
    (out / 'push.log').write_text(push.stdout + push.stderr)
    if push.returncode:
        print(push.stdout + push.stderr)
    push.check_returncode()
    pushed = next(p for p in feed.rglob('*.nupkg') if p.name.lower() == expected_name)
    if sha(pushed.read_bytes()) != sha(package.read_bytes()):
        raise ValueError('feed bytes differ from inspected archive')
    report = {'package': str(package), 'feedPackage': str(pushed), 'version': args.version, 'sha256': sha(package.read_bytes()), 'archiveInspectedBeforePush': True}
    (out / 'publication.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
