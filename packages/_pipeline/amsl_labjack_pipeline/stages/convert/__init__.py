from pathlib import Path
from typing import Annotated as Ann

from cappa.arg import Arg
from cappa.base import command
from pydantic import Field

from amsl_labjack_pipeline.models import stage
from amsl_labjack_pipeline.models.params import Params
from amsl_labjack_pipeline.models.path import DataDir, DirectoryPathSerPosix
from amsl_labjack_pipeline.models.paths import paths


class Deps(stage.Deps):
    stage: DirectoryPathSerPosix = Path(__file__).parent
    cines: DataDir = paths.cines


class Outs(stage.Outs):
    large_sources: DataDir = paths.large_sources
    headers: DataDir = paths.headers


@command(default_long=True, invoke="amsl_labjack_pipeline.stages.convert.__main__.main")
class Convert(Params[Deps, Outs]):
    """Convert CINEs to NetCDF and extract file headers."""

    deps: Ann[Deps, Arg(hidden=True)] = Field(default_factory=Deps)
    outs: Ann[Outs, Arg(hidden=True)] = Field(default_factory=Outs)
