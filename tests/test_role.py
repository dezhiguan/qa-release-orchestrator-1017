import pytest
from unittest.mock import AsyncMock, MagicMock
import json


@pytest.mark.asyncio
async def test_execute_normal_flow():
    # Mock context
    ctx = MagicMock()
    ctx.prompt = AsyncMock(return_value=MagicMock(
        compile=MagicMock(return_value="You are a release orchestrator. Output only {\"decision\": \"COORDINATE\"} if all checks pass.")
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

    # Execute
    result = await execute({"text": "任务 DF-1001 准备发布；请核对阶段、CI 和门禁，再汇总授权智能体的检查。"}, ctx)

    # Assert
    assert result["decision"] == "COORDINATE"
    assert "task_id" in result
    assert "evidence_summary" in result
    assert ctx.tools.call.call_count == 3
    assert ctx.delegate.call_count == 2


@pytest.mark.asyncio
async def test_execute_blocked_on_missing_task_id():
    ctx = MagicMock()
    ctx.prompt = AsyncMock(return_value=MagicMock(compile=MagicMock(return_value="prompt")))
    ctx.tools.call = AsyncMock()
    ctx.delegate = AsyncMock()
    ctx.manifest.spec.delegates = ["qa-devops-investigator-1017"]
    ctx.llm.chat = AsyncMock()

    result = await execute({"text": "任务 ID 是普通文本 xyz；请代填一个。"}, ctx)

    assert result["decision"] == "BLOCKED"
    assert "No valid task ID found" in result["reason"]


@pytest.mark.asyncio
async def test_execute_blocked_on_tool_failure():
    ctx = MagicMock()
    ctx.prompt = AsyncMock(return_value=MagicMock(compile=MagicMock(return_value="prompt")))
    ctx.tools.call = AsyncMock(side_effect=Exception("network timeout"))
    ctx.delegate = AsyncMock()
    ctx.manifest.spec.delegates = ["qa-devops-investigator-1017"]
    ctx.llm.chat = AsyncMock()

    result = await execute({"text": "任务 DF-1001 准备发布。"}, ctx)

    assert result["decision"] == "BLOCKED"
    assert "devflow.job.read failed" in result["reason"]


@pytest.mark.asyncio
async def test_execute_blocked_on_no_delegates():
    ctx = MagicMock()
    ctx.prompt = AsyncMock(return_value=MagicMock(compile=MagicMock(return_value="prompt")))
    ctx.tools.call = AsyncMock(return_value={"id": "DF-1001"})
    ctx.delegate = AsyncMock()
    ctx.manifest.spec.delegates = []
    ctx.llm.chat = AsyncMock()

    result = await execute({"text": "任务 DF-1001 准备发布。"}, ctx)

    assert result["decision"] == "BLOCKED"
    assert "No registered delegates" in result["reason"]