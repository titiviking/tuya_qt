# Tuya S6 (qt) Cloud — Home Assistant Integration

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5.svg)](https://www.home-assistant.io/)
[![IoT Class](https://img.shields.io/badge/IoT%20Class-cloud__polling-555)](#compatibility)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Control the **S6 Home Alarm** (Tuya category `qt`, e.g., **ES-S6M-121**) from Home Assistant using the Tuya Cloud.  
Provides a native **Alarm Control Panel** (Disarm / Arm Away / Arm Home) and exposes key settings and diagnostics.

> **No credentials are stored in this repository.** You enter your own Access ID/Secret and Device ID in Home Assistant’s UI.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
  - [HACS (Custom Repository)](#hacs-custom-repository)
  - [Manual](#manual)
- [Configuration (UI)](#configuration-ui)
- [Entities](#entities)
- [Logging](#logging)
- [Troubleshooting](#troubleshooting)
- [Privacy & Security](#privacy--security)
- [Compatibility](#compatibility)
- [Known Limitations](#known-limitations)
- [Support / Contributing](#support--contributing)
- [License](#license)

---

## Features

- **Alarm Control Panel**
  - Disarm, Arm Away, Arm Home
  - Uses new HA enum API (`alarm_state`) for HA 2025.11+ compliance
  - No PIN required by default (can be enabled in code)

- **Controls & Settings (entities)**
  - Mode: `system_arm_type`
  - Language: `language` (select)
  - Delays & durations: `arm_delay`, `alarm_delay`, `alarm_sound_duration`, `ring_times`, `tel_alarm_cycle`
  - Toggles: `inside_siren_sound`, `gsm_en`, `tel_ctrl_en`, `arm_sms_en`, `disarm_sms_en`,
    `keyboard_tone_en`, `arm_delay_tone_en`, `alarm_delay_tone_en`, `arm_disarm_tone_en`,
    `inside_siren_en`, `wireless_siren_en`
  - Diagnostics (read-only): `bat_status`, `dc_status`, `gsm_status`, `device_info`, `alarm_msg`, `history_msg`, `sub_device`, etc.

- **Fast, stable state updates**
  - After any arm/disarm, the integration performs a short verify-after-command loop against the cloud for accurate UI (prevents “flip-flop” states).

---

## Requirements

1. **Tuya IoT Platform** project (Cloud → Development)
   - Note your **Access ID** and **Access Secret**.
2. **Link your Tuya App account** to the project  
   (Cloud → Development → your project → **Link Tuya App Account**)  
   Your S6 must appear in the project’s device list.
3. **Authorize APIs** to the project (names may vary slightly)
   - **Device Status**, **Device Control**, **Device Management**
4. **Device ID** of your S6 alarm (from the Tuya console).

> Tip: Keep the **IP allowlist OFF** during initial setup. You can restrict later if desired.

---

## Installation

### Manual

1. Copy the folder to: `config/custom_components/tuya_qt/`
2. Restart Home Assistant.

> Ensure the domain/folder match: `custom_components/tuya_qt/` and `manifest.json` contains `"domain": "tuya_qt"`.

---

## Configuration (UI)

**Settings → Devices & Services → Add Integration → “Tuya S6 (qt) Cloud”**

Enter:
- **Region**: `auto` (recommended) or `eu`, `us`, `in`, `cn`
- **Access ID** and **Access Secret**: from your Tuya project
- **Device ID**: your S6 alarm’s device ID
- **Poll Interval (s)**: default `30`

> The integration auto-detects Tuya’s current **signature scheme** (with/without `nonce`) and will find the correct **data center** when Region = `auto`.

---

## Entities

- **Alarm Control Panel**: `alarm_control_panel.<name>_alarm`
- Numbers, Switches, Selects, and Sensors that mirror the S6’s functions and status DPs.

No YAML is required.

---

## Logging

Enable debug logs if you need to troubleshoot:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.tuya_qt: debug
```

Restart HA and check **Settings → System → Logs** (or container logs).

---

## Troubleshooting

**“Could not connect / sign invalid (1004)”**  
- Recheck **Access Secret** (no leading/trailing spaces).  
- Use **Region = `auto`** to let the integration discover the right data center.  


**“No entities” but login succeeded**  
- Confirm your S6 is visible under the **linked app account** in the project.  
- Ensure **Device Status** and **Device Control** are authorized for the project.  
- Enable debug logging and check the `/functions` and `/status` calls.

**UI asks for a PIN**  
- This integration disables PIN prompts by default: `code_format = None` and `_attr_code_arm_required = False`.  
  If you want to require a code, enable it in the alarm entity and add validation (optionally mapped to the device’s `password` DP).

**Slow/flip-flop state after arm/disarm**  
- The integration performs a **verify-after-command** loop and freezes scheduled polls while verifying, then publishes once the cloud confirms (or after a short timeout).

---

## Privacy & Security

- Your **Access ID/Secret** and **Device ID** are entered only in Home Assistant’s UI and stored in HA’s config storage.  
- The integration signs requests using Tuya’s **New Signature** scheme (includes `stringToSign`/`Content-SHA256`; supports `nonce` when required).

---

## Compatibility

- Home Assistant **2025.10+** (tested)  
- Uses `AlarmControlPanelState` enum to satisfy HA **2025.11** deprecations  
- **IoT Class:** `cloud_polling`

---

## Known Limitations

- The S6 exposes `disarmed`, `armed` (away), and `home` only (no night/custom).  
- Some raw DPs (`tel_num`, `sub_device`, `history_msg`, etc.) are read-only diagnostics.

---

## Support / Contributing

- Open issues and PRs on this repository.  
- When reporting issues, include relevant debug logs (redact any personal tokens if shown).

Consistency tip:
- `manifest.json`: `"domain": "tuya_qt"`  
- `logger` namespace: `custom_components.tuya_qt`

---

## License

This project is licensed under the [MIT License](LICENSE).
