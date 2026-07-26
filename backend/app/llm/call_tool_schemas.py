from app.llm.tool_schemas import PLAIN_JSON_TOOL_DECLARATIONS

# Call-channel-only — text chat and browser voice never need this, since
# both are already authenticated via JWT before a message ever reaches the
# LLM (see backend CLAUDE.md's "Who you're talking to"). See
# call_system_prompt.py and telephony_service.py for how the result gates
# every other tool.
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

CALL_TOOL_FUNCTIONS = PLAIN_JSON_TOOL_DECLARATIONS + [VERIFY_PHONE_NUMBER_FUNCTION]
