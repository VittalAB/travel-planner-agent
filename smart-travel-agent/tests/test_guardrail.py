import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from core.middleware.gaurdrail import (
    CLASSIFICATION_FAILURE_REPLY,
    MIXED_REQUEST_REPLY,
    intent_guardrail,
)


class IntentGuardrailTests(unittest.TestCase):
    def test_mixed_travel_and_general_question_is_blocked(self) -> None:
        with patch("core.middleware.gaurdrail.safety_model") as classifier:
            classifier.invoke.return_value = AIMessage(content="MIXED")
            result = intent_guardrail.before_agent(
                {
                    "messages": [
                        HumanMessage(content="Plan a trip to Japan"),
                        AIMessage(content="Where are you traveling from?"),
                        HumanMessage(
                            content="Travel, visa, Musk who is he any relation "
                            "with Starlink"
                        ),
                    ]
                },
                None,
            )

        self.assertEqual(result["jump_to"], "end")
        self.assertEqual(result["messages"][0].content, MIXED_REQUEST_REPLY)
        classifier_input = classifier.invoke.call_args.args[0][1].content
        self.assertIn("Latest user request to classify:", classifier_input)
        self.assertNotIn("Assistant:", classifier_input)

    def test_only_travel_request_is_allowed_through(self) -> None:
        with patch("core.middleware.gaurdrail.safety_model") as classifier:
            classifier.invoke.return_value = AIMessage(content="TRAVEL_ONLY")
            result = intent_guardrail.before_agent(
                {"messages": [HumanMessage(content="Visa requirements for Japan?")]},
                None,
            )

        self.assertIsNone(result)

    def test_unexpected_classifier_output_fails_closed(self) -> None:
        with patch("core.middleware.gaurdrail.safety_model") as classifier:
            classifier.invoke.return_value = AIMessage(
                content="This is probably TRAVEL_ONLY"
            )
            result = intent_guardrail.before_agent(
                {"messages": [HumanMessage(content="Who is Elon Musk?")]},
                None,
            )

        self.assertEqual(result["jump_to"], "end")
        self.assertEqual(result["messages"][0].content, CLASSIFICATION_FAILURE_REPLY)

    def test_classifier_error_fails_closed(self) -> None:
        with patch("core.middleware.gaurdrail.safety_model") as classifier:
            classifier.invoke.side_effect = RuntimeError("classifier unavailable")
            result = intent_guardrail.before_agent(
                {"messages": [HumanMessage(content="Plan a trip")]},
                None,
            )

        self.assertEqual(result["jump_to"], "end")
        self.assertEqual(result["messages"][0].content, CLASSIFICATION_FAILURE_REPLY)


if __name__ == "__main__":
    unittest.main()
