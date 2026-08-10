# SPDX-License-Identifier: MIT
"""
lib/compat.py - Cross-platform compatibility layer for GBase.

Provides constants and helper functions that abstract away OS differences
between Windows, macOS, and Linux. All GBase modules should import from
here instead of using platform-specific APIs directly.

Usage:
    from lib.compat import IS_WINDOWS, HOME, TEMP_DIR, get_data_dir
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# -- Platform Detection --------------------------------------------------

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# -- Path Constants -------------------------------------------------------

HOME = Path.home()
TEMP_DIR = Path(tempfile.gettempdir())
NULL_DEVICE = "NUL" if IS_WINDOWS else "/dev/null"
PATH_SEPARATOR = ";" if IS_WINDOWS else ":"  # For env var lists like PATH
DEFAULT_SHELL = None if IS_WINDOWS else "/bin/bash"  # Windows uses auto-detect


# -- Environment Variable Helpers -----------------------------------------


def get_env_list(name: str, default: str = "") -> list[str]:
    """Split an env var by the platform-appropriate path separator."""
    val = os.environ.get(name, default)
    if not val:
        return []
    return [v.strip() for v in val.split(PATH_SEPARATOR) if v.strip()]


def get_data_dir() -> Path:
    """Return the GBase data directory, platform-appropriate."""
    env_dir = os.environ.get("GBASE_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.cwd() / "data"


def get_log_dir() -> Path:
    """Return the GBase log directory."""
    env_dir = os.environ.get("GBASE_LOG_DIR")
    if env_dir:
        return Path(env_dir)
    return get_data_dir() / "logs"


def get_temp_path(filename: str) -> Path:
    """Return a path in the system temp directory."""
    return TEMP_DIR / filename


# -- System Monitoring ----------------------------------------------------


def get_disk_usage_percent(path: str = ".") -> float:
    """Cross-platform disk usage percentage.

    Uses shutil.disk_usage() which works on Windows, macOS, and Linux.
    Returns 0.0 on error.
    """
    try:
        usage = shutil.disk_usage(path)
        return round(usage.used / usage.total * 100, 1)
    except Exception:
        return 0.0


def get_available_memory_kb() -> int | None:
    """Cross-platform available memory in KB.

    Tries psutil first, then falls back to /proc/meminfo on Linux.
    Returns None if memory info cannot be determined.
    """
    try:
        import psutil
        return psutil.virtual_memory().available // 1024
    except ImportError:
        pass
    # Fallback for Linux without psutil
    if IS_LINUX:
        try:
            import re
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        match = re.search(r"(\d+)", line)
                        if match:
                            return int(match.group(1))
        except Exception:
            pass
    return None


# -- Process Management ---------------------------------------------------


def kill_process(pid: int, force: bool = False) -> bool:
    """Cross-platform process termination.

    Args:
        pid: Process ID to terminate
        force: If True, use SIGKILL/Taskkill /F instead of SIGTERM

    Returns:
        True if process was terminated successfully, False on error
    """
    try:
        if IS_WINDOWS:
            flag = "/F" if force else ""
            cmd = ["taskkill"]
            if flag:
                cmd.append(flag)
            cmd.extend(["/PID", str(pid)])
            subprocess.run(cmd, capture_output=True, timeout=5)
            return True
        else:
            import signal
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return True
    except (ProcessLookupError, PermissionError, OSError):
        return False
    except subprocess.TimeoutExpired:
        return False


def get_port_owner(port: int) -> int | None:
    """Find the PID of the process listening on a port.

    Uses netstat on Windows, psutil on Unix, with lsof fallback.
    Returns None if not found or on error.
    """
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    return int(parts[-1])
        except Exception:
            pass
    else:
        # Try psutil first
        try:
            import psutil
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == "LISTEN":
                    return conn.pid
        except (ImportError, Exception):
            pass
        # Fallback to lsof
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pids = result.stdout.strip().split()
            if pids:
                return int(pids[0])
        except Exception:
            pass
    return None


# -- Path Safety ----------------------------------------------------------


def is_absolute_path(path: str) -> bool:
    """Cross-platform absolute path check."""
    return os.path.isabs(path)


def safe_path_join(*parts: str) -> str:
    """Join path parts using the platform separator."""
    return str(Path(*parts))


def is_subpath(child: str, parent: str) -> bool:
    """Check if child is a subpath of parent. Python 3.9+ compatible."""
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


# -- Shell Execution Helper -----------------------------------------------


def get_shell_executable() -> str | None:
    """Return the appropriate shell executable for the current platform.

    Returns None on Windows (auto-detect cmd.exe).
    Returns /bin/bash on Unix (or /bin/zsh if preferred).
    """
    if IS_WINDOWS:
        return None  # Let Windows use cmd.exe by default
    return DEFAULT_SHELL


# -- Shell Script Helper ---------------------------------------------------


def run_shell_script(
    script_path: str,
    *args: str,
    timeout: int = 60,
) -> dict:
    """跨平台运行 shell 脚本。

    Windows 上自动跳过（返回 skip 状态），Unix 上用 bash 执行。

    Returns:
        {"status": "ok"|"skip"|"error", "stdout": str, "stderr": str, ...}
    """
    if IS_WINDOWS:
        return {
            "status": "skip",
            "stdout": "",
            "stderr": "",
            "message": f"Shell 脚本在 Windows 上不可用: {script_path}",
        }

    try:
        result = subprocess.run(
            [DEFAULT_SHELL or "bash", script_path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "stdout": "", "stderr": "执行超时", "returncode": -1}
    except FileNotFoundError:
        return {"status": "error", "stdout": "", "stderr": f"Shell 未找到: {DEFAULT_SHELL}", "returncode": -1}
