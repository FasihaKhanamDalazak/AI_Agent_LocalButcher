import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm.system_prompt import SYSTEM_PROMPT
from app.llm.tool_executor import execute_tool
from app.llm.tool_schemas import TOOLS
from app.models.user import User

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Manual tool calling on purpose, not the SDK's automatic function calling —
# this is the one place every tool call is intercepted so it can be executed
# against the authenticated user, not just fired blindly.
MAX_TOOL_ROUNDS = 8

_GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[TOOLS],
)


class AssistantUnavailableError(Exception):
    """
    Raised whenever the Gemini API call itself fails — quota exhaustion
    (the free tier's 20 requests/day is easy to hit), an outage, etc.
    Callers (chat_service, then the REST/voice endpoints) always show this
    generic message to the customer, never `str(the underlying APIError)`
    — that object's text is the raw provider response (quota metrics,
    billing links, retry-delay seconds) and must stay server-log-only.
    """

    def __init__(self):
        super().__init__("The assistant is a little overwhelmed right now — please try again in a moment.")


async def run_conversation_turn(
    db: AsyncSession,
    user: User,
    history: list[types.Content],
    user_message: str,
) -> str:
    """
    Sends `user_message` plus prior `history` to Gemini, executes any tool
    calls the model makes (looping until it produces a final text answer or
    MAX_TOOL_ROUNDS is hit), and returns the final reply text.
    """
    contents = list(history) + [types.Content(role="user", parts=[types.Part(text=user_message)])]

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = await _client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=_GENERATION_CONFIG,
            )
        except genai_errors.APIError as e:
            # Caught here (not left to main.py's global handler) so the
            # customer-facing message can be specific and on-brand — but
            # that means this is the only place the real provider error
            # (quota metrics, billing links, etc.) still reaches the logs.
            logger.exception("Gemini API call failed")
            raise AssistantUnavailableError() from e
        model_content = response.candidates[0].content
        contents.append(model_content)

        function_calls = [part.function_call for part in model_content.parts if part.function_call is not None]
        if not function_calls:
            return response.text or ""

        response_parts = []
        for call in function_calls:
            result = await execute_tool(db, user, call.name, dict(call.args or {}))
            response_parts.append(types.Part(function_response=types.FunctionResponse(name=call.name, response=result)))

        contents.append(types.Content(role="user", parts=response_parts))

    return (
        "Sorry, I'm having trouble completing that right now — "
        "could you try rephrasing, or ask me one thing at a time?"
    )
