import json
import logging

logger = logging.getLogger(__name__)

def format_sse_event(event: str, data: dict) -> str:
    """
    Format a dictionary as an SSE event string.

    Args:
        event: The event type (e.g., 'progress', 'complete', 'error').
        data: The data to send as JSON.

    Returns:
        A properly formatted SSE event string.
    """
    try:
        event_str = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        logger.debug(f"Formatted SSE event: {event_str}")
        return event_str
    except Exception as e:
        logger.error(f"Failed to format SSE event: {str(e)}")
        return format_sse_event("error", {"success": False, "message": f"SSE formatting failed: {str(e)}", "data": {}})

def send_sse(response: dict, event: str = "complete") -> str:
    """
    Prepare an SSE event from a response dictionary.

    Args:
        response: The response dictionary to send.
        event: The event type (default: 'complete').

    Returns:
        Formatted SSE event string.
    """
    return format_sse_event(event, response)