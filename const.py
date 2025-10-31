# const.py
DOMAIN = "tuya_qt"
PLATFORMS = ["alarm_control_panel", "switch", "number", "select", "sensor"]

TUYA_ENDPOINTS = {
    "eu": "https://openapi.tuyaeu.com",
    "us": "https://openapi.tuyaus.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
    # you can still pass a full https://... URL directly if you like
}

# order to probe when region='auto'
AUTO_REGIONS = ["eu", "us", "in", "cn"]

DEFAULT_POLL = 30

DP_SYSTEM_ARM = "system_arm_type"

S6_ALL_DPS = [
    "system_arm_type","gsm_status","language","dc_status","bat_status",
    "arm_delay","alarm_delay","alarm_sound_duration","ring_times","tel_alarm_cycle",
    "inside_siren_sound","gsm_en","tel_ctrl_en","arm_sms_en","disarm_sms_en",
    "keyboard_tone_en","arm_delay_tone_en","alarm_delay_tone_en","arm_disarm_tone_en",
    "inside_siren_en","wireless_siren_en","password","tel_num","device_info",
    "sub_device","alarm_msg","history_msg","cmd_ctrl",
]
