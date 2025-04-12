#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path


def fix_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed_count = 0
    result = []
    i = 0
    indent_stack = []

    # Buffer to track if we're in a potential else-after-return situation
    in_if_block = False
    if_indent_level = 0
    has_return = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Track indentation level
        if stripped and not stripped.startswith("#"):
            indent_level = len(line) - len(line.lstrip())

            # Check for if statement
            if re.match(r"\s*if\s+.*:", line):
                in_if_block = True
                if_indent_level = indent_level
                indent_stack.append(indent_level)

            # Check for return statement in if block
            elif in_if_block and re.match(r"\s*return\s+.*", line):
                has_return = True

            # Check for else or elif after an if block with return
            elif (
                has_return
                and in_if_block
                and re.match(r"\s*else\s*:", line)
                and indent_level == if_indent_level
            ):
                # Skip the else line
                fixed_count += 1
                i += 1
                # Process the next lines at a deeper indentation level
                while i < len(lines) and (
                    not lines[i].strip()
                    or len(lines[i]) - len(lines[i].lstrip()) > indent_level
                ):
                    # Adjust indentation
                    current_line = lines[i]
                    if current_line.strip():
                        # Reduce indentation by 4 spaces (or 1 tab)
                        current_indent = len(current_line) - len(current_line.lstrip())
                        new_indent = max(current_indent - 4, indent_level)
                        current_line = " " * new_indent + current_line.lstrip()
                    result.append(current_line)
                    i += 1

                # Reset tracking
                in_if_block = False
                has_return = False
                continue

            # Check for elif after an if block with return
            elif (
                has_return
                and in_if_block
                and re.match(r"\s*elif\s+.*:", line)
                and indent_level == if_indent_level
            ):
                # Change elif to if
                fixed_count += 1
                result.append(line.replace("elif", "if"))
                i += 1
                continue

            # End of if block
            elif in_if_block and indent_level <= if_indent_level:
                in_if_block = False
                has_return = False

        result.append(line)
        i += 1

    # Only write if changes were made
    if fixed_count > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(result)

    return fixed_count


def process_directory(directory):
    total_fixed = 0
    for path in Path(directory).rglob("*.py"):
        fixed = fix_file(path)
        if fixed:
            print(f"Fixed {fixed} unnecessary else/elif after return in {path}")
            total_fixed += fixed
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
    print(f"Total unnecessary else/elif after return fixed: {total}")
