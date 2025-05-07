"""AMSL LabJack CLI."""

from collections import deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import dwfpy as dwf
from pyqtgraph import DateAxisItem, GraphicsLayoutWidget, intColor, mkQApp

if TYPE_CHECKING:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QKeyEvent
else:
    from pyqtgraph.Qt.QtCore import Qt, QTimer, Signal
    from pyqtgraph.Qt.QtGui import QKeyEvent


class GraphicsLayoutWidgetWithKeySignal(GraphicsLayoutWidget):
    """Emit key signals on `key_signal`."""

    key_signal = Signal(QKeyEvent)

    def keyPressEvent(self, ev: QKeyEvent):  # noqa: N802
        """Handle keypresses."""
        super().keyPressEvent(ev)
        self.key_signal.emit(ev)


WAVEFORM_CHANNEL = 0
SCOPE_CHANNEL = 0
AMPLITUDE = 1.0  # (V)
FREQUENCY = 8.0  # (Hz)

CYCLES_IN_HISTORY = 10
SAMPLING_RATE = 10.0 * FREQUENCY  # (Hz) Satisfies the Nyquist criterion of 2f
SAMPLING_PERIOD = 1 / SAMPLING_RATE  # (s)
HISTORY_LENGTH = int(CYCLES_IN_HISTORY / FREQUENCY / SAMPLING_PERIOD)

WINDOW = GraphicsLayoutWidgetWithKeySignal()
APP = mkQApp()


def keyPressEvent(ev: QKeyEvent):  # noqa: N802
    """Handle quit events and propagate keypresses to image views."""
    if ev.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q, Qt.Key.Key_Enter):
        APP.closeAllWindows()
        ev.accept()


NAME = "Voltage"
PLOT = WINDOW.addPlot(0, 0)  # pyright: ignore[reportAttributeAccessIssue]
WINDOW.key_signal.connect(keyPressEvent)
PLOT.addLegend()
PLOT.setAxisItems({"bottom": DateAxisItem()})
PLOT.setLabel("left", units="VoltS")
PLOT.setTitle(NAME)

current_time = datetime.now()
TIME: deque[float] = deque(maxlen=HISTORY_LENGTH)
TIME.extendleft(
    (current_time - i * timedelta(seconds=SAMPLING_PERIOD)).timestamp()
    for i in range(HISTORY_LENGTH)
)
VOLTAGE = deque([0.0] * HISTORY_LENGTH, maxlen=HISTORY_LENGTH)
TIME.append(datetime.now().timestamp())
CURVE = PLOT.plot(TIME, VOLTAGE, pen=intColor(0), name=NAME)
TIMER = QTimer()


def main():
    with dwf.AnalogDiscovery2() as device:
        waveform_generator_1 = device.analog_output.channels[WAVEFORM_CHANNEL]
        waveform_generator_1.setup(
            function="sine",
            amplitude=AMPLITUDE,
            frequency=FREQUENCY,
            configure=True,
            start=True,
        )
        scope = device.analog_input
        scope.configure()
        scope[SCOPE_CHANNEL].setup()

        def plot():
            """Plot function."""
            TIME.append(datetime.now().timestamp())
            scope.read_status()
            VOLTAGE.append(scope[SCOPE_CHANNEL].get_sample())
            CURVE.setData(TIME, VOLTAGE)

        TIMER.timeout.connect(plot)
        TIMER.start(int(SAMPLING_PERIOD * 1000))
        WINDOW.show()
        APP.exec()
        APP.quit()


if __name__ == "__main__":
    main()
