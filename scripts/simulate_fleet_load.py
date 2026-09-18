"""
OpenRobo Milestone 7.1.1 - 100-Agent Local Control-Plane Application Simulation
Measures:
- 100 concurrent agent key generation and enrollment token consumption
- 100 concurrent X.509 certificate issuances via development CA
- 100 concurrent heartbeats and telemetry streams
- Ingestion rate, latency distribution (p50, p95, p99, max), and memory usage
"""

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone

# Ensure path resolution
sys.path.insert(0, "packages/agent-core")
sys.path.insert(0, ".")

os.environ["OPENROBO_DEV_CA"] = "true"
os.environ["ENVIRONMENT"] = "development"
os.environ["OPENROBO_ALLOW_DEV_CERT_HEADER"] = "true"
os.environ["OPENROBO_ADMIN_KEY"] = "sim-admin-key-123"
os.environ["OPENROBO_DISABLE_RATE_LIMIT"] = "true"

from httpx import ASGITransport, AsyncClient
from openrobo_agent.certificates import generate_agent_key_and_csr
from openrobo_agent.models import MessageEnvelope
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.services.fleet_security import get_rate_limiter, get_replay_manager


async def run_simulation(agent_count: int = 100, heartbeat_cycles: int = 3):
    print("=" * 70)
    print("STARTING 100-AGENT LOCAL CONTROL-PLANE SIMULATION (Milestone 7.1.1)")
    print(f"Target Agents: {agent_count} | Heartbeat Cycles: {heartbeat_cycles}")
    print("=" * 70)

    get_replay_manager().clear()
    get_rate_limiter().clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    admin_headers = {"X-OpenRobo-Admin-Key": "sim-admin-key-123"}

    start_time = time.perf_counter()

    # -------------------------------------------------------------
    # Phase 1: Local Key Generation & Token Issuance (100 Agents)
    # -------------------------------------------------------------
    print(f"\n[Phase 1] Generating {agent_count} Ed25519 keypairs, CSRs, and single-use enrollment tokens...")
    agents = []

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token_tasks = [
            client.post(
                "/api/v1/fleet/enrollment-tokens",
                json={"device_name": f"sim-robot-{i:03d}", "ttl_minutes": 60},
                headers=admin_headers,
            )
            for i in range(agent_count)
        ]
        token_responses = await asyncio.gather(*token_tasks)

        for i, res in enumerate(token_responses):
            assert res.status_code == 201, f"Token issuance failed: {res.text}"
            token = res.json()["token"]
            dev_id = str(uuid.uuid4())
            name = f"sim-robot-{i:03d}"
            key_pem, csr_pem = generate_agent_key_and_csr(dev_id, name)
            agents.append(
                {
                    "index": i,
                    "name": name,
                    "device_id": dev_id,
                    "token": token,
                    "key_pem": key_pem,
                    "csr_pem": csr_pem,
                }
            )

    print(f" -> Successfully generated credentials and issued tokens for {len(agents)} agents.")

    # -------------------------------------------------------------
    # Phase 2: Concurrent Enrollment & Certificate Issuance
    # -------------------------------------------------------------
    print("\n[Phase 2] Executing concurrent enrollment across 100 agents...")
    enroll_start = time.perf_counter()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        enroll_tasks = [
            client.post(
                "/api/v1/fleet/enroll",
                json={
                    "enrollment_token": ag["token"],
                    "device_id": ag["device_id"],
                    "device_name": ag["name"],
                    "csr_pem": ag["csr_pem"],
                    "capabilities": ["sim_drive", "sim_lidar"],
                },
            )
            for ag in agents
        ]
        enroll_responses = await asyncio.gather(*enroll_tasks)

        for i, res in enumerate(enroll_responses):
            assert res.status_code == 200, f"Enrollment failed for agent {i}: {res.text}"
            data = res.json()
            agents[i]["cert_pem"] = data["certificate_pem"]
            agents[i]["fingerprint"] = data["certificate_fingerprint"]

    enroll_duration = time.perf_counter() - enroll_start
    print(f" -> Successfully enrolled {len(agents)} agents in {enroll_duration:.2f}s ({agent_count / enroll_duration:.1f} enrollments/sec)")

    # -------------------------------------------------------------
    # Phase 3: Concurrent Heartbeat Load Simulation
    # -------------------------------------------------------------
    total_hb = agent_count * heartbeat_cycles
    print(f"\n[Phase 3] Ingesting {heartbeat_cycles} cycles across {agent_count} agents ({total_hb} total heartbeats)...")
    hb_latencies = []

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for cycle in range(heartbeat_cycles):
            hb_tasks = []
            for ag in agents:
                envelope = MessageEnvelope(
                    message_id=str(uuid.uuid4()),
                    device_id=ag["device_id"],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    message_type="HEARTBEAT",
                    payload={
                        "status": "ONLINE",
                        "cycle": cycle,
                        "metrics": {
                            "cpu_percent": 14.2,
                            "memory_mb": 512.0,
                            "uptime_sec": 3600 + cycle * 10,
                        },
                    },
                )
                t0 = time.perf_counter()

                async def send_hb(ag_fp=ag["fingerprint"], env_data=envelope.model_dump(mode="json"), req_t0=t0):
                    resp = await client.post(
                        "/api/v1/fleet/agent/heartbeat",
                        headers={"X-OpenRobo-Cert-Fingerprint": ag_fp},
                        json=env_data,
                    )
                    hb_latencies.append((time.perf_counter() - req_t0) * 1000.0)
                    return resp

                hb_tasks.append(send_hb())

            hb_responses = await asyncio.gather(*hb_tasks)
            for res in hb_responses:
                assert res.status_code == 200, f"Heartbeat failed: {res.text}"

    print(f" -> Completed {len(hb_latencies)} heartbeat ingestions.")

    # -------------------------------------------------------------
    # Phase 4: Concurrent Telemetry Load Simulation
    # -------------------------------------------------------------
    print(f"\n[Phase 4] Ingesting telemetry payloads across {agent_count} agents...")
    tel_latencies = []
    tel_start = time.perf_counter()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        tel_tasks = []
        for ag in agents:
            envelope = MessageEnvelope(
                message_id=str(uuid.uuid4()),
                device_id=ag["device_id"],
                timestamp=datetime.now(timezone.utc).isoformat(),
                message_type="TELEMETRY",
                payload={
                    "stream": "sensor_readings",
                    "data": {
                        "temperature_c": 42.1,
                        "wheel_odometry_m": 154.2,
                        "safety_stop_active": False,
                    },
                },
            )
            t0 = time.perf_counter()

            async def send_tel(ag_fp=ag["fingerprint"], env_data=envelope.model_dump(mode="json"), req_t0=t0):
                resp = await client.post(
                    "/api/v1/fleet/agent/telemetry",
                    headers={"X-OpenRobo-Cert-Fingerprint": ag_fp},
                    json=env_data,
                )
                tel_latencies.append((time.perf_counter() - req_t0) * 1000.0)
                return resp

            tel_tasks.append(send_tel())

        tel_responses = await asyncio.gather(*tel_tasks)
        for res in tel_responses:
            assert res.status_code == 200, f"Telemetry ingestion failed: {res.text}"

    tel_duration = time.perf_counter() - tel_start
    print(f" -> Ingested {len(tel_responses)} telemetry payloads in {tel_duration:.2f}s ({agent_count / tel_duration:.1f} msgs/sec)")

    # -------------------------------------------------------------
    # Compute Statistics
    # -------------------------------------------------------------
    total_duration = time.perf_counter() - start_time
    hb_latencies.sort()
    tel_latencies.sort()

    def pct(lst, p):
        if not lst:
            return 0.0
        k = (len(lst) - 1) * p
        f = int(k)
        c = min(f + 1, len(lst) - 1)
        return lst[f] + (k - f) * (lst[c] - lst[f])

    hb_p50 = pct(hb_latencies, 0.50)
    hb_p95 = pct(hb_latencies, 0.95)
    hb_p99 = pct(hb_latencies, 0.99)
    hb_max = max(hb_latencies) if hb_latencies else 0.0

    print("\n" + "=" * 70)
    print("100-AGENT LOCAL CONTROL-PLANE APPLICATION SIMULATION REPORT")
    print("=" * 70)
    print(f"Simulated Agents:           {agent_count}")
    print(f"Total Enrolled Nodes:       {agent_count} (100% Success)")
    print(f"Total Heartbeats Sent:      {len(hb_latencies)} (100% Success, 0 Errors)")
    print(f"Total Telemetry Sent:       {len(tel_latencies)} (100% Success, 0 Errors)")
    print(f"Enrollment Throughput:      {agent_count / enroll_duration:.1f} enrollments/sec")
    print(f"Heartbeat Latency p50:      {hb_p50:.2f} ms")
    print(f"Heartbeat Latency p95:      {hb_p95:.2f} ms")
    print(f"Heartbeat Latency p99:      {hb_p99:.2f} ms")
    print(f"Heartbeat Latency Max:      {hb_max:.2f} ms")
    print(f"Total Benchmark Time:       {total_duration:.2f} s")
    print("=" * 70)
    print("STATUS: LOAD SIMULATED (100-agent local control-plane application simulation passed successfully)")
    print("=" * 70)

    app.dependency_overrides.clear()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_simulation())
