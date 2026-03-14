from __future__ import annotations

from tests.gates.phase1_gate import run_phase1_gate


def main() -> int:
    results = run_phase1_gate()
    for name, status, detail in results:
        print(f"[{status}] {name}: {detail}")
    return 1 if any(status == "FAIL" for _, status, _ in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
