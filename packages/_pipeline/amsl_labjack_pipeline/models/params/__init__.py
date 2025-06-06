"""Pipeline stages model."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from typing import Generic, Self

import matplotlib
from context_models.validators import context_model_validator
from IPython.display import Markdown, display
from matplotlib.axes import Axes
from numpy import set_printoptions
from pandas import DataFrame, MultiIndex, RangeIndex, Series, options
from pydantic import BaseModel
from seaborn import move_legend, set_theme

from amsl_labjack_pipeline.models.column import Col
from amsl_labjack_pipeline.models.column.types import Ps
from amsl_labjack_pipeline.models.params.types import (
    Data_T,
    Deps_T,
    DfOrS_T,
    Outs_T,
    Preview,
)
from amsl_labjack_pipeline.models.path import get_amsl_labjack_pipeline_config
from amsl_labjack_pipeline.models.stage import Stage
from amsl_labjack_pipeline.sync_dvc.types import DvcValidationInfo
from amsl_labjack_pipeline.sync_dvc.validators import (
    dvc_extend_with_named_plots_if_missing,
)


class Constants(BaseModel):
    """Parameter constants."""

    scale: float = 1.3
    paper_scale: float = 1.0
    precision: int = 3
    display_rows: int = 12


const = Constants()


def set_display_options(
    scale: float = const.scale,
    precision: int = const.precision,
    display_rows: int = const.display_rows,
):
    """Set display options."""
    float_spec = f"#.{precision}g"
    # The triple curly braces in the f-string allows the format function to be
    # dynamically specified by a given float specification. The intent is clearer this
    # way, and may be extended in the future by making `float_spec` a parameter.
    options.display.float_format = f"{{:{float_spec}}}".format
    options.display.min_rows = options.display.max_rows = display_rows
    set_printoptions(precision=precision)
    set_theme(
        context="notebook",
        style="whitegrid",
        palette="deep",
        font="sans-serif",
        font_scale=scale,
    )
    matplotlib.rcParams |= {
        # * Figure
        "figure.autolayout": True,
        # * Images (e.g. imshow)
        "image.cmap": "gray",
        # * Legend format
        # ? Make legend opaque
        "legend.framealpha": None,
        # * Saving figures
        # ? Fix whitespace around axes
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.2,
        # ? Transparent figure background, leave axes white
        "savefig.facecolor": (1, 1, 1, 0),
        # ? DPI for saving figures only
        "savefig.dpi": 600,
        # ! Also hide title
        # "axes.titlepad": 0,
        # "axes.titlesize": "xx-small",
        # "axes.titlecolor": "#00000000",
    }


def display_markdown(df: DataFrame, floatfmt: str = "#.3g"):
    """Render dataframes as Markdown, facilitating MathJax rendering.

    Notes
    -----
    https://github.com/jupyter-book/jupyter-book/issues/1501#issuecomment-2301641068
    """
    display(Markdown(df.to_markdown(floatfmt=floatfmt)))


def head(df: DataFrame) -> DataFrame:
    return df.head()


def get_floatfmt(precision: int = 3) -> str:
    """Get floating number format at given precision."""
    return f"#.{precision}g"


class Params(Stage, Generic[Deps_T, Outs_T]):
    """Stage parameters."""

    deps: Deps_T
    """Stage dependencies."""
    outs: Outs_T
    """Stage outputs."""

    # ? Format parameters and properties

    scale: float = const.scale
    """Plot scale."""
    marker_scale: float = 20
    """Marker scale."""
    precision: int = const.precision
    """Number precision."""
    display_rows: int = const.display_rows
    """Number of rows to display in data frames."""

    @property
    def size(self) -> float:
        """Marker size."""
        return self.scale * self.marker_scale

    @property
    def floatfmt(self) -> str:
        """Floating number format."""
        return get_floatfmt(self.precision)

    @property
    def font_scale(self) -> float:
        """Font scale."""
        return self.scale

    def set_display_options(
        self,
        scale: float | None = None,
        precision: int | None = None,
        display_rows: int | None = None,
    ):
        """Set display options."""
        set_display_options(
            scale or self.scale,
            precision or self.precision,
            display_rows or self.display_rows,
        )

    def move_legend(
        self, ax: Axes, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3
    ):
        """Move legend."""
        move_legend(ax, loc=loc, bbox_to_anchor=bbox_to_anchor, ncol=ncol)

    def preview(
        self,
        df: DfOrS_T,
        cols: Iterable[Col] | None = None,
        index: Col | None = None,
        f: Preview[Ps] = head,
        ncol: int = 0,
        *args: Ps.args,
        **kwds: Ps.kwargs,
    ) -> DfOrS_T:
        """Preview a dataframe in the notebook."""
        if df.empty:
            display(df)
            return df
        fmt_ = self.floatfmt
        if isinstance(df, Series):
            display_markdown(
                DataFrame(df[:ncol] if ncol else df)
                .pipe(f, *args, **kwds)
                .rename_axis("Parameter")
                .rename(columns={0: "Value"})
            )
            return df

        df_ = df.pipe(f, *args, **kwds)
        if cols:
            fmt_ = tuple(c.fmt or self.floatfmt for c in cols)
            cols_ = (
                [c() for c in cols if c() in df_.columns] if cols else list(df_.columns)
            )
        else:
            fmt_ = self.floatfmt
            cols_ = list(df_.columns)
        cols_ = cols_[:ncol] if ncol else cols_

        if index:
            display_markdown(
                df_.reset_index(drop=df_.empty).set_index(index())[cols_],
                floatfmt=fmt_,  # pyright: ignore[reportArgumentType]
            )
            return df
        if isinstance(df_.index, MultiIndex):
            display_markdown(df_[cols_], floatfmt=fmt_)  # pyright: ignore[reportArgumentType]
            return df
        if df_.index.name and not isinstance(df_.index, RangeIndex):
            display_markdown(df_[cols_], floatfmt=fmt_)  # pyright: ignore[reportArgumentType]
            return df
        index_ = cols_.pop(0)
        display_markdown(
            df_.reset_index(drop=df_.empty).set_index(index_)[cols_],
            floatfmt=fmt_,  # pyright: ignore[reportArgumentType]
        )
        return df

    @classmethod
    def hide(cls):
        """Hide unsuppressed output in notebook cells."""
        display()

    @contextmanager
    def display_options(
        self,
        scale: float = const.scale,
        precision: int = const.precision,
        display_rows: int = const.display_rows,
    ):
        """Display options."""
        try:
            self.set_display_options(scale, precision, display_rows)
            yield
        finally:
            self.set_display_options()


class DataParams(Params[Deps_T, Outs_T], Generic[Deps_T, Outs_T, Data_T]):
    """Stage parameters."""

    model_config = get_amsl_labjack_pipeline_config()

    @context_model_validator(mode="after")
    def dvc_validate_params(self, info: DvcValidationInfo) -> Self:
        """Extend stage plots for `dvc.yaml` with named plots if plots haven't been set."""
        return dvc_extend_with_named_plots_if_missing(self, info)

    data: Data_T
    """Stage data."""
