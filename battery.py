import smbus2

def get_battery():
    try:
        bus = smbus2.SMBus(1)
        # PiSugar 3 I2C address: 0x57
        data = bus.read_i2c_block_data(0x57, 0x2a, 1)
        percentage = data[0]
        bus.close()
        return percentage
    except Exception:
        return -1

if __name__ == "__main__":
    pct = get_battery()
    print(f"Battery: {pct}%")
