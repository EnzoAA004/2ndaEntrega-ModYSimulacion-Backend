from datetime import date


def ensure_date_order(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from must be before or equal to date_to")

