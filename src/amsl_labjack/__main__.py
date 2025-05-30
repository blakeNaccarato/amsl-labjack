"""AMSL LabJack CLI."""

from collections import deque
from os import kill
from re import search
from signal import SIGTERM
from typing import TYPE_CHECKING

import dwfpy as dwf
from labjack import ljm
from labjack.ljm import (
    LJMError,
    closeAll,
    eStreamStart,
    eStreamStop,
    eWriteName,
    namesToAddresses,
    setStreamCallback,
)
from pyqtgraph import GraphicsLayoutWidget, intColor, mkQApp

if TYPE_CHECKING:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QKeyEvent
else:
    from pyqtgraph.Qt.QtCore import Qt, Signal
    from pyqtgraph.Qt.QtGui import QKeyEvent


# TODO: Configure channel/DAQ settings to load from TOML config model

WAVEFORM_CHANNEL = 0
AMPLITUDE = 1.0  # (V)
FREQUENCY = 500  # (Hz)

FIRST_AIN = 0
AIN_COUNT = 4
SAMPLING_RATE = 10_000  # (Hz) Should satisfy the Nyquist criterion

FALL_BEHIND_THRESHOLD = 1.0  # (s) Scan backlog error threshold
RANGE = 11.0  # (+/- V) Max 11.0 for T8
READ_RATE_RATIO = 0.10
CYCLES_IN_HISTORY = 1

SAMPLING_PERIOD = 1 / SAMPLING_RATE  # (s)
READ_RATE = int(READ_RATE_RATIO * SAMPLING_RATE)
HISTORY_LENGTH = int(CYCLES_IN_HISTORY * SAMPLING_RATE / FREQUENCY)


class GraphicsLayoutWidgetWithKeySignal(GraphicsLayoutWidget):
    """Emit key signals on `key_signal`."""

    key_signal = Signal(QKeyEvent)

    def keyPressEvent(self, ev: QKeyEvent):  # noqa: N802
        """Handle keypresses."""
        super().keyPressEvent(ev)
        self.key_signal.emit(ev)


APP = mkQApp()
APP.setStyle("Fusion")
WINDOW = GraphicsLayoutWidgetWithKeySignal()
WINDOW.show()


def keyPressEvent(ev: QKeyEvent):  # noqa: N802
    """Handle quit events and propagate keypresses to image views."""
    if ev.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q, Qt.Key.Key_Enter):
        APP.closeAllWindows()
        ev.accept()


WINDOW.key_signal.connect(keyPressEvent)
TIME: deque[float] = deque(maxlen=HISTORY_LENGTH)
TIME.extend(SAMPLING_PERIOD * i for i in range(HISTORY_LENGTH))
NAME = "Voltage"
# TODO: Fix types
PLOT = WINDOW.addPlot(0, 0)  # pyright: ignore[reportAttributeAccessIssue]
PLOT.addLegend()
PLOT.setLabel("bottom", text="Seconds")
PLOT.setLabel("left", units="Volts")
PLOT.setTitle(NAME)
VOLTAGE = deque([0.0] * HISTORY_LENGTH, maxlen=HISTORY_LENGTH)
CURVE = PLOT.plot(TIME, VOLTAGE, pen=intColor(0), name=NAME)


def main():
    closeAll()
    try:
        handle = ljm.open()
    except LJMError as e:
        match = search(r"pid (\d+)", e.errorString)
        if not match:
            raise LJMError from e
        pid = int(match[1])
        kill(pid, SIGTERM)
        handle = ljm.open()
    eStreamStop(handle)
    channel_names = [f"AIN{i}" for i in range(FIRST_AIN, FIRST_AIN + AIN_COUNT)]
    channels = namesToAddresses(aNames=channel_names, numFrames=len(channel_names))[0]
    for channel in channel_names:
        eWriteName(handle, f"{channel}_RANGE", RANGE)
    # ljm.eWriteName(handle=handle, name="STREAM_TRIGGER_INDEX", value=0)
    # ljm.eWriteName(handle=handle, name="STREAM_CLOCK_SOURCE", value=0)
    # ljm.eWriteName(handle, "STREAM_RESOLUTION_INDEX", 0)
    # TODO: Use actual `_rate` instead of nominal `SAMPLING_RATE`
    _rate = eStreamStart(
        handle=handle,
        aScanList=channels,
        numAddresses=len(channels),
        scanRate=SAMPLING_RATE,
        scansPerRead=READ_RATE,
    )
    # TODO: Use a context manager and incorporate the callback
    setStreamCallback(handle, plot)
    # TODO: Use LabJack analog outputs for self test
    with dwf.AnalogDiscovery2() as device:
        waveform_generator_1 = device.analog_output.channels[WAVEFORM_CHANNEL]
        waveform_generator_1.setup(
            function="sine",
            amplitude=AMPLITUDE,
            frequency=FREQUENCY,
            configure=True,
            start=True,
        )
        # TODO: Use a context manager for PyQtGraph app
        APP.exec()
    APP.quit()
    # TODO: Use a context manager for clean shutdown of LabJack
    eStreamStop(handle)
    ljm.close(handle)


def plot(handle: int):
    # TODO: Gracefully handle high backlog as well as dumping when e.g. 95% buffer full
    data, _device_scan_backlog, ljm_scan_backlog = ljm.eStreamRead(handle)
    # TODO: Plot multiple curves in pens
    VOLTAGE.extend(data[::AIN_COUNT])
    CURVE.setData(TIME, VOLTAGE)  # TODO: Fix types
    if ljm_scan_backlog * SAMPLING_PERIOD > FALL_BEHIND_THRESHOLD:
        raise RuntimeError(f"Device scan backlog exceeds {FALL_BEHIND_THRESHOLD} s.")


if __name__ == "__main__":
    main()
