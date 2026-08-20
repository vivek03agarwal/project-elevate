"""Strict Pydantic Interface Schemas for WorkWeek HCM and ServiceNow ITSM (SDD Sec. 2 & Sec. 4).

Provides contract-validated models for:
1. WorkWeek HCM (Employee Profile, PTO Accruals, Leave Submissions)
2. ServiceNow / ServiceImmediately ITSM (Incidents, Priorities, Categories, State Transitions)
3. Concur Travel & Expense Reports
4. Agent Chat Ingress & Egress Contracts
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class LeaveCategory(str, Enum):
    VACATION = "Vacation"
    OUTPATIENT_SICK = "Outpatient Sick"
    HOSPITALISATION = "Hospitalisation"
    MATERNITY_GPML = "Maternity (GPML)"
    PATERNITY_GPPL = "Paternity (GPPL)"
    BABY_BONDING = "Baby Bonding Leave"
    SHARED_PARENTAL = "Shared Parental Leave"
    ADOPTION = "Adoption Leave"
    CHILDCARE = "Childcare Leave"
    MARRIAGE = "Marriage Leave"
    VOLUNTEER = "Volunteer Time Off"
    PERSONAL_UNPAID = "Personal Leave (Unpaid)"


class IncidentPriority(str, Enum):
    P1_CRITICAL = "1 - Critical"
    P2_HIGH = "2 - High"
    P3_MODERATE = "3 - Moderate"
    P4_LOW = "4 - Low"


class IncidentCategory(str, Enum):
    HARDWARE = "Hardware"
    FACILITIES = "Facilities"
    ACCESS_SECURITY = "Access"
    NETWORK_VPN = "Network"
    SOFTWARE_SAAS = "Software"


class IncidentState(str, Enum):
    NEW = "New"
    IN_PROGRESS = "In Progress"
    ON_HOLD = "On Hold"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


# ---------------------------------------------------------------------------
# WorkWeek HCM Contracts
# ---------------------------------------------------------------------------
class WorkWeekEmployeeProfile(BaseModel):
    employee_id: str = Field(..., description="Unique employee identifier (e.g. EMP-504405)")
    full_name: str
    email: str
    job_level: str = Field(..., description="Job level tier (L3 through L8)")
    office_location: str = "Singapore Hub"
    tenure_years: float
    is_fte: bool = True
    manager_name: str
    direct_reports_count: int = 0


class WorkWeekPtoBalances(BaseModel):
    employee_id: str
    outpatient_sick_days: float = Field(default=14.0, ge=0.0, le=14.0)
    hospitalisation_days: float = Field(default=60.0, ge=0.0, le=60.0)
    vacation_days: float = Field(default=18.0, ge=0.0)
    childcare_days: float = Field(default=6.0, ge=0.0)
    volunteer_days: float = Field(default=2.0, ge=0.0)


class WorkWeekLeaveSubmissionRequest(BaseModel):
    employee_id: str
    leave_type: LeaveCategory
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    days_count: float = Field(..., gt=0.0)
    reason: Optional[str] = None
    mc_attachment_uri: Optional[str] = None


class WorkWeekLeaveConfirmation(BaseModel):
    confirmation_ref: str = Field(..., description="Reference ID (e.g. #LV-99214 or #PRV-8812)")
    status: str = "Approved"
    leave_type: str
    days_deducted: float
    remaining_balance: float


# ---------------------------------------------------------------------------
# ServiceNow / ServiceImmediately ITSM Contracts
# ---------------------------------------------------------------------------
class ServiceNowIncidentCreate(BaseModel):
    caller_id: str = Field(..., description="Employee User ID or Email")
    category: IncidentCategory
    short_description: str = Field(..., min_length=5, max_length=200)
    description: Optional[str] = None
    priority: IncidentPriority = IncidentPriority.P3_MODERATE

    @field_validator("priority")
    @classmethod
    def auto_classify_routine_requests(cls, v: IncidentPriority, values: Any) -> IncidentPriority:
        # Preprocessing rule: routine password/login requests must not be Critical
        return v


class ServiceNowIncidentRecord(BaseModel):
    sys_id: str
    number: str = Field(..., description="Ticket number (e.g. INC-44102)")
    category: str
    short_description: str
    priority: str
    state: IncidentState
    assigned_to: str
    opened_at: str
    resolved_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Concur Expense Contracts
# ---------------------------------------------------------------------------
class ConcurExpenseItem(BaseModel):
    expense_id: str
    category: str
    amount_usd: float = Field(..., gt=0.0)
    transaction_date: str
    merchant_name: str
    attendees_count: int = 1
    most_senior_level_present: Optional[str] = "L5"
    receipt_attached: bool = True
    aging_days: int = 0


# ---------------------------------------------------------------------------
# Agent Chat Contracts
# ---------------------------------------------------------------------------
class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = "default_session"
    inbound_jwt: Optional[str] = None
    user_seniority: Optional[str] = "L5"


class AgentChatResponse(BaseModel):
    response: str
    sources: List[str] = Field(default_factory=list)
    tools_invoked: List[str] = Field(default_factory=list)
    keigo_modified: bool = False
    session_id: str
