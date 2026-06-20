"""
fix_spec_for_prism.py - Remove external $ref links so Prism can mock locally
"""
import re

input_file = "specs/merged/full_spec.yaml"
output_file = "specs/merged/full_spec_local.yaml"

with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()

# Count external refs
external_refs = re.findall(r'\$ref: http://', content)
print(f"Found {len(external_refs)} external $ref links")

# Replace external HTTP $refs with generic 'type: object'
content = re.sub(r'\$ref: http://[^\n]+', 'type: object', content)
content = re.sub(r'security:\n(  - \{.*\}\n)+', '', content)

with open(output_file, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Saved cleaned spec to: {output_file}")
print(f"Now run: npx @stoplight/prism-cli@4.10.5 mock {output_file} -p 4000")
