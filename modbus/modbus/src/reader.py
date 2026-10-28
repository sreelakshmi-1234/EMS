import logging
import asyncio
import datetime
import time
from ..processor import Mapper
# from pyModbusTCP.utils import decode_ieee, word_list_to_long
# from pymodbus.constants import Endian

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class deviceReader:
    def __init__(self, config, modbus_client_manager, sampling_manager, sse_broadcaster):
        self.server_ip = config["server_ip"]
        self.server_port = config["server_port"]
        self.slave_id = config["slave_id"]
        self.channel_id = None  # Set dynamically by ChannelProcessor
        self.block = config["block"]
        self.device_id = config["device_id"]
        self.device_type = config["deviceType"]
        self.request_timeout = config.get("request_timeout", 3.0)  # Safe default of 3s
        self.connect_timeout = config.get("connect_timeout", 3.0)  # Safe default of 3s
        self.modbus_client_manager = modbus_client_manager
        self.mapper = Mapper(sampling_manager=sampling_manager, sse_broadcaster=sse_broadcaster)

    async def read_registers_with_retries(self, start_address=0, count=20, retries=1, functionCode=3, register_mapping=None):
        for attempt in range(retries):
            request_started = None
            try:
                client = await self.modbus_client_manager.get_client(
                    channel_id=self.channel_id,
                    server_ip=self.server_ip,
                    server_port=self.server_port,
                    retries=retries,
                    request_timeout=self.request_timeout,
                    connect_timeout=self.connect_timeout
                )

                # Dynamically apply this specific device's timeouts to the shared client
                client.timeout = self.request_timeout
                if hasattr(client, 'comm_params'):
                    client.comm_params.timeout_connect = self.connect_timeout

                function_code = int(functionCode)
                result = None
                request_started = time.perf_counter()

                if function_code == 1:
                    # Read Coils
                    result = await client.read_coils(address=start_address, count=count, device_id=self.slave_id)
                elif function_code == 2:
                    # Read Discrete Inputs
                    result = await client.read_discrete_inputs(address=start_address, count=count, device_id=self.slave_id)
                elif function_code == 3:
                    # Read Holding Registers
                    result = await client.read_holding_registers(address=start_address, count=count, device_id=self.slave_id)
                elif function_code == 4:
                    # Read Input Registers
                    result = await client.read_input_registers(address=start_address, count=count, device_id=self.slave_id)
                else:
                    raise ValueError(f"Unsupported function code: {function_code}")

                logger.info(
                    "[CH: %s] Modbus response received for %s FC%s at address %s in %.3f seconds",
                    self.channel_id,
                    self.device_id,
                    function_code,
                    start_address,
                    time.perf_counter() - request_started,
                )

                if not result.isError():
                    if function_code in (1, 2):
                        data = result.bits
                    else:
                        data = result.registers
                    
                    now = datetime.datetime.now(datetime.timezone.utc)
                    # logger.info(f"[ time at {now}  CH: {self.channel_id}] Read devId: {self.device_id} FC{function_code} {self.slave_id}@{self.server_ip}:{self.server_port} count {count}: {data}")

                    # decoded_value = client.convert_from_registers(
                    #     data,
                    #     data_type="int32",   # "int16", "uint16", "int32", "uint32", "float32", "float64"
                    #     word_order="big",  # register word order
                    # )

                    # logger.info(f"Decoded value: {decoded_value}")

                    mapped_values = await self.mapper.map_registers(
                        channel=self.channel_id,
                        server_ip=self.server_ip,
                        server_port=self.server_port,
                        slave_id=self.slave_id,
                        registers=data,
                        block=self.block,
                        device_id=self.device_id,
                        device_type = self.device_type,
                        register_mapper=register_mapping
                    )
                    values = {
                        alias: details.get("value")
                        for alias, details in mapped_values.items()
                    }
                    logger.info(
                        "[CH: %s] %s @ %s:%s FC%s address=%s count=%s values=%s",
                        self.channel_id,
                        self.device_id,
                        self.server_ip,
                        self.server_port,
                        function_code,
                        start_address,
                        count,
                        values,
                    )
                    return mapped_values
                else:
                    logger.warning(
                        f"[CH: {self.channel_id}] Modbus error for slave {self.slave_id} "
                        f"device_id {self.device_id} FC {function_code} "
                        f"address {start_address} count {count}: {result}"
                    )

            except Exception as e:
                if request_started is not None:
                    logger.warning(
                        "[CH: %s] Modbus request failed for %s after %.3f seconds",
                        self.channel_id,
                        self.device_id,
                        time.perf_counter() - request_started,
                    )
                logger.error(f"[CH: {self.channel_id}] device_id {self.device_id} Attempt {attempt+1} failed for {self.slave_id}: {e}")
            # sleep before retrying, but not after the last attempt
            if attempt < retries - 1:
                await asyncio.sleep(1)  # Backoff

        # If all retries fail
        logger.error(f"[CH: {self.channel_id}] device_id {self.device_id} Failed to read data for {self.slave_id} after {retries} attempts")
        failed_values = [None] * count
        logger.info(f"[CH: {self.channel_id}] device_id {self.device_id} Using default values for {self.slave_id}: {failed_values}")

        mapped_values = await self.mapper.map_registers(
            registers=failed_values,
            block=self.block,
            device_id=self.device_id,
            register_mapper=register_mapping,
            save_latest=False,
        )
        return mapped_values
