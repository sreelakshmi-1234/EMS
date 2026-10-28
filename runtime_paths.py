"""Central paths for files stored in the backend data directory."""

from pathlib import Path


class DataPaths:
    _ROOT = Path(__file__).resolve().parent / "ems_backend_data" / "ems_backend_data"

    @classmethod
    def resolve(cls, path):
        return cls._ROOT / path

    @classmethod
    def define(cls, path):
        return cls.resolve(path)
