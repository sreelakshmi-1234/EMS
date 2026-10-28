import json
from pathlib import Path


class DeviceLibraryResolver:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parents[3] / "ems_backend_data" / "ems_backend_data" / "device_library")

    def get_mapping(self, device_type, make, model):
        folder = self.base_dir / device_type / make
        for name in (model, model.lower()):
            file_path = folder / f"{name}.json"
            if file_path.is_file():
                return json.loads(file_path.read_text(encoding="utf-8"))

        raise FileNotFoundError(f"No mapping for {device_type}/{make}/{model}")

    @staticmethod
    def build(register_mapping, max_regs, register_base=None):
        if register_base is None:
            register_base = DeviceLibraryResolver._infer_register_base(register_mapping)
        if register_base not in (0, 1):
            raise ValueError(f"register_base must be 0 or 1, got {register_base}")

        registers_by_function = {}
        for mapping in register_mapping.values():
            function_code = int(mapping.get("fc", 3))
            register = int(mapping.get("register", mapping.get("srno", 0)))
            registers_by_function.setdefault(function_code, []).append((register, mapping))

        read_plan = {}
        for function_code, registers in registers_by_function.items():
            ranges = []
            max_count = max_regs.get(function_code)
            for register, mapping in sorted(registers):
                size = 2 if mapping.get("dataType") in ("int32", "float", "float32") else 1
                # start a new range if there are no ranges yet, or if the current register is not contiguous with the last range, or if the last range exceeds the max_count
                if not ranges or (
                    max_count is not None
                    and ranges[-1]["count"]
                    and register + size - ranges[-1]["start"] > max_count
                ):
                    ranges.append({"start": register, "count": 0, "mapping": {}})
                # handles the case where the register is not contiguous with the last range
                current = ranges[-1]
                if register > current["start"] + current["count"]:
                    current = {"start": register, "count": 0, "mapping": {}}
                    ranges.append(current)
                current["count"] = max(current["count"], register + size - current["start"])
                current["mapping"][str(register)] = {**mapping, "srno": register - current["start"]}

            read_plan[function_code] = [
                {**read_range, "start": read_range["start"] - register_base}
                for read_range in ranges
            ]

        return read_plan

    @staticmethod
    def _infer_register_base(register_mapping):
        """Infer the library's display-address convention when metadata is absent."""
        registers = [
            int(mapping.get("register", mapping.get("srno", 0)))
            for mapping in register_mapping.values()
        ]
        if not registers:
            return 0

        # Libraries use display addresses (for example 30100/40100), while
        # Modbus requests use zero-based offsets.  srno is the zero-based
        # position within the read range, so any positive first register with
        # srno 0 is also a one-based display map.
        first_register = min(registers)
        first_mapping = next(
            mapping
            for mapping in register_mapping.values()
            if int(mapping.get("register", mapping.get("srno", 0))) == first_register
        )
        if first_register > 0 and int(first_mapping.get("srno", 0)) == 0:
            return 1
        return 0