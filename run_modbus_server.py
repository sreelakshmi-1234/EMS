import time
import threading
import sys
from pyModbusTCP.server import ModbusServer

PORT = 511
SLAVE_ID = 5
REG_PCS_COMM_FAILURE = 45  # 0-indexed register 46 in Modbus: pcs_bms_communication_failure
REG_EMS_COMM_FAILURE = 46  # 0-indexed register 47 in Modbus: ems_bms_communication_failure

def main():
    print("=" * 65)
    print(">> EMS LOCAL MODBUS SERVER (Replacement for ModSim)")
    print("   Port: 511 | Slave: 5 | Function: 4 (Input Registers)")
    print("=" * 65)

    server = ModbusServer(host="127.0.0.1", port=PORT, no_block=True)
    
    try:
        server.start()
    except Exception as e:
        print(f"\n[ERROR] Could not start server on port {PORT}: {e}")
        sys.exit(1)

    init_regs = [0] * 50
    init_regs[0] = 1     # Breaker closed
    init_regs[1] = 7500  # 750 V
    init_regs[2] = 250   # 25 A
    server.data_bank.set_input_registers(0, init_regs)
    server.data_bank.set_holding_registers(0, init_regs)

    print("\n[OK] Server is RUNNING on 127.0.0.1:511!")
    print("-" * 65)

    def print_menu():
        val = server.data_bank.get_input_registers(REG_PCS_COMM_FAILURE, 1)[0]
        status = "[ALARM ACTIVE (1)]" if val == 1 else "[NORMAL (0)]"
        print(f"\nCurrent Register 46 status: {status}")
        print("Options:")
        print("  [1] Send 2-Second Glitch (1 for 2s, then auto 0) -> Glitch Filter Test")
        print("  [2] Set Register 46 = 1 (ALARM ACTIVE)          -> 4s Debounce Test")
        print("  [3] Set Register 46 = 0 (NORMAL / CLEAR)        -> 4s Clearance Test")
        print("  [q] Quit Server")
        print("Enter choice (1/2/3/q): ", end="", flush=True)

    def glitch_worker():
        print("\n\n>>> Glitch started: Register 46 = 1 (Active for 2 seconds)...")
        server.data_bank.set_input_registers(REG_PCS_COMM_FAILURE, [1])
        time.sleep(2)
        server.data_bank.set_input_registers(REG_PCS_COMM_FAILURE, [0])
        print(">>> Glitch ended: Register 46 = 0 (Back to normal)")
        print_menu()

    while True:
        print_menu()
        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            t = threading.Thread(target=glitch_worker, daemon=True)
            t.start()
        elif choice == "2":
            server.data_bank.set_input_registers(REG_PCS_COMM_FAILURE, [1])
            print("\n>>> Register 46 set to 1 (ALARM ACTIVE).")
        elif choice == "3":
            server.data_bank.set_input_registers(REG_PCS_COMM_FAILURE, [0])
            print("\n>>> Register 46 set to 0 (NORMAL).")
        elif choice.lower() == "q":
            break
        else:
            print("Invalid choice, please enter 1, 2, 3 or q.")

    server.stop()
    print("\nModbus Server stopped. Bye!")

if __name__ == "__main__":
    main()
