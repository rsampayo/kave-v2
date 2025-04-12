#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path


def get_module_name(file_path):
    """Extract module name from file path."""
    parts = str(file_path).split(os.sep)

    # Extract the module name without .py extension
    module_name = os.path.splitext(parts[-1])[0]

    # Convert snake_case to Title Case
    module_name = " ".join(word.capitalize() for word in module_name.split("_"))

    # Get package context from directory
    package_context = ""
    if len(parts) > 2:
        if "app" in parts:
            app_index = parts.index("app")
            if len(parts) > app_index + 2:  # We have at least one subpackage
                package_context = " for the " + " ".join(
                    parts[app_index + 1 : -1]
                ).replace("_", " ")

    return module_name, package_context


def add_docstring_to_file(file_path):
    """Add a module docstring to a file if it doesn't have one."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if there's already a docstring at the module level
    module_with_docstring_pattern = re.compile(
        r'^("""|\'\'\')[\s\S]+?("""|\'\'\')', re.MULTILINE
    )
    if module_with_docstring_pattern.search(content):
        return False

    # Check for imports or code at the beginning
    has_leading_code = bool(
        re.match(r"^(import|from|[a-zA-Z_])", content, re.MULTILINE)
    )

    # Get module name for docstring
    module_name, package_context = get_module_name(file_path)

    # Create docstring
    docstring = (
        f'"""Module providing {module_name} functionality{package_context}."""\n\n'
    )

    # Add docstring at the beginning of the file
    if has_leading_code:
        modified_content = docstring + content
    else:
        modified_content = content.lstrip() + "\n" + docstring

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(modified_content)

    return True


def process_directory(directory):
    """Process all Python files in a directory recursively."""
    total_fixed = 0
    for path in Path(directory).rglob("*.py"):
        if add_docstring_to_file(path):
            print(f"Added docstring to {path}")
            total_fixed += 1
    return total_fixed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory")
        sys.exit(1)

    total = process_directory(directory)
    print(f"Total docstrings added: {total}")
