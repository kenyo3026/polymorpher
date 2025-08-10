#!/usr/bin/env python3
import argparse
from pathlib import Path

def clean_blank_lines(content: str) -> str:
    """
    Remove tabs/spaces from lines that are otherwise blank.
    """
    lines = content.split("\n")
    cleaned_lines = [
        "" if line.strip() == "" else line
        for line in lines
    ]
    return "\n".join(cleaned_lines)

def process_file(file_path: Path):
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return

    original_content = file_path.read_text(encoding="utf-8")
    cleaned_content = clean_blank_lines(original_content)

    file_path.write_text(cleaned_content, encoding="utf-8")
    print(f"✅ Cleaned and saved: {file_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Remove tabs/spaces from otherwise blank lines in one or more files."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more file paths to process"
    )

    args = parser.parse_args()

    for file in args.files:
        process_file(Path(file))

if __name__ == "__main__":
    main()
