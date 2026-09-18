import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from openrobo_agent.certificates import (
    parse_certificate,
    validate_csr_identity,
)
from openrobo_agent.models import (
    DeviceStatus,
    EnrollmentRequest,
    EnrollmentResponse,
    MessageEnvelope,
)
from openrobo_release.deployment_protocol import (
    DeploymentAckEnvelope,
    DeploymentInstructionEnvelope,
    DeploymentStatusReport,
    InstructionType,
)
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.deployment import DeploymentInstructionModel
from apps.api.models.fleet import (
    AgentEnrollmentTokenModel,
    AgentHeartbeatModel,
    AgentTelemetryEventModel,
    FleetDeviceModel,
)
from apps.api.services.deployment_service import DeploymentService
from apps.api.services.fleet_pki import get_fleet_pki_service
from apps.api.services.fleet_security import (
    derive_fleet_device_status,
    generate_enrollment_token,
    get_identity_extractor,
    get_rate_limiter,
    get_replay_manager,
    get_websocket_registry,
    hash_enrollment_token,
    verify_admin_authorization,
    verify_device_authorization,
)

logger = logging.getLogger("openrobo.fleet.router")
router = APIRouter(prefix="/fleet", tags=["Fleet Management & Agent Foundation"])

ALLOWED_OPERATIONS = {
    "PING",
    "GET_AGENT_INFO",
    "GET_RUNTIME_STATUS",
    "GET_ROS_ENVIRONMENT",
    "GET_ROS_GRAPH",
    "GET_RUNTIME_DIAGNOSTICS",
    "GET_CONNECTION_INSPECTOR_STATUS",
    "GET_SIMULATOR_STATUS",
    "HEARTBEAT",
    "TELEMETRY",
    "DEPLOYMENT_ACK",
    "DEPLOYMENT_STATUS",
    "DEPLOYMENT_EVENT",
}

FORBIDDEN_OPERATIONS = {
    "SHELL",
    "EXEC",
    "COMMAND",
    "RUN_SCRIPT",
    "PYTHON",
    "UPLOAD_AND_EXECUTE",
    "STAGE_RELEASE",
    "ACTIVATE_RELEASE",
    "CANCEL_DEPLOYMENT",
    "GET_DEPLOYMENT_STATUS",
    "RUN",
    "TASK",
    "SCRIPT",
    "ACTION",
}


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# Pydantic Schemas for Router
class CreateTokenRequest(BaseModel):
    device_name: Optional[str] = Field(None, description="Optional target device name or bound device ID")
    ttl_minutes: int = Field(default=60, ge=1, le=10080, description="Token TTL in minutes")


class TokenResponse(BaseModel):
    token: str
    token_id: str
    expires_at: datetime
    device_name: Optional[str] = None


class RevokeDeviceRequest(BaseModel):
    reason: str = Field(default="Administrative revocation", description="Reason for certificate revocation")


class TelemetryBatchRequest(BaseModel):
    messages: List[MessageEnvelope]


class DeviceSummary(BaseModel):
    id: str
    name: str
    domain: str
    robot_type: str
    status: str
    certificate_fingerprint: str
    capabilities: List[str]
    last_heartbeat_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class DeviceDetail(DeviceSummary):
    certificate_serial: Optional[str]
    revoked_at: Optional[datetime]
    revocation_reason: Optional[str]
    last_heartbeat: Optional[Dict[str, Any]]


# Dependencies
async def get_authenticated_device(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> FleetDeviceModel:
    extractor = get_identity_extractor()
    fingerprint = extractor.extract_device_fingerprint(request)

    if not fingerprint:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client certificate authentication required. No verified client certificate identity presented.",
        )

    stmt = select(FleetDeviceModel).where(FleetDeviceModel.certificate_fingerprint == fingerprint)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No registered device corresponds to the presented certificate fingerprint.",
        )

    # Check Revocation
    if device.revoked_at is not None or device.status == "REVOKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device '{device.id}' certificate is REVOKED. Access denied.",
        )

    # Check Certificate Expiration
    if device.certificate_pem:
        parsed_cert = parse_certificate(device.certificate_pem)
        if parsed_cert.get("is_expired"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Device '{device.id}' certificate is EXPIRED. Access denied.",
            )

    return device


# Endpoints
@router.post("/enrollment-tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment_token(
    req: CreateTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    verify_admin_authorization(request)
    limiter = get_rate_limiter()
    limiter.check("create_token", max_requests=60, window_seconds=60)

    raw_token, token_hash = generate_enrollment_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=req.ttl_minutes)

    token_model = AgentEnrollmentTokenModel(
        id=str(uuid.uuid4()),
        token_hash=token_hash,
        device_name=req.device_name,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(token_model)
    await db.commit()
    await db.refresh(token_model)

    return TokenResponse(
        token=raw_token,
        token_id=token_model.id,
        expires_at=expires_at,
        device_name=req.device_name,
    )


@router.post("/enroll", response_model=EnrollmentResponse)
async def enroll_device(
    req: EnrollmentRequest,
    db: AsyncSession = Depends(get_db),
):
    limiter = get_rate_limiter()
    limiter.check("enroll", max_requests=30, window_seconds=60)

    if len(req.csr_pem.encode("utf-8")) > 16384:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSR payload exceeds maximum permitted size (16KB).",
        )

    token_str = req.get_token()
    token_hash = hash_enrollment_token(token_str)
    now = datetime.now(timezone.utc)

    # Atomic single-use consumption update with expiration enforcement
    update_stmt = (
        update(AgentEnrollmentTokenModel)
        .where(
            AgentEnrollmentTokenModel.token_hash == token_hash,
            AgentEnrollmentTokenModel.is_used.is_(False),
            AgentEnrollmentTokenModel.expires_at > now,
        )
        .values(
            is_used=True,
            used_at=now,
            used_by_device_id=req.device_id,
        )
    )
    upd_res = await db.execute(update_stmt)

    if upd_res.rowcount == 0:
        stmt = select(AgentEnrollmentTokenModel).where(AgentEnrollmentTokenModel.token_hash == token_hash)
        result = await db.execute(stmt)
        token_model = result.scalar_one_or_none()

        if not token_model:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid enrollment token.",
            )

        if token_model.is_used:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Enrollment token has already been consumed.",
            )

        if ensure_utc(token_model.expires_at) <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Enrollment token has expired.",
            )

    # Fetch token details
    stmt = select(AgentEnrollmentTokenModel).where(AgentEnrollmentTokenModel.token_hash == token_hash)
    result = await db.execute(stmt)
    token_model = result.scalar_one()

    # Enforce token-device binding if token was pre-bound
    if token_model.device_name:
        bound_name = token_model.device_name.strip().lower()
        req_names = {
            (req.device_name or "").strip().lower(),
            (req.display_name or "").strip().lower(),
            (req.device_id or "").strip().lower(),
        }
        if bound_name not in req_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token is bound to device '{token_model.device_name}', but request specified device '{req.device_id}'.",
            )

    # Validate CSR signature and identity
    is_valid_csr, csr_err = validate_csr_identity(req.csr_pem, req.device_id)
    if not is_valid_csr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSR validation failed: {csr_err}",
        )

    # Sign CSR via PKI Service
    pki = get_fleet_pki_service()
    try:
        cert_pem, fingerprint, serial_number, cert_expires_at = pki.sign_csr(req.csr_pem)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to sign CSR: {e}",
        )

    # Create or update device model
    device_name = req.device_name or req.display_name or token_model.device_name or f"robot-{req.device_id[:8]}"

    device_stmt = select(FleetDeviceModel).where(FleetDeviceModel.id == req.device_id)
    device_res = await db.execute(device_stmt)
    existing_device = device_res.scalar_one_or_none()

    caps_list: List[str] = []
    if req.capabilities:
        if isinstance(req.capabilities, list):
            caps_list = [str(c) for c in req.capabilities]
        elif hasattr(req.capabilities, "model_dump"):
            caps_list = [f"{k}={v}" for k, v in req.capabilities.model_dump().items() if v]
        elif isinstance(req.capabilities, dict):
            caps_list = [f"{k}={v}" for k, v in req.capabilities.items() if v]

    if existing_device:
        existing_device.name = device_name
        existing_device.domain = req.domain
        existing_device.robot_type = req.robot_type
        existing_device.certificate_fingerprint = fingerprint
        existing_device.certificate_serial = serial_number
        existing_device.certificate_pem = cert_pem
        existing_device.capabilities_json = caps_list
        existing_device.status = "ENROLLED"
        existing_device.revoked_at = None
        existing_device.revocation_reason = None
    else:
        new_device = FleetDeviceModel(
            id=req.device_id,
            name=device_name,
            domain=req.domain,
            robot_type=req.robot_type,
            certificate_fingerprint=fingerprint,
            certificate_serial=serial_number,
            certificate_pem=cert_pem,
            status="ENROLLED",
            capabilities_json=caps_list,
        )
        db.add(new_device)

    await db.commit()

    ca_pem = ""
    try:
        ca_pem = pki._get_ca().ca_cert_pem
    except Exception:
        pass

    return EnrollmentResponse(
        device_id=req.device_id,
        certificate_pem=cert_pem,
        ca_certificate_pem=ca_pem,
        certificate_fingerprint=fingerprint,
        certificate_serial=serial_number,
        expires_at=cert_expires_at,
        status=DeviceStatus.ONLINE,
    )


@router.get("/devices", response_model=List[DeviceSummary])
async def list_devices(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    verify_admin_authorization(request)
    stmt = select(FleetDeviceModel).order_by(FleetDeviceModel.created_at.desc())
    result = await db.execute(stmt)
    devices = result.scalars().all()

    now = datetime.now(timezone.utc)
    summaries = []
    for d in devices:
        computed_status = derive_fleet_device_status(d, now)
        summaries.append(
            DeviceSummary(
                id=d.id,
                name=d.name,
                domain=d.domain,
                robot_type=d.robot_type,
                status=computed_status,
                certificate_fingerprint=d.certificate_fingerprint,
                capabilities=d.capabilities_json or [],
                last_heartbeat_at=d.last_heartbeat_at,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
        )
    return summaries


@router.get("/devices/{device_id}", response_model=DeviceDetail)
async def get_device(
    device_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    verify_admin_authorization(request)
    stmt = select(FleetDeviceModel).where(FleetDeviceModel.id == device_id)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    computed_status = derive_fleet_device_status(device, now)

    return DeviceDetail(
        id=device.id,
        name=device.name,
        domain=device.domain,
        robot_type=device.robot_type,
        status=computed_status,
        certificate_fingerprint=device.certificate_fingerprint,
        certificate_serial=device.certificate_serial,
        revoked_at=device.revoked_at,
        revocation_reason=device.revocation_reason,
        capabilities=device.capabilities_json or [],
        last_heartbeat_at=device.last_heartbeat_at,
        last_heartbeat=device.last_heartbeat_json,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


@router.post("/devices/{device_id}/revoke", response_model=DeviceDetail)
async def revoke_device(
    device_id: str,
    req: RevokeDeviceRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    verify_admin_authorization(request)
    stmt = select(FleetDeviceModel).where(FleetDeviceModel.id == device_id)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    device.status = "REVOKED"
    device.revoked_at = now
    device.revocation_reason = req.reason
    await db.commit()
    await db.refresh(device)

    # Immediately close any active WebSockets for this revoked device
    ws_reg = get_websocket_registry()
    await ws_reg.close_device_connections(device_id, code=1008, reason="Device Revoked")

    return DeviceDetail(
        id=device.id,
        name=device.name,
        domain=device.domain,
        robot_type=device.robot_type,
        status="REVOKED",
        certificate_fingerprint=device.certificate_fingerprint,
        certificate_serial=device.certificate_serial,
        revoked_at=device.revoked_at,
        revocation_reason=device.revocation_reason,
        capabilities=device.capabilities_json or [],
        last_heartbeat_at=device.last_heartbeat_at,
        last_heartbeat=device.last_heartbeat_json,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


@router.get("/devices/{device_id}/telemetry")
async def get_device_telemetry(
    device_id: str,
    request: Request,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    verify_admin_authorization(request)
    stmt = (
        select(AgentTelemetryEventModel)
        .where(AgentTelemetryEventModel.device_id == device_id)
        .order_by(AgentTelemetryEventModel.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "device_id": e.device_id,
            "message_id": e.message_id,
            "event_type": e.event_type,
            "payload": e.payload_json,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]


@router.post("/agent/heartbeat", status_code=status.HTTP_200_OK)
async def ingest_heartbeat(
    envelope: MessageEnvelope,
    device: FleetDeviceModel = Depends(get_authenticated_device),
    db: AsyncSession = Depends(get_db),
):
    # Rate limit check per device
    limiter = get_rate_limiter()
    limiter.check(f"hb_{device.id}", max_requests=180, window_seconds=60)

    # Cross-device authorization check
    verify_device_authorization(device.id, envelope.device_id)

    # Replay protection check
    replay = get_replay_manager()
    replay.validate_and_record(device.id, envelope.message_id, envelope.timestamp)

    now = datetime.now(timezone.utc)
    device.last_heartbeat_at = now
    device.last_heartbeat_json = envelope.payload

    hb_model = AgentHeartbeatModel(
        id=str(uuid.uuid4()),
        device_id=device.id,
        timestamp=now,
        status=envelope.payload.get("status", "ACTIVE"),
        payload_json=envelope.payload,
    )
    db.add(hb_model)
    await db.commit()

    return {"status": "ACK", "message_id": envelope.message_id, "device_id": device.id}


@router.post("/agent/telemetry", status_code=status.HTTP_200_OK)
async def ingest_telemetry(
    envelope: MessageEnvelope,
    device: FleetDeviceModel = Depends(get_authenticated_device),
    db: AsyncSession = Depends(get_db),
):
    limiter = get_rate_limiter()
    limiter.check(f"tel_{device.id}", max_requests=300, window_seconds=60)

    # Cross-device authorization check
    verify_device_authorization(device.id, envelope.device_id)

    # Replay protection check
    replay = get_replay_manager()
    replay.validate_and_record(device.id, envelope.message_id, envelope.timestamp)

    event_type = envelope.payload.get("event_type", envelope.message_type)
    event_model = AgentTelemetryEventModel(
        id=str(uuid.uuid4()),
        device_id=device.id,
        message_id=envelope.message_id,
        timestamp=datetime.fromisoformat(envelope.timestamp.replace("Z", "+00:00")),
        event_type=event_type,
        payload_json=envelope.payload,
    )
    db.add(event_model)
    await db.commit()

    return {"status": "ACK", "message_id": envelope.message_id}


@router.post("/agent/telemetry-batch", status_code=status.HTTP_200_OK)
async def ingest_telemetry_batch(
    payload: Union[TelemetryBatchRequest, List[MessageEnvelope]],
    device: FleetDeviceModel = Depends(get_authenticated_device),
    db: AsyncSession = Depends(get_db),
):
    envelopes = payload.messages if isinstance(payload, TelemetryBatchRequest) else payload

    if len(envelopes) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telemetry batch exceeds maximum limit of 500 envelopes.",
        )

    replay = get_replay_manager()
    accepted = 0
    duplicates = 0
    ack_ids: List[str] = []

    for env in envelopes:
        verify_device_authorization(device.id, env.device_id)
        try:
            replay.validate_and_record(device.id, env.message_id, env.timestamp)
            event_type = env.payload.get("event_type", env.message_type)
            event_model = AgentTelemetryEventModel(
                id=str(uuid.uuid4()),
                device_id=device.id,
                message_id=env.message_id,
                timestamp=datetime.fromisoformat(env.timestamp.replace("Z", "+00:00")),
                event_type=event_type,
                payload_json=env.payload,
            )
            db.add(event_model)
            accepted += 1
            ack_ids.append(env.message_id)
        except HTTPException as e:
            if e.status_code == status.HTTP_409_CONFLICT:
                duplicates += 1
                ack_ids.append(env.message_id)  # duplicate can be acknowledged as already received
            else:
                raise e

    await db.commit()
    return {"status": "BATCH_PROCESSED", "accepted": accepted, "duplicates": duplicates, "acknowledged_ids": ack_ids}


@router.websocket("/agent/ws")
async def agent_websocket(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    """
    Authenticated edge agent WebSocket endpoint.
    Strict mTLS/reverse-proxy authentication: connection is rejected immediately if
    no verified client certificate identity is presented.
    """
    extractor = get_identity_extractor()
    fingerprint = extractor.extract_device_fingerprint(websocket)

    if not fingerprint:
        # Strict security: Close immediately if no verified certificate identity is present.
        # No unauthenticated frame fallback.
        await websocket.close(code=1008, reason="Client certificate authentication required")
        return

    stmt = select(FleetDeviceModel).where(FleetDeviceModel.certificate_fingerprint == fingerprint)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        await websocket.close(code=1008, reason="Unknown Device Certificate")
        return

    # Check Revocation & Expiry
    if device.revoked_at is not None or device.status == "REVOKED":
        await websocket.close(code=1008, reason="Device Revoked")
        return

    if device.certificate_pem:
        parsed = parse_certificate(device.certificate_pem)
        if parsed.get("is_expired"):
            await websocket.close(code=1008, reason="Device Certificate Expired")
            return

    # Verified authenticated identity -> Accept session
    await websocket.accept()

    ws_registry = get_websocket_registry()
    ws_registry.register(device.id, websocket)
    replay = get_replay_manager()

    # Deliver any pending durable outbox instructions for this authenticated device
    try:
        pending_instructions = await DeploymentService.get_pending_instructions_for_device(db, device.id)
        for inst in pending_instructions:
            payload_dict = {}
            try:
                payload_dict = json.loads(inst.payload_json)
            except Exception:
                pass
            created_dt = inst.created_at.replace(tzinfo=timezone.utc) if inst.created_at.tzinfo is None else inst.created_at
            expires_dt = inst.expires_at.replace(tzinfo=timezone.utc) if inst.expires_at.tzinfo is None else inst.expires_at
            inst_envelope = DeploymentInstructionEnvelope(
                instruction_id=inst.id,
                deployment_id=inst.deployment_id,
                device_id=inst.device_id,
                generation=inst.generation,
                instruction_type=InstructionType(inst.instruction_type),
                payload=payload_dict,
                payload_digest=inst.payload_digest,
                created_at=created_dt.isoformat(),
                expires_at=expires_dt.isoformat(),
            )
            await websocket.send_json(
                {
                    "message_type": "DEPLOYMENT_INSTRUCTION",
                    "instruction": inst_envelope.model_dump(),
                }
            )
            inst.status = "SENT"
            inst.attempt_count += 1
            now_dt = datetime.now(timezone.utc)
            inst.last_attempt_at = now_dt
            inst.next_attempt_at = now_dt + timedelta(seconds=min(300, 2 ** min(inst.attempt_count, 8)))
        if pending_instructions:
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to deliver pending instructions to device {device.id}: {e}")

    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                data = json.loads(raw_msg)
                envelope = MessageEnvelope.model_validate(data)
            except Exception as e:
                await websocket.send_json({"status": "ERROR", "error": f"Invalid MessageEnvelope: {e}"})
                continue

            # 1. Protocol version validation
            if envelope.protocol_version not in ("1.0", "1.1"):
                await websocket.send_json(
                    {
                        "status": "ERROR",
                        "error": f"Unsupported protocol_version '{envelope.protocol_version}'.",
                    }
                )
                continue

            # 2. Device authorization validation
            if envelope.device_id != device.id:
                await websocket.send_json(
                    {
                        "status": "ERROR",
                        "error": f"Cross-device access forbidden: device '{device.id}' cannot assert identity '{envelope.device_id}'.",
                    }
                )
                continue

            # 3. Check live revocation
            await db.refresh(device)
            if device.revoked_at is not None or device.status == "REVOKED":
                await websocket.close(code=1008, reason="Device Revoked")
                break

            # 4. Operations allowlist
            msg_type = envelope.message_type.upper()
            if msg_type in FORBIDDEN_OPERATIONS:
                await websocket.send_json(
                    {
                        "status": "FORBIDDEN",
                        "error": f"Execution operation '{msg_type}' is strictly prohibited.",
                    }
                )
                continue

            if msg_type not in ALLOWED_OPERATIONS:
                await websocket.send_json(
                    {
                        "status": "REJECTED",
                        "error": f"Unknown or disallowed operation '{msg_type}'.",
                    }
                )
                continue

            # 5. Replay protection
            try:
                replay.validate_and_record(device.id, envelope.message_id, envelope.timestamp)
            except HTTPException as e:
                await websocket.send_json(
                    {
                        "status": "REJECTED",
                        "error": e.detail,
                        "code": e.status_code,
                    }
                )
                continue

            # 6. Process message
            if msg_type == "PING":
                await websocket.send_json(
                    {
                        "message_type": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reply_to": envelope.message_id,
                    }
                )
            elif msg_type == "DEPLOYMENT_ACK":
                try:
                    ack_env = DeploymentAckEnvelope.model_validate(envelope.payload)
                    if ack_env.device_id != device.id:
                        await websocket.send_json({"status": "ERROR", "error": "Cross-device ACK forbidden"})
                        continue
                    inst_stmt = select(DeploymentInstructionModel).where(
                        DeploymentInstructionModel.id == ack_env.instruction_id,
                        DeploymentInstructionModel.device_id == device.id,
                    )
                    inst_res = await db.execute(inst_stmt)
                    inst = inst_res.scalar_one_or_none()
                    if not inst:
                        await websocket.send_json(
                            {"status": "ERROR", "error": f"Instruction '{ack_env.instruction_id}' not found for device '{device.id}'"}
                        )
                        continue

                    # Amendment 3: Strict ACK correlation
                    if ack_env.deployment_id != inst.deployment_id:
                        await websocket.send_json(
                            {"status": "ERROR", "error": f"ACK deployment_id mismatch: {ack_env.deployment_id} != {inst.deployment_id}"}
                        )
                        continue
                    if ack_env.generation != inst.generation:
                        await websocket.send_json(
                            {"status": "ERROR", "error": f"ACK generation mismatch: {ack_env.generation} != {inst.generation}"}
                        )
                        continue
                    if inst.status in ("EXPIRED", "CANCELLED", "FAILED"):
                        await websocket.send_json(
                            {"status": "ERROR", "error": f"Cannot ACK instruction in terminal status '{inst.status}'"}
                        )
                        continue

                    if ack_env.accepted:
                        inst.status = "ACKNOWLEDGED"
                    else:
                        inst.status = "REJECTED"
                        inst.rejection_reason = ack_env.error_message or ack_env.error_code or "REJECTED"

                    inst.acknowledged_at = datetime.now(timezone.utc)
                    await db.commit()
                    await websocket.send_json({"status": "ACK", "message_id": envelope.message_id, "device_id": device.id})
                except Exception as e:
                    await websocket.send_json({"status": "ERROR", "error": f"Invalid DEPLOYMENT_ACK payload: {e}"})
            elif msg_type == "DEPLOYMENT_STATUS":
                try:
                    status_report = DeploymentStatusReport.model_validate(envelope.payload)
                    if status_report.device_id != device.id:
                        await websocket.send_json({"status": "ERROR", "error": "Cross-device status report forbidden"})
                        continue
                    await DeploymentService.handle_device_status_report(db, device.id, status_report)
                    await db.commit()
                    await websocket.send_json(
                        {"status": "ACK", "message_id": envelope.message_id, "report_id": status_report.report_id, "device_id": device.id}
                    )
                except Exception as e:
                    await db.rollback()
                    await websocket.send_json({"status": "ERROR", "error": f"Status update failed: {e}"})
            else:
                await websocket.send_json(
                    {
                        "status": "ACK",
                        "message_id": envelope.message_id,
                        "device_id": device.id,
                    }
                )

    except WebSocketDisconnect:
        pass
    finally:
        ws_registry.unregister(device.id, websocket)
