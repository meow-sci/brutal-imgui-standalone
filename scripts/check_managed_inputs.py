"""Fail fast when external BRUTAL managed inputs are missing; print their versions (informational only).

Compatibility is not pinned by hash: ManagedCompatibility.cs checks native imports and layouts at runtime.
"""
import argparse
import re
from pathlib import Path

REQUIRED = ['Brutal.ImGui', 'Brutal.Glfw', 'Brutal.Core.Common', 'Brutal.Core.Strings', 'Brutal.Core.Numerics']


def resource_string(data, key):
    """Read a VS_VERSION_INFO string (UTF-16LE) from the PE version resource, if present."""
    match = re.search(key.encode('utf-16-le') + rb'\0\0(?:\0\0)?((?:[^\0]\0)+)\0\0', data)
    return match.group(1).decode('utf-16-le') if match else 'unknown'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--managed-dir', required=True, type=Path)
    args = parser.parse_args()
    missing = [name for name in REQUIRED if not (args.managed_dir / (name + '.dll')).is_file()]
    if missing:
        raise ValueError(f'missing external managed references in {args.managed_dir}: {missing}')
    for name in REQUIRED:
        data = (args.managed_dir / (name + '.dll')).read_bytes()
        print(f'{name}.dll: file {resource_string(data, "FileVersion")}, product {resource_string(data, "ProductVersion")}')


if __name__ == '__main__':
    main()
