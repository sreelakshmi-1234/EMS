import asyncio
import logging
import sys
from pathlib import Path

# Add project root (EMS/) to sys.path so all packages can be imported
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add ems_backend_data parent so ems_backend_data.ems_backend_data works
ems_backend_parent = Path(__file__).resolve().parents[2] / "ems_backend_data" / "ems_backend_data"
if str(ems_backend_parent) not in sys.path:
    sys.path.insert(0, str(ems_backend_parent))

from modbus.modbus.src import ChannelProcessor, ModbusClientManager
from modbus.modbus.config_loader import ConfigLoader
from ems_backend_data.ems_backend_data.processor.src.samplings.src.sampling_manager import SamplingManager

try:
    from controller_layer.writers.ems_modbus_server import EMSModbus
except ModuleNotFoundError:
    class EMSModbus:
        @classmethod
        def get_instance(cls):
            return cls()

        async def start(self):
            await asyncio.Event().wait()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(device_id)s] %(message)s",
)
logger = logging.getLogger(__name__)

async def main(sse_broadcaster=None):
    config_loader = ConfigLoader()
    device_config = config_loader.load_config("config/device_config.json")
    ModbusClientManager.initialize(asyncio.get_running_loop())
    sampling_manager = SamplingManager()
    ems_modbus_server = EMSModbus.get_instance()
    devices = device_config["devices"]
   

    # Start EMS Modbus server in background
    asyncio.create_task(ems_modbus_server.start())
    
    logger.info("EMS Modbus Server started in background...")
    
    from collections import defaultdict
    channel_map = defaultdict(list)
    for device in devices:
        channel_id = device.get("channel", 1)
        channel_map[channel_id].append(device)

    # Create a task for each channel to run its own polling loop
    channel_tasks = []
    for channel_id, channel_devices in channel_map.items():
        # creates a ChannelProcessor for each explicitly defined channel
        processor = ChannelProcessor(
            channel_id=channel_id,
            devices=channel_devices,
            modbus_client_manager=ModbusClientManager,
            sampling_manager=sampling_manager,
            sse_broadcaster=sse_broadcaster
        )
        # Start the channel loop with the specified polling interval
        task = asyncio.create_task(run_channel_loop(processor, device_config.get("polling_interval", 1)))
        channel_tasks.append(task)

    # Keep the event loop running so that all channel tasks can run concurrently
    await asyncio.gather(*channel_tasks)


async def run_channel_loop(processor, polling_interval):
    while True:
        try:
            # for each channel, we measure the time taken to process the channel and then sleep for the remaining time to maintain a consistent polling interval
            start_time = asyncio.get_event_loop().time()
            await processor.process_channel()
            elapsed_time = asyncio.get_event_loop().time() - start_time
            # Sleep for the remaining time to maintain a 1-second interval
            sleep_time = max(0, polling_interval - elapsed_time)
            await asyncio.sleep(sleep_time)
        except Exception as e:
            logger.error(f"Error in channel {processor.channel_id}: {e}")
            await asyncio.sleep(polling_interval)  # Ensure loop continues even on error

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("modbus Shutting down...")
