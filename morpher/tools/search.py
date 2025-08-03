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
    enable_search_outside: bool = False,
    as_text: bool = True,
):
    """
    Search for content patterns in files within specified path and workspace constraints.

    Args:
        path (str): Directory or file path to search
        content_pattern (str): Regex pattern to search for in file contents
        filepath_pattern (str): File pattern to match (e.g., "*.py", "*.txt")
        cwd (str): Working directory (workspace root). Defaults to current directory
        enable_search_outside (bool): Allow searching outside workspace
        as_text (bool): Return formatted text or raw results

    Returns:
        str or list: Search results
    """
    # Handle cwd
    if not cwd:
        cwd = os.getcwd()

    if not os.path.exists(cwd):
        raise FileNotFoundError(f"Working directory does not exist: {cwd}")

    # Handle path
    path = Path(path).resolve()

    # Check workspace boundaries
    path_is_within_cwd = is_within_workspace(str(path), cwd)
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
                for line_num, line in enumerate(f, 1):
                    if pattern.search(line):
                        file_matches.append({
                            'line': line_num,
                            'text': line.strip()
                        })

                if file_matches:
                    results.append({
                        'file': file_path,
                        'matches': file_matches
                    })
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")

    if as_text:
        return format_results_to_pretty_str(results)
    return results

def format_results_to_pretty_str(results):
    """Format search results as readable text"""
    if not results:
        return "No matching results found"

    output = f"Found {len(results)} files with matches\n\n"

    for file_result in results:
        relative_path = os.path.relpath(file_result['file'])
        output += f"# {relative_path}\n"
        for match in file_result['matches']:
            output += f"  {match['line']:3d} | {match['text']}\n"
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