"""MCP tool stubs for learning-tutor skill.

These functions define the interface for tools the AI agent can call.
Actual MCP registration happens via the agent's tool system.
"""


async def get_learning_topic(topic_id: int, child_id: int) -> dict:
    """Get topic details + child's mastery level."""
    # Implementation will be wired through MCP tool registry
    raise NotImplementedError("MCP tool — requires agent runtime")


async def get_child_learning_profile(child_id: int, subject: str | None = None) -> dict:
    """Get child's learning profile: mastered/learning/available counts."""
    raise NotImplementedError("MCP tool — requires agent runtime")


async def record_learning_result(session_id: int, evaluation: dict) -> dict:
    """Record AI evaluation result, update progress, trigger rewards."""
    raise NotImplementedError("MCP tool — requires agent runtime")
