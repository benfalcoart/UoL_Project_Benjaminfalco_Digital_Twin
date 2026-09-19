from API import system_monitor


print(f"Timestamp:        {system_monitor.get_timestamp()}")
print(f"CPU temperature:  {system_monitor.get_cpu_temperature()} C")
print(f"Storage free:     {system_monitor.get_storage_free_gb()} GB")
print(f"Cameras detected: {system_monitor.get_detected_camera_count()}")
print(f"Cameras active:   {system_monitor.get_active_camera_count()}")

battery = system_monitor.get_battery_status()

if battery:
    print(f"Battery:          {battery.percentage}%")
    print(f"Voltage:          {battery.voltage} V")
    print(f"Current:          {battery.current} A")
    print(f"Power:            {battery.power} W")
else:
    print("Battery:          unavailable")