import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auto_configs.latest_telemetry_manager import LatestTelemetryManager


class Mapper:
    def __init__(self, sampling_manager, sse_broadcaster=None):
        self.sampling_manager = sampling_manager
        self.latest_telemetry_manager = LatestTelemetryManager()

    async def map_registers(self, registers, register_mapper, **context):
        save_latest = context.pop("save_latest", True)
        mapped_values = {}
        for mapping in register_mapper.values():
            offset = int(mapping.get("srno", 0))
            value = registers[offset] if offset < len(registers) else None
            if value is not None and mapping.get("dataType") == "int16" and value > 32767:
                value -= 65536
            scaling = mapping.get("scaling", 1) or 1
            if value is not None:
                value = value / scaling
            alias = mapping.get("alias", mapping.get("name", "unknown"))
            mapped_values[alias] = {
                **context,
                "alias": alias,
                "name": mapping.get("name", alias),
                "value": value,
                "type": mapping.get("type", "analog"),
                "unit": mapping.get("unit", ""),
                "dataType": mapping.get("dataType"),
                "register": mapping.get("register"),
                "alarmType": mapping.get("alarmType", "normal"),
                "severity": mapping.get("severity", "critical"),
                "isEvent": mapping.get("isEvent", False),
                "isNormalReverse": mapping.get("isNormalReverse", False),
            }

            if (
                mapping.get("type") == "alarm"
                and mapping.get("alarmType") == "bitwise"
            ):
                raw_value = registers[offset] if offset < len(registers) else 0
                mapped_values[alias]["bitMapAlarm"] = {
                    bit["alias"]: {
                        "value": (int(raw_value or 0) >> int(position)) & 1,
                        "severity": bit.get("severity", "info"),
                    }
                    for position, bit in mapping.get("bitMap", {}).items()
                }
        await self.sampling_manager.process_mapped_data(mapped_values)
        if save_latest:
            self.latest_telemetry_manager.save_device_data(
                context.get("device_id"),
                mapped_values,
            )
        return mapped_values
