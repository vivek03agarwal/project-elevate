"""Transactional Action Tools for WorkWeek HCM and ServiceImmediately ITSM (SDD Sec. 2 & Sec. 3).

Enables autonomous self-service transactions:
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
    caller_id: str = "EMP-504405",
) -> Dict[str, Any]:
    """Creates a new incident ticket in ServiceImmediately ITSM.

    Args:
        category: Ticket category ('Hardware', 'Facilities', 'Access', 'Network', 'Software').
        short_description: Concise summary of the issue or request (e.g. 'Loaner Mac Pro request for conference').
        priority: Requested priority ('1 - Critical', '2 - High', '3 - Moderate', '4 - Low').
                  Note: Hardware and routine requests requested as Critical are automatically
                  downgraded to Moderate or Low per Section 5.5.
        caller_id: Employee ID or email (defaults to authenticated user).

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

    ticket_number = f"INC-{len(MOCK_ITSM_TICKETS) + 44115}"
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
        "message": f"ServiceImmediately ticket {ticket_number} created successfully with priority {assigned_priority}.",
    }


def serviceimmediately_get_incident_status(ticket_id: str) -> Dict[str, Any]:
    """Retrieves the status of an existing ServiceImmediately incident ticket.

    Args:
        ticket_id: The ticket number (e.g. 'INC-44102').
    """
    for t in MOCK_ITSM_TICKETS:
        if t.number.lower() == ticket_id.lower() or t.sys_id.lower() == ticket_id.lower():
            return {"found": True, "ticket": t.model_dump()}
    return {"found": False, "message": f"Ticket {ticket_id} not found."}


def workweek_get_pto_balances(employee_id: str = "EMP-504405") -> Dict[str, Any]:
    """Retrieves the employee's current real-time PTO balances from WorkWeek HCM.

    Args:
        employee_id: Unique employee ID (defaults to 'EMP-504405').
    """
    return {
        "employee_id": employee_id,
        "outpatient_sick_days": MOCK_PTO_BALANCES.outpatient_sick_days,
        "hospitalisation_days": MOCK_PTO_BALANCES.hospitalisation_days,
        "vacation_days": MOCK_PTO_BALANCES.vacation_days,
        "childcare_days": MOCK_PTO_BALANCES.childcare_days,
        "volunteer_days": MOCK_PTO_BALANCES.volunteer_days,
    }


def workweek_submit_leave_request(
    leave_type: str,
    start_date: str,
    end_date: str,
    days_count: float,
    reason: Optional[str] = None,
    employee_id: str = "EMP-504405",
) -> Dict[str, Any]:
    """Submits a formal leave request to WorkWeek HCM.

    Args:
        leave_type: Type of leave ('Vacation', 'Outpatient Sick', 'Hospitalisation', 'Childcare Leave', 'Volunteer Time Off').
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        days_count: Total working days requested.
        reason: Optional notes or context.
        employee_id: Employee ID.
    """
    if "study" in leave_type.lower():
        return {
            "success": False,
            "error": "Study Leave is not recognized under Altostrat Singapore Policy Handbook. Request rejected.",
        }

    leave_id = f"LV-{len(MOCK_LEAVE_REQUESTS) + 99220}"
    new_req = {
        "id": leave_id,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "days": days_count,
        "status": "Approved",
        "submitted_at": "2026-08-20",
    }
    MOCK_LEAVE_REQUESTS.insert(0, new_req)

    # Deduct balance
    if "vacation" in leave_type.lower():
        MOCK_PTO_BALANCES.vacation_days = max(0.0, MOCK_PTO_BALANCES.vacation_days - days_count)
    elif "sick" in leave_type.lower():
        MOCK_PTO_BALANCES.outpatient_sick_days = max(0.0, MOCK_PTO_BALANCES.outpatient_sick_days - days_count)

    return {
        "success": True,
        "confirmation_ref": leave_id,
        "leave_type": leave_type,
        "days_deducted": days_count,
        "remaining_vacation_balance": MOCK_PTO_BALANCES.vacation_days,
        "remaining_sick_balance": MOCK_PTO_BALANCES.outpatient_sick_days,
        "status": "Approved",
    }
