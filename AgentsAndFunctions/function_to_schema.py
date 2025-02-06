import openai
import inspect
import datetime
import os
from typing import Any, Callable, Tuple, Union


# converts any(tm) python function to a schema
# Shamelessly stolen from https://cookbook.openai.com/examples/orchestrating_agents

def function_to_schema(func) -> dict:
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    try:
        signature = inspect.signature(func)
    except ValueError as e:
        raise ValueError(
            f"Failed to get signature for function {func.__name__}: {str(e)}"
        )

    parameters = {}
    for param in signature.parameters.values():
        try:
            param_type = type_map.get(param.annotation, "string")
        except KeyError as e:
            raise KeyError(
                f"Unknown type annotation {param.annotation} for parameter {param.name}: {str(e)}"
            )
        parameters[param.name] = {"type": param_type}

    required = [
        param.name
        for param in signature.parameters.values()
        if param.default == inspect._empty
    ]

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": (func.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required,
            },
        },
    }



def is_function_schema_compatible(
    func: Callable, 
    and_parse: bool = False, 
    verbose: bool = False
) -> Union[bool, Tuple[bool, str], Tuple[bool, dict]]:
    """
    Checks if a Python function is compatible with function_to_schema.
    
    Parameters:
        func (Callable): The function to check.
        and_parse (bool): If True, returns the schema if compatible.
        verbose (bool): If True, returns disqualifying reasons if incompatible.
    
    Returns:
        bool: True if compatible, False if not.
        (bool, str): If verbose=True, includes reasons for incompatibility.
        (bool, dict): If and_parse=True and compatible, includes schema.
    """

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    disqualifiers = []

    # === Step 1: Ensure it's a valid function ===
    if not callable(func):
        return (False, "Provided object is not a function.") if verbose else False

    # === Step 2: Check function signature ===
    try:
        signature = inspect.signature(func)
    except ValueError:
        return (False, f"Could not retrieve signature for {func.__name__}.") if verbose else False

    # === Step 3: Check for missing or unsupported type hints ===
    parameters = {}
    for param in signature.parameters.values():
        if param.annotation == inspect._empty:
            disqualifiers.append(f"Parameter '{param.name}' is missing a type annotation.")
        elif param.annotation not in type_map:
            if not isinstance(param.annotation, type):
                disqualifiers.append(f"Parameter '{param.name}' has an unrecognized type annotation: {param.annotation}.")
            elif issubclass(param.annotation, (tuple, set, complex, datetime.datetime)):
                disqualifiers.append(f"Parameter '{param.name}' has an unsupported type: {param.annotation}.")

    # === Step 4: Detect problematic argument types ===
    if any(param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD} for param in signature.parameters.values()):
        disqualifiers.append("Function uses *args or **kwargs, which are not supported.")

    # === Step 5: Detect interactive functions ===
    source_code = inspect.getsource(func)
    if "input(" in source_code:
        disqualifiers.append("Function contains an input() call, which requires user interaction.")

    # === Step 6: Check return type ===
    if signature.return_annotation not in type_map and signature.return_annotation != inspect._empty:
        if isinstance(signature.return_annotation, type) and not issubclass(signature.return_annotation, (tuple, set, complex, datetime.datetime)):
            pass  # Allowed return type
        else:
            disqualifiers.append(f"Return type '{signature.return_annotation}' is unsupported.")

    # === Step 7: Return results ===
    is_compatible = not disqualifiers

    # If and_parse is True and function is compatible, return the schema
    if is_compatible and and_parse:
        try:
            schema = function_to_schema(func)
            return (True, schema)
        except Exception as e:
            return (False, f"Function is structurally valid but failed to convert: {str(e)}") if verbose else False

    # If verbose, return a list of disqualifiers
    if verbose:
        return (is_compatible, "; ".join(disqualifiers))

    return is_compatible


def analyze_and_improve_function(func):
    """
    !Note! Requires OpenAI or DeepSeek API key. 

    Submits a Python function to OpenAI's chat.completions.create for analysis and revision.
    
    The AI performs two reasoning passes:
    1. Analyzing the function's purpose and compatibility with function_to_schema.
    2. Suggesting improvements and providing a revised function if needed.
    
    Parameters:
        func (Callable): The function to analyze.
    
    Returns:
        str: AI-generated response containing analysis, recommendations, and revised function.
    """

    # Extract function source code
    try:
        func_source = inspect.getsource(func)
    except Exception as e:
        return f"Error retrieving function source: {str(e)}"

    # OpenAI system prompt
    system_prompt = (
        "You are an expert Python developer with deep knowledge of OpenAI's function calling system.\n"
        "First, clearly explain how the function_to_schema conversion process works:\n"
        "- It converts Python functions into JSON-compatible schemas.\n"
        "- It extracts the function name, docstring, parameters, and required fields.\n"
        "- It maps Python types to JSON schema types.\n"
        "- It does NOT support *args, **kwargs, interactive input(), or non-serializable types like datetime, complex, or tuples.\n"
        "\n"
        "Now, your role:\n"
        "1️⃣ The user will submit a Python function.\n"
        "2️⃣ Your job is to analyze it and determine its purpose.\n"
        "3️⃣ Check if it is currently compatible with function_to_schema.\n"
        "4️⃣ If it is NOT compatible, explain why and suggest improvements.\n"
        "5️⃣ In the second reasoning pass, provide a fully revised function that is compatible with function_to_schema.\n"
        "6️⃣ Make the function improvements clear, while maintaining the original intent of the function.\n"
        "7️⃣ Ensure that all output is structured, clear, and readable.\n"
    )

    # Submit function to OpenAI's completion endpoint
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the function:\n```python\n{func_source}\n```"}
        ],
        temperature=0.3,  # Keep temperature low for structured, logical reasoning
        max_tokens=1000
    )

    return response.choices[0].message.content



# First draft at complete python conversion tool. 
def read_python_file(file_path):
    """Reads a Python file and returns its content as a string."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def analyze_python_script(file_path):
    """
    Analyzes a Python script, extracts functions, determines its purpose, and proposes a tool breakdown.
    
    Parameters:
        file_path (str): Path to the Python file.
    
    Returns:
        dict: Analysis, pseudocode breakdown, and function recommendations.
    """
    script_content = read_python_file(file_path)

    system_prompt = (
        "You are an expert Python developer and AI tool orchestration specialist.\n"
        "Your task is to analyze a full Python script, determine its overall purpose, and extract key functions that can be modularized into OpenAI-compatible tools.\n\n"
        "### Instructions:\n"
        "1️⃣ Identify the **overall goal** of the script.\n"
        "2️⃣ Extract and summarize **major functions**.\n"
        "3️⃣ Determine how the script can be **broken into separate tools**.\n"
        "4️⃣ Provide a **pseudocode outline** of the tools that could be created.\n"
        "5️⃣ Make a **recommendation**: Should this script be modularized into tools?\n"
        "6️⃣ Keep responses structured, logical, and formatted for clarity.\n"
    )

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the script:\n```python\n{script_content}\n```"}
        ],
        temperature=0.3,
        max_tokens=1500
    )

    return response.choices[0].message.content

def create_tools_from_analysis(script_analysis, file_path):
    """
    Guides the user through confirming tool generation and creates tools based on AI recommendations.
    
    Parameters:
        script_analysis (str): The AI's analysis and proposed tool breakdown.
        file_path (str): Path to the original script.
    """
    print("\n--- AI Analysis of Python Script ---")
    print(script_analysis)
    
    user_response = input("\nWould you like to generate these tools? (y/n): ").strip().lower()
    if user_response != "y":
        print("Exiting without modifications.")
        return

    # Step 1: Extract tool suggestions
    system_prompt = (
        "You are an AI developer assistant specializing in Python function modularization.\n"
        "The user has approved breaking a script into tools.\n"
        "You will receive a tool name, a description, and the script's overall purpose.\n"
        "Your task is to generate a valid Python function that follows OpenAI's function schema rules:\n"
        "- It must have type annotations.\n"
        "- It must not use *args or **kwargs.\n"
        "- It must return JSON-compatible outputs (dict, list, str, int, float, bool, None).\n"
        "Return a fully implemented function that adheres to these guidelines."
    )

    tools = extract_tools_from_analysis(script_analysis)  # Function to extract tool breakdown from analysis
    final_tool_definitions = []

    client = openai.OpenAI()

    for tool in tools:
        tool_prompt = (
            f"The script is intended to achieve the following goal:\n{tool['script_purpose']}\n\n"
            f"Here is a tool that should be created:\n"
            f"- **Tool Name**: {tool['name']}\n"
            f"- **Description**: {tool['description']}\n"
            f"- **Inputs**: {tool['inputs']}\n"
            f"- **Expected Output**: {tool['output']}\n"
            "Generate a complete Python function that meets these requirements."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": tool_prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )

        generated_function = response.choices[0].message.content
        print(f"\nGenerated Function for {tool['name']}:\n")
        print(generated_function)

        # Step 2: Validate function
        exec_globals = {}
        try:
            exec(generated_function, exec_globals)  # Execute to get function object
            generated_func = next(val for val in exec_globals.values() if callable(val))
            
            compatible, compatibility_report = is_function_schema_compatible(generated_func, verbose=True)
            if not compatible:
                print(f"\n⚠️ Function {tool['name']} is NOT schema-compatible: {compatibility_report}\n")
                continue
        except Exception as e:
            print(f"\n⚠️ Error testing function {tool['name']}: {str(e)}\n")
            continue

        final_tool_definitions.append(generated_function)

    # Step 3: Write tools to a new Python file
    if final_tool_definitions:
        new_file_path = file_path.replace(".py", "_tools.py")
        with open(new_file_path, "w", encoding="utf-8") as f:
            for function_def in final_tool_definitions:
                f.write(function_def + "\n\n")

        print(f"\n✅ Tools successfully written to {new_file_path}")

def extract_tools_from_analysis(script_analysis):
    """
    Parses the AI's analysis to extract suggested tools.
    
    Parameters:
        script_analysis (str): The AI's analysis response.
    
    Returns:
        list: A list of dictionaries containing tool details.
    """
    # Placeholder: This function should parse the analysis text and extract tool suggestions.
    # Ideally, you'd use regex or NLP to extract structured tool names, descriptions, and expected inputs/outputs.
    # For now, this will return a mocked list.
    
    return [
        {
            "name": "process_data",
            "description": "Processes and cleans raw data inputs.",
            "inputs": ["data: list[str]"],
            "output": "dict with cleaned data",
            "script_purpose": "This script processes user-provided data and formats it for further analysis."
        },
        {
            "name": "generate_summary",
            "description": "Generates a textual summary from structured data.",
            "inputs": ["data: dict"],
            "output": "str with a summary",
            "script_purpose": "This script generates a natural language summary of structured data."
        }
    ]

# === Main Execution ===
if __name__ == "__main__":
    file_path = input("Enter the path to the Python script: ").strip()
    
    try:
        script_analysis = analyze_python_script(file_path)
        create_tools_from_analysis(script_analysis, file_path)
    except Exception as e:
        print(f"Error: {str(e)}")
