# Development Diary – August 10, 2026

# Raspberry Pi 5 — Initial Headless Network Configuration

## 1. Initial boot

The Raspberry Pi 5 was prepared with Raspberry Pi OS on a microSD card and powered on.

On initial power-up:

- The Raspberry Pi showed a **solid red LED**, indicating that power was being supplied.
- After pressing the Pi 5's power button, the activity LED began **rapidly flashing green**, indicating activity on the microSD card and that the system was attempting to boot.
- The Pi successfully booted Raspberry Pi OS.

At this point, however, the Raspberry Pi had no credentials for the local Wi-Fi network and therefore could not connect to it.

---

# 2. Connecting the Pi using Ethernet

Rather than re-image the microSD card to provide Wi-Fi credentials, an Ethernet connection was used for initial configuration.

The Raspberry Pi was connected directly to the Cogeco modem/router using Ethernet.

(The Windows computer was already connected to the same LAN.)

The following command was used from Windows PowerShell to attempt hostname discovery:

```powershell
ping raspberrypi.local
```

This failed:

```text
Ping request could not find host raspberrypi.local.
```

This was not necessarily evidence that the Pi had failed to boot. It only indicated that the hostname could not be resolved from Windows.

---

# 3. Finding the Raspberry Pi through the router

The Cogeco router's administration interface was opened at:

```text
192.168.0.1
```

The router's connected-device list showed the Raspberry Pi.

The Pi appeared as:

```text
Photogrammetry-Device
```

with Ethernet IP:

```text
192.168.0.129
```

The router showed it as connected over Ethernet at:

```text
1000 Mbps
```

This confirmed that:

- Raspberry Pi OS had booted successfully.
- Ethernet was operational.
- DHCP was operational.
- The router had assigned the Pi an IP address.
- Gigabit Ethernet had successfully negotiated.
- The configured hostname was `Photogrammetry-Device`.

---

# 4. SSH connection over Ethernet

The Raspberry Pi was accessed from Windows using SSH.

The connection was made using:

```powershell
ssh bfalco@192.168.0.129
```

After authentication, the shell prompt was:

```text
bfalco@Photogrammetry-Device:~ $
```

At this point the Raspberry Pi could be administered completely headlessly over Ethernet. This will be useful for development

---

# 5. Examining the Pi's network interfaces

From the Raspberry Pi SSH session, NetworkManager's device status was checked:

```bash
nmcli device status
```

The output was:

```text
DEVICE         TYPE      STATE                   CONNECTION
eth0           ethernet  connected               netplan-eth0
lo             loopback  connected (externally)  lo
wlan0          wifi      disconnected            --
p2p-dev-wlan0  wifi-p2p  disconnected            --
```

This confirmed:

- `eth0` was connected.
- `wlan0` was available and recognized.
- The Wi-Fi adapter was not yet connected to a network.

---

# 6. Scanning for Wi-Fi networks

Nearby Wi-Fi networks were scanned using:

```bash
nmcli device wifi list
```

The two relevant networks were:

```text
COGECO-EDB2-2.4G
COGECO-EDB2
```

The 2.4 GHz network showed approximately:

```text
195 Mbit/s
100% signal
```

while `COGECO-EDB2` showed approximately:

```text
540 Mbit/s
99% signal
```

`COGECO-EDB2` was therefore selected for the Pi's normal home Wi-Fi connection.

---

# 8. Connecting the Pi to home Wi-Fi

An initial attempt was made without elevated privileges:

```bash
nmcli device wifi connect "COGECO-EDB2" --ask
```

This returned:

```text
Error: Failed to add/activate new connection: Not authorized to control networking.
```

The command was therefore rerun with `sudo`:

```bash
sudo nmcli device wifi connect "COGECO-EDB2" --ask
```

NetworkManager requested the WPA2 password:

```text
Password (802-11-wireless-security.psk):
```

The Wi-Fi password was entered interactively and was **not exposed in the command or documentation**.

NetworkManager then reported:

```text
Device 'wlan0' successfully activated with 'eff99ffb-3c16-43d7-84fb-b35d61027962'.
```

The Pi was now connected simultaneously through:

- Ethernet
- Wi-Fi

---

# 9. Determining the Pi's Wi-Fi IP address

The IPv4 configuration of the Wi-Fi interface was inspected:

```bash
ip -4 addr show wlan0
```

The relevant output was:

```text
3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    inet 192.168.0.130/24 brd 192.168.0.255 scope global dynamic noprefixroute wlan0
```

Therefore:

**Ethernet IP:**

```text
192.168.0.129
```

**Wi-Fi IP:**

```text
192.168.0.130
```

The Wi-Fi address was dynamically assigned through DHCP.

SSH connectivity over Wi-Fi could therefore be performed using:

```powershell
ssh bfalco@192.168.0.130
```

---

# 10. Creating a standalone Raspberry Pi Wi-Fi hotspot

A second Wi-Fi configuration was created for field operation.

The goal was to allow a laptop to connect **directly to the Raspberry Pi without requiring a router, Internet connection, or existing Wi-Fi infrastructure**.

The intended topology is:

```text
Laptop
   │
   │ Wi-Fi
   ▼
Raspberry Pi 5
   │
   ├── Cameras
   ├── Sensors
   └── Other capture hardware
```

A new NetworkManager connection profile was created:

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name "Photogrammetry-Hotspot" autoconnect no ssid "Photogrammetry-Device"
```

The profile was configured to operate as a Wi-Fi access point:

```bash
sudo nmcli connection modify "Photogrammetry-Hotspot" 802-11-wireless.mode ap
```

It was configured to use the 2.4 GHz band:

```bash
sudo nmcli connection modify "Photogrammetry-Hotspot" 802-11-wireless.band bg
```

2.4 GHz was selected because field use benefits from range and obstacle penetration more than maximum Wi-Fi throughput.

NetworkManager's shared IPv4 mode was enabled:

```bash
sudo nmcli connection modify "Photogrammetry-Hotspot" ipv4.method shared ipv6.method disabled
```

WPA-PSK security was enabled:

```bash
sudo nmcli connection modify "Photogrammetry-Hotspot" wifi-sec.key-mgmt wpa-psk
```

The hotspot password was then configured:

```bash
sudo nmcli connection modify "Photogrammetry-Hotspot" wifi-sec.psk "YOUR-HOTSPOT-PASSWORD"
```

`YOUR-HOTSPOT-PASSWORD` represents the actual password and should **not** be replaced with the real password in public/project documentation.

---

# 11. Inspecting NetworkManager connection profiles

The available connection profiles were displayed using:

```bash
nmcli connection show
```

At one stage, the following profiles existed:

```text
NAME                                 TYPE
netplan-eth0                         ethernet
COGECO-EDB2                          wifi
lo                                   loopback
netplan-wlan0-Photogrammetry-Device  wifi
Photogrammetry-Hotspot               wifi
```

There was an old `netplan-wlan0-Photogrammetry-Device` Wi-Fi profile in addition to the newly created hotspot profile.

To simplify the configuration, the old profile was deleted.

The intended remaining configuration was:

```text
netplan-eth0
COGECO-EDB2
lo
Photogrammetry-Hotspot
```

Thus there are now two intentional Wi-Fi profiles:

**`COGECO-EDB2`**

Normal Wi-Fi client mode. The Raspberry Pi connects to the existing home network.

**`Photogrammetry-Hotspot`**

Access-point mode. The Raspberry Pi creates its own network for direct field access.

---

# 12. Testing the hotspot

The hotspot was manually activated using:

```bash
sudo nmcli connection up "Photogrammetry-Hotspot"
```

Because the Raspberry Pi has one `wlan0` interface, activating the hotspot causes that interface to stop acting as a client of `COGECO-EDB2` and instead operate as an access point.

The saved `COGECO-EDB2` configuration is **not deleted or overwritten**.

The Windows computer detected a new wireless network:

```text
Photogrammetry-Device
```

The laptop successfully connected to this network using the configured WPA password.

---

# 13. Connecting directly to the Pi through its hotspot

NetworkManager's shared networking configuration assigned the Raspberry Pi the hotspot-side address:

```text
10.42.0.1
```

Connectivity could be tested from Windows using:

```powershell
ping 10.42.0.1
```

SSH was then tested directly through the Pi's hotspot:

```powershell
ssh bfalco@10.42.0.1
```

Authentication succeeded!

This confirms that the Raspberry Pi can be operated completely independently of the home network. Important for field work in a cave with no wifi!

The resulting field connection is:

```text
Windows Laptop
      │
      │  Photogrammetry-Device Wi-Fi
      │
      ▼
  10.42.0.1
Raspberry Pi 5
```

No router or Internet connection is required.

---

# 14. Switching back to home Wi-Fi

The saved home Wi-Fi profile can be manually restored with:

```bash
sudo nmcli connection up "COGECO-EDB2"
```

Likewise, field hotspot mode can manually be enabled with:

```bash
sudo nmcli connection up "Photogrammetry-Hotspot"
```

So the two manual modes are currently:

```bash
sudo nmcli connection up "COGECO-EDB2"
```

for **home/client mode**, and:

```bash
sudo nmcli connection up "Photogrammetry-Hotspot"
```

for **field/access-point mode**.

---

# Current Network Configuration

At this stage, the Raspberry Pi has successfully demonstrated **three methods of remote access**:

| Mode | Pi address | Purpose |
|---|---|---|
| Ethernet | `192.168.0.129` | Wired LAN / configuration |
| Home Wi-Fi | `192.168.0.130` | Normal home-network access |
| Pi Hotspot | `10.42.0.1` | Direct field connection |

The `.129` and `.130` addresses are DHCP-assigned and therefore **should not be assumed to remain permanent**. The hotspot address `10.42.0.1` is the important predictable address for direct field operation under the current NetworkManager shared-mode setup.

## Current milestone

I have successfully established:

**Pi boots → Ethernet works → SSH works → Wi-Fi works → standalone hotspot works → SSH over standalone hotspot works.**

The **next step has not been implemented yet**.

I still need to configure the automatic fallback behaviour:

```text
BOOT
 │
 ▼
Is a known Wi-Fi network available?
 │
 ├── YES ──► Connect to known Wi-Fi
 │
 │
 └── NO ───► Start Photogrammetry-Device hotspot
                  │
                  ▼
          Laptop connects directly
                  │
                  ▼
              SSH / Web UI
```