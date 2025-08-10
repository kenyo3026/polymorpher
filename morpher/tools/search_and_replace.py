import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union


class OutputStyle(Enum):
    """Output formatting styles"""
    DEFAULT = "default"
    GIT_DIFF = "git_diff"
    GIT_CONFLICT = "git_conflict"

class ExecutionMode(Enum):
    """Execution modes"""
    PREVIEW = "preview"
    APPLY = "apply"

@dataclass
class LineMatch:
    """Represents a line that matches the search pattern"""
    line_number: int
    original_line: str
    replacement_lines: List[str]

@dataclass
class FileResult:
    """Results for a single file"""
    file_path: Path
    matches: List[LineMatch] = field(default_factory=list)

    @property
    def has_matches(self) -> bool:
        return len(self.matches) > 0

    @property
    def total_matches(self) -> int:
        return len(self.matches)

@dataclass
class SearchReplaceConfig:
    """Configuration for search and replace operation"""
    search: str
    replace: Union[str, List[str]]
    file_pattern: str = "*"
    case_sensitive: bool = True
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    def __post_init__(self):
        # Normalize replacement to list of lines
        if isinstance(self.replace, str):
            self.replace = self.replace.split('\n')

@dataclass
class SearchReplaceResult:
    """Complete search and replace results"""
    config: SearchReplaceConfig
    file_results: List[FileResult] = field(default_factory=list)

    @property
    def total_files_with_matches(self) -> int:
        return sum(1 for fr in self.file_results if fr.has_matches)

    @property
    def total_matches(self) -> int:
        return sum(fr.total_matches for fr in self.file_results)

class LineSearcher:
    """Handles line-based exact matching"""

    def __init__(self, config: SearchReplaceConfig):
        self.config = config

    def find_matches(self, content: str) -> List[LineMatch]:
        """Find all matching lines in content"""
        lines = content.split('\n')
        matches = []

        # Determine search range
        start_idx = (self.config.start_line - 1) if self.config.start_line else 0
        end_idx = (self.config.end_line - 1) if self.config.end_line else len(lines) - 1
        start_idx = max(0, start_idx)
        end_idx = min(len(lines) - 1, end_idx)

        # Check if search pattern is multi-line
        search_lines = self.config.search.split('\n')
        is_multiline_search = len(search_lines) > 1

        if is_multiline_search:
            matches = self._find_multiline_matches(lines, search_lines, start_idx, end_idx)
        else:
            matches = self._find_single_line_matches(lines, start_idx, end_idx)

        return matches

    def _find_single_line_matches(self, lines: List[str], start_idx: int, end_idx: int) -> List[LineMatch]:
        """Find single line matches"""
        matches = []
        for i in range(start_idx, end_idx + 1):
            line = lines[i]
            if self._line_matches(line, self.config.search):
                match = LineMatch(
                    line_number=i + 1,
                    original_line=line,
                    replacement_lines=self.config.replace.copy()
                )
                matches.append(match)
        return matches

    def _find_multiline_matches(self, lines: List[str], search_lines: List[str], start_idx: int, end_idx: int) -> List[LineMatch]:
        """Find multi-line matches"""
        matches = []
        search_line_count = len(search_lines)

        # Slide through the lines looking for multi-line matches
        i = start_idx
        while i <= end_idx - search_line_count + 1:
            # Check if the next N lines match the search pattern
            candidate_lines = lines[i:i + search_line_count]
            if len(candidate_lines) == search_line_count and self._multiline_matches(candidate_lines, search_lines):
                # Create a match that represents multiple lines
                original_content = '\n'.join(candidate_lines)
                match = LineMatch(
                    line_number=i + 1,  # Start line number
                    original_line=original_content,  # Store all matched lines
                    replacement_lines=self.config.replace.copy()
                )
                matches.append(match)

                # Skip the matched lines to avoid overlapping matches
                i += search_line_count
            else:
                i += 1

        return matches

    def _multiline_matches(self, candidate_lines: List[str], search_lines: List[str]) -> bool:
        """Check if multiple lines match the search pattern"""
        if len(candidate_lines) != len(search_lines):
            return False

        for candidate_line, search_line in zip(candidate_lines, search_lines):
            if not self._line_matches(candidate_line, search_line):
                return False
        return True

    def _line_matches(self, line: str, search: str) -> bool:
        """Check if a line matches the search pattern"""
        # For exact line matching, we compare the stripped versions
        # but this can be made more flexible in the future
        line_to_check = line.strip()
        search_to_check = search.strip()

        if not self.config.case_sensitive:
            return search_to_check.lower() == line_to_check.lower()
        return search_to_check == line_to_check


class OutputFormatter:
    """Handles different output formatting styles"""

    @staticmethod
    def format_default(file_result: FileResult) -> str:
        """Generate complete modified file content"""
        if not file_result.has_matches:
            # Return original content if no matches
            try:
                with open(file_result.file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                return ""

        # Read original content and apply replacements
        try:
            with open(file_result.file_path, 'r', encoding='utf-8') as f:
                lines = f.read().split('\n')
        except:
            return ""

        # Apply replacements from bottom to top to maintain line numbers
        for match in reversed(file_result.matches):
            line_idx = match.line_number - 1

            # Check if this is a multi-line match
            original_lines = match.original_line.split('\n')
            lines_to_replace = len(original_lines)

            if 0 <= line_idx < len(lines):
                # Replace the matched lines with replacement lines
                lines[line_idx:line_idx + lines_to_replace] = match.replacement_lines

        return '\n'.join(lines)

    @staticmethod
    def format_git_diff(file_result: FileResult) -> str:
        """Generate git diff style output"""
        if not file_result.has_matches:
            return ""

        output = []
        output.append(f"diff --git a/{file_result.file_path} b/{file_result.file_path}")
        output.append("index 0000000..0000000 100644")
        output.append(f"--- a/{file_result.file_path}")
        output.append(f"+++ b/{file_result.file_path}")

        for match in file_result.matches:
            line_num = match.line_number
            output.append(f"@@ -{line_num},1 +{line_num},{len(match.replacement_lines)} @@")
            output.append(f"-{match.original_line}")
            for replacement_line in match.replacement_lines:
                output.append(f"+{replacement_line}")

        return '\n'.join(output)

    @staticmethod
    def format_git_conflict(file_result: FileResult) -> str:
        """Generate git conflict style output for VS Code rendering"""
        if not file_result.has_matches:
            return OutputFormatter.format_default(file_result)

        try:
            with open(file_result.file_path, 'r', encoding='utf-8') as f:
                lines = f.read().split('\n')
        except:
            return ""

        # Apply conflict markers from bottom to top
        for match in reversed(file_result.matches):
            line_idx = match.line_number - 1

            # Check if this is a multi-line match
            original_lines = match.original_line.split('\n')
            lines_to_replace = len(original_lines)

            if 0 <= line_idx < len(lines):
                conflict_block = ["<<<<<<< HEAD"] + original_lines + ["======="] + match.replacement_lines + [">>>>>>> incoming"]
                lines[line_idx:line_idx + lines_to_replace] = conflict_block

        return '\n'.join(lines)

class SearchReplaceEngine:
    """Main search and replace engine"""

    def __init__(self):
        self.formatter = OutputFormatter()

    def search_and_replace(
        self,
        file: Union[str, Path],
        search: str,
        replace: Union[str, List[str]],
        mode: str = "apply",
        output_style: str = "default",
        output_file: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> SearchReplaceResult:
        """
        Main entry point for search and replace operations

        Args:
            file: File or directory to search
            search: Exact line to search for
            replace: Replacement text (can be multiline)
            mode: "preview" or "apply"
            output_style: "default", "git_diff", or "git_conflict"
            output_file: Optional output file path (for apply mode)
            **kwargs: Additional configuration options
        """
        # Check if search and replace are identical
        if self._is_search_replace_identical(search, replace):
            print("ℹ️  Search and replace patterns are identical - no changes needed.")
            # Create empty result
            config = SearchReplaceConfig(search=search, replace=replace, **kwargs)
            return SearchReplaceResult(config=config)

        # Create configuration
        config = SearchReplaceConfig(
            search=search,
            replace=replace,
            **kwargs
        )

        # Find files to process
        target_path = Path(file)
        files_to_process = self._find_files(target_path, config.file_pattern)

        # Process each file
        result = SearchReplaceResult(config=config)
        searcher = LineSearcher(config)

        for file_path in files_to_process:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                matches = searcher.find_matches(content)
                file_result = FileResult(file_path=file_path, matches=matches)
                result.file_results.append(file_result)

            except Exception as e:
                print(f"Error processing {file_path}: {e}")

        # Handle output based on mode
        execution_mode = ExecutionMode(mode.lower())
        style = OutputStyle(output_style.lower())

        if execution_mode == ExecutionMode.PREVIEW:
            self._handle_preview(result, style)
        else:  # APPLY
            self._handle_apply(result, style, output_file)

        return result

    def _is_search_replace_identical(self, search: str, replace: Union[str, List[str]]) -> bool:
        """Check if search and replace patterns are identical"""
        # Normalize replace to string
        if isinstance(replace, list):
            replace_str = '\n'.join(replace)
        else:
            replace_str = replace

        # Compare normalized patterns
        return search.strip() == replace_str.strip()

    def _find_files(self, target_path: Path, pattern: str) -> List[Path]:
        """Find files matching the pattern"""
        if target_path.is_file():
            return [target_path]

        if target_path.is_dir():
            return list(target_path.rglob(pattern))

        raise FileNotFoundError(f"Path not found: {target_path}")

    def _handle_preview(self, result: SearchReplaceResult, style: OutputStyle):
        """Handle preview mode output"""
        for file_result in result.file_results:
            if not file_result.has_matches:
                continue

            print(f"\n{'='*60}")
            print(f"File: {file_result.file_path}")
            print(f"Matches: {file_result.total_matches}")
            print('='*60)

            if style == OutputStyle.DEFAULT:
                print(self.formatter.format_default(file_result))
            elif style == OutputStyle.GIT_DIFF:
                print(self.formatter.format_git_diff(file_result))
            elif style == OutputStyle.GIT_CONFLICT:
                print(self.formatter.format_git_conflict(file_result))

    def _handle_apply(self, result: SearchReplaceResult, style: OutputStyle, output_file: Optional[Path]):
        """Handle apply mode output"""
        for file_result in result.file_results:
            if not file_result.has_matches:
                continue

            # Determine output path
            if output_file:
                target_path = Path(output_file)
            else:
                target_path = file_result.file_path

            # Generate content based on style
            if style == OutputStyle.DEFAULT:
                content = self.formatter.format_default(file_result)
            elif style == OutputStyle.GIT_DIFF:
                content = self.formatter.format_git_diff(file_result)
                # For git diff, save to .diff file
                target_path = target_path.with_suffix('.diff')
            elif style == OutputStyle.GIT_CONFLICT:
                content = self.formatter.format_git_conflict(file_result)

            # Write to file
            try:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Applied changes to: {target_path}")
            except Exception as e:
                print(f"Error writing to {target_path}: {e}")

def search_and_ask_replace(
    file: Union[str, Path],
    search: str,
    replace: Union[str, List[str]],
    output_style: str = "default",
    output_file: Optional[Union[str, Path]] = None,
    **kwargs
):
    """
    Interactive search and replace - preview first, then ask for confirmation.

    This function first shows a preview of all changes that would be made,
    then prompts the user for confirmation before applying them.

    Args:
        file: Target file or directory path to search in
        search: Exact line(s) to find. Use '\\n' for consecutive multi-line patterns
        replace: Replacement content. Can be multiline string or empty string for deletion
        output_style: Output formatting style:
            - "default": Complete modified file content
            - "git_diff": Git diff style output  
            - "git_conflict": Git conflict markers (VS Code compatible)
        output_file: Custom output path (None = modify original file)
        **kwargs: Additional options:
            - case_sensitive (bool): Case sensitive search (default: True)
            - start_line (int): Start line number for search range (1-based)
            - end_line (int): End line number for search range (1-based)
            - file_pattern (str): File pattern for directory search (default: "*")

    Returns:
        Union[SearchReplaceResult, str]: 
            - SearchReplaceResult if changes are applied or no matches found
            - str with cancellation message if user declines or interrupts

    User Interaction:
        - Shows preview of changes with match statistics
        - Prompts: "Apply these changes? (y [YES] | n [NO]): "
        - Accepts: 'y', 'yes', 'true', 'apply' to confirm
        - Accepts: 'n', 'no', 'false', 'cancel' to decline
        - Handles Ctrl+C and EOF gracefully

    Examples:
        # Basic interactive (preview and ask) replacement
        result = search_and_ask_replace("file.txt", "old line", "new line")

        # With git conflict style
        result = search_and_ask_replace("file.txt", "old", "new", 
                                       output_style="git_conflict")

        # Multi-line replacement with confirmation
        result = search_and_ask_replace("file.txt", "TODO\\nFIXME", 
                                       "COMPLETED\\nDONE")
    """
    engine = SearchReplaceEngine()
    preview_result = engine.search_and_replace(
        file=file,
        search=search,
        replace=replace,
        mode='preview',
        output_style=output_style,
        output_file=output_file,
        **kwargs
    )

    # Check if any matches were found
    if preview_result.total_matches == 0:
        print("❌ No matches found.")
        return preview_result

    print(f"\n📊 Found {preview_result.total_matches} match(es) in {preview_result.total_files_with_matches} file(s)")
    print("=" * 60)

    # Ask for confirmation
    while True:
        try:
            permission = input("Apply these changes? (y[YES]|n[NO]): ").strip()

            if permission.lower() in ['y', 'yes', 'true', 'apply']:
                # print("✅ Applying changes...")
                return engine.search_and_replace(
                    file=file,
                    search=search,
                    replace=replace,
                    mode='apply',
                    output_style=output_style,
                    output_file=output_file,
                    **kwargs
                )
            elif permission.lower() in ['n', 'no', 'false', 'cancel']:
                message = "❌ Changes cancelled by user."
                # print(message)
                return message
            else:
                message = "❓ Please enter 'Y'/'yes' to apply or 'N'/'no' to cancel."
                # print(message)
                continue
        except KeyboardInterrupt:
            message = "\n❌ Operation cancelled by user (Ctrl+C)."
            # print(message)
            return message
        except EOFError:
            message = "\n❌ Operation cancelled (EOF)."
            # print(message)
            return message

# Convenience function for direct usage
def search_and_replace(
    file: Union[str, Path],
    search: str,
    replace: Union[str, List[str]],
    mode: str = "apply",
    output_style: str = "default",
    output_file: Optional[Union[str, Path]] = None,
    **kwargs
) -> SearchReplaceResult:
    """
    Search for specific text patterns in files and replace them with new content. 

    Features:
    - One-to-many: single line → multiple lines
    - Many-to-one: multiple lines → single line  
    - Deletion: replace with empty string ""
    - Line range targeting with start_line/end_line

    Args:
        file: Target file or directory path
        search: Exact line(s) to find. Use '\\n' for consecutive multi-line patterns
        replace: Replacement content. Empty string "" for deletion
        mode: Execution mode options:
            - "preview": Show changes without modifying files
            - "apply": Apply changes directly to files
            - "preview_and_ask": Preview first, then ask for confirmation
        output_style: Output formatting style:
            - "default": Complete modified file content
            - "git_diff": Git diff style output
            - "git_conflict": Git conflict markers (VS Code compatible)
        output_file: Custom output path (None = modify original)
        **kwargs: Additional options:
            - case_sensitive (bool): Case sensitive search (default: True)
            - start_line (int): Start line number (1-based)
            - end_line (int): End line number (1-based)  
            - file_pattern (str): File pattern for directory search (default: "*")

    Returns:
        SearchReplaceResult: Results with match statistics and file info

    Raises:
        ValueError: If invalid mode is specified
        FileNotFoundError: If target file/directory doesn't exist

    Examples:
        # Basic replacement
        search_and_replace("file.txt", "old line", "new line")

        # Preview mode
        search_and_replace("file.txt", "old line", "new line", mode="preview")

        # Interactive (preview and ask) mode with confirmation
        search_and_replace("file.txt", "old line", "new line", mode="preview_and_ask")

        # Delete lines
        search_and_replace("file.txt", "unwanted line", "", mode="apply")

        # One to many replacement
        search_and_replace("file.txt", "TODO", "Step 1\\nStep 2\\nStep 3", mode="apply")

        # Many to one replacement
        search_and_replace("file.txt", "Line 1\\nLine 2", "Single line", mode="apply")

        # With git conflict style for VS Code
        search_and_replace("file.txt", "old", "new", output_style="git_conflict")

        # Case insensitive with line range
        search_and_replace("file.txt", "OLD", "new", case_sensitive=False, 
                          start_line=10, end_line=50)
    """
    # Validate mode parameter
    valid_modes = ["preview", "apply", "preview_and_ask"]
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}")

    # Handle interactive (preview and ask) mode
    if mode == "preview_and_ask":
        return search_and_ask_replace(
            file=file,
            search=search,
            replace=replace,
            output_style=output_style,
            output_file=output_file,
            **kwargs
        )

    # Handle standard preview/apply modes
    engine = SearchReplaceEngine()
    return engine.search_and_replace(
        file=file,
        search=search,
        replace=replace,
        mode=mode,
        output_style=output_style,
        output_file=output_file,
        **kwargs
    )


if __name__ == "__main__":
    import argparse
    import tempfile

    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Search & Replace V2 - Line-based exact matching with multiple output styles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview mode with default output
  python search_replace_v2.py -f file.txt -s "old line" -r "new line" -m preview

  # Apply changes with git diff style
  python search_replace_v2.py -f file.txt -s "old line" -r "new line" -m apply --style git_diff

  # Apply with git conflict style for VS Code
  python search_replace_v2.py -f file.txt -s "old line" -r "new line" -m apply --style git_conflict

  # Preview with line range
  python search_replace_v2.py -f file.txt -s "old line" -r "new line" -m preview --start-line 10 --end-line 20

  # Run demo with test content (no arguments)
  python search_replace_v2.py
        """
    )

    parser.add_argument('-f', '--file', type=str, help='File or directory to search')
    parser.add_argument('-s', '--search', type=str, help='Text to search for (exact line match)')
    parser.add_argument('-r', '--replace', type=str, help='Replacement text (can be multiline with \\n)')
    parser.add_argument('-m', '--mode', choices=['preview', 'apply', 'preview_and_ask'], default='preview',
                       help='Execution mode (default: preview)')
    parser.add_argument('--style', choices=['default', 'git_diff', 'git_conflict'], default='default',
                       help='Output style (default: default)')
    parser.add_argument('-o', '--output-file', type=str, help='Output file path (for apply mode)')
    parser.add_argument('--file-pattern', type=str, default='*', help='File pattern to match (default: *)')
    parser.add_argument('--case-sensitive', action='store_true', default=True,
                       help='Case sensitive search (default: True)')
    parser.add_argument('--case-insensitive', action='store_true',
                       help='Case insensitive search')
    parser.add_argument('--start-line', type=int, help='Start line number (1-based)')
    parser.add_argument('--end-line', type=int, help='End line number (1-based)')

    args = parser.parse_args()

    # Handle case sensitivity
    case_sensitive = args.case_sensitive and not args.case_insensitive

    # If file and search parameters are provided, process the actual file
    if args.file and args.search and args.replace is not None:
        print(f"🔍 Processing file: {args.file}")
        print(f"Search: '{args.search}'")
        # Fix f-string backslash issue
        replace_display = args.replace.replace('\n', '\\n')
        print(f"Replace: '{replace_display}'")
        print(f"Mode: {args.mode}")
        print(f"Style: {args.style}")
        print(f"Case sensitive: {case_sensitive}")

        # Process replacement text (handle \n sequences)
        args.search = args.search.replace('\\n', '\n')
        args.replace = args.replace.replace('\\n', '\n')

        try:
            result = search_and_replace(
                file=args.file,
                search=args.search,
                replace=args.replace,
                mode=args.mode,
                output_style=args.style,
                output_file=args.output_file,
                file_pattern=args.file_pattern,
                case_sensitive=case_sensitive,
                start_line=args.start_line,
                end_line=args.end_line
            )

            print(f"\n📊 Results:")
            print(f"Total files processed: {len(result.file_results)}")
            print(f"Files with matches: {result.total_files_with_matches}")
            print(f"Total matches: {result.total_matches}")

        except Exception as e:
            print(f"❌ Error: {e}")

    else:
        # Run demo with test content
        print("🧪 Running demo with test content...")
        print("(Use --help to see command line options)\n")

        # Create a test file
        test_content = '\n'.join(
            [
                'This is a test',
                'TODO: Fix this',
                'Some other content',
                'TODO: Fix this',
                'End of file',
            ]
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            test_file = f.name

        try:
            print("=== Preview Mode (Default) ===")
            search_and_replace(test_file, "TODO: Fix this", "FIXED: Done", mode="preview")

            print("\n=== Preview Mode (Git Diff) ===")
            search_and_replace(test_file, "TODO: Fix this", "FIXED: Done", 
                               mode="preview", output_style="git_diff")

            print("\n=== Preview Mode (Git Conflict) ===")
            search_and_replace(test_file, "TODO: Fix this", ["FIXED: Done", "Additional info"], 
                               mode="preview", output_style="git_conflict")

            print("\n=== Apply Mode (Git Conflict to file) ===")
            result = search_and_replace(test_file, "TODO: Fix this", "FIXED: Done", 
                                        mode="apply", output_style="git_conflict", output_file="demo_output.txt")

            print(f"Total files processed: {len(result.file_results)}")
            print(f"Total matches: {result.total_matches}")
            print("Generated demo_output.txt with git conflict format")

        finally:
            # Cleanup
            import os
            if os.path.exists(test_file):
                os.unlink(test_file)
            if os.path.exists("demo_output.txt"):
                print("Cleaning up demo_output.txt")
                os.unlink("demo_output.txt")