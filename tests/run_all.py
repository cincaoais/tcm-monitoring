"""Run every test_*.py in this folder. Plain asserts, no framework. Run: python tests/run_all.py"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

modules = sorted(f[:-3] for f in os.listdir(HERE)
                 if f.startswith("test_") and f.endswith(".py"))

total = failed = 0
for name in modules:
    mod = importlib.import_module(f"tests.{name}")
    fns = [v for k, v in sorted(vars(mod).items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        total += 1
        try:
            fn()
            print(f"ok   {name}.{fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}.{fn.__name__}: {e}")

print(f"\n{total - failed}/{total} passed" + ("" if not failed else f"  ({failed} FAILED)"))
sys.exit(1 if failed else 0)
