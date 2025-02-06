# minimal conversational template with sample function calling tools integration

from openai import OpenAI
import json  # Required to parse tool call arguments

client = OpenAI()

# Define a simple tool (function) for adding two numbers
tools = [{
    "type": "function",
    "function": {
        "name": "add_numbers",
        "description": "Adds two numbers together.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"}
            },
            "required": ["a", "b"],
            "additionalProperties": False
        },
        "strict": True  # Ensures the model strictly follows the schema
    }
}]

# User message that triggers a tool call
messages = [{"role": "user", "content": "What is 5 + 7?"}]

# First request to model: it decides whether to call a function
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools
)

response_message = completion.choices[0].message

# If the model calls a tool, extract the function name & arguments
if response_message.tool_calls:
    tool_call = response_message.tool_calls[0]  # First tool call instance
    tool_name = tool_call.function.name  # Name of function being called
    args = json.loads(tool_call.function.arguments)  # Extract arguments

    # Execute tool function manually
    if tool_name == "add_numbers":
        result = args["a"] + args["b"]  # Simple addition

        # Append the tool response to messages & send back to model for final reply
        messages.append(response_message)  # Store model's function call message
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(result)})

        final_completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools
        )

        print(final_completion.choices[0].message.content)  # Model incorporates tool result
