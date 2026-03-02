import glob
import os

for filepath in glob.glob('tests/*.py'):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace open(..., 'r') with open(..., 'r', encoding='utf-8')
    new_content = content.replace(", 'r')", ", 'r', encoding='utf-8')")
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Patched {filepath}")
print("Done patching.")
