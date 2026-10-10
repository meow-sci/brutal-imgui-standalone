"""Bounded little-endian 64-bit image inventory (no execution or system tools)."""
import struct


def inventory(data, rid):
    def u(fmt, offset):
        return struct.unpack_from('<' + fmt, data, offset)

    def text(offset):
        return data[offset:data.index(b'\0', offset)].decode('ascii')

    names, dependencies = [], []
    if rid == 'osx-arm64':
        if u('II', 0) != (0xfeedfacf, 0x100000c):
            raise ValueError('expected Mach-O64 arm64')
        offset, export_offset, export_size = 32, None, 0
        for _ in range(u('I', 16)[0]):
            cmd, size = u('II', offset)
            if cmd in (0x22, 0x80000022):
                export_offset, export_size = u('II', offset + 40)
            if cmd == 0x80000033:
                export_offset, export_size = u('II', offset + 8)
            if cmd in (0xc, 0x80000018, 0x8000001f, 0x20, 0x80000023):
                dependencies.append(text(offset + u('I', offset + 8)[0]))
            offset += size
        if export_offset is None or not export_size:
            raise ValueError('missing Mach-O dynamic export trie')

        def leb(offset):
            value, shift = 0, 0
            while True:
                byte = data[offset]
                offset += 1
                value |= (byte & 127) << shift
                if not byte & 128:
                    return value, offset
                shift += 7
                if shift > 63:
                    raise ValueError('invalid export ULEB128')

        def visit(node, prefix, ancestors):
            if node in ancestors or not 0 <= node < export_size:
                raise ValueError('invalid export trie')
            offset = export_offset + node
            terminal_size, terminal = leb(offset)
            if terminal_size:
                flags, _ = leb(terminal)
                if flags & 0x18:
                    raise ValueError('forwarded/resolver Mach-O export')
                names.append(prefix.removeprefix('_'))
            offset = terminal + terminal_size
            children = data[offset]
            offset += 1
            for _ in range(children):
                suffix = text(offset)
                offset += len(suffix) + 1
                child, offset = leb(offset)
                visit(child, prefix + suffix, ancestors | {node})

        visit(0, '', set())
    elif rid == 'linux-x64':
        if data[:6] != b'\x7fELF\x02\x01' or u('H', 18)[0] != 62:
            raise ValueError('expected ELF64 x86-64')
        shoff, = u('Q', 40)
        entsize, count = u('HH', 58)
        sections = [u('IIQQQQIIQQ', shoff + i * entsize) for i in range(count)]
        for sec in sections:
            strings = sections[sec[6]][4] if sec[6] else 0
            if sec[1] == 11:
                for offset in range(sec[4], sec[4] + sec[5], sec[9]):
                    name, info, visibility, index, _, _ = u('IBBHQQ', offset)
                    if index and info >> 4 in (1, 2) and visibility & 3 in (0, 3):
                        names.append(text(strings + name))
            if sec[1] == 6:
                for offset in range(sec[4], sec[4] + sec[5], sec[9]):
                    tag, value = u('QQ', offset)
                    if tag == 1:
                        dependencies.append(text(strings + value))
    elif rid == 'win-x64':
        pe, = u('I', 0x3c)
        if data[:2] != b'MZ' or data[pe:pe + 4] != b'PE\0\0' or u('H', pe + 4)[0] != 0x8664:
            raise ValueError('expected PE x86-64')
        count, = u('H', pe + 6)
        optional_size, = u('H', pe + 20)
        optional = pe + 24
        if u('H', optional)[0] != 0x20b:
            raise ValueError('expected PE32+')
        sections = []
        for i in range(count):
            sec = optional + optional_size + i * 40
            size, rva, raw_size, raw_offset = u('IIII', sec + 8)
            sections.append((rva, max(size, raw_size), raw_offset))

        def locate(rva):
            sec = next(s for s in sections if s[0] <= rva < s[0] + s[1])
            return sec[2] + rva - sec[0]

        export_rva, export_size = u('II', optional + 112)
        if export_rva:
            export = locate(export_rva)
            funcs_count, names_count, funcs, strings, ordinals = u('IIIII', export + 20)
            addresses = [u('I', locate(funcs) + i * 4)[0] for i in range(funcs_count)]
            if sum(bool(a) for a in addresses) != names_count:
                raise ValueError('unnamed PE exports')
            for i in range(names_count):
                name = text(locate(u('I', locate(strings) + i * 4)[0]))
                ordinal = u('H', locate(ordinals) + i * 2)[0]
                if export_rva <= addresses[ordinal] < export_rva + export_size:
                    raise ValueError('forwarded PE export: ' + name)
                names.append(name)
        import_rva, _ = u('II', optional + 120)
        if import_rva:
            offset = locate(import_rva)
            while any(u('IIIII', offset)):
                dependencies.append(text(locate(u('I', offset + 12)[0])))
                offset += 20
    else:
        raise ValueError('unsupported RID')
    if len(names) != len(set(names)):
        raise ValueError('duplicate exports')
    return {'exports': sorted(names), 'dependencies': sorted(dependencies), 'rid': rid}
