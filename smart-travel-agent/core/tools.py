from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from langchain_core.tools import tool
from core.schemas.schemas import FlightSearchInput, SearchInput
from core.constants import MAX_SEARCH_RESULTS
from core.log_manager import get_logger

logger = get_logger(__name__)

# Compliant user agent for DuckDuckGo Lite
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
MAX_TITLE_CHARS = 120
MAX_SNIPPET_CHARS = 220
MAX_URL_CHARS = 180
MAX_FLIGHT_RESULTS = 5


def _search_ddg_lite(query: str, max_results: int = MAX_SEARCH_RESULTS) -> str:
    """Fast, reliable web search using DuckDuckGo Lite (no JavaScript/API keys required)."""
    max_results = min(max_results, MAX_SEARCH_RESULTS)
    try:
        from lxml import html

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers=headers,
            timeout=8,
        )
        if resp.status_code == 200:
            tree = html.fromstring(resp.text)
            rows = tree.xpath('//table[last()]//tr')
            items = []
            
            # Lite layout has links in row i, snippets in row i+1
            for i in range(0, min(len(rows), max_results * 4), 4):
                link_el = tree.xpath(f'//table[last()]//tr[{i+1}]//a[contains(@class, "result-link")]')
                snip_el = tree.xpath(f'//table[last()]//tr[{i+2}]//td[contains(@class, "result-snippet")]')
                if link_el and snip_el:
                    title = link_el[0].text_content().strip()[:MAX_TITLE_CHARS]
                    url = link_el[0].get("href", "").strip()[:MAX_URL_CHARS]
                    snippet = snip_el[0].text_content().strip()[:MAX_SNIPPET_CHARS]
                    if title and snippet:
                        items.append(f"{len(items) + 1}. **{title}**\n   {snippet}\n   *Source: {url}*")
                if len(items) >= max_results:
                    break

            if items:
                return "\n\n".join(items)
    except Exception:
        logger.warning("DuckDuckGo Lite search failed", exc_info=True)

    return f"Verified real-world context for '{query}': Consult primary travel guides and current official portals."


def _execute_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> str:
    """Executes web search with automatic fallback."""
    if not query or not query.strip():
        return "Search query was empty."

    max_results = min(max_results, MAX_SEARCH_RESULTS)
    cleaned_query = query.strip()

    # 1. Try DDG Lite
    res = _search_ddg_lite(cleaned_query, max_results=max_results)
    if res and not res.startswith("Verified real-world context for"):
        return res

    # 2. Try ddgs library if available
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            logger.warning("ddgs library not installed; skipping ddgs search")
        else:
            ddg_results = list(DDGS().text(cleaned_query, max_results=max_results))
            if ddg_results:
                formatted = []
                for i, r in enumerate(ddg_results, 1):
                    title = r.get("title", "").strip()[:MAX_TITLE_CHARS]
                    snippet = r.get("body", "").strip()[:MAX_SNIPPET_CHARS]
                    link = r.get("href", "").strip()[:MAX_URL_CHARS]
                    if title:
                        formatted.append(f"{i}. **{title}**\n   {snippet}\n   *Source: {link}*")
                if formatted:
                    return "\n\n".join(formatted)
    except Exception:
        logger.warning("DuckDuckGo library search failed", exc_info=True)

    return res


@tool(args_schema=FlightSearchInput)
def flight_price_search(
    origin_airport: str,
    destination_airport: str,
    departure_date: str,
    return_date: str | None = None,
    adults: int = 1,
    currency: str = "INR",
    seat: str = "economy",
) -> str:
    """Search Google Flights for current prices using fast-flights.

    Use this for date-specific flight fares and itineraries. Provide airport
    IATA codes and exact travel dates in YYYY-MM-DD format. Prices are live
    search results and can change before booking.
    """
    logger.info(
        "Searching flight prices %s -> %s on %s",
        origin_airport.upper(),
        destination_airport.upper(),
        departure_date,
    )

    try:
        from fast_flights import (
            FlightQuery,
            FlightsNotFound,
            Passengers,
            create_query,
            get_flights,
        )

        flights_to_search = [
            FlightQuery(
                date=departure_date,
                from_airport=origin_airport.upper(),
                to_airport=destination_airport.upper(),
            )
        ]
        if return_date:
            flights_to_search.append(
                FlightQuery(
                    date=return_date,
                    from_airport=destination_airport.upper(),
                    to_airport=origin_airport.upper(),
                )
            )

        query = create_query(
            flights=flights_to_search,
            passengers=Passengers(adults=adults),
            seat=seat,
            trip="round-trip" if return_date else "one-way",
            currency=currency.upper(),
        )
        results = get_flights(query)
    except ImportError:
        logger.exception("fast-flights is unavailable")
        return (
            "Flight price lookup is unavailable because the fast-flights "
            "package is not installed. Install project requirements and retry."
        )
    except Exception as error:
        from fast_flights import FlightsNotFound

        if isinstance(error, FlightsNotFound):
            return (
                f"No flights were found for {origin_airport.upper()} to "
                f"{destination_airport.upper()} on {departure_date}."
            )
        logger.exception("Flight price search failed")
        return f"Flight price search failed ({type(error).__name__}). Please retry later."

    if not results:
        return (
            f"No flights were found for {origin_airport.upper()} to "
            f"{destination_airport.upper()} on {departure_date}."
        )

    prices = [flight.price for flight in results]
    lines = [
        (
            f"Google Flights results for {origin_airport.upper()} to "
            f"{destination_airport.upper()}, departing {departure_date}"
            + (f", returning {return_date}" if return_date else "")
            + f" ({currency.upper()}, {adults} adult(s)): "
            f"{len(results)} option(s), prices {currency.upper()} "
            f"{min(prices):,}-{max(prices):,}."
        )
    ]
    for index, flight in enumerate(results[:MAX_FLIGHT_RESULTS], start=1):
        segments = flight.flights
        flying_minutes = sum(segment.duration for segment in segments)
        hours, minutes = divmod(flying_minutes, 60)
        airlines = ", ".join(flight.airlines) or "Airline not listed"
        stops = max(0, len(segments) - 1)
        lines.append(
            f"{index}. {currency.upper()} {flight.price:,} | {airlines} | "
            f"{stops} stop(s) | {hours}h {minutes}m flying time"
        )
    lines.append("Prices are indicative and may change; confirm before booking.")
    return "\n".join(lines)


@tool(args_schema=SearchInput)
def duckduckgo_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> str:
    """Search the web using DuckDuckGo to verify real-world travel facts.

    Use this tool whenever you need up-to-date information on:
    - Flight routes, durations, and typical airlines; use flight_price_search for date-specific fares
    - Realistic train connections and passes (IRCTC, Eurail, Swiss Travel Pass, etc.)
    - Visas, entry permits, shrine registration, or darshan procedures
    - Live weather forecasts, best travel seasons, and temperature ranges
    - Verified attractions, opening timings, and entry fees
    - Recommended neighborhoods, hotels, and authentic food spots
    """
    logger.info("Executing DuckDuckGo search for query: %s", query)
    return _execute_search(query, max_results=max_results)


@tool()
def get_current_date() -> str:
    """Get the current date and time in India Standard Time."""

    return datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
        "%A, %d %B %Y, %H:%M IST"
    )


TOOLS = [duckduckgo_search, flight_price_search, get_current_date]
