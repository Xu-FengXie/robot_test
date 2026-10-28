# -*- coding: utf-8 -*-
"""Replace a locked-by-sync PDF with a freshly generated one, retrying with backoff."""
import os
import pathlib
import sys
import time

base = pathlib.Path(sys.argv[1]).resolve()
tmp = base.with_suffix(base.suffix + ".tmp")

if not tmp.exists():
    raise SystemExit(f"ERROR: temp file not found: {tmp}")

data = tmp.read_bytes()
print(f"staged: {tmp.name} ({len(data)/1024:.1f} KB)")

delay = 1.5
for attempt in range(1, 16):
    try:
        if base.exists():
            os.remove(base)
        os.replace(tmp, base)
        print(f"OK  {base.name}  ({len(data)/1024:.1f} KB)  attempt={attempt}")
        sys.exit(0)
    except PermissionError as e:
        print(f"  attempt {attempt}: locked ({e.winerror}) -> retry in {delay:.1f}s")
        time.sleep(delay)
        delay = min(delay * 1.4, 8.0)

raise SystemExit("ERROR: could not replace target after 15 attempts")
