"""OpenRobo Agent Long-Lived Service & Systemd Unit Generator."""

import asyncio
import json
import logging
import os
import ssl
import time
from typing import Optional

import websockets
from openrobo_release.deployment_protocol import (
    CANONICAL_PROTOCOL_VERSION,
    DeploymentAckEnvelope,
    DeploymentInstructionEnvelope,
    DeploymentStatusReport,
)
from openrobo_release.trust_store import TrustedReleaseKeyStore

from openrobo_agent.config import AgentConfig
from openrobo_agent.deployment.artifact_client import ArtifactClient
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.source_registry import TrustedArtifactSourceRegistry
from openrobo_agent.deployment.status_outbox import AgentStatusOutbox
from openrobo_agent.deployment.worker import DeploymentWorker
from openrobo_agent.heartbeat import HeartbeatSampler
from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.models import MessageEnvelope
from openrobo_agent.spool import OfflineTelemetrySpool
from openrobo_agent.telemetry import TelemetryCollector
from openrobo_agent.transport import HttpTransportClient, calculate_backoff_delay

logger = logging.getLogger("openrobo_agent")


def generate_systemd_unit(
    user: str = "openrobo-agent",
    exec_path: str = "/usr/local/bin/openrobo-agent",
    config_dir: str = "/etc/openrobo-agent",
    state_dir: str = "/var/lib/openrobo-agent",
) -> str:
    """Generate a hardened systemd unit file running under a dedicated non-root service account."""
    return f"""[Unit]
Description=OpenRobo Edge Fleet Agent
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={user}
Environment="OPENROBO_CONFIG_DIR={config_dir}"
Environment="OPENROBO_STATE_DIR={state_dir}"
ExecStart={exec_path} run
Restart=on-failure
RestartSec=5s
StartLimitIntervalSec=60s
StartLimitBurst=5

# Sandboxing & Hardening
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={state_dir}
ReadOnlyPaths={config_dir}
PrivateTmp=true
NoNewPrivileges=true
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
"""


class AgentDaemon:
    """Main agent daemon coordinating heartbeat, telemetry sampling, spooling, transport, and deployment execution."""

    def __init__(self, config: AgentConfig, current_ros_distro: Optional[str] = None):
        self.config = config
        self.config.ensure_directories()

        self.identity_manager = DeviceIdentityManager(config)
        self.sampler = HeartbeatSampler(self.identity_manager)
        self.collector = TelemetryCollector(self.identity_manager)
        self.spool = OfflineTelemetrySpool(
            config.spool_path,
            max_events=config.spool_max_events,
            max_bytes=config.spool_max_bytes,
        )

        self.transport = HttpTransportClient(
            base_url=config.control_plane_url,
            cert_path=str(config.cert_path) if config.cert_path.exists() else None,
            key_path=str(config.key_path) if config.key_path.exists() else None,
            ca_cert_path=str(config.ca_cert_path) if config.ca_cert_path.exists() else None,
        )

        # M7.2 Deployment Subsystem Wiring
        allow_dev_http = (
            os.getenv("ENVIRONMENT") == "development"
            and os.getenv("OPENROBO_ALLOW_DEV_ARTIFACT_HTTP", "false").lower() in ("true", "1")
        )
        self.slot_manager = ABSlotManager(deployment_root=self.config.state_dir / "slots")

        # Load trust anchors from read-only config_dir if available, fallback to state_dir
        self.key_store = TrustedReleaseKeyStore(trust_dir=self.config.trusted_keys_dir)
        self.source_registry = TrustedArtifactSourceRegistry(self.config.artifact_sources_path)

        self.artifact_client = ArtifactClient(
            downloads_dir=self.config.state_dir / "downloads",
            allow_http_dev=allow_dev_http,
        )
        self.status_outbox = AgentStatusOutbox(self.config.status_outbox_path)

        resolved_distro = current_ros_distro or os.environ.get("ROS_DISTRO")
        if not resolved_distro:
            try:
                resolved_distro = HeartbeatSampler(self.identity_manager).sample_capabilities().distro
            except Exception:
                resolved_distro = None

        self.worker = DeploymentWorker(
            device_id=self.identity_manager.device_id,
            state_dir=self.config.state_dir,
            slot_manager=self.slot_manager,
            key_store=self.key_store,
            artifact_client=self.artifact_client,
            source_registry=self.source_registry,
            current_ros_distro=resolved_distro,
            status_callback=self._handle_worker_status,
        )

        # Startup crash reconciliation
        self.worker.reconcile_on_startup()

        self._running = False
        self._active_ws = None
        self._status_pending_event = asyncio.Event()

    async def _handle_worker_status(self, report: DeploymentStatusReport) -> None:
        """Callback invoked when worker emits state transitions: saves to durable outbox and signals sender."""
        logger.info(
            "Worker status update for %s: %s (gen: %d)",
            report.deployment_id,
            report.state.value,
            report.generation,
        )
        self.status_outbox.enqueue(report)
        self._status_pending_event.set()

    async def handle_deployment_instruction(self, envelope: DeploymentInstructionEnvelope) -> DeploymentAckEnvelope:
        """Process incoming deployment instruction via local worker."""
        return await self.worker.handle_instruction(envelope)

    def step_heartbeat(self) -> MessageEnvelope:
        """Sample heartbeat and envelope it."""
        hb = self.sampler.sample_heartbeat()
        envelope = MessageEnvelope(
            protocol_version="1.0.0",
            device_id=self.identity_manager.device_id,
            message_type="HEARTBEAT",
            payload=hb.model_dump(),
        )
        self.spool.enqueue(envelope)
        return envelope

    def step_telemetry(self) -> int:
        """Collect delta events and enqueue into spool."""
        events = self.collector.collect_delta_events()
        for ev in events:
            env = MessageEnvelope(
                protocol_version="1.0.0",
                device_id=self.identity_manager.device_id,
                message_type=str(ev.event_type),
                payload=ev.payload,
            )
            self.spool.enqueue(env)
        return len(events)

    def flush_spool(self, batch_size: int = 50) -> int:
        """Flush queued spool events over transport using typed endpoint routing."""
        queued = self.spool.peek(limit=batch_size)
        if not queued:
            return 0

        total_acked = 0
        heartbeats = [e for e in queued if e.message_type.upper() == "HEARTBEAT"]
        telemetries = [e for e in queued if e.message_type.upper() != "HEARTBEAT"]

        # 1. Dispatch heartbeats to /agent/heartbeat
        for hb_env in heartbeats:
            res = self.transport.send_heartbeat(hb_env)
            if res.get("status") == "ACK" or (res.get("success", True) and not res.get("error")):
                self.spool.acknowledge(hb_env.message_id)
                total_acked += 1

        # 2. Dispatch telemetry batch to /agent/telemetry-batch
        if telemetries:
            ack_ids = self.transport.send_batch(telemetries)
            if ack_ids:
                acked = self.spool.acknowledge(ack_ids)
                total_acked += acked

        return total_acked

    def _build_ws_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Builds client mTLS SSL context if using wss://."""
        if not self.config.cert_path.exists() or not self.config.key_path.exists():
            return None

        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self.config.ca_cert_path.exists():
            ctx.load_verify_locations(cafile=str(self.config.ca_cert_path))
        ctx.load_cert_chain(
            certfile=str(self.config.cert_path),
            keyfile=str(self.config.key_path),
        )
        return ctx

    async def _run_telemetry_loop(self, stop_event: asyncio.Event) -> None:
        """Independent supervised loop for sampling heartbeat, telemetry, and spool flushing."""
        last_hb = 0.0
        last_tel = 0.0
        consecutive_failures = 0

        while not stop_event.is_set():
            now = time.time()
            if now - last_hb >= self.config.heartbeat_interval_sec:
                self.step_heartbeat()
                last_hb = now

            if now - last_tel >= self.config.telemetry_interval_sec:
                self.step_telemetry()
                last_tel = now

            try:
                flushed = self.flush_spool()
                if flushed > 0:
                    consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                delay = calculate_backoff_delay(consecutive_failures)
                logger.warning("Spool flush failed (#%d): %s. Backing off %.2fs", consecutive_failures, e, delay)
                await asyncio.sleep(min(delay, 5.0))

            await asyncio.sleep(1.0)

    async def _run_deployment_ws_session(self, stop_event: asyncio.Event) -> None:
        """Supervised loop maintaining authenticated deployment WebSocket connection."""
        ws_url = self.config.get_deployment_ws_url()
        ssl_ctx = self._build_ws_ssl_context() if ws_url.startswith("wss://") else None

        reconnect_attempts = 0
        while not stop_event.is_set():
            try:
                headers = {}
                # If dev proxy bridge header is configured in dev mode, pass it
                if os.getenv("OPENROBO_TEST_FINGERPRINT"):
                    headers["X-OpenRobo-Cert-Fingerprint"] = os.getenv("OPENROBO_TEST_FINGERPRINT")

                async with websockets.connect(
                    ws_url,
                    ssl=ssl_ctx,
                    extra_headers=headers if headers else None,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    logger.info("Authenticated deployment WebSocket connected to %s", ws_url)
                    self._active_ws = ws
                    reconnect_attempts = 0
                    self._status_pending_event.set()

                    while not stop_event.is_set():
                        raw_msg = await ws.recv()
                        try:
                            msg_data = json.loads(raw_msg)
                        except Exception as e:
                            logger.error("Malformed message on deployment WS: %s", e)
                            continue

                        msg_type = msg_data.get("message_type")
                        if msg_type == "DEPLOYMENT_INSTRUCTION":
                            inst_dict = msg_data.get("instruction")
                            if inst_dict:
                                try:
                                    inst_envelope = DeploymentInstructionEnvelope.model_validate(inst_dict)
                                    ack_envelope = await self.worker.handle_instruction(inst_envelope)
                                    ack_msg = MessageEnvelope(
                                        protocol_version=CANONICAL_PROTOCOL_VERSION,
                                        device_id=self.identity_manager.device_id,
                                        message_type="DEPLOYMENT_ACK",
                                        payload=ack_envelope.model_dump(),
                                    )
                                    await ws.send(ack_msg.model_dump_json())
                                except Exception as e:
                                    logger.error("Failed handling deployment instruction: %s", e)
                        elif msg_data.get("status") == "ACK":
                            rep_id = msg_data.get("report_id")
                            if rep_id:
                                self.status_outbox.mark_acknowledged(rep_id)

            except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
                self._active_ws = None
                reconnect_attempts += 1
                delay = min(calculate_backoff_delay(reconnect_attempts), 10.0)
                logger.warning("Deployment WebSocket disconnected: %s. Reconnecting in %.2fs", e, delay)
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._active_ws = None
                reconnect_attempts += 1
                logger.error("Unexpected error in deployment WebSocket: %s", e)
                await asyncio.sleep(2.0)
            finally:
                self._active_ws = None

    async def _run_status_sender_loop(self, stop_event: asyncio.Event) -> None:
        """Supervised loop draining durable status outbox over the active WebSocket."""
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(self._status_pending_event.wait(), timeout=2.0)
                self._status_pending_event.clear()
            except asyncio.TimeoutError:
                pass

            if stop_event.is_set():
                break

            ws = self._active_ws
            if ws and not ws.closed:
                unacked = self.status_outbox.get_pending_or_unacknowledged()
                for item in unacked:
                    try:
                        status_report = item.to_status_report()
                        msg_env = MessageEnvelope(
                            protocol_version=CANONICAL_PROTOCOL_VERSION,
                            device_id=self.identity_manager.device_id,
                            message_type="DEPLOYMENT_STATUS",
                            payload=status_report.model_dump(),
                        )
                        await ws.send(msg_env.model_dump_json())
                        self.status_outbox.mark_sent(item.report_id)
                    except Exception as e:
                        logger.error("Failed sending status report %s: %s", item.report_id, e)
                        break

    async def run_loop(self, stop_event: Optional[asyncio.Event] = None) -> None:
        """Run continuous asynchronous agent loop supervising independent concurrent tasks."""
        self._running = True
        local_stop = stop_event or asyncio.Event()
        logger.info("OpenRobo Agent daemon started for device %s", self.identity_manager.device_id)

        telemetry_task = asyncio.create_task(self._run_telemetry_loop(local_stop))
        deployment_task = asyncio.create_task(self._run_deployment_ws_session(local_stop))
        status_sender_task = asyncio.create_task(self._run_status_sender_loop(local_stop))

        tasks = [telemetry_task, deployment_task, status_sender_task]

        try:
            while self._running and not local_stop.is_set():
                await asyncio.sleep(0.5)
        finally:
            local_stop.set()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._running = False
            logger.info("OpenRobo Agent daemon stopped cleanly.")

    def stop(self) -> None:
        self._running = False


class SystemdServiceGenerator:
    def __init__(self, config: AgentConfig, user: str = "openrobo-agent"):
        self.config = config
        self.user = user

    def generate_unit(self) -> str:
        return generate_systemd_unit(
            user=self.user,
            state_dir=str(self.config.state_dir),
            config_dir=str(self.config.config_dir),
        )
