"""
Small evaluation runner for the AI assistant.

Runs real AI requests and checks:
1. Whether the answer contains the expected concepts.
2. Whether the answer is grounded in the expected internal source.
"""

import asyncio

from app.auth.context import AppContext
from app.auth.permissions import KNOWLEDGE_READ, NOTES_CREATE, PROFILE_READ
from app.core.event_loop import loop_factory
from app.database.connection import close_database_pool, open_database_pool
from app.database.seed import USER_ID
from app.services.ai.agent_service import run_assistant
from evals.cases import EVAL_CASES


async def run() -> None:
    context = AppContext(
        user_id=USER_ID,
        permissions=frozenset(
            {
                KNOWLEDGE_READ,
                NOTES_CREATE,
                PROFILE_READ,
            }
        ),
    )

    passed = 0

    await open_database_pool()

    try:
        for case in EVAL_CASES:
            response = await run_assistant(
                message=case["question"],
                context=context,
            )

            answer = response.answer.lower()

            concepts_ok = all(
                concept.lower() in answer for concept in case["required_concepts"]
            )

            source_ok = any(
                source.title == case["expected_source"] for source in response.sources
            )

            success = concepts_ok and source_ok

            status = "PASS" if success else "FAIL"

            print(f"\n[{status}] {case['name']}")
            print(f"Answer: {response.answer}")
            print(f"Concepts OK: {concepts_ok}")
            print(f"Source OK: {source_ok}")

            if success:
                passed += 1

    finally:
        await close_database_pool()

    print(f"\nResult: {passed}/{len(EVAL_CASES)} evals passed")

    if passed != len(EVAL_CASES):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(
        run(),
        loop_factory=loop_factory,
    )
