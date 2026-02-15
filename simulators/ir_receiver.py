import time
import random


# Simulated IR remote button codes (NEC protocol style)
IR_CODES = {
    0xFF6897: "0",
    0xFF30CF: "1",
    0xFF18E7: "2",
    0xFF7A85: "3",
    0xFF10EF: "4",
    0xFF38C7: "5",
    0xFF5AA5: "6",
    0xFF42BD: "7",
    0xFF4AB5: "8",
    0xFF52AD: "9",
    0xFFA25D: "POWER",
    0xFFE21D: "FUNC",
    0xFF22DD: "PREV",
    0xFF02FD: "NEXT",
    0xFFC23D: "PLAY",
    0xFFE01F: "VOL_DOWN",
    0xFFA857: "VOL_UP",
    0xFF906F: "UP",
    0xFF9867: "EQ",
    0xFFB04F: "DOWN",
}

# Map remote buttons to RGB actions
BUTTON_ACTIONS = {
    "POWER": "toggle",
    "1": "red",
    "2": "green",
    "3": "blue",
    "4": "yellow",
    "5": "cyan",
    "6": "magenta",
    "7": "white",
    "8": "orange",
    "9": "purple",
    "0": "off",
    "VOL_UP": "brightness_up",
    "VOL_DOWN": "brightness_down",
}


def run_ir_simulator(delay, callback, stop_event):
    """
    Simulates IR receiver sensor behavior.
    Randomly generates IR remote button presses.
    callback(button_name, action) is called on each press.
    """
    buttons = list(BUTTON_ACTIONS.keys())

    while not stop_event.is_set():
        # Random delay between 3-8 seconds (simulate remote presses)
        wait_time = random.uniform(3, 8)
        if stop_event.wait(timeout=wait_time):
            break

        button = random.choice(buttons)
        action = BUTTON_ACTIONS[button]
        callback(button, action)
