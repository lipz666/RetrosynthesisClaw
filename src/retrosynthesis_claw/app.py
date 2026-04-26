"""Application entrypoint for RetrosynthesisClaw."""

from __future__ import annotations

import json

from .orchestrator import RetrosynthesisOrchestrator


def main() -> None:
    """Run a sample synthesis planning workflow."""

    orchestrator = RetrosynthesisOrchestrator.create_default()
    plan = orchestrator.run("CCOc1ccc2nc(S(N)(=O)=O)sc2c1")
    print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
