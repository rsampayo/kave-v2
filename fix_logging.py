#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

# Pattern to match logger calls with f-strings
# This is a simplistic approach and may need refinement
pattern = re.compile(r'(logger\.\w+)\(f["\'](.+?)["\'](.+)?\)')


def fix_logging_in_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Count matches before fixing
    matches = pattern.findall(content)
    if not matches:
        return 0

    # Replace f-string logging with % formatting
    def replace_fstring(match):
        logger_call = match.group(1)
        message = match.group(2)
        args = match.group(3) if match.group(3) else ""

        # Replace {var} with %s
        message_replaced = re.sub(r"\{([^{}]+?)\}", "%s", message)

        # Extract variables from {}
        variables = re.findall(r"\{([^{}]+?)\}", message)
        if not variables:
            return f"{logger_call}({message_replaced!r}{args})"

        # Build the new arguments
        new_args = ", ".join(var.strip() for var in variables)
        if args and args.strip():
            return f"{logger_call}({message_replaced!r}, {new_args}{args})"
        else:
            return f"{logger_call}({message_replaced!r}, {new_args})"

    modified_content = pattern.sub(replace_fstring, content)

    # Only write if changes were made
    if modified_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(modified_content)
        return len(matches)
    return 0


def process_directory(directory):
    total_fixed = 0
    for path in Path(directory).rglob("*.py"):
        fixed = fix_logging_in_file(path)
        if fixed:
            print(f"Fixed {fixed} logging issues in {path}")
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
    print(f"Total logging issues fixed: {total}")
