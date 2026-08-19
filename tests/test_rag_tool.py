"""Unit tests for agent/tools/rag_tool.py."""
import unittest
from unittest.mock import MagicMock, patch

from agent.tools.rag_tool import search_policy_docs


class TestRagTool(unittest.TestCase):
    def test_search_policy_docs_missing_config(self):
        with patch("agent.config.GOOGLE_CLOUD_PROJECT", None):
            result = search_policy_docs("sick leave")
            self.assertIn("grounded_context", result)
            self.assertIn("citations", result)
            self.assertIn("Error", result["grounded_context"])
            self.assertEqual(result["citations"], [])

    def test_search_policy_docs_missing_engine_id(self):
        with patch("agent.config.GOOGLE_CLOUD_PROJECT", "test-project"), \
             patch("agent.config.VERTEX_AI_SEARCH_ENGINE_ID", None):
            result = search_policy_docs("sick leave")
            self.assertIn("grounded_context", result)
            self.assertIn("Error", result["grounded_context"])
            self.assertEqual(result["citations"], [])

    @patch("google.cloud.discoveryengine_v1.SearchServiceClient")
    def test_search_policy_docs_mocked_results(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Mock result structure
        mock_result = MagicMock()
        mock_result.document.derived_struct_data = {
            "title": "1.1 Outpatient Sick Leave",
            "link": "https://hr-portal.altostrat.com/handbook#1.1",
            "extractive_segments": [{"content": "Up to 14 days paid outpatient sick leave."}],
            "snippets": [{"snippet": "Submit MC within 48 hours."}],
        }
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.search.return_value = mock_response

        with patch("agent.config.GOOGLE_CLOUD_PROJECT", "test-project"), \
             patch("agent.config.VERTEX_AI_SEARCH_ENGINE_ID", "test-engine"):
            result = search_policy_docs("sick leave")
            self.assertIn("grounded_context", result)
            self.assertIn("citations", result)
            self.assertIn("1.1 Outpatient Sick Leave", result["grounded_context"])
            self.assertIn("Up to 14 days paid outpatient sick leave.", result["grounded_context"])
            self.assertEqual(result["citations"], ["https://hr-portal.altostrat.com/handbook#1.1"])

    @patch("google.cloud.discoveryengine_v1.SearchServiceClient")
    def test_search_policy_docs_empty_results(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.results = []
        mock_client.search.return_value = mock_response

        with patch("agent.config.GOOGLE_CLOUD_PROJECT", "test-project"), \
             patch("agent.config.VERTEX_AI_SEARCH_ENGINE_ID", "test-engine"):
            result = search_policy_docs("unknown query")
            self.assertIn("No relevant policy documents found", result["grounded_context"])
            self.assertEqual(result["citations"], [])

    @patch("google.cloud.discoveryengine_v1.SearchServiceClient")
    def test_search_policy_docs_error_handling(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.side_effect = RuntimeError("Connection timeout")

        with patch("agent.config.GOOGLE_CLOUD_PROJECT", "test-project"), \
             patch("agent.config.VERTEX_AI_SEARCH_ENGINE_ID", "test-engine"):
            result = search_policy_docs("sick leave")
            self.assertIn("Search error", result["grounded_context"])
            self.assertEqual(result["citations"], [])


if __name__ == "__main__":
    unittest.main()
