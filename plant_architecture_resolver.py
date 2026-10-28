import json
# from pathlib import Path
import logging

from runtime_paths import DataPaths

logger = logging.getLogger(__name__)

class PlantArchitectureResolver:
    def __init__(self, base_dir="plant_architecture"):
        """
        Initialize the resolver with the base directory of the plant architecture.
        """
        self.base_dir = DataPaths.define(base_dir)
        if not self.base_dir.exists():
            raise FileNotFoundError(f"Base directory '{base_dir}' does not exist.")

    def _find_device_file(self, device_id):
        """
        Search for a device file named {device_id}.json in the base directory and its subdirectories.
        :param device_id: The device ID (e.g., 'block_1_inverter_inverter_1').
        :return: The Path object of the found file.
        :raises FileNotFoundError: If no file matching the device ID is found.
        """
        # Recursively search for the file
        matches = list(self.base_dir.rglob(f"{device_id}.json"))
        if not matches:
            raise FileNotFoundError(f"No device file found for device ID: {device_id}")
        elif len(matches) > 1:
            raise ValueError(f"Multiple files found for device ID: {device_id}")
        return matches[0]

    def _get_device_file_path(self, device_id):
        """
        Get the expected path for a device file without requiring it to exist.
        Creates parent directories if needed.
        :param device_id: The device ID (e.g., 'block_1_inverter_inverter_1').
        :return: The Path object where the file should be.
        """
        # Determine expected structured path from device_id
        parts = device_id.split('_')
        expected_dir = self.base_dir

        for i, part in enumerate(parts):
            if part in ('block', 'pcs') and i + 1 < len(parts):
                subsystem = f"{part}_{parts[i+1]}"
                if part == 'block':
                    expected_dir = self.base_dir / subsystem / "prev_inverter"
                elif part == 'pcs' and i + 2 < len(parts):
                    if i + 3 < len(parts) and parts[i+2] == 'pcs' and parts[i+3] == 'controller':
                        component = "pcs_controller"
                    else:
                        component = parts[i+2]
                    expected_dir = self.base_dir / "plant" / subsystem / component
                break
        
        expected_path = expected_dir / f"{device_id}.json"
        
        # Return existing file if at expected location
        if expected_path.exists():
            return expected_path
        
        # Search for existing file and move to expected location
        matches = list(self.base_dir.rglob(f"{device_id}.json"))
        if matches:
            existing = matches[0]
            expected_dir.mkdir(parents=True, exist_ok=True)
            existing.rename(expected_path)
            return expected_path
        
        # Create new file at expected location
        expected_dir.mkdir(parents=True, exist_ok=True)
        return expected_path
    
    def find_devices_by_type(self, device_type):
        """
        Search for all device files containing {device_type}.json in base directory and subdirectories.
        :param device_type: The type of device (e.g., 'inverter').
        :return: List of Path objects matching the device type.
        """
        matches = list(self.base_dir.rglob(f"*{device_type}*.json"))
        if not matches:
            raise FileNotFoundError(f"No files found for device type: {device_type}")
        return matches
    
    def get_device_id_meter_file_name(self, device_id):
        """
        Search for a device file named {device_id}.json in the base directory and its subdirectories.
        :param device_id: The device ID (e.g., 'block_1_inverter_inverter_1').
        :return: The Path object of the found file.
        :raises FileNotFoundError: If no file matching the device ID is found.
        """
        # Recursively search for the file
        matches = list(self.base_dir.rglob(f"{device_id}.json"))
        if not matches:
            raise FileNotFoundError(f"No device file found for device ID: {device_id}")
        elif len(matches) > 1:
            raise ValueError(f"Multiple files found for device ID: {device_id}")
        return str(matches[0]).split('\\')[-4]

    async def resolve_block_device(self, device_id):
        """
        Resolve a specific device file by searching for {device_id}.json.
        :param device_id: The device ID (e.g., 'block_1_inverter_inverter_1').
        :return: A dictionary representing the device's data.
        """
        device_file = self._find_device_file(device_id)

        if not device_file.exists():
            raise FileNotFoundError(f"Device file not found: {device_file}")

        with open(device_file, 'r') as f:
            return json.load(f)
        
    def resolve_block_device_sync(self, device_id):
        """
        Resolve a specific device file by searching for {device_id}.json.
        :param device_id: The device ID (e.g., 'block_1_inverter_inverter_1').
        :return: A dictionary representing the device's data.
        """
        device_file = self._find_device_file(device_id)

        if not device_file.exists():
            raise FileNotFoundError(f"Device file not found: {device_file}")

        with open(device_file, 'r') as f:
            return json.load(f)

    async def update_block_device(self, device_id, updates):
        """
        Update a specific device file by searching for {device_id}.json.
        :param device_id: The device ID (e.g., 'block_1_inverter_inverter_1').
        :param updates: A dictionary of updates to apply to the device file.
        """
        device_file = self._get_device_file_path(device_id)

        if not device_file.exists():
            data = {}
        else:
            with open(device_file, 'r') as f:
                data = json.load(f)

        # Apply updates while preserving existing metadata
        for tag, tag_updates in updates.items():
            if tag in data:
                # Preserve existing metadata and only update specified keys
                data[tag].update(tag_updates)
            else:
                # If the tag doesn't exist, add it as a new entry
                data[tag] = tag_updates

        # Write updated data back to the file
        with open(device_file, 'w') as f:
            json.dump(data, f, indent=2)

        # logger.info(f"Updated block device: {device_file}")

    async def update_block_devices(self, batch):
        """Apply one resolution-sampling batch to its device JSON files."""
        for device_id, row in batch:
            timestamp = row.get("time_stamp")
            updates = {
                tag: {"value": value, "Time_Stamp": timestamp}
                for tag, value in row.items()
                if tag not in {"time_stamp", "app_status"}
            }
            await self.update_block_device(device_id, updates)

    async def resolve_alarm(self, alarm_key=None):
        """
        Resolve the centralized alarms file.
        :param alarm_key: Optional. If provided, resolve a specific alarm entry.
        :return: A dictionary representing the alarms' data.
        """
        alarm_file = self.base_dir / "alarms" / "alarms.json"

        if not alarm_file.exists():
            raise FileNotFoundError(f"Alarm file not found: {alarm_file}")

        with open(alarm_file, 'r') as f:
            alarms = json.load(f)

        if alarm_key:
            return alarms.get(alarm_key, None)
        return alarms

    async def update_alarm(self, alarm_key, updates):
        """
        Update a specific alarm entry in the centralized alarms file.
        :param alarm_key: The key of the alarm to update (e.g., 'block_1_inverter_inverter_2_Temperature_C').
        :param updates: A dictionary of updates to apply to the alarm entry.
        """
        alarm_file = self.base_dir / "alarms" / "alarms.json"

        alarm_file.parent.mkdir(parents=True, exist_ok=True)
        if not alarm_file.exists():
            alarms = {}
        else:
            with open(alarm_file, 'r') as f:
                alarms = json.load(f)

        # Check if the alarm key exists
        if alarm_key not in alarms:
            raise KeyError(f"Alarm key '{alarm_key}' not found in alarms file.")

        # Update the specific alarm entry while preserving existing metadata
        alarms[alarm_key]['info'].update(updates)

        # Write updated data back to the file
        with open(alarm_file, 'w') as f:
            json.dump(alarms, f, indent=2)

        # logger.info(f"Updated alarm entry: {alarm_key}")

    async def resolve_computed_device(self, device_id):
        """
        Resolve a computed device file (e.g., plant_device.json or plant_alarm.json).
        :param device_id: The computed device ID (e.g., 'plant_device', 'plant_alarm').
        :return: A dictionary representing the computed device's data.
        """
        computed_file = self.base_dir / f"{device_id}.json"

        if not computed_file.exists():
            raise FileNotFoundError(f"Computed device file not found: {computed_file}")

        with open(computed_file, 'r') as f:
            return json.load(f)

    async def update_computed_device(self, device_id, updates):
        """
        Update a computed device file (e.g., plant_device.json or plant_alarm.json).
        :param device_id: The computed device ID (e.g., 'plant_device', 'plant_alarm').
        :param updates: A dictionary of updates to apply to the computed device file.
        """
        computed_file = self.base_dir / f"{device_id}.json"

        computed_file.parent.mkdir(parents=True, exist_ok=True)
        if not computed_file.exists():
            data = {}
        else:
            with open(computed_file, 'r') as f:
                data = json.load(f)

        # Apply updates while preserving existing metadata
        for tag, tag_updates in updates.items():
            if tag in data:
                # Preserve existing metadata and only update specified keys
                data[tag].update(tag_updates)
            else:
                # If the tag doesn't exist, add it as a new entry
                data[tag] = tag_updates

        # Write updated data back to the file
        with open(computed_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Updated computed device: {computed_file}")

    def update_computed_device_sync(self, device_id, updates):
        """
        Update a computed device file (e.g., plant_device.json or plant_alarm.json).
        :param device_id: The computed device ID (e.g., 'plant_device', 'plant_alarm').
        :param updates: A dictionary of updates to apply to the computed device file.
        """
        computed_file = self.base_dir / f"{device_id}.json"

        computed_file.parent.mkdir(parents=True, exist_ok=True)
        if not computed_file.exists():
            data = {}
        else:
            with open(computed_file, 'r') as f:
                data = json.load(f)

        # Apply updates while preserving existing metadata
        for tag, tag_updates in updates.items():
            if tag in data:
                # Preserve existing metadata and only update specified keys
                data[tag].update(tag_updates)
            else:
                # If the tag doesn't exist, add it as a new entry
                data[tag] = tag_updates

        # Write updated data back to the file
        with open(computed_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Updated computed device: {computed_file}")
