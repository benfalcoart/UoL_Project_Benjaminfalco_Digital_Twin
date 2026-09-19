"""
Testing the custom battery driver.
"""

from API.hardware.ina219 import INA219

monitor = INA219()

reading = monitor.read_battery()

print(f"Voltage:    {reading.voltage:.3f} V")
print(f"Current:    {reading.current:.4f} A")
print(f"Power:      {reading.power:.3f} W")
print(f"Percentage: {reading.percentage:.1f}%")