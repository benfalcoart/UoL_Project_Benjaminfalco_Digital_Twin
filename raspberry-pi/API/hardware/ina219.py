"""This driver script interacts with the WaveHat battery module installed on the pi to get battery info.
This is based off of the Offical WaveHat driver python script to detect/estimate battery life"""
from dataclasses import dataclass
import smbus


_REG_CONFIG = 0x00
_REG_SHUNTVOLTAGE = 0x01
_REG_BUSVOLTAGE = 0x02
_REG_POWER = 0x03
_REG_CURRENT = 0x04
_REG_CALIBRATION = 0x05


@dataclass
class BatteryReading:
    voltage: float
    current: float
    power: float
    percentage: float


class INA219:
    def __init__(self, i2c_bus: int = 1, address: int = 0x42):
        self.bus = smbus.SMBus(i2c_bus)
        self.address = address

        self._calibration_value = 4096
        self._current_lsb = 0.1
        self._power_lsb = 0.002

        self._configure()

    def _read_register(self, register: int) -> int:
        data = self.bus.read_i2c_block_data(
            self.address,
            register,
            2
        )

        return (data[0] << 8) | data[1]

    def _write_register(self, register: int, value: int):
        data = [
            (value >> 8) & 0xFF,
            value & 0xFF
        ]

        self.bus.write_i2c_block_data(
            self.address,
            register,
            data
        )

    def _configure(self):
        self._write_register(
            _REG_CALIBRATION,
            self._calibration_value
        )

        bus_voltage_range = 0x01
        gain = 0x03
        bus_adc_resolution = 0x0D
        shunt_adc_resolution = 0x0D
        mode = 0x07

        config = (
            bus_voltage_range << 13
            | gain << 11
            | bus_adc_resolution << 7
            | shunt_adc_resolution << 3
            | mode
        )

        self._write_register(_REG_CONFIG, config)

    def get_voltage(self) -> float:
        value = self._read_register(_REG_BUSVOLTAGE)
        return (value >> 3) * 0.004

    def get_current(self) -> float:
        value = self._read_register(_REG_CURRENT)

        if value > 32767:
            value -= 65535

        current_ma = value * self._current_lsb
        return current_ma / 1000

    def get_power(self) -> float:
        self._write_register(
            _REG_CALIBRATION,
            self._calibration_value
        )

        value = self._read_register(_REG_POWER)

        if value > 32767:
            value -= 65535

        return value * self._power_lsb

    def get_percentage(self, voltage: float) -> float:
        percentage = (voltage - 6.0) / 2.4 * 100
        return max(0.0, min(100.0, percentage))

    def read_battery(self) -> BatteryReading:
        voltage = self.get_voltage()
        current = self.get_current()
        power = self.get_power()
        percentage = self.get_percentage(voltage)

        return BatteryReading(
            voltage=round(voltage, 3),
            current=round(current, 4),
            power=round(power, 3),
            percentage=round(percentage, 1)
        )