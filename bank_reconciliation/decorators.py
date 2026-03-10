"""Debug decorators for function logging and timing."""

import functools
import time
from datetime import timedelta
from typing import Any, Callable, Optional, Set, TypeVar

import humanize
import structlog

F = TypeVar("F", bound=Callable[..., Any])

DEFAULT_EXCLUDE_PARAMS: Set[str] = {
    "password",
    "token",
    "secret",
    "api_key",
    "private_key",
    "credential",
    "auth",
    "authorization",
}


def _should_exclude(param_name: str, exclude_set: Set[str]) -> bool:
    """Check if parameter name should be excluded from logging."""
    param_lower = param_name.lower()
    return any(excluded in param_lower for excluded in exclude_set)


def _truncate_value(value: Any, max_length: int) -> Any:
    """Truncate value if it exceeds max_length."""
    if isinstance(value, str):
        if len(value) > max_length:
            return value[:max_length] + "..."
    else:
        str_value = repr(value)
        if len(str_value) > max_length:
            return str_value[:max_length] + "..."
    return value


def _sanitize_params(
    args: tuple,
    kwargs: dict,
    exclude_params: Set[str],
    max_arg_length: int,
    func: Callable,
) -> dict:
    """Extract and sanitize function parameters, skipping self/cls."""
    import inspect

    sanitized = {}

    # Get function signature
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
    except (ValueError, TypeError):
        # If we can't get signature, just use kwargs
        params = list(kwargs.keys())

    # Process kwargs
    for key, value in kwargs.items():
        if not _should_exclude(key, exclude_params):
            sanitized[key] = _truncate_value(value, max_arg_length)

    # Process positional args
    for i, arg in enumerate(args):
        # Skip self and cls (first argument for instance/class methods)
        if i == 0 and len(params) > 0 and params[0] in ("self", "cls"):
            continue

        # Get param name if available
        if i < len(params):
            param_name = params[i]
            if not _should_exclude(param_name, exclude_params):
                sanitized[param_name] = _truncate_value(arg, max_arg_length)

    return sanitized


def log_call(
    log_level: str = "debug",
    include_args: bool = True,
    include_result: bool = True,
    exclude_params: Optional[Set[str]] = None,
    max_arg_length: int = 200,
) -> Callable[[F], F]:
    """
    Decorator to log function calls with timing and arguments.

    Logs three events:
    - "<function> called": Entry with arguments (if include_args=True)
    - "<function> returned": Exit with result and timing (always includes timing)
    - "<function> raised": Exception with timing (if error occurs)

    Args:
        log_level: Log level to use ("debug", "info", "warning")
        include_args: Whether to log function arguments
        include_result: Whether to log return value
        exclude_params: Additional parameter names to exclude (merged with defaults)
        max_arg_length: Maximum length for argument values before truncation

    Returns:
        Decorated function with logging

    Example:
        @log_call()
        def reconcile_transactions(threshold: float = 0.85) -> Result:
            pass
    """

    def decorator(func: F) -> F:
        # Get logger for the function's module
        logger = structlog.get_logger(func.__module__)

        # Merge exclude params
        exclude_set = DEFAULT_EXCLUDE_PARAMS.copy()
        if exclude_params:
            exclude_set.update(p.lower() for p in exclude_params)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build context
            context = {}

            # Add class name if this is a method
            # Only add class_name if first param name is 'self' or 'cls'
            import inspect

            try:
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if args and len(params) > 0 and params[0] in ("self", "cls"):
                    if hasattr(args[0], "__class__") and not isinstance(args[0], type):
                        context["class_name"] = args[0].__class__.__name__
            except (ValueError, TypeError):
                pass

            # Log arguments if enabled
            if include_args:
                sanitized = _sanitize_params(
                    args, kwargs, exclude_set, max_arg_length, func
                )
                context.update(sanitized)

            # Log entry
            log_fn = getattr(logger, log_level)
            log_fn(f"{func.__name__} called", **context)

            # Time execution (always logged)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_sec = time.perf_counter() - start
                elapsed_ms = elapsed_sec * 1000

                # Log completion with timing (always included)
                completion_context = {
                    "duration_ms": round(elapsed_ms, 2),
                    "duration": humanize.precisedelta(
                        timedelta(seconds=elapsed_sec), minimum_unit="milliseconds"
                    ),
                }
                if include_result:
                    completion_context["result"] = _truncate_value(
                        result, max_arg_length
                    )

                log_fn(f"{func.__name__} returned", **completion_context)
                return result

            except Exception as e:
                elapsed_sec = time.perf_counter() - start
                elapsed_ms = elapsed_sec * 1000
                logger.error(
                    f"{func.__name__} raised",
                    duration_ms=round(elapsed_ms, 2),
                    duration=humanize.precisedelta(
                        timedelta(seconds=elapsed_sec), minimum_unit="milliseconds"
                    ),
                    error_type=type(e).__name__,
                    error_message=str(e),
                    exc_info=True,
                )
                raise

        return wrapper  # type: ignore

    return decorator
