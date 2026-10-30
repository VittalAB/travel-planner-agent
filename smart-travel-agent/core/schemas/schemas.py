

from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from core.constants import MAX_SEARCH_RESULTS



class SearchInput(BaseModel):
    query: str = Field(
        ...,
        max_length=500,
        description="Search query to verify live travel facts, flight routes, train options, entry tickets, weather, or local guidelines.",
    )
    max_results: int = Field(
        MAX_SEARCH_RESULTS,
        ge=1,
        le=MAX_SEARCH_RESULTS,
        description=f"Number of search results to return (maximum {MAX_SEARCH_RESULTS}).",
    )


class FlightSearchInput(BaseModel):
    origin_airport: str = Field(
        ...,
        pattern=r"^[A-Za-z]{3}$",
        description="Three-letter IATA airport code, such as BLR.",
    )
    destination_airport: str = Field(
        ...,
        pattern=r"^[A-Za-z]{3}$",
        description="Three-letter IATA airport code, such as CDG.",
    )
    departure_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Departure date in YYYY-MM-DD format.",
    )
    return_date: str | None = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Optional return date in YYYY-MM-DD format.",
    )
    adults: int = Field(1, ge=1, le=9)
    currency: str = Field(
        "INR",
        pattern=r"^[A-Za-z]{3}$",
        description="Three-letter currency code, for example INR, USD, or EUR.",
    )

    @model_validator(mode="after")
    def validate_travel_dates(self) -> "FlightSearchInput":
        departure = datetime.strptime(self.departure_date, "%Y-%m-%d").date()
        if self.return_date is not None:
            return_date = datetime.strptime(self.return_date, "%Y-%m-%d").date()
            if return_date < departure:
                raise ValueError("return_date must be on or after departure_date")
        return self
