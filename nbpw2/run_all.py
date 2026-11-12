# -*- coding: utf-8 -*-
"""Run all NBPW-2 pilot experiments."""
import subprocess, sys

MODS = ["test_core", "run_e1", "run_e1b", "analyze_e1", "run_e2", "run_e3",
        "run_e4", "run_e5", "run_e6", "run_e7", "run_e8", "run_e9", "run_e10", "run_e11"]

def main():
    for m in MODS:
        print("\n=== " + m + " ===", flush=True)
        r = subprocess.run([sys.executable, "-m", "nbpw2." + m])
        if r.returncode != 0:
            print("FAILED:", m)
            return r.returncode
    print("\nALL DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
