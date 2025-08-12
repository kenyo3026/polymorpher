import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union, Dict
import tempfile
import shutil
import difflib


class OutputStyle(Enum):
    """Output formatting styles"""
    DEFAULT = "default"
    GIT_DIFF = "git_diff"
    GIT_CONFLICT = "git_conflict"


class ExecutionMode(Enum):
    """Execution modes"""
    PREVIEW = "preview"
    APPLY = "apply"


class WriteOperation(Enum):
    """Types of write operations"""
    CREATE = "create"
    OVERWRITE = "overwrite"
    APPEND = "append"
    PREPEND = "prepend"


@dataclass
class FileChange:
    """Represents a file change operation"""
    file_path: Path
    original_content: str
    new_content: str
    operation: WriteOperation

    @property
    def has_changes(self) -> bool:
        return self.original_content != self.new_content

    @property
    def is_new_file(self) -> bool:
        return not self.file_path.exists()

    @property
    def content_size(self) -> int:
        return len(self.new_content)

    @property
    def line_count(self) -> int:
        return len(self.new_content.split('\n'))


@dataclass
class FileResult:
    """Results for a single file operation"""
    file_path: Path
    change: Optional[FileChange] = None
    success: bool = False
    error_message: Optional[str] = None
    backup_path: Optional[Path] = None

    @property
    def has_change(self) -> bool:
        return self.change is not None and self.change.has_changes

    @property
    def operation_type(self) -> str:
        if not self.change:
            return "no_change"
        if self.change.is_new_file:
            return "created"
        elif self.change.operation == WriteOperation.OVERWRITE:
            return "overwritten"
        elif self.change.operation == WriteOperation.APPEND:
            return "appended"
        elif self.change.operation == WriteOperation.PREPEND:
            return "prepended"
        return "modified"


@dataclass
class WriteConfig:
    """Configuration for write operation"""
    content: str
    file_path: Union[str, Path]
    operation: WriteOperation = WriteOperation.OVERWRITE
    encoding: str = "utf-8"
    backup: bool = True
    create_dirs: bool = True
    preserve_permissions: bool = True

    def __post_init__(self):
        self.file_path = Path(self.file_path)
        # Normalize content line endings
        self.content = self.content.replace('\r\n', '\n').replace('\r', '\n')


@dataclass
class WriteResult:
    """Complete write operation results"""
    config: WriteConfig
    file_results: List[FileResult] = field(default_factory=list)

    @property
    def total_files_processed(self) -> int:
        return len(self.file_results)

    @property
    def total_files_changed(self) -> int:
        return sum(1 for fr in self.file_results if fr.has_change)

    @property
    def total_files_created(self) -> int:
        return sum(1 for fr in self.file_results if fr.change and fr.change.is_new_file)

    @property
    def success(self) -> bool:
        return all(fr.success for fr in self.file_results)


class FileProcessor:
    """Handles file content processing and operations"""

    def __init__(self, config: WriteConfig):
        self.config = config

    def prepare_change(self) -> FileChange:
        """Prepare file change based on operation type"""
        file_path = self.config.file_path

        # Read original content
        original_content = self._read_file_safely(file_path)

        # Prepare new content based on operation
        new_content = self._prepare_content(original_content)

        return FileChange(
            file_path=file_path,
            original_content=original_content,
            new_content=new_content,
            operation=self.config.operation
        )

    def _read_file_safely(self, file_path: Path) -> str:
        """Read file content safely"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding=self.config.encoding) as f:
                    return f.read()
            return ""
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return ""

    def _prepare_content(self, original_content: str) -> str:
        """Prepare content based on operation type"""
        if self.config.operation == WriteOperation.CREATE:
            if self.config.file_path.exists():
                raise FileExistsError(f"File {self.config.file_path} already exists")
            return self.config.content

        elif self.config.operation == WriteOperation.OVERWRITE:
            return self.config.content

        elif self.config.operation == WriteOperation.APPEND:
            if original_content and not original_content.endswith('\n'):
                return original_content + '\n' + self.config.content
            return original_content + self.config.content

        elif self.config.operation == WriteOperation.PREPEND:
            if self.config.content and not self.config.content.endswith('\n'):
                return self.config.content + '\n' + original_content
            return self.config.content + original_content

        return self.config.content


class OutputFormatter:
    """Handles different output formatting styles"""

    @staticmethod
    def format_default(file_result: FileResult) -> str:
        """Generate complete file content"""
        if not file_result.has_change:
            return file_result.change.original_content if file_result.change else ""
        return file_result.change.new_content

    @staticmethod
    def format_git_diff(file_result: FileResult) -> str:
        """Generate git diff style output"""
        if not file_result.has_change:
            return ""

        change = file_result.change
        output = []

        if change.is_new_file:
            # New file
            output.append(f"diff --git a/{change.file_path} b/{change.file_path}")
            output.append("new file mode 100644")
            output.append("index 0000000..1111111")
            output.append("--- /dev/null")
            output.append(f"+++ b/{change.file_path}")

            new_lines = change.new_content.split('\n')
            output.append(f"@@ -0,0 +1,{len(new_lines)} @@")
            for line in new_lines:
                output.append(f"+{line}")
        else:
            # Modified file - use difflib for better diff
            output.append(f"diff --git a/{change.file_path} b/{change.file_path}")
            output.append("index 0000000..1111111 100644")
            output.append(f"--- a/{change.file_path}")
            output.append(f"+++ b/{change.file_path}")

            original_lines = change.original_content.split('\n')
            new_lines = change.new_content.split('\n')

            # Use difflib to generate unified diff
            diff = difflib.unified_diff(
                original_lines,
                new_lines,
                n=3,
                lineterm=''
            )

            # Skip the first two lines (file headers) as we already added them
            diff_lines = list(diff)[2:]
            output.extend(diff_lines)

        return '\n'.join(output)

    @staticmethod
    def format_git_conflict(file_result: FileResult) -> str:
        """Generate git conflict style output for VS Code rendering"""
        if not file_result.has_change:
            return file_result.change.original_content if file_result.change else ""

        change = file_result.change

        if change.is_new_file:
            return change.new_content

        # Create conflict markers
        conflict_content = []
        conflict_content.append("<<<<<<< HEAD")
        conflict_content.append(change.original_content)
        conflict_content.append("=======")
        conflict_content.append(change.new_content)
        conflict_content.append(">>>>>>> incoming")

        return '\n'.join(conflict_content)


class SafetyValidator:
    """Handles safety checks and validations"""

    @staticmethod
    def validate_config(config: WriteConfig) -> List[str]:
        """Validate configuration for potential issues"""
        warnings = []

        # Check file path safety
        try:
            file_path = config.file_path.resolve()
            current_dir = Path.cwd().resolve()

            # Warn if writing outside current directory tree
            if not str(file_path).startswith(str(current_dir)):
                warnings.append(f"Writing outside current directory: {file_path}")
        except Exception:
            warnings.append("Could not resolve file path")

        # Check if file exists for CREATE operation
        if config.operation == WriteOperation.CREATE and config.file_path.exists():
            warnings.append(f"CREATE operation but file already exists: {config.file_path}")

        # Check for large content
        if len(config.content) > 1024 * 1024:  # 1MB
            warnings.append(f"Large content size: {len(config.content) / 1024 / 1024:.1f}MB")

        # Check for many lines
        line_count = len(config.content.split('\n'))
        if line_count > 10000:
            warnings.append(f"Large line count: {line_count} lines")

        # Check for binary content
        if '\x00' in config.content:
            warnings.append("Content contains null bytes (potential binary data)")

        return warnings

    @staticmethod
    def validate_file_access(file_path: Path) -> List[str]:
        """Validate file access permissions"""
        warnings = []

        try:
            if file_path.exists():
                if not os.access(file_path, os.R_OK):
                    warnings.append(f"File not readable: {file_path}")
                if not os.access(file_path, os.W_OK):
                    warnings.append(f"File not writable: {file_path}")
            else:
                # Check parent directory
                parent = file_path.parent
                if not parent.exists():
                    warnings.append(f"Parent directory does not exist: {parent}")
                elif not os.access(parent, os.W_OK):
                    warnings.append(f"Parent directory not writable: {parent}")
        except Exception as e:
            warnings.append(f"Could not check file permissions: {e}")

        return warnings


class WriteEngine:
    """Main write file engine"""

    def __init__(self):
        self.formatter = OutputFormatter()
        self.validator = SafetyValidator()

    def write_file(
        self,
        file_path: Union[str, Path],
        content: str,
        mode: str = "apply",
        output_style: str = "default",
        operation: str = "overwrite",
        output_file: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> WriteResult:
        """
        Main entry point for file write operations

        Args:
            file_path: Target file path
            content: Content to write
            mode: "preview" or "apply"
            output_style: "default", "git_diff", or "git_conflict"
            operation: "create", "overwrite", "append", or "prepend"
            output_file: Optional output file path (for apply mode)
            **kwargs: Additional configuration options
        """
        # Check if content would result in no changes
        if self._is_content_identical(file_path, content, operation):
            print("ℹ️  Content is identical to existing file - no changes needed.")
            config = WriteConfig(content=content, file_path=file_path, **kwargs)
            return WriteResult(config=config)

        # Create configuration
        config = WriteConfig(
            content=content,
            file_path=file_path,
            operation=WriteOperation(operation.lower()),
            **kwargs
        )

        # Validate configuration
        config_warnings = self.validator.validate_config(config)
        access_warnings = self.validator.validate_file_access(config.file_path)

        if config_warnings or access_warnings:
            print("⚠️  Safety Warnings:")
            for warning in config_warnings + access_warnings:
                print(f"  - {warning}")
            print()

        # Process file
        processor = FileProcessor(config)
        result = WriteResult(config=config)

        try:
            change = processor.prepare_change()
            file_result = FileResult(file_path=config.file_path, change=change)
            result.file_results.append(file_result)

            # Handle output based on mode
            execution_mode = ExecutionMode(mode.lower())
            style = OutputStyle(output_style.lower())

            if execution_mode == ExecutionMode.PREVIEW:
                self._handle_preview(result, style)
            else:  # APPLY
                self._handle_apply(result, style, output_file)

        except Exception as e:
            file_result = FileResult(
                file_path=config.file_path, 
                success=False, 
                error_message=str(e)
            )
            result.file_results.append(file_result)
            print(f"❌ Error: {e}")

        return result

    def _is_content_identical(self, file_path: Union[str, Path], content: str, operation: str) -> bool:
        """Check if content would result in no changes"""
        file_path = Path(file_path)

        # Only check for overwrite operations
        if operation.lower() != "overwrite":
            return False

        if not file_path.exists():
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()

            # Normalize line endings for comparison
            existing_normalized = existing_content.replace('\r\n', '\n').replace('\r', '\n')
            content_normalized = content.replace('\r\n', '\n').replace('\r', '\n')

            return existing_normalized.strip() == content_normalized.strip()
        except Exception:
            return False

    def _create_backup(self, file_path: Path) -> Optional[Path]:
        """Create backup of existing file"""
        if not file_path.exists():
            return None

        try:
            backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
            counter = 1
            while backup_path.exists():
                backup_path = file_path.with_suffix(f"{file_path.suffix}.backup.{counter}")
                counter += 1

            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")
            return None

    def _handle_preview(self, result: WriteResult, style: OutputStyle):
        """Handle preview mode output"""
        for file_result in result.file_results:
            print(f"\n{'='*60}")
            print(f"File: {file_result.file_path}")
            if file_result.change:
                print(f"Operation: {file_result.operation_type}")
                print(f"Size: {file_result.change.content_size} bytes, {file_result.change.line_count} lines")
            print(f"Mode: PREVIEW")
            print('='*60)

            if not file_result.has_change:
                print("No changes to preview.")
                continue

            if style == OutputStyle.DEFAULT:
                print(self.formatter.format_default(file_result))
            elif style == OutputStyle.GIT_DIFF:
                print(self.formatter.format_git_diff(file_result))
            elif style == OutputStyle.GIT_CONFLICT:
                print(self.formatter.format_git_conflict(file_result))

    def _handle_apply(self, result: WriteResult, style: OutputStyle, output_file: Optional[Path]):
        """Handle apply mode output"""
        for file_result in result.file_results:
            if not file_result.has_change:
                print(f"ℹ️  No changes needed for: {file_result.file_path}")
                file_result.success = True
                continue

            try:
                # Determine target path
                if output_file:
                    target_path = Path(output_file)
                else:
                    target_path = file_result.file_path

                # Create backup if needed (only for DEFAULT style and same file)
                if (result.config.backup and 
                    target_path.exists() and 
                    target_path == file_result.file_path and 
                    style == OutputStyle.DEFAULT):
                    file_result.backup_path = self._create_backup(target_path)
                    if file_result.backup_path:
                        print(f"📦 Backup created: {file_result.backup_path}")

                # Generate content based on style
                if style == OutputStyle.DEFAULT:
                    content = self.formatter.format_default(file_result)
                elif style == OutputStyle.GIT_DIFF:
                    content = self.formatter.format_git_diff(file_result)
                elif style == OutputStyle.GIT_CONFLICT:
                    content = self.formatter.format_git_conflict(file_result)

                # Create directories if needed
                if result.config.create_dirs:
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                # Write to file
                with open(target_path, 'w', encoding=result.config.encoding) as f:
                    f.write(content)

                # Preserve permissions if requested (only for DEFAULT style)
                if (result.config.preserve_permissions and 
                    file_result.file_path.exists() and 
                    target_path != file_result.file_path and
                    style == OutputStyle.DEFAULT):
                    try:
                        shutil.copystat(file_result.file_path, target_path)
                    except Exception:
                        pass  # Ignore permission copy errors

                file_result.success = True
                print(f"✅ Successfully {file_result.operation_type}: {target_path}")

            except Exception as e:
                file_result.success = False
                file_result.error_message = str(e)
                print(f"❌ Error writing {file_result.file_path}: {e}")


def write_and_ask(
    file_path: Union[str, Path],
    content: str,
    output_style: str = "default",
    operation: str = "overwrite",
    output_file: Optional[Union[str, Path]] = None,
    **kwargs
):
    """
    Interactive write - preview first, then ask for confirmation.

    This function first shows a preview of the changes that would be made,
    then prompts the user for confirmation before applying them.

    Args:
        file_path: Target file path
        content: Content to write
        output_style: Output formatting style:
            - "default": Complete file content
            - "git_diff": Git diff style output
            - "git_conflict": Git conflict markers (VS Code compatible)
        operation: Write operation type:
            - "create": Create new file (fail if exists)
            - "overwrite": Replace entire file content
            - "append": Add content to end of file
            - "prepend": Add content to beginning of file
        output_file: Custom output path (None = modify original file)
        **kwargs: Additional options:
            - encoding (str): File encoding (default: utf-8)
            - backup (bool): Create backup (default: True)
            - create_dirs (bool): Create parent directories (default: True)
            - preserve_permissions (bool): Preserve file permissions (default: True)

    Returns:
        Union[WriteResult, str]:
            - WriteResult if changes are applied or no changes needed
            - str with cancellation message if user declines or interrupts

    User Interaction:
        - Shows preview of changes with file statistics
        - Prompts: "Apply these changes? (y [YES] | n [NO]): "
        - Accepts: 'y', 'yes', 'true', 'apply' to confirm
        - Accepts: 'n', 'no', 'false', 'cancel' to decline
        - Handles Ctrl+C and EOF gracefully

    Examples:
        # Basic interactive write
        result = write_and_ask("file.txt", "new content")

        # Append with confirmation
        result = write_and_ask("log.txt", "\\nNew entry", operation="append")

        # Create new file with git conflict preview
        result = write_and_ask("new.txt", "content", operation="create", 
                              output_style="git_conflict")
    """
    engine = WriteEngine()
    preview_result = engine.write_file(
        file_path=file_path,
        content=content,
        mode='preview',
        output_style=output_style,
        operation=operation,
        output_file=output_file,
        **kwargs
    )

    # Check if any changes would be made
    if not preview_result.total_files_changed:
        print("ℹ️  No changes would be made.")
        return preview_result

    print(f"\n📊 Changes summary:")
    print(f"Files to be modified: {preview_result.total_files_changed}")
    if preview_result.total_files_created:
        print(f"Files to be created: {preview_result.total_files_created}")
    print("=" * 60)

    # Ask for confirmation
    while True:
        try:
            permission = input("Apply these changes? (y[YES]|n[NO]): ").strip()

            if permission.lower() in ['y', 'yes', 'true', 'apply']:
                return engine.write_file(
                    file_path=file_path,
                    content=content,
                    mode='apply',
                    output_style=output_style,
                    operation=operation,
                    output_file=output_file,
                    **kwargs
                )
            elif permission.lower() in ['n', 'no', 'false', 'cancel']:
                message = "❌ Changes cancelled by user."
                return message
            else:
                print("❓ Please enter 'Y'/'yes' to apply or 'N'/'no' to cancel.")
                continue
        except KeyboardInterrupt:
            message = "\n❌ Operation cancelled by user (Ctrl+C)."
            return message
        except EOFError:
            message = "\n❌ Operation cancelled (EOF)."
            return message


# Convenience function for direct usage
def write_file(
    file_path: Union[str, Path],
    content: str,
    mode: str = "apply",
    output_style: str = "default",
    operation: str = "overwrite",
    output_file: Optional[Union[str, Path]] = None,
    **kwargs
) -> WriteResult:
    """
    Advanced file writing with flexible operation modes and safety features.

    Features:
    - Multiple operations: create, overwrite, append, prepend
    - Preview mode for safe testing
    - Multiple output styles: default, git_diff, git_conflict
    - Interactive mode with confirmation
    - Automatic backup creation
    - Safety checks and warnings
    - Directory creation
    - Permission preservation

    Args:
        file_path: Target file path
        content: Content to write
        mode: Execution mode options:
            - "preview": Show changes without modifying files
            - "apply": Apply changes directly to files
            - "preview_and_ask": Preview first, then ask for confirmation
        output_style: Output formatting style:
            - "default": Complete file content
            - "git_diff": Git diff style output
            - "git_conflict": Git conflict markers (VS Code compatible)
        operation: Write operation type:
            - "create": Create new file (fail if exists)
            - "overwrite": Replace entire file content
            - "append": Add content to end of file
            - "prepend": Add content to beginning of file
        output_file: Custom output path (None = modify original file)
        **kwargs: Additional options:
            - encoding (str): File encoding (default: utf-8)
            - backup (bool): Create backup (default: True)
            - create_dirs (bool): Create parent directories (default: True)
            - preserve_permissions (bool): Preserve file permissions (default: True)

    Returns:
        WriteResult: Results with operation status and metadata

    Raises:
        ValueError: If invalid mode is specified
        FileNotFoundError: If target file/directory doesn't exist for certain operations
        FileExistsError: If CREATE operation and file already exists

    Examples:
        # Create new file
        write_file("new_file.txt", "Hello World", operation="create")

        # Preview overwrite
        write_file("existing.txt", "New content", mode="preview")

        # Interactive mode with confirmation
        write_file("file.txt", "content", mode="preview_and_ask")

        # Append to file
        write_file("log.txt", "\\nNew log entry", operation="append")

        # Prepend to file
        write_file("file.txt", "Header content\\n", operation="prepend")

        # Git conflict style for VS Code
        write_file("file.txt", "new content", output_style="git_conflict", mode="preview")

        # Custom output file
        write_file("source.txt", "content", output_file="output.txt")
    """
    # Validate mode parameter
    valid_modes = ["preview", "apply", "preview_and_ask"]
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}")

    # Handle interactive (preview and ask) mode
    if mode == "preview_and_ask":
        return write_and_ask(
            file_path=file_path,
            content=content,
            output_style=output_style,
            operation=operation,
            output_file=output_file,
            **kwargs
        )

    # Handle standard preview/apply modes
    engine = WriteEngine()
    return engine.write_file(
        file_path=file_path,
        content=content,
        mode=mode,
        output_style=output_style,
        operation=operation,
        output_file=output_file,
        **kwargs
    )


if __name__ == "__main__":
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Write File V2 - Advanced file writing with multiple modes and safety features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create new file
  python write_v2.py -f new_file.txt -c "Hello World" -m apply --operation create

  # Preview overwrite with git diff
  python write_v2.py -f existing.txt -c "New content" -m preview --style git_diff

  # Interactive mode (preview and ask)
  python write_v2.py -f file.txt -c "content" -m preview_and_ask

  # Append to file
  python write_v2.py -f log.txt -c "\\nNew entry" -m apply --operation append

  # Prepend to file
  python write_v2.py -f file.txt -c "Header\\n" -m apply --operation prepend

  # Git conflict style for VS Code
  python write_v2.py -f file.txt -c "new content" -m preview --style git_conflict

  # Run demo with test content (no arguments)
  python write_v2.py
        """
    )

    parser.add_argument('-f', '--file', type=str, help='Target file path')
    parser.add_argument('-c', '--content', type=str, help='Content to write')
    parser.add_argument('-m', '--mode', choices=['preview', 'apply', 'preview_and_ask'], 
                       default='preview', help='Execution mode (default: preview)')
    parser.add_argument('--style', choices=['default', 'git_diff', 'git_conflict'], 
                       default='default', help='Output style (default: default)')
    parser.add_argument('--operation', choices=['create', 'overwrite', 'append', 'prepend'], 
                       default='overwrite', help='Write operation (default: overwrite)')
    parser.add_argument('-o', '--output-file', type=str, help='Output file path (for apply mode)')
    parser.add_argument('--encoding', type=str, default='utf-8', help='File encoding (default: utf-8)')
    parser.add_argument('--no-backup', action='store_true', help='Disable backup creation')
    parser.add_argument('--no-create-dirs', action='store_true', help='Disable directory creation')
    parser.add_argument('--no-preserve-permissions', action='store_true', 
                       help='Disable permission preservation')

    args = parser.parse_args()

    # If file and content parameters are provided, process the actual file
    if args.file and args.content is not None:
        print(f"📝 Processing file: {args.file}")
        print(f"Content: '{args.content}'")
        print(f"Mode: {args.mode}")
        print(f"Style: {args.style}")
        print(f"Operation: {args.operation}")
        print(f"Encoding: {args.encoding}")
        print(f"Backup: {not args.no_backup}")
        print(f"Create dirs: {not args.no_create_dirs}")
        print(f"Preserve permissions: {not args.no_preserve_permissions}")

        # Process content (handle \n sequences)
        processed_content = args.content.replace('\\n', '\n')

        # Prepare kwargs
        kwargs = {
            'encoding': args.encoding,
            'backup': not args.no_backup,
            'create_dirs': not args.no_create_dirs,
            'preserve_permissions': not args.no_preserve_permissions,
        }

        try:
            result = write_file(
                file_path=args.file,
                content=processed_content,
                mode=args.mode,
                output_style=args.style,
                operation=args.operation,
                output_file=args.output_file,
                **kwargs
            )

            print(f"\n📊 Results:")
            print(f"Files processed: {result.total_files_processed}")
            print(f"Files changed: {result.total_files_changed}")
            print(f"Files created: {result.total_files_created}")
            print(f"Overall success: {result.success}")

            for file_result in result.file_results:
                if file_result.backup_path:
                    print(f"Backup: {file_result.backup_path}")
                if file_result.error_message:
                    print(f"Error: {file_result.error_message}")

        except Exception as e:
            print(f"❌ Error: {e}")

    else:
        # Run demo with test content
        print("🧪 Running demo with test content...")
        print("(Use --help to see command line options)\n")

        # Create a test file
        test_content = "Original line 1\nOriginal line 2\nOriginal line 3"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            test_file = f.name

        try:
            print("=== Preview Mode (Default) ===")
            write_file(test_file, "New content line 1\nNew content line 2", mode="preview")

            print("\n=== Preview Mode (Git Diff) ===")
            write_file(test_file, "Modified content", mode="preview", output_style="git_diff")

            print("\n=== Preview Mode (Git Conflict) ===")
            write_file(test_file, "Conflict content", mode="preview", output_style="git_conflict")

            print("\n=== Append Operation ===")
            write_file(test_file, "\nAppended line", mode="preview", operation="append")

            print("\n=== Prepend Operation ===")
            write_file(test_file, "Prepended line\n", mode="preview", operation="prepend")

            print("\n=== Apply Mode (Create new file) ===")
            result = write_file("demo_output.txt", "Demo content\nLine 2", 
                              mode="apply", operation="create")

            print(f"Success: {result.success}")
            print(f"Files created: {result.total_files_created}")

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.unlink(test_file)
            if os.path.exists("demo_output.txt"):
                print("Cleaning up demo_output.txt")
                os.unlink("demo_output.txt") 