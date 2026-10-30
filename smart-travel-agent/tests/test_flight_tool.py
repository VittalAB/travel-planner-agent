import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.tools import TOOLS, flight_price_search


class FlightPriceSearchTests(unittest.TestCase):
    def test_tool_is_registered_and_builds_round_trip_query(self) -> None:
        result = SimpleNamespace(
            price=42_000,
            airlines=["AI"],
            flights=[SimpleNamespace(duration=95), SimpleNamespace(duration=130)],
        )

        with patch("fast_flights.get_flights", return_value=[result]) as get_flights:
            response = flight_price_search.invoke(
                {
                    "origin_airport": "blr",
                    "destination_airport": "cdg",
                    "departure_date": "2026-12-24",
                    "return_date": "2027-01-06",
                    "adults": 2,
                    "currency": "inr",
                }
            )

        self.assertIn(flight_price_search, TOOLS)
        query = get_flights.call_args.args[0]
        self.assertEqual(query.get_trip_type(), "round-trip")
        self.assertEqual(len(query.flight_data), 2)
        self.assertIn("INR 42,000", response)
        self.assertIn("3h 45m flying time", response)

    def test_no_matching_flights_returns_clear_message(self) -> None:
        with patch("fast_flights.get_flights", return_value=[]):
            response = flight_price_search.invoke(
                {
                    "origin_airport": "BLR",
                    "destination_airport": "DEL",
                    "departure_date": "2026-12-24",
                }
            )

        self.assertIn("No flights were found", response)


if __name__ == "__main__":
    unittest.main()
