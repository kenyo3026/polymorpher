
import os
from pathlib import Path

def load(file_path: str, ensure_abs: bool = True) -> str:
    """
    Loads the content of a file as plain text given its file path.

    Args:
        file_path (str): The path to the file to be loaded. Supports:
                        - Absolute paths: /Users/username/file.txt
                        - Relative paths: ./file.txt, ../file.txt
                        - Home directory: ~/file.txt
                        - Environment variables: $HOME/file.txt
        ensure_abs (bool): Whether to resolve path to absolute form (default: True)

    Returns:
        str: The content of the file as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If the file cannot be read.
    """
    try:
        if ensure_abs:
            file_path = os.path.expanduser(os.path.expandvars(file_path))

        path_obj = Path(file_path).resolve()

        with open(path_obj, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except Exception as e:
        return f"Error reading file: {str(e)}"