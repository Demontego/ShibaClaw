import json
from typing import Any, Dict

def generate_example_value(schema: Dict[str, Any]) -> Any:
    """Generates a dummy/example value based on a JSON schema property."""
    prop_type = schema.get("type")
    if isinstance(prop_type, list):
        # Extract first non-null type
        prop_type = next((t for t in prop_type if t != "null"), "string")
        
    if prop_type == "string":
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]
        return "example_value"
    elif prop_type == "integer":
        return 123
    elif prop_type == "number":
        return 45.67
    elif prop_type == "boolean":
        return True
    elif prop_type == "array":
        items_schema = schema.get("items", {})
        return [generate_example_value(items_schema)]
    elif prop_type == "object":
        properties = schema.get("properties", {})
        return {k: generate_example_value(v) for k, v in properties.items()}
    return None

def format_structured_error_feedback(tool_name: str, error_msg: str, schema: Dict[str, Any]) -> str:
    """
    Formats a highly structured, helpful feedback message for a failed tool call.
    Includes the error, the expected JSON schema, and a concrete example of a correct call.
    """
    # Generate example arguments
    properties = schema.get("properties", {})
    example_args = {k: generate_example_value(v) for k, v in properties.items()}
    
    schema_pretty = json.dumps(schema, indent=2, ensure_ascii=False)
    example_pretty = json.dumps(example_args, indent=2, ensure_ascii=False)
    
    return (
        f"Error: Tool '{tool_name}' failed: {error_msg}\n\n"
        f"Please correct your arguments according to the expected JSON schema below and retry.\n\n"
        f"Expected Parameter Schema:\n"
        f"```json\n{schema_pretty}\n```\n\n"
        f"Example of a correct call:\n"
        f"```json\n{{\n  \"name\": \"{tool_name}\",\n  \"arguments\": {example_pretty}\n}}\n```"
    )
