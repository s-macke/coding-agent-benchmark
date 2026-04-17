#!/usr/bin/env python3
"""Usage: python3 run_tests.py <path-to-basic-executable>

Runs every example through the given interpreter, feeds canned stdin where
INPUT is used, and asserts that each required substring appears in the
captured output. Infinite programs are killed by timeout after they have
had a chance to emit the first few iterations.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    filename: str
    stdin: str
    mode: str  # "exit" or "timeout"
    timeout: float
    expected: tuple[str, ...]


CASES: tuple[Case, ...] = (
    Case("example1.bas",  "",    "exit",    2, ("hello",)),
    Case("example2.bas",  "",    "timeout", 1, ("hello\nhello",)),
    Case("example3.bas",  "",    "exit",    2, ("values", "2", "5")),
    Case("example4.bas",  "",    "timeout", 1, ("1\n2\n3",)),
    Case("example5.bas",  "Ada", "exit",    2, ("what is your name", "hello", "Ada")),
    Case("example6.bas",  "5",   "exit",    2, ("enter a number", "double is", "10")),
    Case("example7.bas",  "5",   "exit",    2, ("enter a number", "times 6 is", "30")),
    Case("example8.bas",  "",    "exit",    2, ("name", "Ada", "precedence", "14",
                                                "parentheses", "20", "unary", "-13")),
    Case("example9.bas",  "",    "exit",    2, ("hello\nhello",)),
    Case("example10.bas", "",    "exit",    2, ("loop 1", "loop 2", "loop 3")),
    Case("example11.bas", "7",   "exit",    2, ("correct",)),
    Case("example12.bas", "",    "exit",    2, ("correct", "value", "7")),
    Case("example13.bas", "",    "exit",    2, ("hello ada", "not bob", "pass", "valid score")),
    Case("example14.bas", "",    "exit",    2, ("i=1", "i=2", "skip three",
                                                "i=4", "i=5")),
)


def run_case(basic: str, examples_dir: Path, case: Case) -> bool:
    path = examples_dir / case.filename
    try:
        proc = subprocess.run(
            [basic, str(path)],
            input=case.stdin,
            capture_output=True,
            text=True,
            timeout=case.timeout,
        )
        rc, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        rc = None
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        timed_out = True

    combined = (out or "") + (err or "")

    if case.mode == "exit":
        mode_ok = not timed_out and rc == 0
    elif case.mode == "timeout":
        mode_ok = timed_out
    else:
        raise ValueError(f"unknown mode {case.mode!r}")

    missing = [s for s in case.expected if s not in combined]

    if mode_ok and not missing:
        print(f"PASS  {case.filename}")
        return True

    print(f"FAIL  {case.filename}")
    if not mode_ok:
        actual = "timeout" if timed_out else f"rc={rc}"
        print(f"      mode: expected {case.mode}, got {actual}")
    if missing:
        print("      missing substrings:")
        for s in missing:
            print(f"        {s!r}")
    print("      output:")
    for line in combined.splitlines() or [""]:
        print(f"        {line}")
    return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <basic-executable>", file=sys.stderr)
        return 2
    basic = argv[1]
    examples_dir = Path(__file__).resolve().parent / "examples"

    results = [run_case(basic, examples_dir, c) for c in CASES]
    passed = sum(results)
    failed = len(results) - passed

    print()
    print(f"Results: {passed} passed, {failed} failed (of {len(results)})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
