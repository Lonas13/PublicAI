from openai import OpenAI
import json

client = OpenAI()

# Define a simple tool (function schema) that fetches the current weather
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Retrieve the current weather for a location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City and country e.g. Paris, France"}
            },
            "required": ["location"],
            "additionalProperties": False
        },
        "strict": True  # Enforces strict parameter validation
    }
}]

# Send user query to model
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's the weather like in Tokyo?"}],
    tools=tools
)

# Extract function call details
tool_call = completion.choices[0].message.tool_calls[0]  # Correctly access the tool call object
args = json.loads(tool_call.function.arguments)  # Use dot notation

# Simulated function execution (replace with actual API call)
def get_weather(location):
    return f"The weather in {location} is 22°C and sunny."

# Call the function and print the result
print(get_weather(args["location"]))
