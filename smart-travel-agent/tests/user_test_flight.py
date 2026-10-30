from fast_flights import FlightQuery, Passengers, create_query, get_flights

query = create_query(
    flights=[
        FlightQuery(date="2026-12-24", from_airport="BLR", to_airport="CDG"),
        FlightQuery(date="2027-01-06", from_airport="CDG", to_airport="BLR"),
    ],
    passengers=Passengers(adults=1),
    seat="economy",
    trip="round-trip",
    currency="INR",
)
results = get_flights(query)

if not results:
    print("No flights found for the requested dates.")
else:
    prices = [flight.price for flight in results]
    print(f"Price range: INR {min(prices):,} - INR {max(prices):,}")
    for flight in results:
        duration_minutes = sum(segment.duration for segment in flight.flights)
        hours, minutes = divmod(duration_minutes, 60)
        airlines = ", ".join(flight.airlines) or "Unknown"
        print(
            f"Airline(s): {airlines} | Price: INR {flight.price:,} | "
            f"Total flight duration: {hours}h {minutes}m"
        )