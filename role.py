import json
import re
from typing import Dict, Any


async def execute(data: dict, ctx) -> dict:
    # Extract task ID from input text
    text = data.get("text", "")
    task_match = re.search(r"任务\s+(DF-\\d+)", text)
    if not task_match:
        return {"decision": "BLOCKED"}
    task_id = task_match.group(1)

    # Load prompt
    try:
        prompt = await ctx.prompt("role")
        compiled_prompt = prompt.compile(input={"task_id": task_id, "text": text})
    except Exception:
        return {"decision": "BLOCKED"}

    # Read task and stage
    try:
        task_resp = await ctx.tools.call("devflow.job.read", job_id=task_id)
    except Exception:
        return {"decision": "BLOCKED"}

    try:
        stage_resp = await ctx.tools.call("devflow.stage.report", job_id=task_id)
    except Exception:
        return {"decision": "BLOCKED"}

    # Fetch CI log
    try:
        ci_resp = await ctx.tools.call("ci.log.fetch", job_id=task_id)
    except Exception:
        return {"decision": "BLOCKED"}

    # Get allowed delegates
    allowed_delegates = list(ctx.manifest.spec.delegates or [])
    if not allowed_delegates:
        return {"decision": "BLOCKED"}

    # Delegate to each registered agent
    delegate_results = []
    for delegate in allowed_delegates:
        try:
            res = await ctx.delegate(delegate, text)
            delegate_results.append({"agent": delegate, "result": res})
        except Exception:
            return {"decision": "BLOCKED"}

    # Final LLM synthesis — only after all tools & delegates succeed
    try:
        llm_input = {
            "task_id": task_id,
            "task": task_resp,
            "stage": stage_resp,
            "ci_log": ci_resp,
            "delegates": delegate_results
        }
        llm_response = await ctx.llm.chat([
            {"role": "user", "content": json.dumps(llm_input, ensure_ascii=False)}
        ], prompt=compiled_prompt)
        
        # Parse decision from LLM response (must be JSON-like dict with "decision")
        # Use safe regex: match top-level {"decision": "..."} exactly
        decision_match = re.search(r'\{\s*"decision"\s*:\s*"(COORDINATE|BLOCKED)"\s*\}', llm_response)
        if not decision_match:
            return {"decision": "BLOCKED"}
        decision = decision_match.group(1)
        
        # Enforce strict policy: only COORDINATE is acceptable success; all else BLOCKED
        if decision != "COORDINATE":
            return {"decision": "BLOCKED"}
            
        return {"decision": "COORDINATE"}
        
    except Exception:
        return {"decision": "BLOCKED"}