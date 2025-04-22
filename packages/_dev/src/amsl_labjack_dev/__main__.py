"""Command-line interface."""

from dataclasses import dataclass

from cappa.base import command, invoke
from cappa.subcommand import Subcommands


@command(invoke="amsl_labjack_dev.tools.add_change")
class AddChange:
    """Add change."""


@command(invoke="amsl_labjack_dev.tools.get_actions")
class GetActions:
    """Get actions used by this repository."""


@command(invoke="amsl_labjack_dev.tools.sync_local_dev_configs")
class SyncLocalDevConfigs:
    """Synchronize local dev configs."""


@command(invoke="amsl_labjack_dev.tools.elevate_pyright_warnings")
class ElevatePyrightWarnings:
    """Elevate Pyright warnings to errors."""


@dataclass
class AmslLabjackDev:
    """Dev tools."""

    commands: Subcommands[
        AddChange | GetActions | SyncLocalDevConfigs | ElevatePyrightWarnings
    ]


def main():
    """CLI entry-point."""
    invoke(AmslLabjackDev)


if __name__ == "__main__":
    main()
