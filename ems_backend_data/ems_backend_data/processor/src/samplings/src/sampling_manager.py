import json
from pathlib import Path
from datetime import datetime

from .event_sampling import EventSampling
from .resolution_sampling import ResolutionSampling
# from .ppp import ResolutionSampling
from .alarm_sampling import AlarmSampling

from .custom_alarm.engine import CustomAlarmEngine

import time
import logging

logger = logging.getLogger(__name__)

class SamplingManager:
    def __init__(self, tag_definitions_path=None):
        """
        Initialize the SamplingManager with tag-specific configurations.
        """

        # Use an absolute path if no path is provided
        samplings_dir = Path(__file__).resolve().parents[1]
        self.tag_definitions_path = (
            Path(tag_definitions_path)
            if tag_definitions_path is not None
            else samplings_dir / "tag_definitions"
        )
        self.tag_configs_cache = {}
        self.custom_alarm_json_path = samplings_dir / "alarm_configs" / "custom_alarms.json"
        self.sampling_strategies = {
            "resolution": ResolutionSampling(),
            "alarm": AlarmSampling(),
            "event": EventSampling(),
        }
        self.custom_alarm_engine = CustomAlarmEngine(
            AlarmSampling(), self.custom_alarm_json_path
        )

    def _load_tag_configs(self, device_type):
        """
        Load tag-specific configurations from JSON only once.
        """
        device_type = device_type.lower()

        if device_type in self.tag_configs_cache:
            return self.tag_configs_cache[device_type]

        try:
            config_file = self.tag_definitions_path / f"{device_type}.json"

            with open(config_file, "r") as f:
                config = json.load(f)

            self.tag_configs_cache[device_type] = config
            return config

        except Exception as e:
            logger.error(f"Error loading tag configurations for {device_type}: {e}")
            raise ValueError(f"Failed to load tag configurations for {device_type}")

    async def process_mapped_data(self, mapped_data):
        """
        Process mapped data based on tag configurations and log to TinyDB.
        """
        device_id = None
        device_type = None
        latest_values = {}

        for name, data in mapped_data.items():
            timestamp = data.get("timestamp") or time.time()
            device_id = data["device_id"]
            value = data["value"]  # Extract the mapped value (can be None)
            type = data["type"]
            alias = data["alias"] #tag
            dev_type = data.get("device_type") or data.get("deviceType") or ("bank" if "bank" in str(data.get("device_id", "")) else "inverter")
            self.tag_configs = self._load_tag_configs(dev_type)
            tag_config = self.tag_configs.get(alias)

            # For Custom Alarm purpose
            device_type = data.get("device_type") 
            latest_values[alias] = value

            if tag_config:
                if (type == "analog") or ("resolution" in tag_config and "aggregation" in tag_config and "change" not in tag_config):
                    if "resolution" in tag_config and "aggregation" in tag_config:
                        resolution = tag_config.get("resolution", 59)
                        aggregation = tag_config.get("aggregation", "avg")
                        await self.sampling_strategies["resolution"].add_data(
                            device_id=device_id,
                            tag=alias,
                            value=value,
                            timestamp=timestamp,
                            resolution=resolution,
                            aggregation=aggregation
                        )
                        
                elif (type == "alarm"):
                    change = tag_config.get("change", True)
                    resolution = tag_config.get("resolution", 60)
                    is_debounce = tag_config.get("is_debounce", False)
                    debounce_time = tag_config.get("debounce_time", 4)
                    alarmType = data.get("alarmType", "normal")   #normal, enum, bitwise
                    severity = data.get("severity", "critical")   # info, warning, critical
                    bitMapAlarm = data.get("bitMapAlarm", {})   # applicable for bitwise alarm only
                    isEvent = data.get("isEvent", False)
                    isNormalReverse = data.get("isNormalReverse", False) # applicable for normal alarm only, if True, then 0 is alarm and 1 is normal

                    if isEvent:
                        # print(f"Event Hitsss: alias: {alias}")
                        await self.sampling_strategies["event"].add_data(
                            device_id=device_id,
                            tag=alias,
                            value=value,
                            timestamp=timestamp,
                            change=change,
                            resolution=resolution,
                            alarmType=alarmType,
                            bitMapAlarm=bitMapAlarm,
                            severity=severity,
                            isNormalReverse=isNormalReverse
                        )
                    
                    else:
                        await self.sampling_strategies["alarm"].add_data(
                            device_id=device_id,
                            tag=alias,
                            value=value,
                            timestamp=timestamp,
                            change=change,
                            resolution=resolution,
                            alarmType=alarmType,
                            bitMapAlarm=bitMapAlarm,
                            severity=severity,
                            isNormalReverse=isNormalReverse,
                            is_debounce=is_debounce,
                            debounce_time=debounce_time
                        )

                    

                    # TinyDB alarm log
                    # time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    # row = {
                    #     "device_id": device_id,
                    #     "tag_name": alias,
                    #     "value": value,
                    #     "time_stamp": time_str,
                    #     "severity": "info",
                    #     "alarm_type": "ChangeAlarm" if change else "ResolutionAlarm"
                    # }
                    # insert_alarm(row)
                    # insert_alarm_tiny(device_id=device_id, row=row)
                    # await async_insert_alarm_tiny(device_id=device_id, row=row)
            # else:
            #     logger.info(f"No Tag Mapping Defined for device id [{device_id}] and key alias [{alias}] and name [{name} device type [{device_type}] config {self.tag_configs}")

        # For Custom Alarm Processing
        await self.custom_alarm_engine.process(
            device_id=device_id,
            device_type=device_type,
            latest_values=latest_values,
            timestamp=timestamp
        )
