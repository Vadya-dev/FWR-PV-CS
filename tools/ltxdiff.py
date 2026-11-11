"""Key-level diff of two LTX files (sections/keys). usage: ltxdiff.py a.ltx b.ltx [--only-a-missing]"""
import re, sys


def parse(path):
    data = open(path, 'rb').read().decode('cp1251', errors='replace')
    secs = {}
    order = []
    cur = None
    for line in data.splitlines():
        s = line.split(';', 1)[0].strip()
        if not s:
            continue
        m = re.match(r'^\[([^\]]+)\]\s*(?::\s*(.*))?$', s)
        if m:
            cur = m.group(1).strip().lower()
            secs.setdefault(cur, {'__parent__': (m.group(2) or '').replace(' ', '').replace('\t', '')})
            order.append(cur)
            continue
        if s.startswith('#include'):
            secs.setdefault('__includes__', {})[s] = ''
            continue
        if cur is None:
            continue
        if '=' in s:
            k, v = s.split('=', 1)
            secs[cur][k.strip().lower()] = re.sub(r'\s+', ' ', v.strip())
        else:
            secs[cur][s.strip().lower()] = None
    return secs, order


def main():
    a, _ = parse(sys.argv[1])
    b, _ = parse(sys.argv[2])
    for sec in sorted(set(a) | set(b)):
        if sec not in b:
            print(f'[{sec}] only in A'); continue
        if sec not in a:
            print(f'[{sec}] only in B'); continue
        for k in sorted(set(a[sec]) | set(b[sec])):
            va, vb = a[sec].get(k, '<missing>'), b[sec].get(k, '<missing>')
            if va != vb:
                print(f'[{sec}] {k}: A={va} | B={vb}')


if __name__ == '__main__':
    main()
