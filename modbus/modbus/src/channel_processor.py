import asyncio
import logging
from .device_reader import deviceReader
from ..device_library.resolver import DeviceLibraryResolver

logger = logging.getLogger(__name__)

class ChannelProcessor:
    def __init__(self, channel_id, devices, modbus_client_manager, sampling_manager, sse_broadcaster):
        self.channel_id = channel_id
        self.devices = devices
        self.modbus_client_manager = modbus_client_manager
        self.sampling_manager = sampling_manager
        self.sse_broadcaster = sse_broadcaster
        self.resolver = DeviceLibraryResolver()

        # Pre-build device runtime objects
        self._prepare_devices()

    # -----------------------------
    # Device preparation (ONCE)
    # -----------------------------
    def _prepare_devices(self):
        for device_config in self.devices:
            device_type = device_config["deviceType"]
            make = device_config["make"]
            model = device_config["model"]

            # Load device library
            register_mapping = self.resolver.get_mapping(
                device_type, make, model
            )

            # Build optimized read plan
            read_plan = DeviceLibraryResolver.build(
                register_mapping=register_mapping,
                max_regs={1: 2000, 2: 2000, 3: 125, 4: 125},
                register_base=device_config.get("register_base")
            )
            configured_function = device_config.get("function")
            if configured_function is not None:
                configured_function = int(configured_function)
                mapping_functions = set(read_plan)
                if mapping_functions != {configured_function}:
                    raise ValueError(
                        f"Device {device_config['device_id']} configures FC"
                        f"{configured_function}, but its mapping requires "
                        f"{sorted(mapping_functions)}"
                    )

            # Attach runtime objects
            # device_config["_mapping"] = register_mapping
            device_config["_read_plan"] = read_plan

            device_config["_reader"] = deviceReader(
                config=device_config,
                modbus_client_manager=self.modbus_client_manager,
                sampling_manager=self.sampling_manager,
                sse_broadcaster=self.sse_broadcaster
            )

            device_config["_reader"].channel_id = self.channel_id

            # logger.info(
            #     f"Prepared device {device_config['device_id']} "
            #     f"with read plan: {read_plan}"
            # )

    # -----------------------------
    # Channel polling loop
    # -----------------------------
    async def process_channel(self):
        logger.info(
            f"Channel {self.channel_id} started "
            f"with {len(self.devices)} devices"
        )

        await asyncio.gather(
            *(self._poll_device(device) for device in self.devices)
        )
            
    # -----------------------------
    # Poll a single device
    # -----------------------------
    async def _poll_device(self, device):
        reader = device["_reader"]
        read_plan = device["_read_plan"]

        for fc, ranges in read_plan.items():
            for r in ranges:
                try:
                    await reader.read_registers_with_retries(
                        start_address=r["start"],
                        count=r["count"],
                        functionCode=fc,
                        register_mapping=r["mapping"]
                    )
                except Exception as e:
                    logger.error(
                        f"Channel {self.channel_id} | "
                        f"Device {device['device_id']} | "
                        f"FC {fc} | Range {r} failed: {e}"
                    )

    # async def process_channel(self):
    #     logger.info(f"Channel {self.channel_id} started with {len(self.devices)} devices")

    #     for device_config in self.devices:
    #         device_type = device_config["deviceType"]
    #         make = device_config["make"]
    #         model = device_config["model"]
    #         functionCode = device_config["function"]

    #         register_mapping = self.resolver.get_mapping(device_type, make, model)
            
    #         reader = deviceReader(
    #             config=device_config,
    #             modbus_client_manager=self.modbus_client_manager,
    #             register_mapper=register_mapping,
    #             sampling_manager=self.sampling_manager,
    #             sse_broadcaster=self.sse_broadcaster,
    #             functionCode = functionCode
    #         )

    #         register_keys = [int(x) for x in list(register_mapping.keys())]
    #         start_address = min(register_keys)

    #         # Get last register and its data type size
    #         last_register = str(max(register_keys))
    #         last_data_type = register_mapping[last_register].get("dataType", "uint16")  # fallback default

    #         data_type_size = self.resolver.get_data_type_size(last_data_type)  # e.g., float = 2, uint32 = 2, uint16 = 1, etc.

    #         end_address = int(last_register) + data_type_size - 1
    #         count = (end_address - start_address)  + 1

    #         reader.channel_id = self.channel_id  # Attach channel ID for logging
    #         await reader.read_registers_with_retries(count=count, start_address=start_address)  # Process devices sequentially