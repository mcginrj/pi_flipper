import ST7789
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO

# Waveshare 1.3" joystick + button GPIO pins
KEY_UP    = 6
KEY_DOWN  = 19
KEY_LEFT  = 5
KEY_RIGHT = 26
KEY_PRESS = 13
KEY_A     = 21   # Back
KEY_B     = 20   # Select/Launch
KEY_C     = 16   # Shutdown

disp = ST7789.ST7789()
disp.Init()
disp.clear()
disp.bl_DutyCycle(100)

GPIO.setmode(GPIO.BCM)
for pin in [KEY_UP,KEY_DOWN,KEY_LEFT,KEY_RIGHT,KEY_PRESS,KEY_A,KEY_B,KEY_C]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def draw_screen(title, items, selected, battery_pct=-1):
    """Draw a menu screen with title, items list, and selected highlight."""
    img  = Image.new("RGB", (240, 240), "BLACK")
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0,0),(240,28)], fill="#2a2a6a")
    draw.text((8, 6), title, fill="WHITE")
    if battery_pct >= 0:
        bat_color = "#00ff00" if battery_pct > 30 else "#ff4444"
        draw.text((190, 6), f"{battery_pct}%", fill=bat_color)

    # Menu items
    for i, item in enumerate(items):
        y = 38 + i * 28
        if i == selected:
            draw.rectangle([(4, y-2),(236, y+20)], fill="#4a3fb5")
            draw.text((12, y), f"> {item}", fill="WHITE")
        else:
            draw.text((12, y), f"  {item}", fill="#aaaaaa")

    # Footer hint
    draw.text((4, 220), "Joy=nav  B=select  A=back", fill="#555555")

    disp.ShowImage(img.rotate(270))

def show_message(title, lines, color="WHITE"):
    """Show a simple message screen."""
    img  = Image.new("RGB", (240, 240), "BLACK")
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0,0),(240,28)], fill="#2a2a6a")
    draw.text((8, 6), title, fill="WHITE")
    for i, line in enumerate(lines):
        draw.text((8, 40 + i * 22), str(line), fill=color)
    disp.ShowImage(img.rotate(270))

def wait_key():
    import time

    while True:
        if not GPIO.input(KEY_UP):
            while not GPIO.input(KEY_UP):
                time.sleep(0.01)
            time.sleep(0.08)
            return "up"

        if not GPIO.input(KEY_DOWN):
            while not GPIO.input(KEY_DOWN):
                time.sleep(0.01)
            time.sleep(0.08)
            return "down"

        if not GPIO.input(KEY_LEFT):
            while not GPIO.input(KEY_LEFT):
                time.sleep(0.01)
            time.sleep(0.08)
            return "back"

        if not GPIO.input(KEY_RIGHT):
            while not GPIO.input(KEY_RIGHT):
                time.sleep(0.01)
            time.sleep(0.08)
            return "select"

        if not GPIO.input(KEY_PRESS):
            while not GPIO.input(KEY_PRESS):
                time.sleep(0.01)
            time.sleep(0.08)
            return "select"

        if not GPIO.input(KEY_A):
            while not GPIO.input(KEY_A):
                time.sleep(0.01)
            time.sleep(0.08)
            return "back"

        if not GPIO.input(KEY_B):
            while not GPIO.input(KEY_B):
                time.sleep(0.01)
            time.sleep(0.08)
            return "select"

        if not GPIO.input(KEY_C):
            while not GPIO.input(KEY_C):
                time.sleep(0.01)
            time.sleep(0.08)
            return "shutdown"

        time.sleep(0.03)
