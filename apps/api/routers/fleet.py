import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from openrobo_agent.models import (
    DeviceStatus,
    EnrollmentRequest,
    EnrollmentResponse,
    MessageEnvelope,
)
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.fleet import (
    AgentEnrollmentTokenModel,
    AgentHeartbeatModel,
    AgentTelemetryEventModel,
    FleetDeviceModel,
)
from apps.api.services.fleet_pki import get_fleet_pki_service
from apps.api.services.fleet_security import (
    derive_fleet_device_status,
    generate_enrollment_token,
    get_identity_extractor,
    get_replay_manager,
    hash_enrollment_token,
    verify_device_authorization,
)

router = APIRouter(prefix="/fleet", tags=["Fleet Management & Agent Foundation"])


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# Pydantic Schemas for Router
class CreateTokenRequest(BaseModel):
    device_name: Optional[str] = Field(None, description="Optional target device name")
    ttl_minutes: int = Field(default=60, ge=1, le=10080, description="Token TTL in minutes")


class TokenResponse(BaseModel):
    token: str
    token_id: str
    expires_at: datetime
    device_name: Optional[str] = None


class RevokeDeviceRequest(BaseModel):
    reason: str = Field(default="Administrative revocation", description="Reason for certificate revocation")


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

    return device


# Endpoints
@router.post("/enrollment-tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment_token(
    req: CreateTokenRequest,
    db: AsyncSession = Depends(get_db),
):
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
    token_str = req.get_token()
    token_hash = hash_enrollment_token(token_str)
    now = datetime.now(timezone.utc)

    # Atomic single-use consumption update
    update_stmt = (
        update(AgentEnrollmentTokenModel)
        .where(
            AgentEnrollmentTokenModel.token_hash == token_hash,
            AgentEnrollmentTokenModel.is_used.is_(False),
        )
        .values(
            is_used=True,
            used_at=now,
            used_by_device_id=req.device_id,
        )
    )
    upd_res = await db.execute(update_stmt)

    if upd_res.rowcount == 0:
        # Check why update didn't match: missing, already used, or expired
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

        if ensure_utc(token_model.expires_at) < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Enrollment token has expired.",
            )

    # Fetch token details
    stmt = select(AgentEnrollmentTokenModel).where(AgentEnrollmentTokenModel.token_hash == token_hash)
    result = await db.execute(stmt)
    token_model = result.scalar_one()

    # Sign CSR via PKI Service
    pki = get_fleet_pki_service()
    try:
        cert_pem, fingerprint, serial_number = pki.sign_csr(req.csr_pem)
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
        elif hasattr(req.capabilities, 'model_dump'):
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

    expires_at = now + timedelta(days=365)

    return EnrollmentResponse(
        device_id=req.device_id,
        certificate_pem=cert_pem,
        ca_certificate_pem=ca_pem,
        certificate_fingerprint=fingerprint,
        certificate_serial=serial_number,
        expires_at=expires_at.isoformat(),
        status=DeviceStatus.ONLINE,
    )


@router.get("/devices", response_model=List[DeviceSummary])
async def list_devices(
    db: AsyncSession = Depends(get_db),
):
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



@router.get("/devices/{device_id}/telemetry")
async def get_device_telemetry(
    device_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
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

@router.get("/devices/{device_id}", response_model=DeviceDetail)
async def get_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
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
    db: AsyncSession = Depends(get_db),
):
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


@router.post("/agent/heartbeat", status_code=status.HTTP_200_OK)
async def ingest_heartbeat(
    envelope: MessageEnvelope,
    device: FleetDeviceModel = Depends(get_authenticated_device),
    db: AsyncSession = Depends(get_db),
):
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
    envelopes: List[MessageEnvelope],
    device: FleetDeviceModel = Depends(get_authenticated_device),
    db: AsyncSession = Depends(get_db),
):
    replay = get_replay_manager()
    accepted = 0
    duplicates = 0

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
        except HTTPException as e:
            if e.status_code == status.HTTP_409_CONFLICT:
                duplicates += 1
            else:
                raise e

    await db.commit()
    return {"status": "BATCH_PROCESSED", "accepted": accepted, "duplicates": duplicates}


@router.websocket("/agent/ws")
async def agent_websocket(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if "message_type" in data and data["message_type"] == "PING":
                await websocket.send_json({"message_type": "PONG", "timestamp": datetime.now(timezone.utc).isoformat()})
            else:
                await websocket.send_json({"status": "ACK", "message_id": data.get("message_id")})
    except WebSocketDisconnect:
        pass
