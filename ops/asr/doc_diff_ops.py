"""doc_diff_ops.py - turn a file change into Claude Docs find/replace ops, so an appendix that holds a script's
full text is updated with only the changed lines instead of re-sending the whole file.

    python3 doc_diff_ops.py old_file new_file [segment_start_regex ...] > ops.json

The doc must hold exactly old_file (check its SHA256 against the doc's note first). Each op replaces the smallest
unique run of old lines (grown with context until it occurs once) by its new text, with "as":"text". Pass the
regexes of the lines that start each code block when the file is split over several blocks: an anchor that would
span two blocks is reported and the script stops. The ops are re-applied locally and must reproduce new_file.
Send them in one `update` on the appendix tab's body; a refused call changes nothing.
"""
import difflib
import json
import re
import sys


def main(old_path, new_path, *seg_res):
    a = open(old_path, encoding='utf-8').read().split('\n')
    b = open(new_path, encoding='utf-8').read().split('\n')
    full = '\n'.join(a)
    starts = sorted({0} | {next(i for i, l in enumerate(a) if re.match(r, l)) for r in seg_res})
    seg = lambda i: max(k for k, s in enumerate(starts) if s <= i)
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        lo, hi = i1, i2
        while True:
            old = '\n'.join(a[lo:hi])
            if old.strip() and full.count(old) == 1:
                break
            if hi < len(a) and (hi - lo) % 2 == 0:
                hi += 1
            elif lo > 0:
                lo -= 1
            else:
                hi += 1
        if seg(lo) != seg(max(lo, hi - 1)):
            sys.exit('anchor at old lines %d-%d spans two code blocks' % (lo + 1, hi))
        new = '\n'.join(a[lo:i1] + b[j1:j2] + a[i2:hi])
        ops.append({'op': 'replace', 'target': {'kind': 'find', 'text': old},
                    'with': {'from': {'kind': 'inline', 'content': new}, 'as': 'text'}})
    t = full
    for o in ops:
        t = t.replace(o['target']['text'], o['with']['from']['content'])
    if t != '\n'.join(b):
        sys.exit('ops do not reproduce the new file')
    json.dump(ops, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main(*sys.argv[1:])
