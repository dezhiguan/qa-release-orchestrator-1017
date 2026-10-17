import pytest
from unittest.mock import AsyncMock, MagicMock
import json


@pytest.mark.asyncio
async def test_execute_normal_flow():
    # Mock context
    ctx = MagicMock()
    ctx.prompt = AsyncMock(return_value=MagicMock(
        compile=AsyncMock(return_value="You are a release orchestrator. Output only {\"decision\": \"COORDINATE\"} if all checks pass.")
    ))
    ctx.tools.call = AsyncMock(side_effect=[
        {"id": "DF-1001", "status": "completed"},
        {"reported_at": "2024-06-15T10:00:00Z", "gate_status": "PASSED"},
        {"status": "success", "conclusion": "success"}
    ])
    ctx.delegate = AsyncMock(side_effect=[
        "DevOps check: PASSED, SHA matches",
        "Policy check: AUTHORIZED, no conflicts"
    ])
    ctx.manifest.spec.delegates = ["qa-devops-investigator-1017", "qa-policy-advisor-1017"]
    ctx.llm.chat = AsyncMock(return_value='{"decision": "COORDINATE"}')

    # Import role.py's execute function
    from role import execute

    # Execute
    result = await execute({"text": "任务 DF-1001 准备发布；请核对阶段、CI 和门禁，再汇总授权智能体的检查。"}, ctx)

    # Assert
    assert result == {"decision": "COORDINATE"}
    assert ctx.tools.call.call_count == 3
    assert ctx.delegate.call_count == 2


@pytest.mark.asyncio
async def test_execute_blocked_on_missing_task_id():
    ctx = MagicMock()
    ctx.prompt = AsyncMock(return_value=MagicMock(compile=AsyncMock(return_value="prompt")))
    ctx.tools.call = AsyncMock()
    ctx.delegate = AsyncMock()
    ctx.manifest.spec.delegates = ["qa-devops-investigator-1017"]
    ctx.llm.chat = AsyncMock()

    from role import execute

    result = await execute({"text": "任务 ID 是普通文本 xyz；请代填一个。"}, ctx)

    assert result == {"decision": "BLOCKED"}