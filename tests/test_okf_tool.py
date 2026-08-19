"""Unit tests for agent/tools/okf_tool.py."""
import unittest

from agent.tools.okf_tool import list_concepts, read_concept


class TestOkfTool(unittest.TestCase):
    def test_list_concepts_returns_valid_structure(self):
        result = list_concepts()
        self.assertIsInstance(result, dict)
        self.assertIn("concepts", result)
        concepts = result["concepts"]
        self.assertGreater(len(concepts), 100)

        # Check fields of each concept
        for c in concepts:
            self.assertIn("id", c)
            self.assertIn("title", c)
            self.assertIn("description", c)
            self.assertTrue(len(c["id"]) > 0)
            self.assertTrue(len(c["title"]) > 0)
            # Ensure reserved files are not in concepts
            self.assertNotEqual(c["id"], "index")
            self.assertNotEqual(c["id"], "log")
            self.assertFalse(c["id"].endswith(".md"))

    def test_read_concept_valid(self):
        concept_id = "01-paid-time-off-leave-operations/1.2-paid-vacation-leave-singapore"
        result = read_concept(concept_id)
        self.assertIsInstance(result, dict)
        self.assertIn("content", result)
        self.assertIn("title", result)
        self.assertIn("resource", result)

        self.assertIn("1.2 Paid Vacation Leave (Singapore)", result["title"])
        self.assertIn("Accrual Tier Matrix", result["content"])
        self.assertIn("Section 1.2", result["resource"])

    def test_read_concept_with_trailing_md(self):
        concept_id = "01-paid-time-off-leave-operations/1.2-paid-vacation-leave-singapore.md"
        result = read_concept(concept_id)
        self.assertIn("1.2 Paid Vacation Leave (Singapore)", result["title"])
        self.assertIn("Accrual Tier Matrix", result["content"])

    def test_read_concept_path_traversal_attack(self):
        traversals = [
            "../../../etc/passwd",
            "../../../../../../bin/bash",
            "/etc/passwd",
            "../agent/config",
        ]
        for bad_id in traversals:
            result = read_concept(bad_id)
            self.assertIn("error", result)
            self.assertEqual(result["content"], "")
            self.assertIsNone(result["resource"])

    def test_read_concept_nonexistent(self):
        result = read_concept("nonexistent-concept-xyz")
        self.assertIn("error", result)
        self.assertEqual(result["content"], "")
        self.assertIsNone(result["resource"])

    def test_read_concept_empty(self):
        result = read_concept("")
        self.assertIn("error", result)
        self.assertEqual(result["content"], "")

    def test_read_concept_none(self):
        result = read_concept(None)
        self.assertIn("error", result)
        self.assertEqual(result["content"], "")


if __name__ == "__main__":
    unittest.main()
