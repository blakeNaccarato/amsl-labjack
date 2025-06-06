"""Data pipeline."""

from collections.abc import Callable
from os import environ
from typing import Any

from loguru import logger
from pandas import set_option

from amsl_labjack_pipeline.models.generated import types

_debug = environ.get("AMSL_LABJACK_DEBUG")
_preview = environ.get("AMSL_LABJACK_PREVIEW")
_write = environ.get("AMSL_LABJACK_WRITE")
_build_docs = environ.get("AMSL_LABJACK_BUILD_DOCS")
DEBUG = str(_debug).casefold() == "true" if _debug else False
"""Whether to run in debug mode. Log to `amsl_labjack.log`."""
PREVIEW = str(_preview).casefold() == "true" if _preview else False
"""Whether to run interactive previews."""
WRITE = str(_write).casefold() == "true" if _write else False
"""Whether to write to the local media folder."""
BUILD_DOCS = str(_build_docs).casefold() == "true" if _build_docs else False


def init():
    """Initialize {mod}`~amsl_labjack_pipeline`."""
    if DEBUG:
        logger.add(sink="amsl_labjack.log")
    set_option("mode.copy_on_write", True)
    set_option("mode.chained_assignment", "raise")
    set_option("mode.string_storage", "pyarrow")
    types.init()


init()


def run_example(func: Callable[..., Any], preview: bool = False) -> tuple[str, Any]:
    """Run an example file, logging the module name containing the function.

    Args:
        func: The example function to run.
        preview: Preview results from the function. Default: False.
    """
    module_name = func.__module__
    logger.info(f'Running example "{module_name}"')
    result = func(preview=preview)
    return module_name, result
