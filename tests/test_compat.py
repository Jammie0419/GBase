# SPDX-License-Identifier: MIT
"""Unit tests for lib/compat.py cross-platform compatibility layer."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.compat import (
    IS_WINDOWS,
    IS_MACOS,
    IS_LINUX,
    HOME,
    TEMP_DIR,
    NULL_DEVICE,
    PATH_SEPARATOR,
    get_disk_usage_percent,
    get_available_memory_kb,
    get_temp_path,
    get_data_dir,
    get_log_dir,
    is_absolute_path,
    safe_path_join,
    is_subpath,
    get_shell_executable,
)


class TestPlatformDetection:
    def test_platform_constants_are_bool(self):
        assert isinstance(IS_WINDOWS, bool)
        assert isinstance(IS_MACOS, bool)
        assert isinstance(IS_LINUX, bool)

    def test_at_most_one_platform(self):
        assert sum([IS_WINDOWS, IS_MACOS, IS_LINUX]) <= 1


class TestPathConstants:
    def test_home_exists(self):
        assert HOME.exists()

    def test_temp_dir_exists(self):
        assert TEMP_DIR.exists()

    def test_null_device(self):
        if IS_WINDOWS:
            assert NULL_DEVICE == "NUL"
        else:
            assert NULL_DEVICE == "/dev/null"

    def test_path_separator(self):
        if IS_WINDOWS:
            assert PATH_SEPARATOR == ";"
        else:
            assert PATH_SEPARATOR == ":"


class TestSystemMonitoring:
    def test_disk_usage_percent(self):
        pct = get_disk_usage_percent(".")
        assert isinstance(pct, float)
        assert 0 <= pct <= 100

    def test_disk_usage_invalid_path(self):
        pct = get_disk_usage_percent("/nonexistent/path/xyz")
        assert pct == 0.0

    def test_available_memory(self):
        mem = get_available_memory_kb()
        # Should return int or None
        if mem is not None:
            assert isinstance(mem, int)
            assert mem > 0


class TestPathHelpers:
    def test_get_temp_path(self):
        p = get_temp_path("test.txt")
        assert p.name == "test.txt"
        assert str(TEMP_DIR) in str(p)

    def test_get_data_dir(self):
        d = get_data_dir()
        assert d is not None

    def test_get_log_dir(self):
        d = get_log_dir()
        assert d is not None

    def test_is_absolute_path(self):
        if IS_WINDOWS:
            assert is_absolute_path("C:\\Users")
            assert not is_absolute_path("relative/path")
        else:
            assert is_absolute_path("/usr/bin")
            assert not is_absolute_path("relative/path")

    def test_safe_path_join(self):
        result = safe_path_join("a", "b", "c")
        assert "a" in result and "b" in result and "c" in result

    def test_is_subpath(self):
        assert is_subpath("/a/b/c", "/a/b")
        assert not is_subpath("/x/y/z", "/a/b")


class TestShellHelper:
    def test_get_shell_executable(self):
        shell = get_shell_executable()
        if IS_WINDOWS:
            assert shell is None
        else:
            assert shell is not None
            assert shell.startswith("/bin/")
