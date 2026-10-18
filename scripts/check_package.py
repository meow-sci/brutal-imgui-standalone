"""Fresh-cache direct and true intermediary-package deployment/runtime checks."""
import argparse
import json
import os
import platform
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from .verify import ROOT, sha, verify_image, verify_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--feed', required=True, type=Path)
    parser.add_argument('--managed-dir', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise ValueError('Use a fresh output/cache directory; never clear a shared cache.')
    out.mkdir(parents=True)
    feed = args.feed.resolve()
    manifest = json.loads((ROOT / 'native/manifest.json').read_text())
    exports = {e['name'] for e in json.loads((ROOT / 'native/provenance/exports.json').read_text()) if e['surface'] == 'production'}
    package = next(p for p in feed.rglob('*.nupkg') if p.name.lower() == f'xbrutal.imguistandalone.{args.version}.nupkg'.lower())
    verify_package(package, manifest, exports)
    records = []
    outputs = []
    host = {('Darwin', 'arm64'): 'osx-arm64', ('Linux', 'x86_64'): 'linux-x64', ('Windows', 'AMD64'): 'win-x64'}.get((platform.system(), platform.machine()))
    if host is None:
        raise ValueError('Runtime checks require a supported process host; do not relabel foreign execution.')
    source_checks = ROOT / 'checks/XBrutal.ImGuiStandalone.Checks'
    intermediary_feed = out / 'intermediary-packages'
    intermediary_feed.mkdir()
    config = f'''<configuration><packageSources><clear/><add key="local-xbrutal" value="{escape(str(feed))}"/><add key="test-intermediary" value="{escape(str(intermediary_feed))}"/><add key="nuget.org" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><packageSource key="local-xbrutal"><package pattern="XBrutal.ImGuiStandalone"/></packageSource><packageSource key="test-intermediary"><package pattern="XBrutal.CheckIntermediary"/></packageSource><packageSource key="nuget.org"><package pattern="*"/></packageSource></packageSourceMapping></configuration>'''
    (out / 'NuGet.Config').write_text(config)
    (out / 'Directory.Build.props').write_bytes((ROOT / 'Directory.Build.props').read_bytes())

    def execute(command, cache):
        env = os.environ.copy()
        env['NUGET_PACKAGES'] = str(cache)
        env['KSA_DLL_DIR'] = str(args.managed_dir.resolve())
        env.pop('KSAFolder', None)
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=240, check=False)
        log = out / f'command-{len(records):03}.log'
        log.write_text(result.stdout + result.stderr)
        records.append({'command': command, 'exitCode': result.returncode, 'log': str(log)})
        (out / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
        if result.returncode:
            print(log.read_text())
        result.check_returncode()
        return result.stdout

    def origin(cache):
        selected = cache / 'xbrutal.imguistandalone' / args.version
        metadata = json.loads((selected / '.nupkg.metadata').read_text())
        if Path(metadata['source']).resolve() != feed or sha((selected / package.name.lower()).read_bytes()) != sha(package.read_bytes()):
            raise ValueError('not the exact inspected local-feed package')
        if not (cache / 'ultz.native.glfw/3.4.0/.nupkg.metadata').exists():
            raise ValueError('exact external GLFW package not restored')

    def inspect_output(directory, rid):
        layout = directory / 'runtimes' if rid is None else directory
        selected = []
        library = directory / 'XBrutal.ImGuiStandalone.dll'
        if library.read_bytes() != (out / 'direct-cache/xbrutal.imguistandalone' / args.version / 'lib/net10.0/XBrutal.ImGuiStandalone.dll').read_bytes():
            raise ValueError('RID-specific managed library or changed package bytes')
        for asset in manifest['assets']:
            if rid is not None and rid != asset['rid']:
                continue
            path = layout / asset['rid'] / 'native' / Path(asset['path']).name if rid is None else directory / Path(asset['path']).name
            verify_image(path.read_bytes(), asset, exports)
            selected.append({'path': str(path), 'sha256': sha(path.read_bytes()), 'origin': 'XBrutal.ImGuiStandalone'})
        for asset in manifest['externalGlfw']['assets']:
            if rid is not None and rid != asset['rid']:
                continue
            filename = Path(asset['path']).name
            path = layout / asset['rid'] / 'native' / filename if rid is None else directory / filename
            if sha(path.read_bytes()) != asset['sha256']:
                raise ValueError('NuGet-resolved GLFW alias hash')
            original_name = {'osx-arm64': 'libglfw.3.dylib', 'linux-x64': 'libglfw.so.3', 'win-x64': 'glfw3.dll'}[asset['rid']]
            if path.with_name(original_name).read_bytes() != path.read_bytes():
                raise ValueError('alias differs from resolved original native bytes')
            selected.append({'path': str(path), 'sha256': sha(path.read_bytes()), 'origin': 'Ultz.Native.GLFW/3.4.0'})
        if rid is not None:
            other_names = {Path(a['path']).name for a in manifest['assets'] if a['rid'] != rid}
            if any((directory / name).exists() for name in other_names) or (directory / 'runtimes').exists():
                raise ValueError('foreign ImGui/native directory in RID publish')
        font = directory / 'fonts/JetBrainsMono-Regular.ttf'
        if font.read_bytes() != (ROOT / 'fonts/JetBrainsMono-Regular.ttf').read_bytes():
            raise ValueError('automatic transitive font delivery')
        outputs.append({'directory': str(directory), 'rid': rid, 'managedSha256': sha(library.read_bytes()), 'selected': selected, 'fontSha256': sha(font.read_bytes())})
        (out / 'outputs.json').write_text(json.dumps(outputs, indent=2) + '\n')

    for mode in ['direct', 'indirect']:
        cache = out / (mode + '-cache')
        project_dir = out / mode
        project_dir.mkdir()
        for source in source_checks.glob('*.cs'):
            shutil.copyfile(source, project_dir / source.name)
        project = project_dir / 'XBrutal.ImGuiStandalone.Checks.csproj'
        text = (source_checks / project.name).read_text()
        if mode == 'indirect':
            middle = out / 'intermediary'
            middle.mkdir()
            middle_project = middle / 'XBrutal.CheckIntermediary.csproj'
            middle_project.write_text(f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><Version>0.0.0-test.1</Version></PropertyGroup><ItemGroup><PackageReference Include="XBrutal.ImGuiStandalone" Version="[{args.version}]"/></ItemGroup></Project>')
            (middle / 'Marker.cs').write_text('namespace XBrutal.CheckIntermediary; public sealed class Marker { }\n')
            execute(['dotnet', 'pack', str(middle_project), '-c', 'Release', '-o', str(intermediary_feed), '--nologo', '-v', 'quiet'], out / 'intermediary-cache')
            with zipfile.ZipFile(next(intermediary_feed.glob('*.nupkg'))) as archive:
                if any('glfw' in name.lower() or name.startswith('contentFiles/') for name in archive.namelist()):
                    raise ValueError('package-owned copy items leaked into intermediary package')
            text = text.replace('<PackageReference Include="XBrutal.ImGuiStandalone" Version="[$(StandalonePackageVersion)]" />', '<PackageReference Include="XBrutal.CheckIntermediary" Version="[0.0.0-test.1]" />')
            if '<PackageReference Include="XBrutal.ImGuiStandalone"' in text:
                raise ValueError('indirect test accidentally references XBrutal directly')
        project.write_text(text.replace('$(StandalonePackageVersion)', args.version))
        execute(['dotnet', 'restore', str(project), '--no-http-cache', '--nologo', '-v', 'quiet'], cache)
        execute(['dotnet', 'build', str(project), '-c', 'Release', '--no-restore', '--nologo', '-v', 'quiet'], cache)
        origin(cache)
        assets = json.loads((project_dir / 'obj/project.assets.json').read_text())
        direct_ids = {entry for target in assets['project']['frameworks'].values() for entry in target.get('dependencies', {})}
        if (mode == 'direct') != ('XBrutal.ImGuiStandalone' in direct_ids):
            raise ValueError('direct/transitive reference proof')
        metadata = execute(['dotnet', 'msbuild', str(project), '-t:ResolvePackageAssets', '-getItem:NativeCopyLocalItems,RuntimeTargetsCopyLocalItems,_XBrutalGlfw', '-nologo'], cache)
        (out / (mode + '-resolved-items.json')).write_text(metadata)
        build_output = project_dir / 'bin/Release/net10.0'
        inspect_output(build_output, None)
        execute(['dotnet', str(build_output / 'XBrutal.ImGuiStandalone.Checks.dll')], cache)
        portable = out / (mode + '-portable-publish')
        execute(['dotnet', 'publish', str(project), '-c', 'Release', '--no-build', '--no-restore', '-o', str(portable), '--nologo', '-v', 'quiet'], cache)
        inspect_output(portable, None)
        execute(['dotnet', str(portable / 'XBrutal.ImGuiStandalone.Checks.dll')], cache)
        for rid in ['osx-arm64', 'linux-x64', 'win-x64']:
            deployed = out / (mode + '-' + rid)
            execute(['dotnet', 'publish', str(project), '-c', 'Release', '-r', rid, '--self-contained', 'false', '-o', str(deployed), '--nologo', '-v', 'quiet'], cache)
            inspect_output(deployed, rid)
            if rid == host:
                execute(['dotnet', str(deployed / 'XBrutal.ImGuiStandalone.Checks.dll')], cache)
                no_build = out / (mode + '-' + rid + '-no-build')
                execute(['dotnet', 'publish', str(project), '-c', 'Release', '-r', rid, '--self-contained', 'false', '--no-build', '--no-restore', '-o', str(no_build), '--nologo', '-v', 'quiet'], cache)
                inspect_output(no_build, rid)
                execute(['dotnet', str(no_build / 'XBrutal.ImGuiStandalone.Checks.dll'), '--loading'], cache)
        if mode == 'direct':
            native = next(a for a in manifest['assets'] if a['rid'] == host)
            glfw = next(a for a in manifest['externalGlfw']['assets'] if a['rid'] == host)
            mutations = [('missing-imgui', native['path'], 'missing'), ('tampered-imgui', native['path'], 'tampered'), ('missing-glfw', glfw['path'], 'missing'), ('tampered-glfw', glfw['path'], 'tampered'), ('incompatible-managed', 'Brutal.ImGui.dll', 'managed'), ('missing-font', 'fonts/JetBrainsMono-Regular.ttf', 'font-missing'), ('tampered-font', 'fonts/JetBrainsMono-Regular.ttf', 'font-tampered')]
            for name, relative, kind in mutations:
                negative = out / name
                shutil.copytree(build_output, negative)
                path = negative / relative
                if kind in ('missing', 'font-missing'):
                    path.unlink()
                elif kind == 'managed':
                    # Same-length rename of one imported entry point in the metadata strings heap: the assembly
                    # still loads, but that P/Invoke no longer resolves in the packaged native image.
                    data = path.read_bytes()
                    if data.count(b'\0ActivateItemByID_internal\0') != 1:
                        raise ValueError('cannot locate the Brutal.ImGui import name to tamper')
                    path.write_bytes(data.replace(b'\0ActivateItemByID_internal\0', b'\0ZctivateItemByID_internal\0'))
                else:
                    path.write_bytes(path.read_bytes() + b'\0')
                diagnostic = {'missing': 'Missing packaged native asset', 'tampered': 'SHA-256 mismatch', 'managed': 'Incompatible loaded managed ABI', 'font-missing': 'bundled JetBrains Mono font is missing', 'font-tampered': 'SHA-256 mismatch'}[kind]
                execute(['dotnet', str(negative / 'XBrutal.ImGuiStandalone.Checks.dll'), '--expect-startup-rejection' if kind.startswith('font') or kind == 'managed' else '--expect-pre-native-rejection', diagnostic], cache)
            ambiguous = out / 'ambiguous-native'
            shutil.copytree(build_output, ambiguous)
            shutil.copyfile(ambiguous / native['path'], ambiguous / Path(native['path']).name)
            execute(['dotnet', str(ambiguous / 'XBrutal.ImGuiStandalone.Checks.dll'), '--expect-pre-native-rejection', 'Ambiguous native assets'], cache)
    report = {'status': 'passed', 'version': args.version, 'packageSha256': sha(package.read_bytes()), 'commands': len(records), 'deploymentLayouts': len(outputs), 'directAndTrueIntermediaryPackage': True, 'freshSeparateCaches': True, 'runtimeHost': host, 'foreignRuntimeExecution': False}
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
