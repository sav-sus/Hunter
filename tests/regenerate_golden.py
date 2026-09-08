"""Rewrite the committed golden file.

Run this after a deliberate change to the score arithmetic or the report shape,
then review the diff. That diff is the point: section 11.9 requires score
movement to be visible in code review rather than surprising a client.

    python -m tests.regenerate_golden
"""

from __future__ import annotations

import json

from hunter.emit.report import stable_payload
from hunter.run import run
from tests.test_golden import AS_OF, EXAMPLE, GOLDEN


def main() -> None:
    result = run(EXAMPLE, as_of=AS_OF)
    payload = json.loads(json.dumps(stable_payload(result), sort_keys=True, default=str))
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN}")
    print(f"score {result.score.total:g}, {len(result.findings)} findings")
    print("Review the diff before committing.")


if __name__ == "__main__":
    main()
