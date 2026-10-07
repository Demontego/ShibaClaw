
import yaml
import os

def validate_manifest(skill_path):
    skill_md_path = os.path.join(skill_path, 'SKILL.md')
    
    if not os.path.exists(skill_md_path):
        return False, f"Error: SKILL.md not found in {skill_path}"

    with open(skill_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract YAML frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) > 2:
            frontmatter_str = parts[1]
            try:
                frontmatter = yaml.safe_load(frontmatter_str)
                if not isinstance(frontmatter, dict):
                    return False, "Error: SKILL.md frontmatter is not a valid YAML dictionary."
                
                required_fields = ['name', 'description']
                for field in required_fields:
                    if field not in frontmatter:
                        return False, f"Error: Missing required field '{field}' in SKILL.md frontmatter."
                
                return True, "SKILL.md manifest is valid."
            except yaml.YAMLError as e:
                return False, f"Error parsing YAML frontmatter in SKILL.md: {e}"
        else:
            return False, "Error: SKILL.md does not contain valid YAML frontmatter delimiters (---)."
    else:
        return False, "Error: SKILL.md does not start with YAML frontmatter (---)."

if __name__ == '__main__':
    if len(os.sys.argv) < 2:
        print("Usage: python validate_manifest.py <skill_path>")
        os.sys.exit(1)
    
    skill_path = os.sys.argv[1]
    is_valid, message = validate_manifest(skill_path)
    print(message)
    if not is_valid:
        os.sys.exit(1)
