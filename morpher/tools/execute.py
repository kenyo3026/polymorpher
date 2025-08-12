from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict
import subprocess
import time
import os

from .utils.ignore_controller import IGNORE_FILENAME, IgnoreController


@dataclass
class CommandConfig:
    """Configuration for executing a command."""
    command: str
    cwd: Optional[Path] = None
    timeout_seconds: int = 0  # 0 means no timeout
    shell: bool = True
    env: Optional[Dict[str, str]] = None
    encoding: str = "utf-8"
    combine_stdout_stderr: bool = True
    enable_ignore: bool = True
    shell_policy: str = "auto"  # "auto" | "unix" | "powershell"


@dataclass
class CommandResult:
    """Result of a command execution."""
    command: str
    cwd: Optional[Path]
    exit_code: Optional[int]
    output: str
    error: Optional[str]
    pid: Optional[int]
    duration_ms: int
    timed_out: bool


class CommandExecutor:
    """Executes shell commands based on CommandConfig and returns structured results."""

    def run(self, config: CommandConfig) -> CommandResult:

        if config.enable_ignore:
            controller = IgnoreController(config.cwd or Path.cwd(), shell=config.shell_policy)
            controller.load()
            blocked = controller.validate_command(config.command)
            if blocked:
                return CommandResult(
                    command=config.command,
                    cwd=config.cwd,
                    exit_code=1,
                    output="",
                    error=f"Blocked by {IGNORE_FILENAME}: attempted to access '{blocked}'",
                    pid=None,
                    duration_ms=0,
                    timed_out=False,
                )

        start_monotonic = time.monotonic()
        cwd_str = str(config.cwd) if config.cwd else None

        popen_kwargs = dict(
            shell=config.shell,
            cwd=cwd_str,
            env={**os.environ, **(config.env or {})} if config.env else None,
            stdout=subprocess.PIPE,
            stderr=(subprocess.STDOUT if config.combine_stdout_stderr else subprocess.PIPE),
            text=True,
            encoding=config.encoding,
        )

        proc: Optional[subprocess.Popen] = None
        timed_out = False
        output = ""
        error_text: Optional[str] = None
        pid: Optional[int] = None
        exit_code: Optional[int] = None

        try:
            proc = subprocess.Popen(config.command, **popen_kwargs)
            pid = proc.pid

            try:
                stdout, stderr = proc.communicate(timeout=(config.timeout_seconds or None))
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                # Drain any remaining output
                stdout, stderr = proc.communicate()

            exit_code = proc.returncode

            if config.combine_stdout_stderr:
                output = stdout or ""
                # In combined mode, stderr is already in stdout
            else:
                # Keep them separate but return both concatenated with a marker
                out_part = stdout or ""
                err_part = stderr or ""
                if err_part:
                    error_text = err_part
                output = out_part

        finally:
            duration_ms = int((time.monotonic() - start_monotonic) * 1000)

        # If timed out, make it explicit in error_text keeping output as-is for context
        if timed_out:
            timeout_msg = f"Command execution timed out after {config.timeout_seconds}s"
            error_text = (error_text + "\n" + timeout_msg) if error_text else timeout_msg

        return CommandResult(
            command=config.command,
            cwd=config.cwd,
            exit_code=exit_code,
            output=output,
            error=error_text,
            pid=pid,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )

def execute_command(
    command: str,
    cwd: Optional[str | Path] = None,
    timeout_seconds: int = 0,
    shell: bool = True,
    env: Optional[Dict[str, str]] = None,
    encoding: str = "utf-8",
    combine_stdout_stderr: bool = True,
    enable_ignore: bool = True,
    shell_policy: str = "auto",
) -> CommandResult:
    """Convenience function to run a command with minimal ceremony."""
    cfg = CommandConfig(
        command=command,
        cwd=Path(cwd).resolve() if cwd else None,
        timeout_seconds=timeout_seconds,
        shell=shell,
        env=env,
        encoding=encoding,
        combine_stdout_stderr=combine_stdout_stderr,
        enable_ignore=enable_ignore,
        shell_policy=shell_policy,
    )
    return CommandExecutor().run(cfg)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute Command V1 - Minimal command runner with timeout and combined output",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute (everything after --)")
    parser.add_argument("--cwd", type=str, default=None, help="Working directory")
    parser.add_argument("--timeout", type=int, default=0, help="Timeout in seconds (0 = no timeout)")
    parser.add_argument("--no-shell", action="store_true", help="Run without shell=True")
    parser.add_argument("--no-ignore", action="store_true", help=f"Disable {IGNORE_FILENAME} validation")
    parser.add_argument("--shell-policy", choices=["auto", "unix", "powershell"], default="auto", help=f"Command parsing policy for {IGNORE_FILENAME} validation")

    args = parser.parse_args()

    # Allow usage like: python execute_command_v1.py -- echo hello
    if not args.command:
        parser.print_help()
        raise SystemExit(2)

    # If the first token is a standalone "--", drop it (common delimiter pattern)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    cmd_str = " ".join(args.command)

    result = execute_command(
        command=cmd_str,
        cwd=args.cwd,
        timeout_seconds=args.timeout,
        shell=not args.no_shell,
        enable_ignore=not args.no_ignore,
        shell_policy=args.shell_policy,
    )

    print("=== Execute Command Result ===")
    print(f"Command   : {result.command}")
    print(f"CWD       : {result.cwd}")
    print(f"PID       : {result.pid}")
    print(f"Exit code : {result.exit_code}")
    print(f"Duration  : {result.duration_ms} ms")
    print(f"Timed out : {result.timed_out}")
    if result.output:
        print("\n--- Output (stdout/stderr) ---")
        print(result.output)
    if result.error:
        print("\n--- Error ---")
        print(result.error)

    # Propagate meaningful exit status
    if result.timed_out:
        os._exit(124)  # conventional timeout exit code
    os._exit(result.exit_code if isinstance(result.exit_code, int) else 1) 