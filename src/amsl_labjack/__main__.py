"""AMSL LabJack CLI."""

from __future__ import annotations

import csv
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
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
from numpy import arange, array, concatenate
from pyqtgraph import GraphicsLayoutWidget, PlotDataItem, intColor, mkQApp
from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt.QtCore import Qt
from pyqtgraph.Qt.QtGui import QKeyEvent
from structlog import get_logger

log = get_logger()


def main():
    with get_device(
        channels=[
            Channel(
                number=i,
                range=11.0,  # (+/- V) Max 11.0 for T8
            )
            for i in range(8)
        ],
        model="T8",
        connection="Ethernet",  # Alt: "USB"
        identifier="192.168.1.3",  # Alt: "480010801" (serial number),
    ) as labjack:
        stream(labjack, callback=callback, plot_period=1.0)


def callback(stream_: Stream):
    if stream_.time[-1] > 10.0:
        stream_.exit()


@contextmanager
def get_device(
    channels: Sequence[Channel],
    model: Model | None = None,
    connection: Connection | None = None,
    identifier: str | None = None,
) -> Generator[LabJack]:
    """Get LabJack handle info."""
    for name, value in {
        "LJM_STREAM_BUFFER_MAX_NUM_SECONDS": 40,  # (s) Up from default 20 s
        "LJM_STREAM_TCP_RECEIVE_BUFFER_SIZE": (24 * 2**10),  # (KiB) COMMAREA rec.
        "LJM_DEBUG_LOG_MODE": DEBUG_LOG_MODE_NEVER,  # Ensures no logging
    }.items():
        writeLibraryConfigS(name, value)
    handle = 0
    try:
        handle = open_labjack(model, connection, identifier)
        channel_names: list[str] = []
        channel_addresses: list[int] = []
        eStreamStop(handle)
        for channel in channels:
            name = f"AIN{channel.number}"
            eWriteName(handle, f"{name}_RANGE", channel.range)
            channel_names.append(name)
            channel_addresses.append(nameToAddress(name)[0])
        for name, value in {
            "STREAM_TRIGGER_INDEX": 0,  # Ensure default 0 (automatic)
            "STREAM_CLOCK_SOURCE": 0,  # Ensure default 0 (automatic)
            "STREAM_RESOLUTION_INDEX": 0,  # Ensure default 0 (automatic)
            "STREAM_BUFFER_SIZE_BYTES": (256 * 2**10),  # (KiB) Max 256 KiB for T8
            "DAC1_FREQUENCY_OUT_ENABLE": 1,  # Square wave on DAC1 for testing
        }.items():
            eWriteName(handle, name, value)
        info = getHandleInfo(handle)
        lj = LabJack(
            handle=handle,
            model=dict(zip(models.values(), models.keys(), strict=False))[info[0]],
            connection=dict(
                zip(connections.values(), connections.keys(), strict=False)
            )[info[1]],
            serial_number=info[2],
            ip_address=numberToIP(info[3]),
            port=info[4],
            max_bytes_per_mb=info[5],
            nominal_rate=(r := 20_000),  # (Hz) Max for T8 is 43_399 Hz
            scans_per_read=int(0.1 * r),  # ~4096 at max rate
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
        eStreamStop(lj.handle)
        yield lj
    finally:
        if handle:
            ljm.close(handle)


POWER_CYCLE_LABJACK_MSG = "Unplug LabJack and plug it back in."


def open_labjack(
    model: Model | None = None,
    connection: Connection | None = None,
    identifier: str | None = None,
):
    return ljm.open(
        deviceType=models[model] if model else dtANY,
        connectionType=connections[connection] if connection else dtANY,
        identifier=identifier or "ANY",
    )


Model: TypeAlias = Literal["T8"]
models: dict[Model, int] = {"T8": dtT8}
Connection: TypeAlias = Literal["USB", "Ethernet"]
connections: dict[Connection, int] = {"USB": ctUSB, "Ethernet": ctETHERNET}


def stream(lj: LabJack, callback: Callable[[Stream], None], plot_period: float):
    app = mkQApp()
    app.setStyle("Fusion")
    window = GraphicsLayoutWidgetWithKeySignal()

    def quit_on_certain_keys(ev: QKeyEvent):
        """Handle quit events and propagate keypresses to image views."""
        if ev.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q, Qt.Key.Key_Enter):
            window.exit.emit()

    def raise_exception(exception: Exception):
        window.exit.emit()
        raise exception

    window.key.connect(quit_on_certain_keys)
    window.exit.connect(app.closeAllWindows)
    window.exception.connect(raise_exception)
    name = "Voltage"
    units = "V"
    plot = window.ci.addPlot(0, 0)
    plot.addLegend()
    plot.setLabel("bottom", "Time", units="s")
    plot.setLabel("left", units=units)
    plot.setTitle(name)
    time = array([0.0])
    signals: list[SignalData] = []
    for i, channel in enumerate(lj.signals):
        data = array([0.0])
        signals.append(
            SignalData(
                data=data,
                plot=plot.plot(time, data, pen=intColor(i), name=channel.name),
                source=channel,
            )
        )
    path = Path("data/data.csv")
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        header = ["Time (s)"] + [signal.source.name for signal in signals]
        writer.writerow(header)
    sleep(0.5)  # LabJack T8 requires at least ~0.3 s to restart a stream
    stream_ = None
    try:
        stream_ = Stream(
            lj=lj,
            start=datetime.now(),
            time=time,
            signals=signals,
            window=window,
            plot_period=plot_period,
            path=path,
            rate=eStreamStart(
                handle=lj.handle,
                aScanList=[signal.address for signal in lj.signals],
                numAddresses=len(lj.signals),
                scanRate=lj.nominal_rate,
                scansPerRead=lj.scans_per_read,
            ),
        )
        setStreamCallback(lj.handle, lambda _handle: callback_(stream_, callback))
        window.show()
        app.exec()
    finally:
        if stream_:
            write(stream_, stream_.time, [signal.data for signal in stream_.signals])
        eStreamStop(lj.handle)
        app.quit()


def callback_(stream_: Stream, callback: Callable[[Stream], None]):
    try:
        period = int(stream_.plot_period * stream_.rate)
        data, _device_scan_backlog, _ljm_scan_backlog = eStreamRead(stream_.lj.handle)
        data = array(data)
        if DUMMY_VALUE in data:
            stream_.window.exception.emit(RuntimeError("Auto-recovery mode entered."))
        stream_.time = concatenate([
            stream_.time,
            (
                arange(len(data) // len(stream_.signals)) / stream_.rate
                + stream_.time[-1]
            ),
        ])
        time = None
        if len(stream_.time) > period:
            time = stream_.time[:period]
            stream_.time = stream_.time[-period:]
        signals_data: list[Vector] = []
        for i, signal in enumerate(stream_.signals):
            signal.data = concatenate([signal.data, data[i :: len(stream_.signals)]])
            if len(signal.data) > period:
                signals_data.append(signal.data[:period])
                signal.data = signal.data[-period:]
            if stream_.window.isVisible():
                signal.plot.setData(stream_.time, signal.data)
        if time is not None:
            write(stream_, time, signals_data)
        callback(stream_)
    except Exception as e:
        stream_.window.exception.emit(e)
        # sourcery skip: raise-specific-error
        raise Exception from e  # noqa: TRY002


def write(stream_: Stream, time: Vector, signals_data: list[Vector]):
    with stream_.path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        for i in range(len(time)):
            writer.writerow([
                time[i],
                *[signal_data[i] for signal_data in signals_data],
            ])


@dataclass
class Channel:
    number: int
    range: float


@dataclass
class Signal:
    name: str
    config: Channel
    address: int


@dataclass
class LabJack:
    model: Model
    connection: Connection
    handle: int
    serial_number: int
    ip_address: str
    port: int
    max_bytes_per_mb: int
    nominal_rate: int
    scans_per_read: int
    signals: list[Signal]


@dataclass
class SignalData:
    source: Signal
    data: Vector
    plot: PlotDataItem


class GraphicsLayoutWidgetWithKeySignal(GraphicsLayoutWidget):
    """Emit key signals on `key`."""

    key = QtCore.Signal(QKeyEvent)
    exception = QtCore.Signal(Exception)
    exit = QtCore.Signal()

    def keyPressEvent(self, ev: QKeyEvent):  # noqa: N802
        """Handle keypresses."""
        super().keyPressEvent(ev)
        self.key.emit(ev)


@dataclass
class Stream:
    lj: LabJack
    rate: float
    start: datetime
    time: Vector
    signals: list[SignalData]
    window: GraphicsLayoutWidgetWithKeySignal
    plot_period: float
    path: Path

    def exit(self):
        self.window.exit.emit()


Vector: TypeAlias = NDArray[Shape["*, 1"], Float]

if __name__ == "__main__":
    main()
