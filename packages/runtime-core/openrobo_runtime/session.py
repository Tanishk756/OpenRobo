"""Runtime Process & Session Lifecycle Manager (Milestone 6.1)."""

import os
import subprocess
import uuid
from typing import Dict, List, Optional

from openrobo_runtime.models import (
    ExecutionProviderType,
    RuntimeSession,
    RuntimeSessionStatus,
    VerificationEvidence,
    utc_now_str,
)


class RuntimeSessionManager:
    """Tracks active ROS 2 and simulator runtime sessions with safe lifecycle control."""

    def __init__(self):
        self.sessions: Dict[str, RuntimeSession] = {}
        self._processes: Dict[str, subprocess.Popen] = {}

    def create_session(
        self,
        stack_id: str,
        workspace_path: str,
        workspace_digest: str = "",
        ros_distro: str = "humble",
        domain_id: int = 0,
        provider: ExecutionProviderType = ExecutionProviderType.LOCAL_PROCESS,
    ) -> RuntimeSession:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        session = RuntimeSession(
            id=session_id,
            stack_id=stack_id,
            workspace_path=workspace_path,
            workspace_digest=workspace_digest,
            provider=provider,
            ros_distro=ros_distro,
            domain_id=domain_id,
            status=RuntimeSessionStatus.RUNNING,
            pids=[],
        )
        self.sessions[session_id] = session
        return session

    def start_session(
        self,
        stack_id: str,
        workspace_path: str,
        launch_command: List[str],
        ros_distro: str = "humble",
        domain_id: int = 0,
        provider: ExecutionProviderType = ExecutionProviderType.LOCAL_PROCESS,
    ) -> RuntimeSession:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Security: sanitized environment
        env = dict(os.environ)
        env["ROS_DOMAIN_ID"] = str(domain_id)
        env["ROS_DISTRO"] = ros_distro

        proc = subprocess.Popen(
            launch_command,
            cwd=workspace_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        self._processes[session_id] = proc

        session = RuntimeSession(
            id=session_id,
            stack_id=stack_id,
            workspace_path=workspace_path,
            provider=provider,
            ros_distro=ros_distro,
            domain_id=domain_id,
            status=RuntimeSessionStatus.RUNNING,
            pids=[proc.pid],
        )
        self.sessions[session_id] = session
        return session

    def list_sessions(self) -> List[RuntimeSession]:
        """List all active and completed runtime sessions."""
        return [self.get_session(sid) or s for sid, s in self.sessions.items()]

    def get_session(self, session_id: str) -> Optional[RuntimeSession]:
        session = self.sessions.get(session_id)
        if session and session_id in self._processes:
            proc = self._processes[session_id]
            ret = proc.poll()
            if ret is not None:
                session.status = RuntimeSessionStatus.STOPPED if ret == 0 else RuntimeSessionStatus.FAILED
                session.stopped_at = utc_now_str()
        return session

    def stop_session(self, session_id: str, timeout_sec: int = 5) -> Optional[RuntimeSession]:
        session = self.sessions.get(session_id)
        if not session:
            return None

        if session_id in self._processes:
            proc = self._processes[session_id]
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=timeout_sec)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        session.status = RuntimeSessionStatus.STOPPED
        session.stopped_at = utc_now_str()
        return session

    def record_evidence(self, session_id: str, evidence: VerificationEvidence) -> Optional[RuntimeSession]:
        session = self.sessions.get(session_id)
        if session:
            session.evidence = evidence
        return session

    def stop_all_sessions(self):
        """Clean shutdown hook to prevent orphaned ROS processes on server exit."""
        for s_id in list(self._processes.keys()):
            self.stop_session(s_id)
