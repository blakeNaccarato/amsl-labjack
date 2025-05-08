"""Command-line interface."""

from amsl_labjack_pipeline.cli import AmslLabJackPipeline
from amsl_labjack_pipeline.parser import invoke


def main():
    """CLI entry-point."""
    invoke(AmslLabJackPipeline)


if __name__ == "__main__":
    main()
