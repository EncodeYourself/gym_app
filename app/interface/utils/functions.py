from app.interface.utils.logging import get_logger
from datetime import datetime


logger = get_logger(__name__)

def parse_time_str(time_str: str) -> datetime.time:
    """
    Parse HH:MM string to datetime.time object.

    Args:
        time_str: Time string in HH:MM format.

    Returns:
        datetime.time object.

    Raises:
        ValueError: If the string is not valid HH:MM.
    """
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except (ValueError, TypeError) as e:
        logger.error(
            "Invalid time format received: %s",
            time_str,
        )
        raise ValueError(
            f"Invalid time format: {time_str}. Expected HH:MM."
        ) from e