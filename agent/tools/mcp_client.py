"""Live Model Context Protocol (MCP) and REST Client for Mock SaaS Backend.

Connects directly to the live Mock SaaS platform:
- Base URL: https://mock-saas.aishprabhat.demo.altostrat.com
- User: Vivekagar Employee (EMP-439)
- APIs:
  - /service-immediately/api/tickets (GET, POST)
  - /work-week/api/employees/{employee_id}/profile (GET)
  - /work-week/api/employees/{employee_id}/timeoff (GET, POST)
  - /work-week/api/employees/{employee_id}/timeoff/requests (GET)
"""

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MOCK_SAAS_URL = os.getenv("MOCK_SAAS_URL", "https://mock-saas.aishprabhat.demo.altostrat.com").rstrip("/")
DEFAULT_EMPLOYEE_ID = os.getenv("EMPLOYEE_ID", "EMP-439")
MCP_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_OMAYt-SofNhqyJXHYmpE-3KGoBkq9aHAiu16hU7io6I")

# Authenticated Session Cookie from user profile
MOCK_SAAS_COOKIE = os.getenv(
    "MOCK_SAAS_COOKIE",
    "GCP_IAP_UID=115709982330568655101; __Host-GCP_IAP_AUTH_TOKEN_444579F2A51CC690=AQ_X0ghVyd9uJC1FQTIOzxWt6656-7-04GoWI09NO2gJc1FX9SNJWR9WiWJuzELdf_rIb9k51Q3hvP5VIPI68ewEF25eeR963r_X5Dbl1MFJJse-d4ORGA_qr3lPowWqYa3lanED8Y1dWlYQrceUkQ_gXMp7NuUCfuVFekj9pL5J0bNh7i4w6WS20iTUd37Nl5m9gx7JyQhVVCErOYOn1_mPKhYcUe2TO42QspiUz_5OVhTg38jBUl6x-ccdK30gFm8oosN7XmYzTE-sThRG3tqnVIKsnnYKunCVfRgvkqHYKnJIC8vtsXDrujsz1e9B-6KE7orHqHPgifFJhLwi89qzytxoNatmq7pq179-bSfZ_mmSGC4lo6y222ED4GOrrE75Ci4HdKRySkEOjqCB9DH6OyLFQ7XXDzICEFhIa7-TBCWBHloGedL4p9FbaNU8NkVtU0pPEMBtHmx_frA7_UVBWr6kewG8iesNg0cKzAKk0jju8C3JyxyzAhrsdXHBqJD4fDz56k_40PqZgQYVkjKVNf6fx0GNQn6XaeOZuT601sVHxx20VrmPvN-l9U81et4buQx-du0l13zMHebObcStgzB_pSy0CzXWEWHuNd9P4HXey0Se-kJPWiHDr3m5ytWuNr6G1hA3vAJw3kkkvXZM_-Lr1q24ikbu-OU6F4YDfDXYxpZvFROAlMpy72Q62d02cSQor7sZDZNMn9TLybv1Rl6CPk0pKeIk-3GPzGjAgkh4ms5O6f--LbVxzgsSD-hjoAJJf7dQbHFLwbqizKXB5hBfYqnePaAx6TacaFLEGPA_sVmYu3rD2t-NwzxMHduKWLig1Do2OJxYmvuuh24nPsiKzrgfjIVbCjwlDKjzhUd3zSgaCuZPdrUVQJGKD9Pp3sZUOmzPtyQaYmdOaNk5YlP-x1JMg7ppv71n_c72gRg6LzTSw1jrLPzQJC-7DcjN5Uisq7upWLKAo6Gy1sErRKrjvdQBmnl7GeLiq0JBV6YE096PbQcPG2GHGgkJt2yY-4GzbVIEbwz_7h9v_xXPgcLDCjOz5nbJGFrYpfgg2i04s9cGSm0enO7f2E5bBBI_NHI5eBsczBCqlEx-_S_FVSePwFdkecyGVK4a4iwF2hR9H_hOz3Je6Ob8q_E8CEXnuW_gC-gDq9qE9rn9TYmaJCXWgLdanN-_Vx6qHG1USHlQLdE-6JFPg4SCetWcH5fnNRp4dCsVegcBIH2cRYGisemFH00ysPMVxIN_V1usZS_mrQ1zL-blGH_NwcxUHYqZ7Qs2cM3fk2LYZ7Xvs2dvGl6CgEomyX3mP8coleyxNEn0jWMmNqPey4Zf8S_NY7u2tKBCSPg7JTNATWwyAbZOyXtgm8_xck7aGAasFatgwDqlJtUAK3Xp1YVeLPS056u3Bim8y127qCr0TtA8EYcMyvEKRcC4NDKxIg5hmEiG8juNG62fkfEp4ke4z8sf0mJetIzoTjlCyy6Gfg7oGZmu8rPvrGrSvwmWLzBTla7IbFyZi1DfqWvIIaxy4Aq110DiPEY3lR0JoiCR7DdhQ3eBdJUDe5c2X8pDINuvcmstYH8z0MNnogyO0yhsZ7FSnpFN3OicPTLgsYIc2HqxtqfcN7h51kMLfolDAUYuUS2c-1AlXP305G4suyV_P0fUp58wE2le9ssm6hfo_oC5O_XbI63lUm4RjFcnxbA2xxbIqken0_R2YNzB1ybsbCcejBIETb1_cZQSDxc3AYlV9SrDHI7w3jQEyhsLY8TGF9ps; GAESA=CrIBMDAxNTQ4ZjcyOTMzNTI4ZTMxNjdiNzkzYmRjZmY2ZTdmN2M0NWRlMTE1M2E2OGU3YmQyNWQ3M2MzZWMyYThkNGE5ZGQ4Y2I4YjIyNGUxNWEyY2Q0MjVkNjYwYzJhZDkxNTllMWYzOWNjZjViZDI2ZGUxMjQ1OTYxN2M3ZmJmNjlhMGQxMDBkZDkwMjMxNDMwOTJmNzM4NTMzMmVjZmJhMTQyN2M4OTQwNTYwNGVjYTdiMBCRldyjgTQ"
)


class MockSaasLiveClient:
    """Client for direct bi-directional synchronization with the live Mock SaaS platform."""

    def __init__(self, base_url: str = MOCK_SAAS_URL, cookie: str = MOCK_SAAS_COOKIE):
        self.base_url = base_url
        self.cookie = cookie
        self.ssl_ctx = ssl.create_default_context()

    def _request(self, path: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cookie": self.cookie,
            "X-MCP-Token": MCP_TOKEN,
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64) Altostrat-Elevate-Agent/2.7",
        }
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=8) as resp:
                if resp.status in (200, 201):
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Live Mock SaaS API call to {url} failed: {e}")
        return None

    # ServiceImmediately ITSM
    def create_ticket(self, category: str, short_description: str, priority: str = "3 - Moderate", requested_by: str = DEFAULT_EMPLOYEE_ID) -> Optional[Dict[str, Any]]:
        payload = {
            "requested_by": requested_by,
            "category": category,
            "short_description": short_description,
            "priority": priority,
        }
        return self._request("service-immediately/api/tickets", method="POST", payload=payload)

    def list_tickets(self, requested_by: str = DEFAULT_EMPLOYEE_ID) -> List[Dict[str, Any]]:
        res = self._request(f"service-immediately/api/tickets?requested_by={requested_by}", method="GET")
        if isinstance(res, list):
            return res
        return []

    # WorkWeek HCM
    def get_employee_profile(self, employee_id: str = DEFAULT_EMPLOYEE_ID) -> Optional[Dict[str, Any]]:
        return self._request(f"work-week/api/employees/{employee_id}/profile", method="GET")

    def get_timeoff_balances(self, employee_id: str = DEFAULT_EMPLOYEE_ID) -> Optional[Dict[str, Any]]:
        return self._request(f"work-week/api/employees/{employee_id}/timeoff", method="GET")

    def get_timeoff_requests(self, employee_id: str = DEFAULT_EMPLOYEE_ID) -> List[Dict[str, Any]]:
        res = self._request(f"work-week/api/employees/{employee_id}/timeoff/requests", method="GET")
        if isinstance(res, list):
            return res
        return []

    def submit_timeoff_request(self, employee_id: str = DEFAULT_EMPLOYEE_ID, leave_type: str = "Vacation", start_date: str = "2026-08-24", end_date: str = "2026-08-24", days: float = 1.0, reason: str = "") -> Optional[Dict[str, Any]]:
        # Mock SaaS backend strictly accepts either 'Vacation' or 'Sick'
        clean_type = "Vacation"
        lt_lower = leave_type.lower()
        if any(k in lt_lower for k in ["sick", "hospital", "medical", "mc", "outpatient", "doctor", "clinic", "health"]):
            clean_type = "Sick"
        elif any(k in lt_lower for k in ["vacation", "annual", "pto", "holiday", "personal"]):
            clean_type = "Vacation"
        else:
            clean_type = "Vacation"

        payload = {
            "start_date": start_date,
            "end_date": end_date,
            "leave_type": clean_type,
            "days": float(days),
        }
        return self._request(f"work-week/api/employees/{employee_id}/timeoff", method="POST", payload=payload)



# Global singleton instance
mock_saas_client = MockSaasLiveClient()
