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
