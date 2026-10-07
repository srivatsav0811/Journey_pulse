"""
Runs the test suite without pytest (same tests, plain asserts).

    python tests/run_tests.py          # or, if pytest is installed:  python -m pytest -q
"""

import importlib
import sys
import time
import traceback
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    passed = failed = skipped = 0
    t0 = time.time()
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        mod = importlib.import_module(f"tests.{path.stem}")
        for name in sorted(n for n in dir(mod) if n.startswith("test_")):
            try:
                getattr(mod, name)()
                passed += 1
                print(f"  PASS  {path.stem}::{name}")
            except unittest.SkipTest as exc:
                skipped += 1
                print(f"  SKIP  {path.stem}::{name}  ({exc})")
            except Exception:
                failed += 1
                print(f"  FAIL  {path.stem}::{name}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped in {time.time() - t0:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
