"""OpenRobo Agent Long-Lived Service & Systemd Unit Generator."""

import asyncio
import logging
import time
from typing import Optional

from openrobo_agent.config import AgentConfig
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
    """Main agent daemon coordinating heartbeat, telemetry sampling, spooling, and transport."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.identity_manager = DeviceIdentityManager(config)
        self.sampler = HeartbeatSampler(self.identity_manager)
        self.collector = TelemetryCollector(self.identity_manager)
        self.spool = OfflineTelemetrySpool(config.spool_path, max_events=config.spool_max_events, max_bytes=config.spool_max_bytes)

        self.transport = HttpTransportClient(
            base_url=config.control_plane_url,
            cert_path=str(config.cert_path) if config.cert_path.exists() else None,
            key_path=str(config.key_path) if config.key_path.exists() else None,
            ca_cert_path=str(config.ca_cert_path) if config.ca_cert_path.exists() else None,
        )
        self._running = False

    def step_heartbeat(self) -> MessageEnvelope:
        """Sample heartbeat and envelope it."""
        hb = self.sampler.sample_heartbeat()
        envelope = MessageEnvelope(
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

    async def run_loop(self, stop_event: Optional[asyncio.Event] = None) -> None:
        """Run continuous asynchronous agent loop."""
        self._running = True
        logger.info("OpenRobo Agent daemon started for device %s", self.identity_manager.device_id)

        last_hb = 0.0
        last_tel = 0.0
        consecutive_failures = 0

        while self._running:
            if stop_event and stop_event.is_set():
                break

            now = time.time()

            # 1. Heartbeat check
            if now - last_hb >= self.config.heartbeat_interval_sec:
                self.step_heartbeat()
                last_hb = now

            # 2. Telemetry delta check
            if now - last_tel >= self.config.telemetry_interval_sec:
                self.step_telemetry()
                last_tel = now

            # 3. Spool flush
            try:
                flushed = self.flush_spool()
                if flushed > 0:
                    consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                delay = calculate_backoff_delay(consecutive_failures)
                logger.warning("Spool flush failed (failure #%d): %s. Backing off for %.2fs", consecutive_failures, e, delay)
                await asyncio.sleep(min(delay, 5.0))

            await asyncio.sleep(1.0)

        self._running = False
        logger.info("OpenRobo Agent daemon stopped.")

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
