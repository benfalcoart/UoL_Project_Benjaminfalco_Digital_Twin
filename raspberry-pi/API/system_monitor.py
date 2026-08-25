from pathlib import Path
from datetime import datetime
import shutil

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

#Counts detected Linux video device nodes. This may not correspond one-to-one with physical cameras.
def get_camera_count():
    return len(list(Path("/dev").glob("video*")))


def get_timestamp():
    return datetime.now().isoformat()

#TODO: stubs: Some of these may not be needed but might be good to know for debugging hardware.
def get_battery_percentage():
    ...

def get_battery_voltage():
    ...

def get_battery_current():
    ...

def get_battery_power():
    ...