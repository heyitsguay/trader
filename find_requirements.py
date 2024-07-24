import os
import re
import subprocess

def find_imports_in_file(file_path):
    imports = set()
    with open(file_path, 'r') as file:
        for line in file:
            match = re.match(r'^\s*(import|from)\s+([\w.]+)', line)
            if match:
                module = match.group(2).split('.')[0]
                imports.add(module)
    return imports

def find_imports_in_project(directory):
    imports = set()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                imports.update(find_imports_in_file(file_path))
    return imports

def write_requirements_file(imports, output_file='requirements.txt'):
    with open(output_file, 'w') as file:
        for i in imports:
            file.write(f"{i}\n")

if __name__ == '__main__':
    project_directory = '.'  # Change this to your project directory
    imports = find_imports_in_project(project_directory)
    write_requirements_file(imports)
    print(f"requirements.txt has been generated with {len(versions)} packages.")

