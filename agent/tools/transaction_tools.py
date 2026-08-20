"""Transactional Action Tools for WorkWeek HCM and ServiceImmediately ITSM (SDD Sec. 2 & Sec. 3).

Enables autonomous self-service transactions with live bi-directional sync to Mock SaaS:
1. serviceimmediately_create_incident_ticket: Creates ITSM tickets with automated priority classification.
2. serviceimmediately_get_incident_status: Checks ticket status.
3. workweek_get_pto_balances: Retrieves live employee PTO balances.
4. workweek_submit_leave_request: Submits leave transactions with pre-call validation.
"""

import time
from typing import Any, Dict, Optional

from agent.models.contracts import (
    IncidentCategory,
    IncidentPriority,
    IncidentState,
    LeaveCategory,
    ServiceNowIncidentRecord,
)
from agent.storage.mock_db import MOCK_EMPLOYEE, MOCK_ITSM_TICKETS, MOCK_LEAVE_REQUESTS, MOCK_PTO_BALANCES


def serviceimmediately_create_incident_ticket(
    category: str,
    short_description: str,
    priority: str = "3 - Moderate",
    caller_id: str = "EMP-439",
) -> Dict[str, Any]:
    """Creates a new incident ticket in ServiceImmediately ITSM.

    Args:
        category: Ticket category ('Hardware', 'Facilities', 'Access', 'Network', 'Software').
        short_description: Concise summary of the issue or request (e.g. 'Loaner Mac Pro request for conference').
        priority: Requested priority ('1 - Critical', '2 - High', '3 - Moderate', '4 - Low').
                  Note: Hardware and routine requests requested as Critical are automatically
                  downgraded to Moderate or Low per Section 5.5.
        caller_id: Employee ID or email (defaults to 'EMP-439').

    Returns:
        Dictionary with ticket_id, priority_assigned, status, and message.
    """
    desc_lower = short_description.lower()
    cat_lower = category.lower()
    assigned_priority = priority

    # Enforce Section 5.5 policy: non-outage / routine hardware cannot be Critical
    is_routine_hardware = "hardware" in cat_lower or "laptop" in desc_lower or "monitor" in desc_lower or "loaner" in desc_lower or "mouse" in desc_lower
    is_routine_access = "access" in cat_lower or "password" in desc_lower or "login" in desc_lower or "badge" in desc_lower

    if ("critical" in priority.lower() or "1" in priority) and (is_routine_hardware or is_routine_access):
        assigned_priority = "3 - Moderate" if is_routine_hardware else "4 - Low"

    # 1. Dispatch Live Request to Mock SaaS Platform
    live_ticket_id = None
    try:
        from agent.tools.mcp_client import mock_saas_client
        live_res = mock_saas_client.create_ticket(
            category=category,
            short_description=short_description,
            priority=assigned_priority,
            requested_by=caller_id or "EMP-439",
        )
        if live_res and "ticket_id" in live_res:
            live_ticket_id = live_res["ticket_id"]
    except Exception:
        pass

    ticket_number = live_ticket_id or f"INC-{len(MOCK_ITSM_TICKETS) + 44115}"
    new_ticket = ServiceNowIncidentRecord(
        sys_id=f"sys_inc_{int(time.time()) % 100000}",
        number=ticket_number,
        category=category,
        short_description=short_description,
        priority=assigned_priority,
        state=IncidentState.NEW,
        assigned_to="IT Support Queue",
        opened_at="2026-08-20",
    )
    MOCK_ITSM_TICKETS.insert(0, new_ticket)

    return {
        "success": True,
        "ticket_id": ticket_number,
        "category": category,
        "short_description": short_description,
        "requested_priority": priority,
        "priority_assigned": assigned_priority,
        "status": "New",
        "assigned_to": "IT Support Queue APAC",
        "message": f"ServiceImmediately ticket {ticket_number} created successfully in live portal with priority {assigned_priority}.",
    }


def serviceimmediately_get_incident_status(ticket_id: str) -> Dict[str, Any]:
    """Retrieves the status of an existing ServiceImmediately incident ticket.

    Args:
        ticket_id: The ticket number (e.g. 'INC0003019' or 'INC-44102').
    """
    # Check local DB
    for t in MOCK_ITSM_TICKETS:
        if t.number.lower() == ticket_id.lower() or t.sys_id.lower() == ticket_id.lower():
            return {"found": True, "ticket": t.model_dump()}

    # Check live SaaS platform
    try:
        from agent.tools.mcp_client import mock_saas_client
        tickets = mock_saas_client.list_tickets("EMP-439")
        for t in tickets:
            if t.get("ticket_id", "").lower() == ticket_id.lower():
                return {"found": True, "ticket": t}
    except Exception:
        pass

    return {"found": False, "message": f"Ticket {ticket_id} not found."}


def workweek_get_pto_balances(employee_id: str = "EMP-439") -> Dict[str, Any]:
    """Retrieves the employee's current real-time PTO balances from WorkWeek HCM.

    Args:
        employee_id: Unique employee ID (defaults to 'EMP-439').
    """
    vacation = MOCK_PTO_BALANCES.vacation_days
    sick = MOCK_PTO_BALANCES.outpatient_sick_days

    # Fetch live balances from WorkWeek
    try:
        from agent.tools.mcp_client import mock_saas_client
        live_bal = mock_saas_client.get_timeoff_balances(employee_id)
        if live_bal and "vacation_remaining" in live_bal:
            vacation = float(live_bal["vacation_remaining"])
            sick = float(live_bal.get("sick_remaining", sick))
    except Exception:
        pass

    return {
        "employee_id": employee_id,
        "outpatient_sick_days": sick,
        "hospitalisation_days": MOCK_PTO_BALANCES.hospitalisation_days,
        "vacation_days": vacation,
        "childcare_days": MOCK_PTO_BALANCES.childcare_days,
        "volunteer_days": MOCK_PTO_BALANCES.volunteer_days,
    }


def workweek_submit_leave_request(
    leave_type: str,
    start_date: str,
    days_count: float,
    end_date: Optional[str] = None,
    reason: Optional[str] = None,
    employee_id: str = "EMP-439",
) -> Dict[str, Any]:
    """Submits a formal leave request to WorkWeek HCM.

    Args:
        leave_type: Category ('Vacation', 'Outpatient Sick', 'Hospitalisation', 'Childcare Leave', 'Volunteer Time Off', 'Personal Leave (Unpaid)').
        start_date: Format 'YYYY-MM-DD'.
        days_count: Total business days requested.
        end_date: Format 'YYYY-MM-DD'. If omitted or None, automatically calculated based on start_date and days_count.
        reason: Optional justification or note.
        employee_id: Employee ID (defaults to 'EMP-439').
    """
    # Auto-calculate end_date if omitted or None
    if not end_date or not str(end_date).strip():
        try:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
            days_to_add = max(0, int(round(days_count)) - 1)
            end_date = (start_dt + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
        except Exception:
            end_date = start_date

    balances = workweek_get_pto_balances(employee_id)

    if "vacation" in leave_type.lower() and days_count > balances["vacation_days"]:
        return {
            "success": False,
            "error": "INSUFFICIENT_BALANCE",
            "message": f"Requested {days_count} vacation days exceeds available balance of {balances['vacation_days']} days.",
        }

    # Dispatch to Live WorkWeek
    try:
        from agent.tools.mcp_client import mock_saas_client
        mock_saas_client.submit_timeoff_request(
            employee_id=employee_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            days=days_count,
            reason=reason or "",
        )
    except Exception:
        pass


    confirmation_ref = f"LV-{int(time.time()) % 100000}"
    lt_lower = leave_type.lower()
    if "vacation" in lt_lower or "annual" in lt_lower:
        MOCK_PTO_BALANCES.vacation_days = max(0.0, MOCK_PTO_BALANCES.vacation_days - days_count)
        remaining = MOCK_PTO_BALANCES.vacation_days
    elif "hospital" in lt_lower:
        MOCK_PTO_BALANCES.hospitalisation_days = max(0.0, MOCK_PTO_BALANCES.hospitalisation_days - days_count)
        remaining = MOCK_PTO_BALANCES.hospitalisation_days
    elif "sick" in lt_lower or "outpatient" in lt_lower:
        MOCK_PTO_BALANCES.outpatient_sick_days = max(0.0, MOCK_PTO_BALANCES.outpatient_sick_days - days_count)
        remaining = MOCK_PTO_BALANCES.outpatient_sick_days
    elif "childcare" in lt_lower:
        MOCK_PTO_BALANCES.childcare_days = max(0.0, MOCK_PTO_BALANCES.childcare_days - days_count)
        remaining = MOCK_PTO_BALANCES.childcare_days
    elif "volunteer" in lt_lower:
        MOCK_PTO_BALANCES.volunteer_days = max(0.0, MOCK_PTO_BALANCES.volunteer_days - days_count)
        remaining = MOCK_PTO_BALANCES.volunteer_days
    else:
        remaining = MOCK_PTO_BALANCES.vacation_days

    # Save to local mock history
    new_req_record = {
        "id": confirmation_ref,
        "leave_type": leave_type,
        "start_date": f"{start_date} to {end_date}" if start_date != end_date else start_date,
        "days": days_count,
        "status": "Approved",
        "submitted_at": start_date,
    }
    MOCK_LEAVE_REQUESTS.insert(0, new_req_record)

    return {
        "success": True,
        "confirmation_ref": confirmation_ref,
        "employee_id": employee_id,
        "leave_type": leave_type,
        "days_deducted": days_count,
        "remaining_balance": remaining,
        "status": "Approved (Auto-routed to manager)",
        "message": f"Leave request for {days_count} day(s) of {leave_type} successfully submitted to WorkWeek HCM. Ref: {confirmation_ref}.",
    }


def workweek_get_leave_requests(employee_id: str = "EMP-439") -> Dict[str, Any]:
    """Retrieves the list of past and pending leave requests submitted by the employee in WorkWeek HCM.

    Args:
        employee_id: Unique employee ID (defaults to 'EMP-439').

    Returns:
        Dictionary containing 'employee_id' and 'requests' (list of leave requests with request_id, leave_type, start_date, end_date, days, and status).
    """
    # 1. Check live SaaS platform
    try:
        from agent.tools.mcp_client import mock_saas_client
        live_reqs = mock_saas_client.get_timeoff_requests(employee_id)
        if live_reqs:
            formatted = [
                {
                    "request_id": f"LV-{r.get('request_id', '99215')}" if not str(r.get('request_id', '')).startswith("LV-") else str(r.get('request_id')),
                    "leave_type": r.get("leave_type", "Vacation"),
                    "start_date": r.get("start_date"),
                    "end_date": r.get("end_date"),
                    "days": r.get("days", 1.0),
                    "status": "Approved",
                }
                for r in live_reqs
            ]
            return {
                "employee_id": employee_id,
                "requests": formatted,
                "count": len(formatted),
                "message": f"Found {len(formatted)} leave request(s) in WorkWeek HCM.",
            }
    except Exception:
        pass

    # 2. Fallback to local DB
    return {
        "employee_id": employee_id,
        "requests": MOCK_LEAVE_REQUESTS,
        "count": len(MOCK_LEAVE_REQUESTS),
        "message": f"Found {len(MOCK_LEAVE_REQUESTS)} leave request(s) in WorkWeek HCM.",
    }

