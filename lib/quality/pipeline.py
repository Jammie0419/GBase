# SPDX-License-Identifier: MIT
"""
lib/pipeline.py - Gate-based workflow system (minimal implementation).

Provides gate-based pipeline execution for quality control workflows.
This is a minimal stub that satisfies imports from main.py.

Full implementation can be added later. The DAG engine (lib/dag_engine.py)
provides more powerful graph-based orchestration.
"""

import json
import logging
import os
import time
from pathlib import Path

from lib.compat import GBASE_PIPELINES_DIR

logger = logging.getLogger(__name__)

# Pipeline storage directory
PIPELINE_DIR = GBASE_PIPELINES_DIR


async def run_gate(
    task: str,
    project: str,
    pipeline_id: str = None,
    arm_timeout: int = 120,
) -> dict:
    """Run a quality gate pipeline.

    Args:
        task: Task description
        project: Project name
        pipeline_id: Optional pipeline ID
        arm_timeout: Timeout in seconds

    Returns:
        Pipeline execution result dict
    """
    if pipeline_id is None:
        pipeline_id = f"pipeline-{int(time.time())}"

    logger.info("Pipeline run: id=%s task=%s project=%s", pipeline_id, task[:50], project)

    # Ensure pipeline directory exists
    pipeline_dir = PIPELINE_DIR / pipeline_id
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "pipeline_id": pipeline_id,
        "task": task,
        "project": project,
        "status": "completed",
        "steps": [],
        "timestamp": time.time(),
        "note": "Minimal pipeline implementation. Use DAG engine for complex workflows.",
    }

    # Save result
    result_file = pipeline_dir / "result.json"
    result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


async def rerun_step(pipeline_id: str, step: str) -> dict:
    """Rerun a specific step in a pipeline.

    Args:
        pipeline_id: Pipeline ID
        step: Step name

    Returns:
        Step execution result
    """
    logger.info("Pipeline rerun: id=%s step=%s", pipeline_id, step)
    return {
        "pipeline_id": pipeline_id,
        "step": step,
        "status": "completed",
        "note": "Minimal implementation",
    }


def list_pipelines() -> list[dict]:
    """List all recorded pipelines.

    Returns:
        List of pipeline summary dicts
    """
    if not PIPELINE_DIR.exists():
        return []

    pipelines = []
    for pipeline_dir in PIPELINE_DIR.iterdir():
        if not pipeline_dir.is_dir():
            continue
        result_file = pipeline_dir / "result.json"
        if result_file.exists():
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                pipelines.append({
                    "id": pipeline_dir.name,
                    "task": data.get("task", ""),
                    "project": data.get("project", ""),
                    "status": data.get("status", ""),
                    "timestamp": data.get("timestamp", 0),
                })
            except Exception:
                pass

    return sorted(pipelines, key=lambda x: x.get("timestamp", 0), reverse=True)
