# Milestone 7.2.2 — Authenticated Remote Deployment Orchestration & Canary Rollout Plan

## Objective

Build on the Milestone 7.2.1 cryptographic release artifact and local A/B slot foundation to introduce:
1. Authenticated remote deployment requests over mTLS / control-plane channels.
2. Controlled artifact distribution and download verification.
3. Fleet-wide targeting, deployment rollout state machine, and progressive canary rollouts.

> [!IMPORTANT]
> Milestone 7.2.2 focuses purely on orchestration, scheduling, and canary stages with explicit operator approval gates. Automatic runtime health gates and automatic metric rollback triggers belong to Milestone 7.2.3.

---

## Architectural Components

`mermaid
flowchart TD
    CP[Control Plane / Release Manager] -->|POST /api/v1/deployments| DS[Deployment Orchestrator]
    DS -->|Target Filtering| TF[Target Fleet / Device Selector]
    DS -->|Stage 1: Canary 10%| C1[Canary Group A]
    DS -->|Stage 2: Canary 50%| C2[Canary Group B]
    DS -->|Stage 3: Full 100%| C3[Remaining Fleet]

    C1 -->|Fetch & Stage| AG[Remote Robot Agent]
    AG -->|Verify Sig & Digest| V[ReleaseVerifier]
    AG -->|Stage into Inactive Slot| SM[ABSlotManager]
    AG -->|Report Deployment Telemetry| CP
`

### 1. Deployment Models & Schemas
- DeploymentRequest:
  - deployment_id: UUID
  -
elease_id: Target release UUID
  - manifest_digest: SHA-256
  - rtifact_source_id: Configured trusted source identifier
  - 	arget_filter: Platform/architecture/tag selector
  -
ollout_strategy: CANARY_STAGED | IMMEDIATE | SINGLE_DEVICE
  - canary_stages: List of percentage thresholds and soaking periods (e.g. [10%, 50%, 100%])
- DeviceDeploymentState:
  - PENDING -> DOWNLOADING -> VERIFYING -> STAGING -> STAGED -> ACTIVATING -> ACTIVE | FAILED

### 2. Controlled Artifact Distribution
- Artifact downloads restricted to allowlisted origins (OPENROBO_TRUSTED_ARTIFACT_HOSTS).
- Size limits, streaming SHA-256 verification, and strict timeout enforcement.
- Agent verifies signature, manifest, and artifact digest before extracting.

### 3. Progressive Canary Engine with Operator Approval
- Deterministic device partitioning by cohort / tags / consistent hash.
- Progression gates require explicit operator approval between canary stages until Milestone 7.2.3.
- Fleet-level deployment lifecycle tracking and cancellation primitives.

---

## Planned Implementation Steps

1. **Deployment Core Models (openrobo_fleet.deployment / pps/api/services/deployment_service.py)**:
   - Define database schema & Alembic migration for deployments and device deployment tracking.
2. **Control Plane REST & WebSocket Protocol**:
   - Add endpoints for creating, inspecting, pausing, and cancelling fleet deployments.
   - Dispatch deployment jobs over authenticated mTLS agent channels.
3. **Agent Deployment Worker**:
   - Integrate agent daemon with remote job poller / push receiver.
   - Execute fetch -> verify -> stage -> activate workflow via ABSlotManager.
4. **Canary Rollout Coordinator**:
   - Progressive batch scheduler with deterministic cohort assignment and manual approval gates.
5. **Acceptance Testing**:
   - Multi-agent simulation testing canary progression (10% -> 50% -> 100%).

---

## Boundaries & Non-Goals for M7.2.2
- **NO Automatic Health Rollback**: Health gates and automatic metric regression rollback belong to M7.2.3.
- **NO Fleet Studio UI Modifications**: Deployment UI visualizations belong to M7.2.3.
