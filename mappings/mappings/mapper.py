import asyncio
import logging
import time
import datetime
from pyModbusTCP.utils import decode_ieee
from plant_architecture_resolver import PlantArchitectureResolver
from controller_layer import ControllerManager

from auto_configs.latest_telemetry_manager import LatestTelemetryManager
from processor.src.mappings.telemetry_garbage import TelemetryGarbageDAO
from utils.db_write_queue import GARBAGE_QUEUE

import websocket
import json
    
logger = logging.getLogger(__name__)

class Mapper:
    def __init__(self, sampling_manager, sse_broadcaster):
        """
        Initialize the Mapper with references to SamplingManager and SSEBroadcaster.
        """
        self.sampling_manager = sampling_manager  # Reference to the SamplingManager
        self.see_publisher = sse_broadcaster    # Reference to the SSEBroadcaster

        self.block_device_resolver = PlantArchitectureResolver(base_dir="plant_architecture")
        # self.control_manager = ControllerManager(resolver=self.block_device_resolver)

        # Initialize latest telemetry manager
        self.latest_telemetry_manager = LatestTelemetryManager()

    async def map_registers(self, channel, server_ip, server_port, slave_id, registers, block, device_id, device_type, register_mapper):
        """
        Map raw register values to their tags, apply transformations, and broadcast data via SSE.
        """
        # Offload synchronous work to a thread
        loop = asyncio.get_event_loop()
        mapped_values, garbage_records = (await loop.run_in_executor(
            None,  # Use default thread pool
            self._map_registers_sync,  # Synchronous function
            registers,
            block,
            device_id,
            device_type,
            register_mapper
        ))
        
        # Save mapped data and raw registers
        self.latest_telemetry_manager.save_device_data(device_id, mapped_values)

        # Pass results to sampling layer (async)
        # await self.sampling_manager.process_mapped_data(mapped_values)
        asyncio.create_task(self.sampling_manager.process_mapped_data(mapped_values))

        # Determine the topic for SSE broadcasting
        topic = f"{device_id}"

        # Broadcast the mapped values to the relevant topic
        # await self.sse_broadcaster.broadcast(topic, mapped_values)
        # self.sse_broadcaster.register("stream_zakir")
        # await self.sse_broadcaster.broadcast(topic, mapped_values)
        # try:
        #     await self.see_publisher.publish(topic, mapped_values)
        # except Exception as e:
        #     logger.info("ERROR WHILE PUBLISHING TOPIC", e)
            
        # logger.info("New Topic Added")

        
        # Insert garbage records if any
        # logger.info(f"Garbage records to insert: {len(garbage_records)}, {garbage_records}")
        if garbage_records:
            for rec in garbage_records:
                # await GARBAGE_QUEUE.put(rec)
                await TelemetryGarbageDAO.insert(rec)



        return mapped_values

    def _map_registers_sync(self, registers, block, device_id, device_type, register_mapper):
        try:
            mapped_values = {}
            garbage_records = []
            # logger.info(device_id, registers)
            for key, mapping in register_mapper.items():
                try:
                    register = mapping["register"]
                    start_addr = mapping.get("srno", int(register))  # Use 'register' if present
                    data_type = mapping["dataType"]
                    scaling = mapping.get("scaling", 1)
                    min_val = mapping.get("min", float("-inf"))
                    max_val = mapping.get("max", float("inf"))
                    name = mapping["name"]
                    alias = mapping["alias"]
                    type = mapping["type"]
                    unit = mapping.get("unit", "")
                    endian = mapping.get("endian", "big")
                    byte_order = mapping.get("byte_order", "big_endian")
                    word_order = mapping.get("word_order", "big_endian")

                    # Determine how many registers to read
                    if data_type in ["int32", "float"]:
                        reg_len = 2
                    else:
                        reg_len = 1

                    reg_slice = registers[start_addr:start_addr + reg_len]
                    # print(reg_slice)
                    # Decode and scale
                    decoded = decode_value(reg_slice, data_type, byte_order, word_order, mapping.get("alarmType"))
                    scaled_value = None

                    if decoded is not None:
                        scaled_value = decoded / scaling
                        if isinstance(scaled_value, float):
                            scaled_value = round(scaled_value, 2)
                        if not (min_val <= scaled_value <= max_val):
                            garbage_records.append({
                                "device_id": device_id,
                                "device_type": device_type,
                                "block": block,
                                "telemetry_alias": alias,
                                "telemetry_name": name,
                                "raw_value": decoded,
                                "scaled_value": scaled_value,
                                "unit": unit,
                                "min_value": min_val,
                                "max_value": max_val,
                                "reason": "OUT_OF_RANGE",
                                "remarks": f"value {scaled_value} not in range {min_val}–{max_val}",
                                "register": register,
                                "data_type": data_type,
                            })
                            logger.warning(f"Garbage Data Detected for device {device_id}, tag {alias}: {scaled_value} not in range {min_val}–{max_val}")
                            scaled_value = None  # Out-of-range

                    mapped_values[alias] = {
                        "block": block,
                        "device_type": device_type,
                        "device_id": device_id,
                        "alias": alias,
                        "name" : name,
                        "value": scaled_value,
                        "type": type,
                        "unit": unit,
                        "dataType" : data_type,
                        "register" : register,
                        "alarmType": mapping.get("alarmType", "normal"),
                        "severity": mapping.get("severity", "critical"),
                        "isEvent": mapping.get("isEvent", False),
                        "isNormalReverse": mapping.get("isNormalReverse", False),
                    }
                    
                    # Handle alarm subtypes
                    if type == "alarm":
                        alarmType = mapped_values[alias]["alarmType"]

                        if alarmType == "bitwise":
                            bit_map = mapping.get("bitMap", {})

                            bitwise_values = {}
                            for bit_pos, defn in bit_map.items():
                                bit_state = (decoded >> int(bit_pos)) & 1
                                tag = defn["alias"]

                                bitwise_values[tag] = {
                                    "device_id": device_id,
                                    "alias": tag,
                                    "value": bit_state,
                                    "type": "alarm",
                                    "severity": defn.get("severity", "info"),
                                    "parent_alias": alias
                                }

                                # Attach to parent entry
                                mapped_values[alias]["bitMapAlarm"] = bitwise_values

                except Exception as e_inner:
                    logger.warning(f"Failed to map {key}: {e_inner}---map register : {registers}")

            now = datetime.datetime.now(datetime.timezone.utc)
            # logger.info(f'mapped values at time {now} :  {mapped_values}')
            return mapped_values, garbage_records

        except Exception as e:
            logger.error(f"Error mapping registers: {e}")
            return {}



import struct
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian

def decode_value(registers, data_type, byte_order="big_endian", word_order="big_endian", alarm_type=None):
    try:
        if data_type == "boolean":
            return bool(registers[0])
        elif data_type == "uint16":
            return registers[0]
        elif data_type == "int16" or data_type == "int":
            val = registers[0]
            # Bitwise fault words are unsigned bitmasks (0-65535); signed
            # interpretation would flip values > 32767 into negatives.
            if alarm_type == "bitwise":
                return val
            return val - 65536 if val > 32767 else val
        elif data_type == "int32":
            if len(registers) < 2:
                return None
            decoder = BinaryPayloadDecoder.fromRegisters(
                registers,
                byteorder=Endian.BIG if byte_order == "big_endian" else Endian.LITTLE,
                wordorder=Endian.BIG if word_order == "big_endian" else Endian.LITTLE,
            )

            return decoder.decode_32bit_int()
        elif data_type == "float" or data_type == "float32":
            if len(registers) < 2: return None
            word = (registers[1] << 16) + registers[0]
            return struct.unpack("f", struct.pack("I", word))[0]
        # Add more types if needed
    except Exception as e:
        logger.error(f"Decoding error for data_type={data_type}: {e}")
    return None


# elif data_type == "int32":
#             if len(registers) < 2:
#                 return None
#             high_word = registers[0]     # MSB
#             low_word = registers[1]    # LSB
#             # pack into 4 bytes (big-endian 32-bit signed int)
#             packed = struct.pack(">HH", high_word, low_word)
#             value = struct.unpack(">i", packed)[0]
#             return value

# elif data_type == "int32":
#             if len(registers) < 2:
#                 return None
#             word = (registers[1] << 16) | registers[0]
#             # Convert to signed 32-bit integer
#             if word & 0x80000000:
#                 word -= 0x100000000
#             return word


# Format the mapped values to Update method block input
def extract_updates(raw_data: dict) -> dict:
    return {details['alias']: {"value": details["value"]} for tag, details in raw_data.items()}
