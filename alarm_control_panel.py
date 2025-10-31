from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,  # enum-based state (new API)
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DP_SYSTEM_ARM
from .coordinator import TuyaS6Coordinator


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the S6 alarm entity from a config entry."""
    coord: TuyaS6Coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([TuyaS6Alarm(coord)], update_before_add=True)


class TuyaS6Alarm(CoordinatorEntity[TuyaS6Coordinator], AlarmControlPanelEntity):
    """Alarm control panel for Tuya S6 (category 'qt')."""

    _attr_has_entity_name = True
    _attr_name = "Alarm"

    # Expose only arm modes device supports; disarm has no feature flag.
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )

    # Explicitly disable code requirement for arming/disarming (frontend will not ask a PIN).
    _attr_code_arm_required = False

    def __init__(self, coordinator: TuyaS6Coordinator) -> None:
        super().__init__(coordinator)
        self._device_id = coordinator.device_id
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_alarm"

    # ---------- HA metadata ----------

    @property
    def available(self) -> bool:
        """Follow coordinator availability."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Stable device metadata; do not assume extra attrs on coordinator."""
        manufacturer: Optional[str] = getattr(self.coordinator, "manufacturer", "Tuya")
        model: Optional[str] = getattr(self.coordinator, "model", "S6 (qt)")
        sw_version: Optional[str] = getattr(self.coordinator, "sw_version", None)
        name: Optional[str] = getattr(self.coordinator, "name", "Tuya S6 Home Alarm")

        info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=manufacturer,
            model=model,
            name=name,
        )
        if sw_version:
            info["sw_version"] = sw_version  # type: ignore[index]
        return info

    # ---------- Code / PIN behavior ----------

    @property
    def code_format(self) -> None:
        """Return None to indicate no code is required."""
        return None  # no PIN required for arm/disarm

    # ---------- State mapping (new API with enum) ----------

    def _dp_state(self) -> Optional[str]:
        """Internal: read current DP from coordinator.data safely."""
        data: dict[str, Any] = getattr(self.coordinator, "data", {}) or {}
        return data.get(DP_SYSTEM_ARM)

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """
        New API (enum). Map Tuya 'system_arm_type' → AlarmControlPanelState.
        Keeps compatibility with future HA versions.
        """
        dp = self._dp_state()
        if dp == "disarmed":
            return AlarmControlPanelState.DISARMED
        if dp == "armed":
            return AlarmControlPanelState.ARMED_AWAY
        if dp == "home":
            return AlarmControlPanelState.ARMED_HOME
        return None

    @property
    def state(self) -> str | None:
        """
        Back-compat for older frontends/automations.
        Mirrors alarm_state into the legacy string constants.
        """
        enum_state = self.alarm_state
        if enum_state is None:
            return None
        if enum_state is AlarmControlPanelState.DISARMED:
            return STATE_ALARM_DISARMED
        if enum_state is AlarmControlPanelState.ARMED_AWAY:
            return STATE_ALARM_ARMED_AWAY
        if enum_state is AlarmControlPanelState.ARMED_HOME:
            return STATE_ALARM_ARMED_HOME
        return None

    # ---------- Commands ----------

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._send("disarmed")

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        await self._send("home")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._send("armed")

    # ---------- Helper ----------

    async def _send(self, value: str) -> None:
        """Send system_arm_type command and verify against cloud."""
        await self.coordinator.async_send_commands(
            [{"code": DP_SYSTEM_ARM, "value": value}],
            verify={DP_SYSTEM_ARM: value},
            timeout_seconds=8.0,
            interval_seconds=0.8,
        )


