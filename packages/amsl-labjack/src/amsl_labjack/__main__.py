"""AMSL LabJack CLI."""

from time import sleep

import dwfpy as dwf


def main():
    with dwf.AnalogDiscovery2() as device:
        device.supplies.positive.setup(voltage=1.0)
        device.supplies.master_enable = True
        sleep(5)


if __name__ == "__main__":
    main()
