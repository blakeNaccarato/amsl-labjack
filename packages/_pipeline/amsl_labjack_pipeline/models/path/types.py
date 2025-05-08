"""Types."""

from typing import Annotated as Ann
from typing import Literal, TypeAlias

from cappa.arg import Arg

from amsl_labjack_pipeline.models.contexts import AmslLabJackPipelineContexts

Key: TypeAlias = Literal["data", "docs"]
"""Data or docs key."""
HiddenContext: TypeAlias = Ann[AmslLabJackPipelineContexts, Arg(hidden=True)]
"""Pipeline context as a hidden argument."""
