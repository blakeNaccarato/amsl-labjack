"""Command-line interface."""

from __future__ import annotations

from dataclasses import dataclass

from cappa.subcommand import Subcommands

from amsl_labjack_pipeline.cli.experiments import Trackpy
from amsl_labjack_pipeline.stages.binarize import Binarize
from amsl_labjack_pipeline.stages.convert import Convert
from amsl_labjack_pipeline.stages.skip_cloud import SkipCloud
from amsl_labjack_pipeline.sync_dvc import SyncDvc


@dataclass
class Stage:
    """Run a pipeline stage."""

    commands: Subcommands[SkipCloud | Convert | Binarize]


@dataclass
class Exp:
    """Run a pipeline experiment."""

    commands: Subcommands[Trackpy]


@dataclass
class AmslLabJackPipeline:
    """Run the research data pipeline."""

    commands: Subcommands[SyncDvc | Stage | Exp]
