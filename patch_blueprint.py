import os
import re

directories_to_scan = [
    '/home/abbas/development/pcd-v32/app/module3',
    '/home/abbas/development/pcd-v32/app/templates/module3',
]

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = re.sub(r"url_for\([\"']routes\.", "url_for('module3.", content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Patched: {filepath}")

for directory in directories_to_scan:
    if os.path.exists(directory):
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(('.py', '.html', '.js')):
                    filepath = os.path.join(root, file)
                    patch_file(filepath)
print("Finished blueprint rename patching.")
