"""
Evaluation cases for the AI assistant.

Unlike unit tests, these cases evaluate probabilistic AI behaviour.
We verify important concepts and source grounding instead of expecting
an exact sentence from the model.

Prerequisite: the seeded development user must own the sample note created
with the "Create the sample note" command in HELPER.md (title
"Project kickoff").
"""

from typing import TypedDict


class EvalCase(TypedDict):
    """One evaluation case for the AI assistant."""

    name: str
    question: str
    expected_source: str
    required_concepts: list[str]


EVAL_CASES: list[EvalCase] = [
    {
        "name": "kickoff_date_uses_user_notes",
        "question": "According to my notes, when is the project kickoff meeting?",
        "expected_source": "Project kickoff",
        "required_concepts": [
            "monday",
            "10:00",
        ],
    },
]
