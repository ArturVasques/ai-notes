"""
Regression tests for the agent tool security boundary.

- The model never chooses identity: no tool schema exposes user_id
  or permissions as parameters.
- Every tool registered on the assistant checks a permission and refuses
  before touching any repository when it is missing.
"""

from uuid import uuid4

from agents import FunctionTool
from agents.tool_context import ToolContext

from app.agents.assistant import assistant_agent
from app.auth.context import AppContext
from app.tools.knowledge_tools import search_knowledge
from app.tools.user_tools import get_my_profile

IDENTITY_FIELDS = {"user_id", "permissions", "context"}


def _tool_context(permissions: set[str]) -> ToolContext[AppContext]:
    return ToolContext(
        context=AppContext(
            user_id=uuid4(),
            permissions=frozenset(permissions),
        ),
        tool_name="test",
        tool_call_id="call-1",
        tool_arguments="{}",
    )


def test_assistant_tools_are_exactly_the_audited_ones() -> None:
    assert assistant_agent.tools == [get_my_profile, search_knowledge]


def test_tool_schemas_never_expose_identity_parameters() -> None:
    for tool in assistant_agent.tools:
        assert isinstance(tool, FunctionTool)

        exposed = set(tool.params_json_schema.get("properties", {}))

        assert not exposed & IDENTITY_FIELDS, f"{tool.name} exposes {exposed}"


async def test_search_knowledge_refuses_without_permission() -> None:
    result = await search_knowledge.on_invoke_tool(
        _tool_context(set()), '{"query": "recovery guidelines"}'
    )

    assert result == "Permission denied."


async def test_get_my_profile_refuses_without_permission() -> None:
    result = await get_my_profile.on_invoke_tool(_tool_context(set()), "{}")

    assert result == "Permission denied."
