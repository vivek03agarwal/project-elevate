"""Model Context Protocol (MCP) Client & Bridge for Mock SaaS Integrations.

Connects to the external Mock SaaS MCP Server:
- Endpoint: https://mock-saas.aishprabhat.demo.altostrat.com
- Auth Token: mcp_HB5laIVgmXjfFK7zBfDPQWixOs3QG0IdUm_goLxRwPY

Provides:
1. MCP Tool discovery and remote invocation via JSON-RPC 2.0 / REST API
2. Dual-mode fallback to local high-fidelity Mock SaaS engine for offline resilience
3. Dynamic MCP tool registration for ADK LlmAgent
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from agent.tools.transaction_tools import (
    serviceimmediately_create_incident_ticket,
    serviceimmediately_get_incident_status,
    workweek_get_pto_balances,
    workweek_submit_leave_request,
)

logger = logging.getLogger(__name__)

DEFAULT_MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://mock-saas.aishprabhat.demo.altostrat.com")
DEFAULT_MCP_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_HB5laIVgmXjfFK7zBfDPQWixOs3QG0IdUm_goLxRwPY")


class MockSaasMcpClient:
    """Client connecting to Model Context Protocol (MCP) SaaS backends."""

    def __init__(self, base_url: str = DEFAULT_MCP_SERVER_URL, auth_token: str = DEFAULT_MCP_TOKEN):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token

    def _call_remote(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Makes an authenticated HTTP call to the remote MCP server."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "User-Agent": "Altostrat-Elevate-Agent/2.7 (MCP-Client)",
        }
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in (200, 201):
                    return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Remote MCP API call to {url} failed: {e}. Falling back to local engine.")
        return None

    def list_mcp_tools(self) -> List[Dict[str, Any]]:
        """Discovers available tools from remote MCP or returns declared schema."""
        remote_tools = self._call_remote("mcp/v1/tools")
        if remote_tools and "tools" in remote_tools:
            return remote_tools["tools"]

        return [
            {
                "name": "workweek_get_pto_balances",
                "description": "Retrieves the employee's current real-time PTO balances from WorkWeek HCM.",
                "parameters": {"type": "object", "properties": {"employee_id": {"type": "string"}}},
            },
            {
                "name": "workweek_submit_leave_request",
                "description": "Submits a formal leave request to WorkWeek HCM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "leave_type": {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "days_count": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["leave_type", "start_date", "end_date", "days_count"],
                },
            },
            {
                "name": "serviceimmediately_create_incident_ticket",
                "description": "Creates a new incident ticket in ServiceImmediately ITSM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "short_description": {"type": "string"},
                        "priority": {"type": "string"},
                    },
                    "required": ["category", "short_description"],
                },
            },
            {
                "name": "serviceimmediately_get_incident_status",
                "description": "Retrieves the status of an existing ServiceImmediately incident ticket.",
                "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]},
            },
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes tool via remote MCP or local fallback."""
        remote_res = self._call_remote("mcp/v1/call", {"name": tool_name, "arguments": arguments})
        if remote_res is not None:
            return remote_res

        # Local High-Fidelity Execution Fallback
        if tool_name == "workweek_get_pto_balances":
            return workweek_get_pto_balances(arguments.get("employee_id", "EMP-504405"))
        elif tool_name == "workweek_submit_leave_request":
            return workweek_submit_leave_request(
                leave_type=arguments.get("leave_type", "Vacation"),
                start_date=arguments.get("start_date", "2026-08-24"),
                end_date=arguments.get("end_date", "2026-08-24"),
                days_count=float(arguments.get("days_count", 1.0)),
                reason=arguments.get("reason"),
            )
        elif tool_name == "serviceimmediately_create_incident_ticket":
            return serviceimmediately_create_incident_ticket(
                category=arguments.get("category", "Hardware"),
                short_description=arguments.get("short_description", "IT Request"),
                priority=arguments.get("priority", "3 - Moderate"),
            )
        elif tool_name == "serviceimmediately_get_incident_status":
            return serviceimmediately_get_incident_status(arguments.get("ticket_id", ""))

        raise ValueError(f"Unknown MCP tool: {tool_name}")


# Global singleton instance
mcp_client = MockSaasMcpClient()
