"""Unit tests for Runtime Session Manager."""

import sys

from openrobo_runtime import RuntimeSessionManager, RuntimeSessionStatus


def test_session_lifecycle():
    manager = RuntimeSessionManager()
    # Launch a safe dummy sleep process via Python
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    session = manager.start_session(
        stack_id="test_stack",
        workspace_path=".",
        launch_command=cmd,
    )
    assert session.status == RuntimeSessionStatus.RUNNING
    assert len(session.pids) == 1

    queried = manager.get_session(session.id)
    assert queried is not None

    stopped = manager.stop_session(session.id)
    assert stopped.status == RuntimeSessionStatus.STOPPED
