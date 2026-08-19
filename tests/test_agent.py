"""Unit tests for agent/agent.py and agent/prompt.py."""
import unittest

from agent.agent import root_agent, select_tools
from agent.prompt import POLICY_AGENT_PROMPT
import agent.config as config


class TestAgent(unittest.TestCase):
    def test_root_agent_configured(self):
        self.assertIsNotNone(root_agent)
        self.assertEqual(root_agent.name, "hr_policy_agent")
        self.assertEqual(root_agent.model, config.GEMINI_MODEL)
        self.assertTrue(len(root_agent.instruction) > 0)
        self.assertIn("Altostrat", root_agent.instruction)
        self.assertGreater(len(root_agent.tools), 0)

    def test_prompt_contains_critical_grounding_directives(self):
        self.assertIn("RETRIEVE FIRST", POLICY_AGENT_PROMPT)
        self.assertIn("STRICT GROUNDING", POLICY_AGENT_PROMPT)
        self.assertIn("DOMAIN BOUNDARIES", POLICY_AGENT_PROMPT)
        self.assertIn("CITATIONS", POLICY_AGENT_PROMPT)
        self.assertIn("Prohibitions Override", POLICY_AGENT_PROMPT)

    def test_select_tools(self):
        okf_tools = select_tools("okf")
        self.assertEqual(len(okf_tools), 2)
        tool_names = [t.__name__ for t in okf_tools]
        self.assertIn("list_concepts", tool_names)
        self.assertIn("read_concept", tool_names)

        rag_tools = select_tools("rag")
        self.assertEqual(len(rag_tools), 1)
        self.assertEqual(rag_tools[0].__name__, "search_policy_docs")

        hybrid_tools = select_tools("hybrid")
        self.assertEqual(len(hybrid_tools), 3)

        with self.assertRaises(ValueError):
            select_tools("invalid_mode")


if __name__ == "__main__":
    unittest.main()
