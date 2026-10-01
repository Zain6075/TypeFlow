#!/usr/bin/env python3
"""Dependency-free test runner:  python tests/run_tests.py

Discovers every ``test_*`` function in this directory and runs it, printing a
pass/fail summary.  (``python -m pytest tests -q`` works too.)
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("TYPEFLOW_DATA_DIR", os.path.join(
    os.environ.get("TEMP", "/tmp"), "typeflow-tests"))

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def main() -> int:
    import test_core

    tests = [(name, obj) for name, obj in sorted(vars(test_core).items())
             if name.startswith("test_") and callable(obj)]
    passed, failed = 0, 0
    for name, test in tests:
        try:
            test()
        except Exception:                                  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
        else:
            passed += 1
            print(f"ok    {name}")
    print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
