import logging
from pymodbus.client import AsyncModbusTcpClient
import asyncio

try:
    from controller_layer.writers.file_writer import FileService
except ModuleNotFoundError:
    class FileService:
        @staticmethod
        async def update_flag(name, value):
            return None

MODBUS_CLIENTS = {}
MAIN_LOOP = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModbusClientManager:
    _lock = None  # Will be externally

    @classmethod
    def initialize(cls, loop):
        global MAIN_LOOP
        MAIN_LOOP = loop
        cls._lock = asyncio.Lock()   # <-- created inside correct loop

    @classmethod
    async def get_client(cls, channel_id, server_ip, server_port, retries, request_timeout=3.0, connect_timeout=3.0):
        key = f"channel_{channel_id}_{server_ip}:{server_port}"
        async with cls._lock:
            client = MODBUS_CLIENTS.get(key)
            
            if client:
                if client.connected:
                    return client
                else:
                    # Remove stale client
                    del MODBUS_CLIENTS[key]
            
            # Create new client with specific timeouts
            client = AsyncModbusTcpClient(host=server_ip, port=server_port, retries=retries, timeout=request_timeout)
            if hasattr(client, 'comm_params'):
                client.comm_params.timeout_connect = connect_timeout
            
            await client.connect()
            if not client.connected:
                # Writing flag for Protocol Connection
                await FileService.update_flag("is_protocol_healthy", 0)
                
                raise ConnectionError(f"Failed to connect to {key}")
            MODBUS_CLIENTS[key] = client

            # Writing flag for Protocol Connection
            await FileService.update_flag("is_protocol_healthy", 1)

            logger.info(f"Created Modbus client for {key}. Active clients: {len(MODBUS_CLIENTS)}")
            return client
        
    @classmethod
    async def get_client_for_writing(cls, channel_id, server_ip, server_port, retries):

        key = f"channel_{channel_id}_{server_ip}:{server_port}"
        # Create new client
        client = AsyncModbusTcpClient(host=server_ip, port=server_port, retries=retries)
        await client.connect()
        if not client.connected:
            raise ConnectionError(f"Failed to connect to {key}")
        logger.info(f"Created Modbus client for {key}. Active clients: {len(MODBUS_CLIENTS)}")
        return client

    @classmethod
    async def close_all(cls):
        async with cls._lock:
            for key, client in list(MODBUS_CLIENTS.items()):
                client.close()
                del MODBUS_CLIENTS[key]
                logger.info(f"Closed Modbus client for {key}")

# Clients are stored globally but never closed. Over time, this can lead to resource leaks.
# Fix : Implement a cleanup mechanism or reuse clients more efficiently
# class ModbusClientManager:
#     @staticmethod
#     async def get_client(channel_id, server_ip, server_port, retries):
#         key = f"channel_{channel_id}_{server_ip}:{server_port}"
#         client = MODBUS_CLIENTS.get(key)
#         if not client or not client.connected:
#             if client:  # Close existing disconnected client
#                 await client.close()
#             client = AsyncModbusTcpClient(host=server_ip, port=server_port, retries=retries)
#             await client.connect()
#             if not client.connected:
#                 raise ConnectionError(f"Failed to connect to {key}")
#             MODBUS_CLIENTS[key] = client
#         return client