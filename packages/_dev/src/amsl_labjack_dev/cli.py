from pathlib import Path

from cappa.base import command


@command(invoke="amsl_labjack_dev.tools.elevate_pyright_warnings")
class ElevatePyrightWarnings:
    """Elevate Pyright warnings to errors."""

    path: Path | None = None
