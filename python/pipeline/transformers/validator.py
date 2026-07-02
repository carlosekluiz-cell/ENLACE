"""Schema and bounds validation for pipeline data."""
import pandas as pd
from typing import Optional


class ValidationError(Exception):
    pass


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: list[str],
    name: str = "data",
) -> None:
    """Validate a DataFrame has required columns and no empty rows."""
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValidationError(f"{name}: missing columns {missing}")
    if df.empty:
        raise ValidationError(f"{name}: empty DataFrame")


def validate_bounds(
    df: pd.DataFrame,
    column: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    name: str = "data",
) -> None:
    """Validate numeric column is within expected bounds."""
    if min_val is not None:
        violations = df[df[column] < min_val]
        if not violations.empty:
            raise ValidationError(f"{name}: {len(violations)} rows have {column} < {min_val}")
    if max_val is not None:
        violations = df[df[column] > max_val]
        if not violations.empty:
            raise ValidationError(f"{name}: {len(violations)} rows have {column} > {max_val}")


def validate_coordinates_brazil(lat: float, lon: float) -> bool:
    """Check if coordinates are within Brazil's bounding box."""
    return -33.77 <= lat <= 5.27 and -73.99 <= lon <= -28.83


def validate_coordinates_colombia(lat: float, lon: float) -> bool:
    """Check if coordinates are within Colombia's bounding box."""
    return -4.23 <= lat <= 13.39 and -81.73 <= lon <= -66.85


_COUNTRY_BBOX = {
    "BR": {"min_lat": -33.77, "max_lat": 5.27, "min_lon": -73.99, "max_lon": -28.83},
    "CO": {"min_lat": -4.23, "max_lat": 13.39, "min_lon": -81.73, "max_lon": -66.85},
}


def validate_coordinates(lat: float, lon: float, country_code: str = "BR") -> bool:
    """Check if coordinates are within a country's bounding box."""
    bbox = _COUNTRY_BBOX.get(country_code)
    if bbox is None:
        return True  # No validation available for unknown countries
    return bbox["min_lat"] <= lat <= bbox["max_lat"] and bbox["min_lon"] <= lon <= bbox["max_lon"]
