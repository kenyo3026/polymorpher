from __future__ import annotations

import fnmatch
import shlex
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Iterable, List

# Centralized configuration for ignore file naming
IGNORE_FILENAME = ".morpherignore"


class CommandPolicy(ABC):
    @property
    @abstractmethod
    def file_reading_commands(self) -> set[str]:
        ...

    @abstractmethod
    def tokenize(self, command: str) -> List[str]:
        ...

    @abstractmethod
    def iter_candidate_args(self, parts: Iterable[str]):
        ...


class UnixPolicy(CommandPolicy):
    @property
    def file_reading_commands(self) -> set[str]:
        return {"cat", "less", "more", "head", "tail", "grep", "awk", "sed"}

    def tokenize(self, command: str) -> List[str]:
        return shlex.split(command, posix=True)

    def iter_candidate_args(self, parts: Iterable[str]):
        for a in parts:
            if isinstance(a, str) and a.startswith("-"):
                continue  # Unix flags
            yield a


class PowerShellPolicy(CommandPolicy):
    @property
    def file_reading_commands(self) -> set[str]:
        return {"get-content", "gc", "type", "select-string", "sls"}

    def tokenize(self, command: str) -> List[str]:
        # posix=False to keep PowerShell-like quoting behavior
        return shlex.split(command, posix=False)

    def iter_candidate_args(self, parts: Iterable[str]):
        for a in parts:
            if not isinstance(a, str):
                continue
            if a.startswith("/"):
                continue  # Windows/PS style flags
            if ":" in a:
                # Skip PowerShell parameter names or drive-qualified items
                # (we keep MVP behavior consistent with TS implementation)
                continue
            yield a


class ShellPolicyFactory:
    """Factory for creating command policy instances"""

    @staticmethod
    def create_policy(shell: str) -> CommandPolicy:
        shell_upper = shell.upper()

        # Direct mapping
        policies = {
            "UNIX": UnixPolicy,
            "POWERSHELL": PowerShellPolicy,
        }

        if shell_upper in policies:
            return policies[shell_upper]()
        elif shell_upper == "AUTO":
            import platform
            return PowerShellPolicy() if platform.system() == "Windows" else UnixPolicy()
        else:
            raise ValueError(f"Invalid shell type: {shell}")


class IgnoreController:
    def __init__(self, cwd: str | Path, shell: str = "auto"):
        self.cwd = Path(cwd).resolve()
        self.policy = ShellPolicyFactory.create_policy(shell)
        self._patterns: List[str] = []
        self._loaded = False

    def load(self) -> None:
        p = self.cwd / IGNORE_FILENAME
        self._patterns = []
        if p.exists():
            for raw in p.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                self._patterns.append(line)
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _matches(self, rel_posix: str) -> bool:
        for pat in self._patterns:
            # Directory pattern
            if pat.endswith("/"):
                anchor = pat.lstrip("/")
                if rel_posix == anchor.rstrip("/") or rel_posix.startswith(anchor):
                    return True
                continue
            # File pattern or glob
            anchor = pat.lstrip("/")
            if fnmatch.fnmatch(rel_posix, anchor):
                return True
        return False

    def validate_access(self, rel_path: str) -> bool:
        """True if allowed, False if ignored."""
        self._ensure_loaded()
        if not self._patterns:
            return True
        try:
            abs_path = (self.cwd / rel_path).resolve()
            rel = abs_path.relative_to(self.cwd).as_posix()
        except Exception:
            # Outside cwd: allow
            return True
        return not self._matches(rel)

    def validate_command(self, command: str) -> Optional[str]:
        self._ensure_loaded()
        if not self._patterns:
            return None
        parts = self.policy.tokenize(command)
        if not parts:
            return None
        base = parts[0].lower()
        if base not in self.policy.file_reading_commands:
            return None
        for arg in self.policy.iter_candidate_args(parts[1:]):
            if not self.validate_access(str(arg)):
                return str(arg)
        return None 