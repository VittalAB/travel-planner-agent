import unittest
from datetime import datetime, timezone

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import ValidationError

from core.token_budget import MAX_COMPLETION_TOKENS, SlidingWindowTokenLimiter, TokenBudgetMiddleware
from core.middleware.date_context import CurrentDateMiddleware, current_date_context
from core.tools import SearchInput, get_current_date


class TokenBudgetTests(unittest.TestCase):
    def test_old_conversation_history_is_removed_to_fit_input_budget(self) -> None:
        request = ModelRequest(
            model=ChatGroq(
                model="openai/gpt-oss-20b",
                api_key="test",
                max_tokens=MAX_COMPLETION_TOKENS,
            ),
            system_message=SystemMessage(content="Travel agent"),
            messages=[
                HumanMessage(content="Earlier question"),
                AIMessage(content="old response " * 2_000),
                HumanMessage(content="Latest question"),
            ],
        )

        bounded_request, reservation = TokenBudgetMiddleware()._prepare(request)

        self.assertEqual(len(bounded_request.messages), 1)
        self.assertEqual(bounded_request.messages[0].content, "Latest question")
        self.assertLessEqual(reservation, 6_500)

    def test_limiter_rejects_reservations_over_its_budget(self) -> None:
        limiter = SlidingWindowTokenLimiter(budget=10)

        with self.assertRaises(ValueError):
            limiter.acquire(11)

    def test_search_input_limits_result_count(self) -> None:
        self.assertEqual(SearchInput(query="travel", max_results=2).max_results, 2)
        with self.assertRaises(ValidationError):
            SearchInput(query="travel", max_results=3)

    def test_current_date_context_uses_india_local_time(self) -> None:
        context = current_date_context(
            datetime(2026, 10, 28, 19, 0, tzinfo=timezone.utc)
        )

        self.assertIn("Thursday, 29 October 2026, 00:30", context)
        self.assertIn("Asia/Kolkata", context)

    def test_current_date_is_added_to_each_model_request(self) -> None:
        request = ModelRequest(
            model=ChatGroq(
                model="openai/gpt-oss-20b",
                api_key="test",
                max_tokens=MAX_COMPLETION_TOKENS,
            ),
            system_message=SystemMessage(content="Travel agent"),
            messages=[HumanMessage(content="What month is it?")],
        )

        dated_request = CurrentDateMiddleware._request_with_current_date(request)

        self.assertIn("Travel agent", dated_request.system_message.content)
        self.assertIn("Current date and time:", dated_request.system_message.content)
        self.assertIn("Asia/Kolkata", dated_request.system_message.content)
        self.assertEqual(get_current_date.name, "get_current_date")
        datetime.strptime(
            get_current_date.invoke({}),
            "%A, %d %B %Y, %H:%M IST",
        )


if __name__ == "__main__":
    unittest.main()
