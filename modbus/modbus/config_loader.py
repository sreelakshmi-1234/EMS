import json
from pathlib import Path


class ConfigLoader:
    def load_config(self, path):
        requested_path = Path(path)
        candidates = [
            Path.cwd() / requested_path,
            Path(__file__).resolve().parents[2] / "ems_backend_data" / "ems_backend_data" / requested_path,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return json.loads(candidate.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"Configuration file not found: {path}")