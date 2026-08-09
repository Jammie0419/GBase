# Changelog

## [0.7.0] - 2026-08-10

### Major Changes

- **Merged v0.5.1 + v0.6.1**: Combined cognitive middleware with deterministic orchestration
- **Windows Compatibility**: Full cross-platform support (Windows/macOS/Linux) via `lib/compat.py`
- **27 modules in HACKER edition**: All features from both versions unified

### Restored from v0.5.1

- **DAG Engine** (744 lines) — GraphBit deterministic workflow orchestration with topological sort
- **DAG Orchestrator** (464 lines) — DAG-first task routing with 5 built-in pilot workflows
- **DAG Agents** (560 lines) — Agent function library for DAG steps
- **Evolution Engine** (463 lines) — Auto-evaluate + auto-rollback trigger chain
- **Skill Router** (382 lines) — Automatic skill matching with synonym expansion
- **Loop Cache** (155 lines) — Tool call pattern learning + deterministic replay
- **Village Connector** (175 lines) — Village OS multi-agent communication
- **Battle Protocol** (159 lines) — Inter-agent task communication protocol
- **Exec** (109 lines) — Command execution wrapper

### Retained from v0.6.1

- **Thinking Lever** (L0-L4 cognitive middleware) — Context scanning, task classification, reflection
- **Neocortex** (pattern scanning + knowledge distillation) — Cognition engine with 5 submodules
- **Trace Review** (520 lines) — Behavior replay analyzer ("dashcam")
- **Monitor** (101 lines) — Agent instance health monitoring
- **Edition system** — hacker/prime/standard/lite with feature flags
- **Knowledge Management** — km_base, km_graph, km_tools
- **Multi-model routing** — Automatic model selection based on task complexity
- **Arm mode** — hammer/ink/bumblebee/laser/forge identity system

### New

- `lib/compat.py` — Cross-platform compatibility layer (120+ lines)
- `lib/pipeline.py` — Minimal gate-based pipeline implementation
- Configurable `sleep_cycle.py` modes (enterprise/lite via GBASE_MODE env var)
- Anti-fragile meta-cognition in experience engine (5 rules)
- Date-based log rotation (90-day retention)
- Cross-platform font registration in pdf_gen.py

### Windows Compatibility Fixes

- Replaced all `python3` with `sys.executable` (17+ files)
- Replaced `/tmp` with `tempfile.gettempdir()` (10+ files)
- Replaced `/proc/meminfo` with `psutil.virtual_memory()` via `get_available_memory_kb()`
- Replaced `df -P /` with `shutil.disk_usage()`
- Replaced `lsof` with `netstat` (Windows) / `psutil` (Unix)
- Replaced `signal.SIGTERM/SIGKILL` with cross-platform `kill_process()`
- Platform-conditional shell execution (cmd.exe on Windows, bash on Unix)
- Cross-platform font paths in pdf_gen.py

## [0.6.1] - Previous

See gbase-0.6.2/ for v0.6.1 history.

## [0.5.1] - Previous

See gbase-0.5.1/ for v0.5.1 history.
