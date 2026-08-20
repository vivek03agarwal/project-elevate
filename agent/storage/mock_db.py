"""Shared In-Memory Mock Database State for WorkWeek HCM and ServiceImmediately ITSM."""

from agent.models.contracts import (
    IncidentState,
    ServiceNowIncidentRecord,
    WorkWeekEmployeeProfile,
    WorkWeekPtoBalances,
)

MOCK_EMPLOYEE = WorkWeekEmployeeProfile(
    employee_id="EMP-504405",
    full_name="Vivek Agarwal",
    email="vivekagar@altostrat.com",
    job_level="L5",
    office_location="Singapore Hub - MBFC Tower 2, Level 28",
    tenure_years=3.5,
    is_fte=True,
    manager_name="Sarah Chen (Director, L7)",
    direct_reports_count=0,
)

MOCK_PTO_BALANCES = WorkWeekPtoBalances(
    employee_id="EMP-504405",
    outpatient_sick_days=14.0,
    hospitalisation_days=60.0,
    vacation_days=18.0,
    childcare_days=6.0,
    volunteer_days=2.0,
)

MOCK_LEAVE_REQUESTS = []

MOCK_ITSM_TICKETS = [
    ServiceNowIncidentRecord(
        sys_id="sys_inc_44102",
        number="INC-44102",
        category="Hardware",
        short_description="External 4K Monitor & USB-C Dock Provisioning",
        priority="3 - Moderate",
        state=IncidentState.IN_PROGRESS,
        assigned_to="Hardware Support APAC",
        opened_at="2026-08-14",
    ),
    ServiceNowIncidentRecord(
        sys_id="sys_inc_41009",
        number="INC-41009",
        category="Facilities",
        short_description="MBFC Tower 2 Turnstile Badge Re-encoding",
        priority="2 - High",
        state=IncidentState.RESOLVED,
        assigned_to="Facilities Physical Security",
        opened_at="2026-07-28",
        resolved_at="2026-07-28",
    ),
]
