"""
Agent service — mirrors the PARAMETRIC_AGENT_PROMPT call from index.ts.
Uses OpenAI (gpt-4o) for reliable tool-calling.
Returns the tool name + arguments chosen by the agent, plus its text reply.
"""
import json
from openai import AsyncOpenAI
from config import get_settings
from prompts import PARAMETRIC_AGENT_PROMPT
from tools import TOOLS


async def run_agent(
    user_text: str,
    vision_description: str | None = None,
    base_code: str | None = None,
) -> dict:
    """
    Run the agent call.

    Returns a dict with:
      {
        "text":      <agent reply text>,
        "tool_name": <"build_parametric_model" | "apply_parameter_changes" | None>,
        "tool_args": <parsed dict of tool arguments | None>
      }
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Build user content — include vision description if available
    if vision_description:
        user_content = (
            f"{user_text}\n\n"
            f"[Image Analysis for 3D modelling]\n{vision_description}"
        )
    else:
        user_content = user_text

    messages = [
        {"role": "system", "content": PARAMETRIC_AGENT_PROMPT},
        {"role": "user", "content": user_content},
    ]

    # If we have existing code in context, include it as assistant turn
    if base_code:
        messages.insert(
            2,
            {"role": "assistant", "content": base_code},
        )
        messages.append({"role": "user", "content": user_content})

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=512,
        temperature=0.3,
    )

    choice = response.choices[0]
    agent_text = choice.message.content or ""
    tool_name = None
    tool_args = None

    if choice.message.tool_calls:
        tc = choice.message.tool_calls[0]
        tool_name = tc.function.name
        try:
            tool_args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            tool_args = {}

    return {
        "text": agent_text,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }
