from shibaclaw.agent.tools.error_feedback import generate_example_value, format_structured_error_feedback

def test_generate_example_value():
    # String schema
    assert generate_example_value({"type": "string"}) == "example_value"
    assert generate_example_value({"type": "string", "enum": ["val1", "val2"]}) == "val1"
    
    # Integer/Number schema
    assert generate_example_value({"type": "integer"}) == 123
    assert generate_example_value({"type": "number"}) == 45.67
    
    # Boolean schema
    assert generate_example_value({"type": "boolean"}) is True
    
    # Array schema
    assert generate_example_value({"type": "array", "items": {"type": "string"}}) == ["example_value"]
    
    # Object schema
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        }
    }
    assert generate_example_value(schema) == {"name": "example_value", "age": 123}

def test_format_structured_error_feedback():
    tool_name = "read_file"
    error_msg = "File not found"
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to read"},
        },
        "required": ["path"],
    }
    
    feedback = format_structured_error_feedback(tool_name, error_msg, schema)
    
    assert "Error: Tool 'read_file' failed: File not found" in feedback
    assert "Expected Parameter Schema:" in feedback
    assert "Example of a correct call:" in feedback
    assert '"path": "example_value"' in feedback
