from google.genai import types

from app.llm.tool_schemas import TOOL_DECLARATIONS

# Plain JSON-schema function declarations for the Deepgram Voice Agent's
# `think.functions` field (see app/services/telephony_service.py) — Deepgram
# expects {"name", "description", "parameters"} dicts, not google.genai's
# typed FunctionDeclaration/Schema objects that Gemini's own SDK uses for
# text chat. Converted from tool_schemas.TOOL_DECLARATIONS below rather than
# hand-duplicated, so the two channels' tool definitions can never silently
# drift apart (same "shared serializer, not duplicated formatting" principle
# as order_to_read/cart_item_to_detailed — see backend CLAUDE.md). Dispatch
# for every one of these still goes through the same app.llm.tool_executor
# as text chat; this file only reshapes the *declarations* the model sees.

_TYPE_MAP = {
    types.Type.STRING: "string",
    types.Type.NUMBER: "number",
    types.Type.BOOLEAN: "boolean",
    types.Type.OBJECT: "object",
}


def _convert_schema(schema: types.Schema) -> dict:
    result: dict = {"type": _TYPE_MAP[schema.type]}
    if schema.description:
        result["description"] = schema.description
    if schema.enum:
        result["enum"] = list(schema.enum)
    if schema.type == types.Type.OBJECT:
        result["properties"] = {name: _convert_schema(prop) for name, prop in (schema.properties or {}).items()}
        if schema.required:
            result["required"] = list(schema.required)
    return result


def _convert_declaration(decl: types.FunctionDeclaration) -> dict:
    return {"name": decl.name, "description": decl.description, "parameters": _convert_schema(decl.parameters)}


# Call-channel-only — text chat never needs this, since that channel is
# already authenticated via JWT before a message ever reaches the LLM (see
# backend CLAUDE.md's "Who you're talking to"). See call_system_prompt.py
# and telephony_service.py for how the result gates every other tool.
VERIFY_PHONE_NUMBER_FUNCTION = {
    "name": "verify_phone_number",
    "description": (
        "Verify the caller's identity by looking up the phone number they just stated, spoken out "
        "loud, against registered accounts. Call this whenever the caller wants help with anything "
        "account-specific (cart, orders, addresses) and hasn't been verified yet this call. Every "
        "other tool except search_knowledge_base requires this to have returned verified=true first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "phone_number": {
                "type": "string",
                "description": (
                    "The phone number the caller just said, as digits/words transcribed from speech "
                    "— pass it through as heard, don't reformat or guess at it yourself."
                ),
            }
        },
        "required": ["phone_number"],
    },
}

CALL_TOOL_FUNCTIONS = [_convert_declaration(decl) for decl in TOOL_DECLARATIONS] + [VERIFY_PHONE_NUMBER_FUNCTION]
