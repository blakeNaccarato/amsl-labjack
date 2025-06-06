"""AMSL LabJack CLI."""

from __future__ import annotations

import _csv  # pyright: ignore[reportAssignmentType]
import csv
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeAlias

from labjack import ljm
from labjack.ljm import (
    eStreamRead,
    eStreamStart,
    eStreamStop,
    eWriteName,
    getHandleInfo,
    nameToAddress,
    numberToIP,
    setStreamCallback,
    writeLibraryConfigS,
)
from labjack.ljm.constants import (
    DEBUG_LOG_MODE_NEVER,
    DUMMY_VALUE,
    ctETHERNET,
    ctUSB,
    dtANY,
    dtT8,
)
from nptyping import Float, NDArray, Shape
from numpy import arange, array, concatenate, nan
from pyqtgraph import (
    GraphicsLayoutWidget,
    PlotDataItem,
    PlotItem,
    ViewBox,
    intColor,
    mkQApp,
)
from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt.QtCore import Qt
from pyqtgraph.Qt.QtGui import QKeyEvent
from pyqtgraph.Qt.QtWidgets import QApplication
from structlog import get_logger

log = get_logger()


def main():
    get_stream(
        model="T8",
        connection="USB",  # Alt: "Ethernet"
        identifier="480010801",  # Alt: "192.168.1.3" (IP)
        nominal_rate=10_000,
        chunk_period=4.0,
        dac1_square_wave=True,
        path=Path("data/data.csv"),
        channels=[Channel(number=i, range="4.8") for i in range(8)],
        after_each_read=lambda stream: (
            stream.window.exit.emit() if stream.time[-1] > 30.0 else None
        ),
    )


def get_stream(
    model: Model | None,
    connection: Connection | None,
    identifier: str | None,
    channels: Sequence[Channel],
    after_each_read: Callable[[Stream], None],
    chunk_period: float,
    dac1_square_wave: bool,
    nominal_rate: int,
    path: Path,
):
    with (
        get(
            connection=connection,
            model=model,
            identifier=identifier,
            channels=channels,
            dac1_square_wave=dac1_square_wave,
        ) as lj,
        stream_data(
            after_each_read=after_each_read,
            lj=lj,
            path=path,
            chunk_period=chunk_period,
            nominal_rate=nominal_rate,
        ) as _stream,
    ):
        pass


@contextmanager
def get(
    model: Model | None,
    connection: Connection | None,
    identifier: str | None,
    channels: Sequence[Channel],
    dac1_square_wave: bool,
) -> Generator[LabJack]:
    """Get LabJack handle info."""
    for name, value in {
        "DEBUG_LOG_MODE": DEBUG_LOG_MODE_NEVER,
        **{
            f"STREAM_{k}": v
            for k, v in {
                "BUFFER_MAX_NUM_SECONDS": 40,  # (s) Up from default 20 s
                "TCP_RECEIVE_BUFFER_SIZE": (24 * 2**10),  # (KiB) COMMAREA rec.
            }.items()
        },
    }.items():
        writeLibraryConfigS(f"LJM_{name}", value)
    handle = None
    try:
        handle = ljm.open(
            connectionType=connections[connection] if connection else dtANY,
            deviceType=models[model] if model else dtANY,
            identifier=identifier or "ANY",
        )
        eStreamStop(handle)
        channel_names: list[str] = []
        channel_addresses: list[int] = []
        for channel in channels:
            name = f"AIN{channel.number}"
            eWriteName(handle=handle, name=f"{name}_RANGE", value=float(channel.range))
            channel_names.append(name)
            channel_addresses.append(nameToAddress(name)[0])
        for name, value in {
            **({"DAC1_FREQUENCY_OUT_ENABLE": 1} if dac1_square_wave else {}),
            **{
                f"STREAM_{k}": v
                for k, v in {
                    "BUFFER_SIZE_BYTES": (256 * 2**10),  # (KiB) Max 256 KiB for T8
                    "CLOCK_SOURCE": 0,  # Ensure default 0 (automatic)
                    "RESOLUTION_INDEX": 0,  # Ensure default 0 (automatic)
                    "TRIGGER_INDEX": 0,  # Ensure default 0 (automatic)
                }.items()
            },
        }.items():
            eWriteName(handle=handle, name=name, value=value)
        info = getHandleInfo(handle)
        lj = LabJack(
            connection=dict(
                zip(connections.values(), connections.keys(), strict=False)
            )[info[1]],
            handle=handle,
            ip_address=numberToIP(info[3]),
            max_bytes_per_mb=info[5],
            model=dict(zip(models.values(), models.keys(), strict=False))[info[0]],
            port=info[4],
            serial_number=info[2],
            signals=[
                Signal(name=name, address=address, config=config)
                for name, address, config in zip(
                    channel_names, channel_addresses, channels, strict=False
                )
            ],
        )
        log.info(
            "labjack_connected",
            lj={k: v for k, v in asdict(lj).items() if k != "signals"},
        )
        yield lj
    finally:
        if handle:
            ljm.close(handle)


@contextmanager
def stream_data(
    after_each_read: Callable[[Stream], None],
    chunk_period: float,
    lj: LabJack,
    nominal_rate: int,
    path: Path,
) -> Generator[Stream]:
    app = get_app()
    stream = None
    try:
        rate = eStreamStart(
            aScanList=[signal.address for signal in lj.signals],
            handle=lj.handle,
            numAddresses=len(lj.signals),
            scanRate=nominal_rate,
            scansPerRead=(scans_per_read := int(READ_RATE_RATIO * nominal_rate)),
        )
        stream = Stream(
            chunk_period=chunk_period,
            lj=lj,
            path=path.with_stem(
                f"{path.stem}_{datetime.now().isoformat(timespec='seconds').replace(':', '')}"
            ),
            period=1 / rate,
            rate=rate,
            read_period=1 / scans_per_read,
            scans_per_chunk=int(chunk_period * nominal_rate),
            scans_per_read=scans_per_read,
            time=(time := array([0.0])),
            signals=[
                SignalData(
                    data=(data := array([nan])),
                    plot=app.plot.plot(time, data, pen=intColor(i), name=channel.name),
                    source=channel,
                )
                for i, channel in enumerate(lj.signals)
            ],
            viewbox=app.plot.vb,  # pyright: ignore[reportArgumentType]
            window=app.window,
            writer=None,  # pyright: ignore[reportArgumentType] # ? Assigned just below
        )
        log.info(
            "stream_started",
            stream={
                k: stream.__dict__[k]
                for k in stream.__dict__
                if k not in ["lj", "time", "signals", "viewbox", "window", "writer"]
            },
        )
        with stream.path.open("w", newline="", encoding="utf-8") as file:
            stream.writer = csv.writer(file)
            stream.writer.writerow(
                ["Time (s)"] + [signal.source.name for signal in stream.signals]
            )
            yield stream
            setStreamCallback(
                handle=stream.lj.handle,
                callback=lambda _handle: on_read_ready(stream, after_each_read),
            )
            stream.window.show()
            app.root.exec()
    finally:
        if stream:
            with stream.path.open("a", newline="", encoding="utf-8") as file:
                write(
                    csv.writer(file),
                    stream.time,
                    [signal.data for signal in stream.signals],
                )
        eStreamStop(lj.handle)
        app.root.quit()


READ_RATE_RATIO = 0.1
"""Suitable ratio of read rate to nominal rate for most plot/read loops."""


def get_app() -> App:
    root = mkQApp()
    root.setStyle("Fusion")
    window = GraphicsLayoutWidgetWithKeySignal()
    window.key.connect(lambda ev: quit_on_certain_keys(ev, window))
    window.exit.connect(root.closeAllWindows)
    window.exception.connect(lambda exc: raise_exception(exc, window))
    plot = window.ci.addPlot(0, 0)
    plot.addLegend()
    plot.setLabel("bottom", "Time", units="s")
    plot.setLabel("left", units="V")
    plot.setTitle("Voltage")
    return App(root=root, plot=plot, window=window)


@dataclass
class App:
    root: QApplication
    plot: PlotItem
    window: GraphicsLayoutWidgetWithKeySignal


def quit_on_certain_keys(ev: QKeyEvent, window: GraphicsLayoutWidgetWithKeySignal):
    """Handle quit events and propagate keypresses to image views."""
    if ev.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q, Qt.Key.Key_Enter):
        window.exit.emit()


def raise_exception(exception: Exception, window: GraphicsLayoutWidgetWithKeySignal):
    window.exit.emit()
    raise exception


def on_read_ready(stream: Stream, after_each_read: Callable[[Stream], None]):
    try:
        signal_data, _lj_backlog, _local_backlog = eStreamRead(stream.lj.handle)
        if DUMMY_VALUE in signal_data:
            stream.window.exception.emit(RuntimeError("Auto-recovery mode entered."))
        read_time = stream.time[-1] + (
            stream.period * arange(1, stream.scans_per_read + 1)
        )
        stream.time = concatenate([stream.time, read_time])
        if stream.window.isVisible():
            stream.viewbox.setXRange(
                stream.time[-1] - stream.chunk_period, stream.time[-1], padding=0
            )
        signal_data_chunks: list[Vector] = []
        get_chunk = len(stream.time) > 2 * stream.scans_per_chunk  # Keep tailing chunk
        for signal_index, signal in enumerate(stream.signals):
            signal.data = concatenate([
                signal.data,
                signal_data[signal_index :: len(stream.signals)],
            ])
            update_plot(stream=stream, signal_index=signal_index)
            if get_chunk:
                signal_data_chunks.append(signal.data[: stream.scans_per_chunk])
                signal.data = signal.data[stream.scans_per_chunk :]
        if get_chunk:
            time_chunk = stream.time[: stream.scans_per_chunk]
            stream.time = stream.time[stream.scans_per_chunk :]
            write(stream.writer, time_chunk, signal_data_chunks)
        after_each_read(stream)
    except Exception as e:
        stream.window.exception.emit(e)
        # sourcery skip: raise-specific-error
        raise Exception from e  # noqa: TRY002


def update_plot(stream: Stream, signal_index: int):
    decimation = 10 if stream.scans_per_chunk > PLOT_POINTS_PER_CHUNK_LIMIT else 1
    if stream.window.isVisible():
        stream.signals[signal_index].plot.setData(
            stream.time[-stream.scans_per_chunk : -1 : decimation],
            stream.signals[signal_index].data[
                -stream.scans_per_chunk : -1 : decimation
            ],
        )


PLOT_POINTS_PER_CHUNK_LIMIT = 10_000
"""More than this number and the plot window can become unresponsive."""


def write(writer: _csv._writer, time: Vector, signals_data: list[Vector]):  # pyright: ignore[reportAttributeAccessIssue]
    for i in range(len(time)):
        writer.writerow([time[i], *[signal_data[i] for signal_data in signals_data]])


@dataclass
class Stream:
    chunk_period: float
    lj: LabJack
    path: Path
    period: float
    rate: float
    read_period: float
    scans_per_chunk: int
    scans_per_read: int
    signals: list[SignalData]
    time: Vector
    viewbox: ViewBox
    window: GraphicsLayoutWidgetWithKeySignal
    writer: _csv._writer


@dataclass
class SignalData:
    data: Vector
    plot: PlotDataItem
    source: Signal


Vector: TypeAlias = NDArray[Shape["*, 1"], Float]


class GraphicsLayoutWidgetWithKeySignal(GraphicsLayoutWidget):
    """Emit key signals on `key`."""

    exception = QtCore.Signal(Exception)
    exit = QtCore.Signal()
    key = QtCore.Signal(QKeyEvent)

    def keyPressEvent(self, ev: QKeyEvent):  # noqa: N802
        """Handle keypresses."""
        super().keyPressEvent(ev)
        self.key.emit(ev)


@dataclass
class LabJack:
    connection: Connection
    handle: int
    model: Model
    ip_address: str
    max_bytes_per_mb: int
    port: int
    serial_number: int
    signals: list[Signal]


Model: TypeAlias = Literal["T8"]
models: dict[Model, int] = {"T8": dtT8}
Connection: TypeAlias = Literal["USB", "Ethernet"]
connections: dict[Connection, int] = {"USB": ctUSB, "Ethernet": ctETHERNET}


@dataclass
class Signal:
    address: int
    config: Channel
    name: str


@dataclass
class Channel:
    number: int
    range: Range


Range: TypeAlias = Literal[
    "0.0",
    "0.018",
    "0.036",
    "0.075",
    "0.15",
    "0.3",
    "0.6",
    "1.2",
    "2.4",
    "4.8",
    "9.6",
    "11.0",
]


if __name__ == "__main__":
    main()
