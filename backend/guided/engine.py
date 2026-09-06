"""
Walks a YAML-defined decision tree for a guided legal scenario
(landlord dispute, consumer complaint, employment issue).
"""
import os
from typing import Dict, Optional

import yaml

_TREES_DIR = os.path.join(os.path.dirname(__file__), "trees")

_SCENARIO_META = {
    "landlord": {"title": "Landlord Dispute", "description": "Deposit, eviction, repairs and rent issues.", "icon": "🏠"},
    "consumer": {"title": "Consumer Complaint", "description": "Defective products, poor service, and billing disputes.", "icon": "🛒"},
    "employment": {"title": "Employment Issue", "description": "Unpaid wages, termination, and workplace disputes.", "icon": "💼"},
}


class GuidedEngine:
    def __init__(self):
        self._trees: Dict[str, dict] = {}
        self._load_trees()

    def _load_trees(self):
        for filename in os.listdir(_TREES_DIR):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                path = os.path.join(_TREES_DIR, filename)
                with open(path, "r", encoding="utf-8") as f:
                    tree = yaml.safe_load(f)
                self._trees[tree["id"]] = tree

    def list_scenarios(self):
        scenarios = []
        for scenario_id, tree in self._trees.items():
            meta = _SCENARIO_META.get(scenario_id, {})
            scenarios.append({
                "id": scenario_id,
                "title": tree.get("title", meta.get("title", scenario_id)),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", "⚖️"),
            })
        return scenarios

    def _get_tree(self, scenario_id: str) -> dict:
        if scenario_id not in self._trees:
            raise ValueError(f"Unknown scenario: {scenario_id}")
        return self._trees[scenario_id]

    def _get_step(self, scenario_id: str, step_id: str) -> dict:
        tree = self._get_tree(scenario_id)
        for step in tree["steps"]:
            if step["id"] == step_id:
                return step
        raise ValueError(f"Unknown step '{step_id}' in scenario '{scenario_id}'")

    def _total_steps_estimate(self, scenario_id: str) -> int:
        tree = self._get_tree(scenario_id)
        depths = []
        step_by_id = {s["id"]: s for s in tree["steps"]}

        def depth(step_id, visited):
            if step_id in visited:
                return 0
            visited = visited | {step_id}
            step = step_by_id.get(step_id)
            if not step or not step.get("options"):
                return 1
            child_depths = [depth(opt["next"], visited) for opt in step["options"]]
            return 1 + (max(child_depths) if child_depths else 0)

        return max(depth(tree["steps"][0]["id"], set()), 1)

    def _format_step(self, scenario_id: str, step: dict, progress: int) -> dict:
        options = [opt["text"] for opt in step.get("options", [])] if step.get("options") else []
        result = step.get("result")
        return {
            "step_id": step["id"],
            "question": step.get("question"),
            "options": options,
            "progress": progress,
            "result": result,
        }

    def start_scenario(self, scenario_id: str) -> dict:
        tree = self._get_tree(scenario_id)
        first_step = tree["steps"][0]
        return self._format_step(scenario_id, first_step, progress=1)

    def process_answer(self, scenario_id: str, step_id: str, answer: str) -> dict:
        current_step = self._get_step(scenario_id, step_id)
        options = current_step.get("options", [])

        next_step_id: Optional[str] = None
        for opt in options:
            if opt["text"].strip().lower() == answer.strip().lower():
                next_step_id = opt["next"]
                break

        if next_step_id is None:
            # Fall back to the first option if the answer didn't match exactly
            # (defensive, since the frontend always sends option text verbatim).
            if options:
                next_step_id = options[0]["next"]
            else:
                raise ValueError("This step has no further options.")

        next_step = self._get_step(scenario_id, next_step_id)

        tree = self._get_tree(scenario_id)
        step_index = next((i for i, s in enumerate(tree["steps"]) if s["id"] == next_step_id), 0)
        progress = step_index + 1

        return self._format_step(scenario_id, next_step, progress=progress)


_engine_singleton = None


def get_engine() -> GuidedEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = GuidedEngine()
    return _engine_singleton
