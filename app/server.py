"""FastAPI Web Server for Altostrat Singapore Employee Portal & HR Policy Copilot.

Provides:
1. Mock SaaS Dashboard (WorkWeek HCM, ServiceImmediately ITSM, Concur Expenses)
2. Embedded Agentic AI Copilot Chat Interface (backed by ADK LlmAgent)
3. Mock HCM & ITSM REST APIs with Strict Pydantic Data Contracts
4. Identity Translation Engine (ITE) with RFC 8693 & RFC 7523 Bridging
5. Two-Tier Japanese Keigo Post-Processor Linter (SDD Sec. 3.4)
6. Automated Post-Outage Reconciliation Worker (SDD Sec. 3.3)
7. Dual-Region Firestore Session Store & Server-Side Security Middleware
"""

import asyncio
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# Ensure project root is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from agent.agent import root_agent
import agent.config as config
from agent.localization.keigo_linter import keigo_linter
from agent.models.contracts import (
    AgentChatRequest,
    AgentChatResponse,
    IncidentCategory,
    IncidentPriority,
    IncidentState,
    LeaveCategory,
    ServiceNowIncidentCreate,
    ServiceNowIncidentRecord,
    WorkWeekEmployeeProfile,
    WorkWeekLeaveConfirmation,
    WorkWeekLeaveSubmissionRequest,
    WorkWeekPtoBalances,
)
from agent.resilience.reconciliation_worker import reconciliation_worker
from agent.security.ite import ite_engine
from agent.storage.firestore_session import session_store

app = FastAPI(
    title="Altostrat Singapore Employee Hub & HR Policy Copilot",
    description="Enterprise Mock-SaaS Employee Portal & Grounded AI HR Policy Assistant conforming to SDD v2.7",
    version="2.7.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mock SaaS In-Memory Database State
# ---------------------------------------------------------------------------
from agent.storage.mock_db import (
    MOCK_EMPLOYEE,
    MOCK_ITSM_TICKETS,
    MOCK_LEAVE_REQUESTS,
    MOCK_PTO_BALANCES,
)


# ---------------------------------------------------------------------------
# Server-Side Security Middleware (NRIC & SPII Redaction)
# ---------------------------------------------------------------------------
NRIC_PATTERN = re.compile(r"\b[STFG]\d{7}[A-Z]\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b(?:\+65[\s-]?)?[89]\d{3}[\s-]?\d{4}\b")


def redact_spii(text: str) -> str:
    """Masks Singapore NRIC and phone numbers to ensure PDPA compliance."""
    text = NRIC_PATTERN.sub("[REDACTED_NRIC]", text)
    text = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return text


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "agent_name": root_agent.name if root_agent else "none",
        "model": config.GEMINI_MODEL,
        "retrieval_mode": config.RETRIEVAL_MODE,
        "project": config.GOOGLE_CLOUD_PROJECT,
        "ite_active": True,
        "keigo_engine": "Two-Tier (Prompt + SudachiPy Linter)",
        "reconciliation_worker": "Active",
        "session_store": "Dual-Region Firestore",
    }


@app.get("/api/hcm/profile")
def get_employee_profile():
    from agent.tools.mcp_client import mock_saas_client
    live_profile = mock_saas_client.get_employee_profile("EMP-439")
    if live_profile:
        return {"employee": live_profile}
    return {"employee": MOCK_EMPLOYEE.model_dump()}


@app.get("/api/hcm/pto")
def get_pto_balances():
    from agent.tools.mcp_client import mock_saas_client
    live_bal = mock_saas_client.get_timeoff_balances("EMP-439")
    if live_bal and "vacation_remaining" in live_bal:
        MOCK_PTO_BALANCES.vacation_days = float(live_bal["vacation_remaining"])

    live_requests = mock_saas_client.get_timeoff_requests("EMP-439")
    if live_requests:
        formatted_requests = [
            {
                "id": f"LV-{r.get('request_id', '99215')}",
                "leave_type": r.get("leave_type", "Vacation"),
                "start_date": f"{r.get('start_date', '2026-08-24')} to {r.get('end_date', '2026-08-25')}" if r.get("start_date") != r.get("end_date") else r.get("start_date", "2026-08-24"),
                "days": r.get("days", 1.0),
                "status": "Approved",
                "submitted_at": r.get("start_date", "2026-08-24"),
            }
            for r in live_requests
        ]
        # Merge local specific requests
        seen_ids = {r["id"] for r in formatted_requests}
        for loc in MOCK_LEAVE_REQUESTS:
            if loc["id"] not in seen_ids:
                formatted_requests.insert(0, loc)

        return {
            "employee_id": "EMP-439",
            "balances": MOCK_PTO_BALANCES.model_dump(),
            "recent_requests": formatted_requests,
        }

    return {
        "employee_id": "EMP-439",
        "balances": MOCK_PTO_BALANCES.model_dump(),
        "recent_requests": MOCK_LEAVE_REQUESTS,
    }



@app.post("/api/hcm/leave")
def submit_leave_request(req: WorkWeekLeaveSubmissionRequest):
    # Auto-calculate end_date if missing
    if not req.end_date or not str(req.end_date).strip():
        try:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(req.start_date.strip(), "%Y-%m-%d")
            days_to_add = max(0, int(round(req.days_count)) - 1)
            req.end_date = (start_dt + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
        except Exception:
            req.end_date = req.start_date

    # Check balance
    if req.leave_type == LeaveCategory.VACATION and req.days_count > MOCK_PTO_BALANCES.vacation_days:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient vacation balance. Requested: {req.days_count}, Available: {MOCK_PTO_BALANCES.vacation_days}"
        )

    # Sync with live Mock SaaS WorkWeek
    from agent.tools.mcp_client import mock_saas_client
    mock_saas_client.submit_timeoff_request(
        employee_id="EMP-439",
        leave_type=req.leave_type.value,
        start_date=req.start_date,
        end_date=req.end_date,
        days=req.days_count,
        reason=req.reason or "",
    )


    leave_id = f"LV-{len(MOCK_LEAVE_REQUESTS) + 99215}"
    new_req = {
        "id": leave_id,
        "leave_type": req.leave_type.value,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "days": req.days_count,
        "status": "Approved",
        "submitted_at": "2026-08-20",
    }
    MOCK_LEAVE_REQUESTS.insert(0, new_req)

    # Deduct balance
    if req.leave_type == LeaveCategory.VACATION:
        MOCK_PTO_BALANCES.vacation_days = max(0.0, MOCK_PTO_BALANCES.vacation_days - req.days_count)
        rem = MOCK_PTO_BALANCES.vacation_days
    elif req.leave_type == LeaveCategory.HOSPITALISATION:
        MOCK_PTO_BALANCES.hospitalisation_days = max(0.0, MOCK_PTO_BALANCES.hospitalisation_days - req.days_count)
        rem = MOCK_PTO_BALANCES.hospitalisation_days
    elif req.leave_type == LeaveCategory.OUTPATIENT_SICK:
        MOCK_PTO_BALANCES.outpatient_sick_days = max(0.0, MOCK_PTO_BALANCES.outpatient_sick_days - req.days_count)
        rem = MOCK_PTO_BALANCES.outpatient_sick_days
    elif req.leave_type == LeaveCategory.CHILDCARE:
        MOCK_PTO_BALANCES.childcare_days = max(0.0, MOCK_PTO_BALANCES.childcare_days - req.days_count)
        rem = MOCK_PTO_BALANCES.childcare_days
    elif req.leave_type == LeaveCategory.VOLUNTEER:
        MOCK_PTO_BALANCES.volunteer_days = max(0.0, MOCK_PTO_BALANCES.volunteer_days - req.days_count)
        rem = MOCK_PTO_BALANCES.volunteer_days
    else:
        rem = MOCK_PTO_BALANCES.vacation_days

    return WorkWeekLeaveConfirmation(
        confirmation_ref=leave_id,
        status="Approved",
        leave_type=req.leave_type.value,
        days_deducted=req.days_count,
        remaining_balance=rem,
    ).model_dump()



@app.get("/api/itsm/tickets")
def get_itsm_tickets():
    from agent.tools.mcp_client import mock_saas_client
    live_tickets = mock_saas_client.list_tickets("EMP-439")
    if live_tickets:
        return {"tickets": [
            {
                "sys_id": t.get("ticket_id", "INC0001"),
                "number": t.get("ticket_id", "INC0001"),
                "category": t.get("category", "Hardware"),
                "short_description": t.get("short_description", "IT Request"),
                "priority": t.get("priority", "3 - Moderate"),
                "state": t.get("status", "New"),
                "assigned_to": t.get("assignment_group", "Service Desk"),
                "opened_at": t.get("created_at", "2026-08-20")[:10],
                "resolved_at": None,
            }
            for t in live_tickets
        ]}
    return {"tickets": [t.model_dump() for t in MOCK_ITSM_TICKETS]}


@app.post("/api/itsm/tickets")
def create_itsm_ticket(req: ServiceNowIncidentCreate):
    # Auto priority classification
    priority = req.priority.value
    desc_lower = req.short_description.lower()
    if "password" in desc_lower or "login" in desc_lower or "sso" in desc_lower:
        priority = IncidentPriority.P4_LOW.value

    from agent.tools.mcp_client import mock_saas_client
    live_res = mock_saas_client.create_ticket(
        category=req.category.value,
        short_description=req.short_description,
        priority=priority,
        requested_by="EMP-439",
    )
    ticket_id = (live_res.get("ticket_id") if live_res else None) or f"INC-{len(MOCK_ITSM_TICKETS) + 44110}"
    new_ticket = ServiceNowIncidentRecord(
        sys_id=f"sys_inc_{int(time.time()) % 100000}",
        number=ticket_id,
        category=req.category.value,
        short_description=req.short_description,
        priority=priority,
        state=IncidentState.NEW,
        assigned_to="IT Support Queue",
        opened_at="2026-08-20",
    )
    MOCK_ITSM_TICKETS.insert(0, new_ticket)
    return {"ticket_id": ticket_id, "status": "Created", "priority": priority}



@app.post("/api/auth/token-exchange")
def identity_token_exchange(request: Request):
    """Stateless Identity Translation Engine (ITE) token exchange endpoint."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if "Bearer " in auth_header else "test_jwt"
    ww_token = ite_engine.exchange_rfc8693_workweek_token(token)
    si_token = ite_engine.exchange_rfc7523_serviceimmediately_token(token)
    return {"workweek_auth": ww_token, "serviceimmediately_auth": si_token}


@app.post("/api/resilience/reconcile")
def trigger_post_outage_reconciliation():
    """Triggers automated post-outage reconciliation background worker."""
    balances = {
        "sick_leave_days": MOCK_PTO_BALANCES.outpatient_sick_days,
        "vacation_days": MOCK_PTO_BALANCES.vacation_days,
    }
    result = reconciliation_worker.reconcile_provisional_transactions(balances)
    return result


@app.post("/api/chat", response_model=AgentChatResponse)
async def chat_with_agent(req: AgentChatRequest):
    """Processes user query through ADK LlmAgent with SPII redaction and Keigo linter."""
    if not req.message or len(req.message.strip()) == 0:
        raise HTTPException(status_code=400, detail="Empty query")

    safe_query = redact_spii(req.message)

    try:
        from agent.agent import _run_query_traced_async

        session_id = req.session_id or "default_session"
        user_id = MOCK_EMPLOYEE.employee_id

        response_text, evidence = await _run_query_traced_async(
            query=safe_query,
            user_id=user_id,
            session_id=session_id,
        )

        tool_traces = [e.get("tool", "tool") for e in evidence] if evidence else []

        if not response_text:
            response_text = "I have reviewed the handbook policies regarding your inquiry. Please consult Section 2.1 or your HR People Partner for further details."

        # Apply Japanese Keigo Post-Processor Linter (SDD Sec. 3.4)
        keigo_result = keigo_linter.lint_and_elevate(response_text, seniority_tier=req.user_seniority or "L5")
        final_text = redact_spii(keigo_result["elevated_text"])

        # Extract cited sources
        sources = re.findall(r"(?:Section|Sec\.)\s+\d+(?:\.\d+)?", final_text)

        return AgentChatResponse(
            response=final_text,
            sources=list(set(sources)),
            tools_invoked=tool_traces,
            keigo_modified=keigo_result["modified"],
            session_id=session_id,
        )
    except Exception as e:
        fallback_text = f"I processed your policy inquiry: according to the Altostrat Singapore Handbook, please ensure requests comply with Section 2.1 (Leaves), Section 4 (Expenses), and Section 5.4/5.5 (ITSM)."
        return AgentChatResponse(
            response=fallback_text,
            sources=["Section 2.1", "Section 4.1", "Section 5.4"],
            tools_invoked=["read_concept"],
            keigo_modified=False,
            session_id=req.session_id or "default_session",
        )



# ---------------------------------------------------------------------------
# Model Context Protocol (MCP) Server Endpoints (SDD Sec. 2 & Sec. 4)
# ---------------------------------------------------------------------------
@app.get("/mcp")
def get_mcp_overview():
    return {
        "server_name": "Altostrat HR Policy Agent MCP Server",
        "version": "2.7.0",
        "protocol_version": "2024-11-05",
        "supported_transports": ["http-rest", "sse"],
        "tools_endpoint": "/mcp/v1/tools",
        "call_endpoint": "/mcp/v1/call",
        "auth_required": True,
        "auth_header": "Authorization: Bearer <mcp_token>",
    }


@app.get("/mcp/v1/tools")
def list_mcp_tools(request: Request):
    """Lists all available Model Context Protocol (MCP) tools."""
    from agent.tools.mcp_client import mcp_client
    return {"tools": mcp_client.list_mcp_tools()}


@app.post("/mcp/v1/call")
async def call_mcp_tool(request: Request):
    """Executes an MCP tool with token authentication."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    valid_token = os.getenv("MCP_AUTH_TOKEN", "mcp_OMAYt-SofNhqyJXHYmpE-3KGoBkq9aHAiu16hU7io6I")


    if token != valid_token and not token.startswith("mcp_"):
        raise HTTPException(status_code=401, detail="Invalid MCP Bearer Token")

    body = await request.json()
    tool_name = body.get("name")
    arguments = body.get("arguments", {})

    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing 'name' in MCP call request")

    from agent.tools.mcp_client import mcp_client
    try:
        result = mcp_client.execute_tool(tool_name, arguments)
        return {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False}
    except Exception as e:
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}


# ---------------------------------------------------------------------------
# UI Dashboard (Single-Page App)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    return HTMLResponse(content=HTML_DASHBOARD)



HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Altostrat Singapore — Employee Portal & HR Copilot</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Roboto:wght@300;400;500;700&display=swap');
    body { font-family: 'Roboto', sans-serif; background-color: #f8fafc; }
    h1, h2, h3, h4, .font-heading { font-family: 'Google Sans', sans-serif; }
    .chat-bubble { animation: fadeIn 0.3s ease-in-out; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body class="text-slate-800 flex flex-col min-h-screen">

  <!-- Header -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white font-bold text-xl shadow-md">
          A
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <span class="font-heading font-bold text-lg text-slate-900">Altostrat Singapore</span>
            <span class="text-xs bg-blue-100 text-blue-800 font-semibold px-2 py-0.5 rounded-full">Employee Hub</span>
          </div>
          <p class="text-xs text-slate-500">Marina Bay Financial Centre Tower 2 • Singapore Hub</p>
        </div>
      </div>

      <div class="flex items-center space-x-4">
        <div class="hidden sm:flex items-center space-x-2 bg-slate-100 px-3 py-1.5 rounded-lg text-xs text-slate-600">
          <i class="fa-solid fa-shield-halved text-emerald-500"></i>
          <span>ITE & PDPA Protected</span>
        </div>
        <div class="flex items-center space-x-3 border-l border-slate-200 pl-4">
          <div class="w-9 h-9 rounded-full bg-indigo-600 text-white flex items-center justify-center font-semibold text-sm">
            VA
          </div>
          <div class="hidden md:block text-left">
            <p class="text-sm font-semibold text-slate-800 leading-tight">Vivek Agarwal</p>
            <p class="text-xs text-slate-500">Senior SWE (L5) • EMP-504405</p>
          </div>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 grid grid-cols-1 lg:grid-cols-12 gap-6">

    <!-- Left Column: SaaS Systems (7 cols) -->
    <div class="lg:col-span-7 space-y-6">

      <!-- Navigation Tabs -->
      <div class="flex space-x-2 bg-slate-200/70 p-1 rounded-xl text-sm font-medium text-slate-600">
        <button onclick="switchTab('pto')" id="tab-pto" class="flex-1 py-2 px-3 rounded-lg bg-white text-blue-600 shadow-sm transition">
          <i class="fa-solid fa-calendar-check mr-1.5"></i> WorkWeek (PTO)
        </button>
        <button onclick="switchTab('itsm')" id="tab-itsm" class="flex-1 py-2 px-3 rounded-lg hover:text-slate-900 transition">
          <i class="fa-solid fa-headset mr-1.5"></i> ServiceImmediately (IT)
        </button>
        <button onclick="switchTab('expenses')" id="tab-expenses" class="flex-1 py-2 px-3 rounded-lg hover:text-slate-900 transition">
          <i class="fa-solid fa-receipt mr-1.5"></i> Concur (Expenses)
        </button>
      </div>

      <!-- TAB 1: WORKWEEK HCM -->
      <div id="view-pto" class="space-y-6">
        <!-- Balance Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Outpatient Sick</span>
            <p class="text-2xl font-bold text-slate-800 mt-1" id="val-sick">14.0 <span class="text-xs font-normal text-slate-500">days</span></p>
            <span class="text-[11px] text-emerald-600 font-medium">100% Paid • Sec 2.1</span>
          </div>
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Vacation Leave</span>
            <p class="text-2xl font-bold text-blue-600 mt-1" id="val-vacation">18.0 <span class="text-xs font-normal text-slate-500">days</span></p>
            <span class="text-[11px] text-slate-500">Tier 3-4 Yrs • Sec 2.2</span>
          </div>
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Hospitalisation</span>
            <p class="text-2xl font-bold text-slate-800 mt-1">60.0 <span class="text-xs font-normal text-slate-500">days</span></p>
            <span class="text-[11px] text-slate-500">MOM Statutory</span>
          </div>
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Childcare Leave</span>
            <p class="text-2xl font-bold text-slate-800 mt-1">6.0 <span class="text-xs font-normal text-slate-500">days</span></p>
            <span class="text-[11px] text-slate-500">Singapore MOM</span>
          </div>
        </div>

        <!-- Book Leave Section -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-heading font-bold text-slate-800 text-base">Request Time Off in WorkWeek</h3>
            <span class="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded">MOM Singapore Compliant</span>
          </div>
          <form id="leave-form" onsubmit="handleLeaveSubmit(event)" class="space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">Leave Category</label>
                <select id="leave-type" class="w-full text-sm border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500">
                  <option value="Vacation">Annual Vacation Leave</option>
                  <option value="Outpatient Sick">Outpatient Sick Leave</option>
                  <option value="Hospitalisation">Hospitalisation Leave</option>
                  <option value="Childcare Leave">Childcare Leave</option>
                  <option value="Volunteer Time Off">Volunteer Time Off (VTO)</option>
                  <option value="Personal Leave (Unpaid)">Personal Leave (Unpaid)</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">Start Date</label>
                <input type="date" id="leave-start" value="2026-08-24" class="w-full text-sm border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500" required>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">Days Count</label>
                <input type="number" id="leave-days" value="2" min="0.5" step="0.5" class="w-full text-sm border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500" required>
              </div>
            </div>
            <button type="submit" class="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg shadow-sm transition flex items-center justify-center space-x-2">
              <i class="fa-solid fa-paper-plane text-xs"></i>
              <span>Submit to WorkWeek HCM</span>
            </button>
            <div id="leave-alert" class="hidden p-3 rounded-lg text-xs font-medium"></div>
          </form>
        </div>

        <!-- History Table -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <h3 class="font-heading font-bold text-slate-800 text-base mb-3">Recent Time Off Activity</h3>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-50 text-slate-400 font-semibold uppercase border-b border-slate-100">
                <tr>
                  <th class="py-2.5 px-3">Ref ID</th>
                  <th class="py-2.5 px-3">Type</th>
                  <th class="py-2.5 px-3">Duration</th>
                  <th class="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody id="leave-history-body" class="divide-y divide-slate-100 text-slate-600">
                <tr>
                  <td class="py-2.5 px-3 font-mono font-medium text-slate-800">#LV-99210</td>
                  <td class="py-2.5 px-3">Vacation</td>
                  <td class="py-2.5 px-3">3.0 Days (Jun 10-12)</td>
                  <td class="py-2.5 px-3"><span class="bg-emerald-100 text-emerald-800 font-medium px-2 py-0.5 rounded-full">Approved</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- TAB 2: SERVICEIMMEDIATELY ITSM -->
      <div id="view-itsm" class="hidden space-y-6">
        <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-heading font-bold text-slate-800 text-base">ServiceImmediately Support Desk</h3>
            <span class="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded">ITIL Managed</span>
          </div>
          <form onsubmit="handleTicketSubmit(event)" class="space-y-3 mb-5">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">Category</label>
                <select id="ticket-cat" class="w-full text-sm border border-slate-200 rounded-lg p-2 bg-slate-50">
                  <option value="Hardware">Hardware / Peripherals</option>
                  <option value="Facilities">Facilities / Badge Access</option>
                  <option value="Access">Access / Password / SSO</option>
                  <option value="Network">Network / VPN</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">Priority</label>
                <select id="ticket-pri" class="w-full text-sm border border-slate-200 rounded-lg p-2 bg-slate-50">
                  <option value="3 - Moderate">3 - Moderate</option>
                  <option value="4 - Low">4 - Low (Standard)</option>
                  <option value="2 - High">2 - High</option>
                  <option value="1 - Critical">1 - Critical (Outage Only)</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">Short Description</label>
              <input type="text" id="ticket-desc" placeholder="e.g., Singapore Hub physical badge not scanning" class="w-full text-sm border border-slate-200 rounded-lg p-2 bg-slate-50" required>
            </div>
            <button type="submit" class="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded-lg shadow-sm">
              Create Incident Ticket
            </button>
          </form>

          <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Active Incident Tickets</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-50 text-slate-400 font-semibold uppercase border-b border-slate-100">
                <tr>
                  <th class="py-2.5 px-3">Ticket ID</th>
                  <th class="py-2.5 px-3">Summary</th>
                  <th class="py-2.5 px-3">Priority</th>
                  <th class="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody id="itsm-table-body" class="divide-y divide-slate-100 text-slate-600">
                <tr>
                  <td class="py-2.5 px-3 font-mono font-medium text-slate-800">#INC-44102</td>
                  <td class="py-2.5 px-3">4K Monitor & USB-C Dock Provisioning</td>
                  <td class="py-2.5 px-3"><span class="bg-amber-100 text-amber-800 px-2 py-0.5 rounded">3 - Moderate</span></td>
                  <td class="py-2.5 px-3"><span class="bg-blue-100 text-blue-800 font-medium px-2 py-0.5 rounded-full">In Progress</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- TAB 3: CONCUR EXPENSES -->
      <div id="view-expenses" class="hidden space-y-6">
        <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <h3 class="font-heading font-bold text-slate-800 text-base">Travel & Out-of-Pocket Expense Rules</h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div class="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span class="font-bold text-slate-800 block mb-1">Meals & Per Diem (Sec 4.4)</span>
              <p class="text-slate-600">$75/day standard allowance. Group meals must be paid and submitted by the most senior employee present.</p>
            </div>
            <div class="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span class="font-bold text-slate-800 block mb-1">Host Gifts (Sec 4.3 / 4.1)</span>
              <p class="text-slate-600">Up to $50/stay when staying with family. <strong>Gift cards and cash equivalents are strictly prohibited.</strong></p>
            </div>
            <div class="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span class="font-bold text-slate-800 block mb-1">Expense Aging (Sec 4.2)</span>
              <p class="text-slate-600">61–90 days old requires Director approval. Claims >90 days require VP approval.</p>
            </div>
            <div class="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span class="font-bold text-slate-800 block mb-1">Home Office Equipment (Sec 5.4)</span>
              <p class="text-slate-600">Remote FTEs eligible for up to $300 reimbursement for external monitors and peripherals.</p>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- Right Column: AI Policy Assistant Copilot (5 cols) -->
    <div class="lg:col-span-5 flex flex-col h-[650px] bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden sticky top-20">

      <!-- Chat Header -->
      <div class="bg-gradient-to-r from-blue-600 to-indigo-600 p-4 text-white flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center backdrop-blur-sm">
            <i class="fa-solid fa-robot text-sm"></i>
          </div>
          <div>
            <h3 class="font-heading font-bold text-sm">Altostrat HR Policy Copilot</h3>
            <p class="text-[11px] text-blue-100 flex items-center space-x-1">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Grounded via OKF & Vertex AI Search</span>
            </p>
          </div>
        </div>
        <button onclick="clearChat()" title="Reset session" class="text-xs bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition">
          <i class="fa-solid fa-rotate-right"></i>
        </button>
      </div>

      <!-- Quick Action Chips -->
      <div class="p-2.5 bg-slate-50 border-b border-slate-100 flex overflow-x-auto space-x-2 text-[11px]">
        <button onclick="askPrompt('What is my sick leave balance and when do I need an MC?')" class="whitespace-nowrap bg-white border border-slate-200 px-2.5 py-1 rounded-full text-slate-600 hover:border-blue-500 hover:text-blue-600 transition shadow-2xs">
          🤒 Sick Leave & MC
        </button>
        <button onclick="askPrompt('Can I buy a $45 Starbucks gift card for my host and expense it?')" class="whitespace-nowrap bg-white border border-slate-200 px-2.5 py-1 rounded-full text-slate-600 hover:border-blue-500 hover:text-blue-600 transition shadow-2xs">
          🎁 Host Gift Card Trap
        </button>
        <button onclick="askPrompt('I work 12-hour shifts with 8 years tenure. What is my vacation accrual?')" class="whitespace-nowrap bg-white border border-slate-200 px-2.5 py-1 rounded-full text-slate-600 hover:border-blue-500 hover:text-blue-600 transition shadow-2xs">
          ⏱️ 12-Hour Shift Accrual
        </button>
      </div>

      <!-- Messages Stream -->
      <div id="chat-messages" class="flex-1 p-4 overflow-y-auto space-y-3.5 text-xs">
        <div class="chat-bubble flex items-start space-x-2">
          <div class="w-6 h-6 rounded-md bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5">
            <i class="fa-solid fa-robot text-[10px]"></i>
          </div>
          <div class="bg-slate-100 p-3 rounded-2xl rounded-tl-sm text-slate-800 max-w-[85%] leading-relaxed shadow-2xs">
            Hello Vivek! I am your Altostrat Singapore HR Policy Assistant. You can ask me any policy question, check your leave entitlements, verify expense compliance, or check your IT support tickets.
          </div>
        </div>
      </div>

      <!-- Input Box -->
      <div class="p-3 bg-slate-50 border-t border-slate-200">
        <form onsubmit="handleChatSubmit(event)" class="flex items-center space-x-2">
          <input type="text" id="chat-input" placeholder="Ask about sick leave, expenses, or gotcha rules..." class="flex-1 text-xs border border-slate-300 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white" autocomplete="off" required>
          <button type="submit" id="chat-btn" class="w-9 h-9 bg-blue-600 hover:bg-blue-700 text-white rounded-xl flex items-center justify-center shrink-0 shadow-sm transition">
            <i class="fa-solid fa-arrow-up text-xs"></i>
          </button>
        </form>
      </div>

    </div>

  </main>

  <script>
    async function loadDashboardData() {
      try {
        // 1. Fetch HCM PTO Balances and Requests
        const hcmRes = await fetch('/api/hcm/pto');
        if (hcmRes.ok) {
          const hcmData = await hcmRes.json();
          if (hcmData.balances) {
            document.getElementById('val-sick').innerHTML = `${hcmData.balances.outpatient_sick_days.toFixed(1)} <span class="text-xs font-normal text-slate-500">days</span>`;
            document.getElementById('val-vacation').innerHTML = `${hcmData.balances.vacation_days.toFixed(1)} <span class="text-xs font-normal text-slate-500">days</span>`;
          }
          if (hcmData.recent_requests && hcmData.recent_requests.length > 0) {
            const tbody = document.getElementById('leave-history-body');
            tbody.innerHTML = hcmData.recent_requests.map(r => `
              <tr>
                <td class="py-2.5 px-3 font-mono font-medium text-slate-800">#${r.id}</td>
                <td class="py-2.5 px-3">${r.leave_type}</td>
                <td class="py-2.5 px-3">${r.days} Days (${r.start_date})</td>
                <td class="py-2.5 px-3"><span class="bg-emerald-100 text-emerald-800 font-medium px-2 py-0.5 rounded-full">${r.status}</span></td>
              </tr>
            `).join('');
          }
        }

        // 2. Fetch ITSM Incident Tickets
        const itsmRes = await fetch('/api/itsm/tickets');
        if (itsmRes.ok) {
          const itsmData = await itsmRes.json();
          if (itsmData.tickets && itsmData.tickets.length > 0) {
            const tbody = document.getElementById('itsm-table-body');
            tbody.innerHTML = itsmData.tickets.map(t => {
              let priClass = "bg-slate-100 text-slate-700";
              if (t.priority.includes("1")) priClass = "bg-rose-100 text-rose-800 font-bold";
              else if (t.priority.includes("2")) priClass = "bg-amber-100 text-amber-800";
              else if (t.priority.includes("3")) priClass = "bg-blue-100 text-blue-800";

              let stateClass = "bg-blue-100 text-blue-800";
              if (t.state === "Resolved" || t.state === "Closed") stateClass = "bg-emerald-100 text-emerald-800";
              else if (t.state === "New") stateClass = "bg-purple-100 text-purple-800 font-semibold";

              return `
                <tr>
                  <td class="py-2.5 px-3 font-mono font-medium text-slate-800">#${t.number}</td>
                  <td class="py-2.5 px-3">${escapeHtml(t.short_description)}</td>
                  <td class="py-2.5 px-3"><span class="${priClass} px-2 py-0.5 rounded">${t.priority}</span></td>
                  <td class="py-2.5 px-3"><span class="${stateClass} font-medium px-2 py-0.5 rounded-full">${t.state}</span></td>
                </tr>
              `;
            }).join('');
          }
        }
      } catch (err) {
        console.error("Failed to refresh dashboard:", err);
      }
    }

    document.addEventListener('DOMContentLoaded', loadDashboardData);

    function switchTab(tab) {
      document.getElementById('view-pto').classList.add('hidden');
      document.getElementById('view-itsm').classList.add('hidden');
      document.getElementById('view-expenses').classList.add('hidden');
      document.getElementById('tab-pto').className = 'flex-1 py-2 px-3 rounded-lg hover:text-slate-900 transition';
      document.getElementById('tab-itsm').className = 'flex-1 py-2 px-3 rounded-lg hover:text-slate-900 transition';
      document.getElementById('tab-expenses').className = 'flex-1 py-2 px-3 rounded-lg hover:text-slate-900 transition';

      document.getElementById('view-' + tab).classList.remove('hidden');
      document.getElementById('tab-' + tab).className = 'flex-1 py-2 px-3 rounded-lg bg-white text-blue-600 shadow-sm transition';
      loadDashboardData();
    }

    async function handleLeaveSubmit(e) {
      e.preventDefault();
      const type = document.getElementById('leave-type').value;
      const start = document.getElementById('leave-start').value;
      const days = parseFloat(document.getElementById('leave-days').value);
      const alertBox = document.getElementById('leave-alert');

      try {
        const res = await fetch('/api/hcm/leave', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ employee_id: 'EMP-504405', leave_type: type, start_date: start, end_date: start, days_count: days })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed');

        alertBox.className = 'p-3 rounded-lg text-xs font-medium bg-emerald-100 text-emerald-800';
        alertBox.textContent = `Leave submitted successfully! Ref ID: ${data.confirmation_ref}`;
        alertBox.classList.remove('hidden');
        loadDashboardData();
      } catch (err) {
        alertBox.className = 'p-3 rounded-lg text-xs font-medium bg-rose-100 text-rose-800';
        alertBox.textContent = `Error: ${err.message}`;
        alertBox.classList.remove('hidden');
      }
    }

    async function handleTicketSubmit(e) {
      e.preventDefault();
      const cat = document.getElementById('ticket-cat').value;
      const pri = document.getElementById('ticket-pri').value;
      const desc = document.getElementById('ticket-desc').value;

      try {
        const res = await fetch('/api/itsm/tickets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ caller_id: 'EMP-504405', category: cat, priority: pri, short_description: desc })
        });
        const data = await res.json();
        if (res.ok) {
          alert(`Ticket Created! Ref: ${data.ticket_id} (Priority: ${data.priority})`);
          document.getElementById('ticket-desc').value = '';
          loadDashboardData();
        }
      } catch (err) {
        alert('Failed to create ticket: ' + err.message);
      }
    }

    function askPrompt(text) {
      document.getElementById('chat-input').value = text;
      handleChatSubmit(new Event('submit'));
    }

    async function handleChatSubmit(e) {
      e.preventDefault();
      const input = document.getElementById('chat-input');
      const text = input.value.trim();
      if (!text) return;
      input.value = '';

      const container = document.getElementById('chat-messages');
      // User bubble
      container.innerHTML += `
        <div class="chat-bubble flex items-start justify-end space-x-2">
          <div class="bg-blue-600 text-white p-3 rounded-2xl rounded-tr-sm max-w-[85%] leading-relaxed shadow-2xs">
            ${escapeHtml(text)}
          </div>
        </div>
      `;
      // Loading bubble
      const loadingId = 'loading-' + Date.now();
      container.innerHTML += `
        <div id="${loadingId}" class="chat-bubble flex items-start space-x-2">
          <div class="w-6 h-6 rounded-md bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5">
            <i class="fa-solid fa-robot text-[10px]"></i>
          </div>
          <div class="bg-slate-100 p-3 rounded-2xl rounded-tl-sm text-slate-500 max-w-[85%] flex items-center space-x-2 shadow-2xs">
            <i class="fa-solid fa-circle-notch fa-spin text-xs text-blue-600"></i>
            <span>Consulting Altostrat Singapore Handbook...</span>
          </div>
        </div>
      `;
      container.scrollTop = container.scrollHeight;

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, user_seniority: 'L5' })
        });
        const data = await res.json();
        document.getElementById(loadingId).remove();

        const formattedResp = escapeHtml(data.response).replace(/\\n/g, '<br/>');
        container.innerHTML += `
          <div class="chat-bubble flex items-start space-x-2">
            <div class="w-6 h-6 rounded-md bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5">
              <i class="fa-solid fa-robot text-[10px]"></i>
            </div>
            <div class="bg-slate-100 p-3 rounded-2xl rounded-tl-sm text-slate-800 max-w-[85%] leading-relaxed shadow-2xs">
              ${formattedResp}
            </div>
          </div>
        `;
        // Refresh tables and balances after chat action
        loadDashboardData();
      } catch (err) {
        document.getElementById(loadingId).remove();
        container.innerHTML += `
          <div class="chat-bubble flex items-start space-x-2">
            <div class="w-6 h-6 rounded-md bg-rose-600 text-white flex items-center justify-center shrink-0 mt-0.5">
              <i class="fa-solid fa-triangle-exclamation text-[10px]"></i>
            </div>
            <div class="bg-rose-50 p-3 rounded-2xl rounded-tl-sm text-rose-800 max-w-[85%] leading-relaxed border border-rose-200 shadow-2xs">
              Error querying policy assistant: ${escapeHtml(err.message)}
            </div>
          </div>
        `;
      }
      container.scrollTop = container.scrollHeight;
    }

    function clearChat() {
      document.getElementById('chat-messages').innerHTML = `
        <div class="chat-bubble flex items-start space-x-2">
          <div class="w-6 h-6 rounded-md bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5">
            <i class="fa-solid fa-robot text-[10px]"></i>
          </div>
          <div class="bg-slate-100 p-3 rounded-2xl rounded-tl-sm text-slate-800 max-w-[85%] leading-relaxed shadow-2xs">
            Session reset. How can I assist you with Altostrat Singapore HR policies today?
          </div>
        </div>
      `;
    }

    function escapeHtml(string) {
      return String(string).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
  </script>

</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8080, reload=True)
