import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.integrations.roster_engine.exceptions import EngineIntegrationError

logger = logging.getLogger(__name__)


class RosterEngineAdapter:
    """Run the packaged engine in a fresh interpreter to isolate global state."""

    def __init__(self, timeout_seconds: int = 120):
        self.backend_root = Path(__file__).resolve().parents[3]
        self.timeout_seconds = timeout_seconds
        if not (self.backend_root / "app" / "scheduling_engine" / "backtracking.py").is_file():
            raise EngineIntegrationError("ENGINE_NOT_FOUND", "The scheduling engine directory could not be located.")

    def generate(self, dataset: dict[str, Any], month: int, year: int) -> dict[str, Any]:
        return self._run({"mode": "generate", "dataset": dataset, "month": month, "year": year})

    def validate(self, dataset: dict[str, Any], assignments: list[dict[str, Any]], weekly_offs: list[dict[str, Any]], month: int, year: int) -> dict[str, Any]:
        return self._run({
            "mode": "validate", "dataset": dataset, "assignments": assignments,
            "weekly_offs": weekly_offs, "month": month, "year": year,
        })

    def _run(self, request: dict[str, Any]) -> dict[str, Any]:
        dataset = request["dataset"]
        unsupported = [rule for rule in dataset["brand_process_rules"] if rule.get("coverage_overrides")]
        if unsupported:
            raise EngineIntegrationError(
                "UNSUPPORTED_COVERAGE_OVERRIDES",
                "The current scheduling engine does not apply date-specific coverage overrides.",
            )
        payload = request
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "app.integrations.roster_engine.worker"],
                input=json.dumps(payload), text=True, capture_output=True,
                cwd=self.backend_root,
                timeout=self.timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EngineIntegrationError("ENGINE_TIMEOUT", "Roster generation exceeded the configured time limit.") from exc
        except OSError as exc:
            logger.exception("Unable to launch isolated roster engine worker")
            raise EngineIntegrationError("ENGINE_WORKER_UNAVAILABLE", "The roster engine worker could not be started.") from exc
        if completed.returncode != 0:
            logger.error("Roster engine worker failed: %s", completed.stderr[-4000:])
            raise EngineIntegrationError("ENGINE_WORKER_FAILURE", "Roster generation failed inside the isolated engine worker.")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            logger.error("Roster engine worker returned invalid JSON: %s", completed.stderr[-4000:])
            raise EngineIntegrationError("ENGINE_INVALID_RESPONSE", "The roster engine returned an invalid response.") from exc
        if "worker_error" in result:
            logger.error("Roster engine worker reported an internal failure: %s", completed.stderr[-4000:])
            raise EngineIntegrationError("ENGINE_WORKER_FAILURE", "Roster generation failed inside the isolated engine worker.")
        return result
