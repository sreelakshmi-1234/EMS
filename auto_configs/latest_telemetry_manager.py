import json
from datetime import datetime, timezone
from pathlib import Path


class LatestTelemetryManager:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else (
            Path(__file__).resolve().parents[1]
            / "ems_backend_data"
            / "ems_backend_data"
            / "latest_telemetry"
        )
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_device_data(self, device_id, mapped_values):
        if not device_id:
            raise ValueError("device_id is required to save latest telemetry")

        payload = {
            "time_stamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "data": mapped_values,
        }
        output_path = self.base_dir / f"{device_id}.json"
        temporary_path = output_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
