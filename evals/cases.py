"""
Evaluation cases for the AI assistant.

Unlike unit tests, these cases evaluate probabilistic AI behaviour.
We verify important concepts and source grounding instead of expecting
an exact sentence from the model.
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
        "name": "poor_recovery_uses_internal_knowledge",
        "question": (
            "According to our internal guidelines, "
            "what should an athlete with a RecoveryScore of 32 do?"
        ),
        "expected_source": "Recovery guidelines",
        "required_concepts": [
            "poor recovery",
            "avoid intense training",
        ],
    },
    {
        "name": "good_recovery_uses_internal_knowledge",
        "question": (
            "According to our internal guidelines, "
            "what does a RecoveryScore above 70 indicate?"
        ),
        "expected_source": "Recovery guidelines",
        "required_concepts": [
            "good recovery",
            "planned training",
        ],
    },
]
