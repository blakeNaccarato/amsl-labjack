from typing import Annotated as Ann

from cappa.arg import Arg
from cappa.base import command
from pydantic import Field

from amsl_labjack_pipeline.models import stage
from amsl_labjack_pipeline.models.params import Params
from amsl_labjack_pipeline.models.path import DataDir
from amsl_labjack_pipeline.models.paths import paths


class Outs(stage.Outs):
    cines: DataDir = paths.cines


@command(
    default_long=True, invoke="amsl_labjack_pipeline.stages.skip_cloud.__main__.main"
)
class SkipCloud(Params[stage.Deps, Outs]):
    """The outs of this stage are too large and unwieldy to cache or push to cloud storage."""

    deps: Ann[stage.Deps, Arg(hidden=True)] = Field(default_factory=stage.Deps)
    outs: Ann[Outs, Arg(hidden=True)] = Field(default_factory=Outs)
