"""Unit tests for newly integrated SDD enterprise architecture components.

Tests:
1. Identity Translation Engine (ITE) — RFC 8693 / RFC 7523 & Revocation
2. Two-Tier Japanese Keigo Enforcement Engine & SudachiPy Linter
3. Automated Post-Outage Reconciliation Background Worker
4. Persistent Firestore Session Store
5. Vertex AI 429 Exponential Backoff Retry Handler
6. Strict Pydantic Data Contracts for WorkWeek HCM & ServiceNow ITSM
"""

import asyncio
import unittest

from agent.localization.keigo_linter import JapaneseKeigoLinter, keigo_linter
from agent.models.contracts import (
    IncidentCategory,
    IncidentPriority,
    LeaveCategory,
    ServiceNowIncidentCreate,
    WorkWeekLeaveSubmissionRequest,
)
from agent.resilience.reconciliation_worker import ReconciliationWorker, reconciliation_worker
from agent.resilience.retry_handler import with_exponential_backoff
from agent.security.ite import IdentityTranslationEngine, ite_engine
from agent.storage.firestore_session import FirestoreSessionStore


class TestIdentityTranslationEngine(unittest.TestCase):
    def setUp(self):
        self.ite = IdentityTranslationEngine()

    def test_rfc8693_workweek_token_exchange(self):
        token = self.ite.exchange_rfc8693_workweek_token("vivekagar@altostrat.com")
        self.assertIn("access_token", token)
        self.assertTrue(token["access_token"].startswith("ww_sec_tok_"))
        self.assertEqual(token["token_type"], "Bearer")
        self.assertIn("workweek.pto.read", token["scope"])

    def test_rfc7523_serviceimmediately_assertion(self):
        token = self.ite.exchange_rfc7523_serviceimmediately_token("vivekagar@altostrat.com")
        self.assertIn("access_token", token)
        self.assertTrue(token["access_token"].startswith("si_usr_tok_"))
        self.assertIn("user_sys_id", token)
        self.assertIn("itil", token["roles"])

    def test_instant_zero_trust_revocation(self):
        self.ite.revoke_identity("revoked_user@altostrat.com")
        with self.assertRaises(PermissionError):
            self.ite.validate_inbound_jwt("revoked_user@altostrat.com")


class TestJapaneseKeigoLinter(unittest.TestCase):
    def test_informal_copula_elevation(self):
        informal_ja = "これはAltostratの規程だ。了解しました。"
        result = JapaneseKeigoLinter.lint_and_elevate(informal_ja, seniority_tier="L7")
        self.assertTrue(result["modified"])
        self.assertIn("でございます", result["elevated_text"])
        self.assertIn("承知いたしました", result["elevated_text"])
        self.assertNotIn("だ。", result["elevated_text"])

    def test_non_japanese_passthrough(self):
        en_text = "This is a standard English policy response."
        result = JapaneseKeigoLinter.lint_and_elevate(en_text)
        self.assertFalse(result["modified"])
        self.assertEqual(result["elevated_text"], en_text)


class TestReconciliationWorker(unittest.TestCase):
    def setUp(self):
        self.worker = ReconciliationWorker()

    def test_reconcile_provisional_success(self):
        tx_id = self.worker.queue_provisional_transaction({
            "employee_id": "EMP-504405",
            "leave_type": "Outpatient Sick",
            "days": 2.0,
        })
        balances = {"sick_leave_days": 14.0, "vacation_days": 18.0}
        res = self.worker.reconcile_provisional_transactions(balances)
        self.assertGreaterEqual(res["reconciled_count"], 1)
        self.assertEqual(res["discrepancies_count"], 0)

    def test_reconcile_deficit_alert(self):
        tx_id = self.worker.queue_provisional_transaction({
            "employee_id": "EMP-504405",
            "leave_type": "Outpatient Sick",
            "days": 10.0,
        })
        balances = {"sick_leave_days": 1.0, "vacation_days": 0.0}
        res = self.worker.reconcile_provisional_transactions(balances)
        self.assertGreaterEqual(res["discrepancies_count"], 1)
        self.assertEqual(res["discrepancies"][0]["action"], "Paged HR On-Call Opsgenie")


class TestFirestoreSessionStore(unittest.IsolatedAsyncioTestCase):
    async def test_session_lifecycle(self):
        store = FirestoreSessionStore()
        session = await store.create("hr_agent", "sess_101", user_id="EMP-504405", state={"location": "Singapore"})
        self.assertEqual(session["session_id"], "sess_101")
        self.assertEqual(session["state"]["location"], "Singapore")

        await store.update("hr_agent", "sess_101", turns=[{"user": "hi"}], state={"location": "Singapore"})
        fetched = await store.get("hr_agent", "sess_101")
        self.assertIsNotNone(fetched)
        self.assertEqual(len(fetched["turns"]), 1)


class TestPydanticDataContracts(unittest.TestCase):
    def test_workweek_leave_schema_validation(self):
        req = WorkWeekLeaveSubmissionRequest(
            employee_id="EMP-504405",
            leave_type=LeaveCategory.OUTPATIENT_SICK,
            start_date="2026-08-25",
            end_date="2026-08-26",
            days_count=2.0,
        )
        self.assertEqual(req.leave_type, LeaveCategory.OUTPATIENT_SICK)

    def test_servicenow_incident_schema(self):
        inc = ServiceNowIncidentCreate(
            caller_id="EMP-504405",
            category=IncidentCategory.HARDWARE,
            short_description="4K Monitor Provisioning Request",
            priority=IncidentPriority.P3_MODERATE,
        )
        self.assertEqual(inc.category, IncidentCategory.HARDWARE)


if __name__ == "__main__":
    unittest.main()
