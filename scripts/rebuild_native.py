"""Explicit frozen-production rebuild. Never runs during dotnet build/pack."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .verify import ROOT, sha, verify_image, verify_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rid', required=True, choices=['osx-arm64', 'linux-x64', 'win-x64'])
    parser.add_argument('--out', required=True, type=Path, help='New scratch directory; never a promoted runtime/source directory')
    parser.add_argument('--zig', default='zig')
    parser.add_argument('--sdk', type=Path, help='macOS SDK (otherwise xcrun --show-sdk-path)')
    args = parser.parse_args()
    verify_sources()
    out = args.out.resolve()
    for protected in [ROOT / 'native', ROOT / 'runtimes', ROOT / 'src', ROOT / 'buildTransitive']:
        if out == protected or protected in out.parents or out in protected.parents:
            raise ValueError('rebuild output overlaps protected source/pins')
    if out.exists():
        raise ValueError('use a new output directory; rebuild never overwrites pins or prior evidence')
    zig = shutil.which(args.zig)
    if not zig or subprocess.check_output([zig, 'version'], text=True).strip() != '0.17.0':
        raise ValueError('recorded Zig 0.17.0 required')
    manifest = json.loads((ROOT / 'native/manifest.json').read_text())
    flags = manifest['compileFlags'] + ['-target', manifest['targets'][args.rid]]
    native = ROOT / 'native'
    for include in ['upstream', 'api', 'accessors', 'generated']:
        flags += ['-I', str(native / include)]
    flags += ['-include', str(native / 'include/playground_imgui_config.h')]
    if args.rid == 'osx-arm64':
        sdk = args.sdk or Path(subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip())
        if not sdk.is_dir():
            raise ValueError('macOS SDK missing')
        flags += ['-isysroot', str(sdk), '-mmacosx-version-min=11.0']
        link = ['-dynamiclib', '-Wl,-install_name,@rpath/libimgui.dylib']
    elif args.rid == 'linux-x64':
        link = ['-shared', '-Wl,--no-undefined', '-Wl,-soname,libimgui.so']
    else:
        flags += ['-DPLAYGROUND_IMGUI_WINDOWS=1']
        link = ['-shared']
    sources = [native / 'upstream' / n for n in ['imgui.cpp', 'imgui_draw.cpp', 'imgui_tables.cpp', 'imgui_widgets.cpp', 'imgui_demo.cpp']]
    sources += [native / 'generated/wrappers.cpp', native / 'manual/manual.cpp', native / 'accessors/accessors.cpp']
    out.mkdir(parents=True)
    commands = []

    def run(command):
        index = len(commands)
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        (out / f'{index}.log').write_text(result.stdout + result.stderr)
        commands.append({'command': command, 'exitCode': result.returncode})
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        result.check_returncode()

    objects = []
    for index, source in enumerate(sources):
        obj = out / f'{index}.o'
        run([zig, 'c++', *flags, '-c', str(source), '-o', str(obj)])
        objects.append(str(obj))
    asset = next(a for a in manifest['assets'] if a['rid'] == args.rid)
    image = out / Path(asset['path']).name
    run([zig, 'c++', *flags, *link, *objects, '-o', str(image)])
    exports = {e['name'] for e in json.loads((native / 'provenance/exports.json').read_text()) if e['surface'] == 'production'}
    observed = verify_image(image.read_bytes(), asset, exports, pinned=False)
    observed.update(sha256=sha(image.read_bytes()), promotedSha256=asset['sha256'], byteIdentical=sha(image.read_bytes()) == asset['sha256'], sourceLockSha256=sha((native / 'frozen-inputs.json').read_bytes()), zig=zig)
    (out / 'result.json').write_text(json.dumps(observed, indent=2) + '\n')
    print(f'Relocated rebuild PASS: {image}; byteIdentical={observed["byteIdentical"]}. Promoted pins were not changed; runtime execution is separate evidence.')


if __name__ == '__main__':
    main()
