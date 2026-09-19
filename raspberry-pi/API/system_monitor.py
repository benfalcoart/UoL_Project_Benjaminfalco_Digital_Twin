from pathlib import Path
from datetime import datetime
import shutil
from API.hardware.ina219 import INA219, BatteryReading
from API.camera_manager import CameraManager

try:
    battery_monitor = INA219()
except OSError:
    battery_monitor = None

cameera_manager = CameraManager()

#TODO: Most of these functions are stubs. They need to be integrated with Pi and Hardware and tested.

#temperature of Pi. good for monitoring it while in the field.
def get_cpu_temperature():
    raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text()
    return round(int(raw) / 1000, 1)

#Returns the available storage on the Pi filesystem in gigabytes. 
#Useful to know if its filling up so Pi can be disengaged and emptied.
def get_storage_free_gb():
    total, used, free = shutil.disk_usage("/")
    return round(free / (1024 ** 3), 2)

#Counts detected Linux video devices from the Camera Manager
def get_camera_count() -> int:
    return cameera_manager.get_number_cameras()


def get_timestamp():
    return datetime.now().isoformat()

def get_battery_status() -> BatteryReading | None:
    #Check if we have a Battery Monitor.
    if battery_monitor is None:
        return None

    try:
        return battery_monitor.read_battery()
    except OSError:
        return None

def get_battery_percentage() -> float:
    return get_battery_status().percentage

def get_battery_voltage() -> float:
    return get_battery_status().voltage

def get_battery_current() -> float:
    return get_battery_status().current

def get_battery_power() -> float:
    return get_battery_status().power