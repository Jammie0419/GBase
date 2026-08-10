# SPDX-License-Identifier: MIT
"""
Integration smoke tests for gbase-0.7.0.

Verifies that all restored modules from v0.5.1 and v0.6.1 components
import correctly on the current platform (Windows/macOS/Linux).
"""

import os
import sys
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCompatLayer:
    """Test the cross-platform compatibility layer."""

    def test_compat_imports(self):
        from lib.compat import (
            IS_WINDOWS, IS_MACOS, IS_LINUX,
            HOME, TEMP_DIR, NULL_DEVICE, PATH_SEPARATOR,
            get_disk_usage_percent, get_available_memory_kb,
            get_temp_path, get_data_dir, get_log_dir,
            is_absolute_path, safe_path_join, is_subpath,
            get_shell_executable, kill_process, get_port_owner,
        )
        assert isinstance(IS_WINDOWS, bool)

    def test_platform_detection_exclusive(self):
        from lib.compat import IS_WINDOWS, IS_MACOS, IS_LINUX
        assert sum([IS_WINDOWS, IS_MACOS, IS_LINUX]) <= 1


class TestRestoredModules:
    """Verify all v0.5.1-restored modules import."""

    def test_dag_engine(self):
        mod = importlib.import_module("lib.dag.engine")
        assert hasattr(mod, "DAGEngine") or hasattr(mod, "GraphBit")

    def test_dag_orchestrator(self):
        mod = importlib.import_module("lib.dag.orchestrator")
        assert hasattr(mod, "DAGOrchestrator")

    def test_dag_agents(self):
        mod = importlib.import_module("lib.dag.agents")
        assert mod is not None

    def test_evolution_engine(self):
        mod = importlib.import_module("lib.evolution.engine")
        assert mod is not None

    def test_skill_router(self):
        mod = importlib.import_module("lib.skills.router")
        assert hasattr(mod, "SkillRouter")

    def test_loop_cache(self):
        mod = importlib.import_module("lib.skills.loop_cache")
        assert hasattr(mod, "LoopCache")

    def test_village_connector(self):
        mod = importlib.import_module("lib.multi_agent.village_connector")
        assert mod is not None

    def test_battle_protocol(self):
        mod = importlib.import_module("lib.multi_agent.battle_protocol")
        assert mod is not None

    def test_exec(self):
        # exec.py 已移至 tools/ 目录
        mod = importlib.import_module("tools.exec")
        assert mod is not None


class TestRetainedModules:
    """Verify v0.6.1-retained modules import."""

    def test_pipeline(self):
        mod = importlib.import_module("lib.quality.pipeline")
        assert mod is not None

    def test_trace_review(self):
        mod = importlib.import_module("lib.experience.trace_review")
        assert mod is not None

    def test_monitor(self):
        mod = importlib.import_module("lib.monitor")
        assert mod is not None

    def test_experience(self):
        mod = importlib.import_module("lib.experience.engine")
        assert mod is not None

    def test_sleep_cycle(self):
        mod = importlib.import_module("lib.sleep_cycle")
        assert hasattr(mod, "IMPORTANCE_FLOOR")
        assert hasattr(mod, "MAX_SESSION_ROWS")

    def test_safe_shell(self):
        mod = importlib.import_module("lib.safe_shell")
        assert mod is not None

    def test_kernel(self):
        mod = importlib.import_module("lib.kernel")
        assert mod is not None


class TestEditionSystem:
    """Verify the edition system."""

    def test_edition_imports(self):
        from editions import HACKER, PRIME, STANDARD, LITE, get_edition, list_editions

    def test_hacker_has_27_modules(self):
        from editions import HACKER
        assert len(HACKER.modules) >= 27

    def test_all_editions_accessible(self):
        from editions import list_editions
        editions = list_editions()
        names = [e[0] for e in editions]
        assert "hacker" in names
        assert "prime" in names
        assert "standard" in names
        assert "lite" in names


class TestToolModules:
    """Verify tool modules import correctly."""

    def test_read_file(self):
        mod = importlib.import_module("tools.read_file")
        assert hasattr(mod, "read_file")

    def test_backup(self):
        mod = importlib.import_module("lib.backup")
        assert hasattr(mod, "backup_file")

    def test_pdf_gen(self):
        mod = importlib.import_module("tools.pdf_gen")
        assert mod is not None

    def test_mock_server(self):
        mod = importlib.import_module("tools.mock_server")
        assert mod is not None

    def test_anchor_keeper(self):
        mod = importlib.import_module("tools.anchor_keeper")
        assert mod is not None
