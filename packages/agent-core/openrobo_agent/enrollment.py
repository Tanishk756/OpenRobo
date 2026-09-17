"""OpenRobo Device Enrollment Client."""

import json
import urllib.error
import urllib.request
from typing import Optional

from openrobo_agent.heartbeat import HeartbeatSampler
from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.models import EnrollmentRequest, EnrollmentResponse


class DeviceEnrollmentClient:
    """Handles edge agent enrollment with the control plane."""

    def __init__(self, identity_manager: DeviceIdentityManager):
        self.identity_manager = identity_manager
        self.sampler = HeartbeatSampler(identity_manager)

    def enroll(self, token: str, control_plane_url: Optional[str] = None) -> EnrollmentResponse:
        """Execute single-use token enrollment flow."""
        base_url = control_plane_url or self.identity_manager.config.control_plane_url
        endpoint = f"{base_url.rstrip('/')}/api/v1/fleet/enroll"

        csr_pem = self.identity_manager.create_csr()
        identity = self.identity_manager.get_identity()
        capabilities = self.sampler.sample_capabilities()

        req_payload = EnrollmentRequest(
            token=token,
            device_id=self.identity_manager.device_id,
            csr_pem=csr_pem,
            display_name=identity.display_name,
            platform=identity.platform,
            architecture=identity.architecture,
            os_name=identity.os_name,
            agent_version=identity.agent_version,
            capabilities=capabilities,
        )

        data_bytes = req_payload.model_dump_json().encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                enroll_resp = EnrollmentResponse.model_validate(resp_data)
                self.identity_manager.save_enrolled_certificate(
                    enroll_resp.certificate_pem,
                    enroll_resp.ca_certificate_pem,
                )
                return enroll_resp
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Enrollment failed with status {e.code}: {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Network error during enrollment: {str(e)}") from e
