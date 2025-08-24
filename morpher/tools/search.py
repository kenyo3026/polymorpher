import os
import re
import glob
from pathlib import Path

def is_within_workspace(path: str, workspace_root: str) -> bool:
    """
    Determine whether the given path is inside the workspace directory.

    Args:
        path (str): The path to check. Can be relative or absolute.
        workspace_root (str): The absolute path to the workspace root directory.

    Returns:
        bool: True if path is inside the workspace root, False otherwise.
    """
    # Resolve both paths to their absolute canonical form
    path = Path(path).resolve()
    workspace_root = Path(workspace_root).resolve()

    try:
        # If no exception, path is within the workspace
        path.relative_to(workspace_root)
        return True
    except ValueError:
        # If ValueError is raised, path is outside workspace_root
        return False

def search_file(
    path: str,
    content_pattern: str,
    filepath_pattern: str = "*",
    cwd: str = None,
    max_matches_per_file: int = 10,
    enable_search_outside: bool = False,
    as_text: bool = True,
    only_filename: bool = False,
):
    """
    Search for content patterns in files within specified path and workspace constraints.

    Args:
        path (str): Directory or file path to search
        content_pattern (str): Regex pattern to search for in file contents
        filepath_pattern (str): File pattern to match (e.g., "*.py", "*.txt")
        cwd (str): Working directory (workspace root). Defaults to current directory
        max_matches_per_file (int): Maximum number of matches to display per file
        enable_search_outside (bool): Allow searching outside workspace
        as_text (bool): Return formatted text or raw results
        only_filename (bool): If True, only return filename and match count; if False, return detailed content

    Returns:
        str or list: Search results
    """
    # Handle cwd
    cwd = Path(cwd or os.getcwd()).expanduser().resolve()
    if not cwd.exists():
        raise FileNotFoundError(f"Working directory does not exist: {cwd}")

    # Handle path
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    path_is_within_cwd = is_within_workspace(path, cwd)
    if not enable_search_outside and not path_is_within_cwd:
        raise ValueError(f"Path '{path}' is outside workspace '{cwd}' and external search is disabled")

    # Determine files to search
    if path.is_file():
        files_to_search = [str(path)]
    elif path.is_dir():
        # Use glob pattern to find matching files
        search_pattern = os.path.join(str(path), "**", filepath_pattern)
        files_to_search = glob.glob(search_pattern, recursive=True)
        files_to_search = [f for f in files_to_search if os.path.isfile(f)]
    else:
        raise FileNotFoundError(f"Path does not exist: {path}")

    # Search for content pattern
    results = []
    pattern = re.compile(content_pattern)

    for file_path in files_to_search:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_matches = []
                file_total_lines = 0
                for line_num, line in enumerate(f, 1):
                    file_total_lines = line_num
                    if pattern.search(line):
                        file_matches.append({
                            'line': line_num,
                            'text': line.strip()
                        })

                if file_matches:
                    results.append({
                        'file': file_path,
                        'matches': file_matches,
                        'total_lines': file_total_lines,
                    })
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")

    if as_text:
        return format_results_to_pretty_str(
            results,
            max_matches_per_file,
            only_filename=only_filename,
        )
    return results

def format_results_to_pretty_str(
    results,
    max_matches_per_file: int = 10,
    only_filename: bool = False,
):
    """Format search results as readable text"""
    if not results:
        return "No matching results found"

    output = f"Found {len(results)} files with matches\n\n"

    for file_result in results:
        relative_path = os.path.relpath(file_result['file'])
        matched_contents = file_result['matches']

        # Determine header format based on whether entire file was matched
        if len(matched_contents) == file_result.get('total_lines', 0):
            header = f"# {relative_path} (entire file content returned)\n"
        else:
            header = f"# {relative_path} ({len(matched_contents)} matches)\n"

        if only_filename:
            output += header
        else:
            output += header

            displayed_count = 0
            for match in matched_contents:
                output += f"  {match['line']:3d} | {match['text']}\n"
                displayed_count += 1

                if displayed_count >= max_matches_per_file:
                    break

            if len(matched_contents) > max_matches_per_file:
                remaining = len(matched_contents) - max_matches_per_file
                output += f"  ... [Content truncated - {remaining} more matches hidden]\n"

            output += "----\n\n"

    return output

# Usage examples
if __name__ == "__main__":
    # Search for "TODO" in all Python files in current directory
    results = search_file(".", "TODO", "*.py")
    print(results)

    # Search in specific file
    results = search_file("morpher/tools/search.py", "import.*os", "*")
    print(results)

    # Get raw results instead of formatted text
    raw_results = search_file(".", "def ", "*.py", as_text=False)
    print(f"Found {len(raw_results)} files with function definitions")