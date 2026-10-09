#!/usr/bin/env python
"""Fail if any tracked file carries an em dash or an en dash.

grep -P cannot do this on Windows, where it refuses any non unibyte locale and
then prints to stderr while reporting no matches, which reads exactly like a
clean result. This reads the files instead.

The scan proves it can see a planted dash before reporting a clean tree, so an
empty result from a broken scan cannot pass as an empty result from a clean one.
"""

import subprocess
import sys

# Built from code points, never written literally. A checker that spells out the
# glyph it hunts flags itself, and then the only way to a green gate is to
# weaken the check.
EM = chr(0x2014)
EN = chr(0x2013)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.split("\n") if line.strip()]


def main() -> int:
    if (f"x{EM}y".count(EM), f"x{EN}y".count(EN)) != (1, 1):
        print("dashes: the scan cannot detect a planted dash, refusing to report")
        return 1

    hits: list[tuple[str, int, int]] = []
    binary = 0
    files = tracked_files()
    for name in files:
        try:
            raw = open(name, "rb").read()
        except OSError:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            binary += 1
            continue
        em, en = text.count(EM), text.count(EN)
        if em or en:
            hits.append((name, em, en))

    print(f"scanned {len(files)} tracked files, {binary} non utf-8 skipped")
    if not hits:
        print("no em dashes, no en dashes")
        return 0

    print(f"{len(hits)} files carry a dash glyph:")
    for name, em, en in hits:
        print(f"    {name}  em={em} en={en}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
