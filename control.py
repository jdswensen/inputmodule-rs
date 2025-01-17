#!/usr/bin/env python3
import argparse
import sys
import threading
import time
from datetime import datetime, timedelta
import random
import math
import sys
from enum import IntEnum


# Need to install
import serial

# Optional dependencies:
# from PIL import Image
# import PySimpleGUI as sg

FWK_MAGIC = [0x32, 0xAC]


class CommandVals(IntEnum):
    Brightness = 0x00
    Pattern = 0x01
    BootloaderReset = 0x02
    Sleep = 0x03
    Animate = 0x04
    Panic = 0x05
    Draw = 0x06
    StageGreyCol = 0x07
    DrawGreyColBuffer = 0x08
    SetText = 0x09
    StartGame = 0x10
    GameControl = 0x11
    GameStatus = 0x12
    SetColor = 0x13
    DisplayOn = 0x14
    InvertScreen = 0x15
    SetPixelColumn = 0x16
    FlushFramebuffer = 0x17
    ClearRam = 0x18
    ScreenSaver = 0x19
    SetFps = 0x1A
    SetPowerMode = 0x1B
    Version = 0x20


class Game(IntEnum):
    Snake = 0x00
    Pong = 0x01
    Tetris = 0x02
    GameOfLife = 0x03


class PatternVals(IntEnum):
    Percentage = 0x00
    Gradient = 0x01
    DoubleGradient = 0x02
    DisplayLotus = 0x03
    ZigZag = 0x04
    FullBrightness = 0x05
    DisplayPanic = 0x06
    DisplayLotus2 = 0x07


class GameOfLifeStartParam(IntEnum):
    Currentmatrix = 0x00
    Pattern1 = 0x01
    Blinker = 0x02
    Toad = 0x03
    Beacon = 0x04
    Glider = 0x05

    def __str__(self):
        return self.name.lower()

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return GameOfLifeStartParam[s.lower().capitalize()]
        except KeyError:
            return s


class GameControlVal(IntEnum):
    Up = 0
    Down = 1
    Left = 2
    Right = 3
    Quit = 4


PATTERNS = [
    'All LEDs on',
    '"LOTUS" sideways',
    'Gradient (0-13% Brightness)',
    'Double Gradient (0-7-0% Brightness)',
    'Zigzag',
    '"PANIC"',
    '"LOTUS" Top Down',
    'All brightness levels (1 LED each)',
]
DRAW_PATTERNS = ['off', 'on', 'foo']
GREYSCALE_DEPTH = 32
RESPONSE_SIZE = 32
WIDTH = 9
HEIGHT = 34
B1_WIDTH = 300
B1_HEIGHT = 400

ARG_UP = 0
ARG_DOWN = 1
ARG_LEFT = 2
ARG_RIGHT = 3
ARG_QUIT = 4
ARG_2LEFT = 5
ARG_2RIGHT = 6

RGB_COLORS = ['white', 'black', 'red', 'green',
              'blue', 'cyan', 'yellow', 'purple']
SCREEN_FPS = ['quarter', 'half', 'one', 'two', 'four', 'eight', 'sixteen', 'thirtytwo']
HIGH_FPS_MASK = 0b00010000
LOW_FPS_MASK = 0b00000111

SERIAL_DEV = None

STOP_THREAD = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootloader", help="Jump to the bootloader to flash new firmware",
                        action="store_true")
    parser.add_argument('--sleep', help='Simulate the host going to sleep or waking up',
                        action=argparse.BooleanOptionalAction)
    parser.add_argument('--is-sleeping', help='Check current sleep state',
                        action='store_true')
    parser.add_argument("--brightness", help="Adjust the brightness. Value 0-255",
                        type=int)
    parser.add_argument("--get-brightness", help="Get current brightness",
                        action="store_true")
    parser.add_argument('--animate', action=argparse.BooleanOptionalAction,
                        help='Start/stop vertical scrolling')
    parser.add_argument('--get-animate', action='store_true',
                        help='Check if currently animating')
    parser.add_argument("--pattern", help='Display a pattern',
                        type=str, choices=PATTERNS)
    parser.add_argument("--image", help="Display a PNG or GIF image in black and white only)",
                        type=argparse.FileType('rb'))
    parser.add_argument("--image-grey", help="Display a PNG or GIF image in greyscale",
                        type=argparse.FileType('rb'))
    parser.add_argument("--percentage", help="Fill a percentage of the screen",
                        type=int)
    parser.add_argument("--clock", help="Display the current time",
                        action="store_true")
    parser.add_argument("--string", help="Display a string or number, like FPS",
                        type=str)
    parser.add_argument("--symbols", help="Show symbols (degF, degC, :), snow, cloud, ...)",
                        nargs='+')
    parser.add_argument("--gui", help="Launch the graphical version of the program",
                        action="store_true")
    parser.add_argument("--panic", help="Crash the firmware (TESTING ONLY)",
                        action="store_true")
    parser.add_argument("--blink", help="Blink the current pattern",
                        action="store_true")
    parser.add_argument("--breathing", help="Breathing of the current pattern",
                        action="store_true")
    parser.add_argument("--eq", help="Equalizer", nargs='+', type=int)
    parser.add_argument(
        "--random-eq", help="Random Equalizer", action="store_true")
    parser.add_argument("--wpm", help="WPM Demo", action="store_true")
    parser.add_argument("--snake", help="Snake", action="store_true")
    parser.add_argument("--snake-embedded",
                        help="Snake on the module", action="store_true")
    parser.add_argument("--pong-embedded",
                        help="Pong on the module", action="store_true")
    parser.add_argument("--game-of-life-embedded",
                        help="Game of Life", type=GameOfLifeStartParam.argparse, choices=list(GameOfLifeStartParam))
    parser.add_argument("--quit-embedded-game",
                        help="Quit the current game", action="store_true")
    parser.add_argument(
        "--all-brightnesses", help="Show every pixel in a different brightness", action="store_true")
    parser.add_argument(
        "--set-color", help="Set RGB color (C1 Minimal Input Module)", choices=RGB_COLORS)
    parser.add_argument(
        "--get-color", help="Get RGB color (C1 Minimal Input Module)", action="store_true")
    parser.add_argument("-v", "--version",
                        help="Get device version", action="store_true")
    parser.add_argument("--serial-dev", help="Change the serial dev. Probably /dev/ttyACM0 on Linux, COM0 on Windows",
                        default='/dev/ttyACM0')

    parser.add_argument(
        "--disp-str", help="Display a string on the LCD Display", type=str)
    parser.add_argument("--display-on", help="Control display power",
                        action=argparse.BooleanOptionalAction)
    parser.add_argument("--invert-screen", help="Invert display",
                        action=argparse.BooleanOptionalAction)
    parser.add_argument("--screen-saver", help="Turn on/off screensaver",
                        action=argparse.BooleanOptionalAction)
    parser.add_argument("--set-fps", help="Set screen FPS",
                        choices=SCREEN_FPS)
    parser.add_argument("--set-power-mode", help="Set screen power mode",
                        choices=['high', 'low'])
    parser.add_argument("--get-fps", help="Set screen FPS",
                        action='store_true')
    parser.add_argument("--get-power-mode", help="Set screen power mode",
                        action='store_true')
    parser.add_argument("--b1image", help="On the B1 display, show a PNG or GIF image in black and white only)",
                        type=argparse.FileType('rb'))

    args = parser.parse_args()

    if args.serial_dev is not None:
        global SERIAL_DEV
        SERIAL_DEV = args.serial_dev

    if args.bootloader:
        bootloader()
    elif args.sleep is not None:
        send_command(CommandVals.Sleep, [args.sleep])
    elif args.is_sleeping:
        res = send_command(CommandVals.Sleep, with_response=True)
        sleeping = bool(res[0])
        print(f"Currently sleeping: {sleeping}")
    elif args.brightness is not None:
        if args.brightness > 255 or args.brightness < 0:
            print("Brightness must be 0-255")
            sys.exit(1)
        brightness(args.brightness)
    elif args.get_brightness:
        br = get_brightness()
        print(f"Current brightness: {br}")
    elif args.percentage is not None:
        if args.percentage > 100 or args.percentage < 0:
            print("Percentage must be 0-100")
            sys.exit(1)
        percentage(args.percentage)
    elif args.pattern is not None:
        pattern(args.pattern)
    elif args.animate is not None:
        animate(args.animate)
    elif args.get_animate:
        animating = get_animate()
        print(f"Currently animating: {animating}")
    elif args.panic:
        send_command(CommandVals.Panic, [0x00])
    elif args.image is not None:
        image_bl(args.image)
    elif args.image_grey is not None:
        image_greyscale(args.image_grey)
    elif args.all_brightnesses:
        all_brightnesses()
    elif args.set_color:
        set_color(args.set_color)
    elif args.get_color:
        (red, green, blue) = get_color()
        print(f"Current color: RGB:({red}, {green}, {blue})")
    elif args.gui:
        gui()
    elif args.blink:
        blinking()
    elif args.breathing:
        breathing()
    elif args.wpm:
        wpm_demo()
    elif args.snake:
        snake()
    elif args.snake_embedded:
        snake_embedded()
    elif args.game_of_life_embedded is not None:
        game_of_life_embedded(args.game_of_life_embedded)
    elif args.quit_embedded_game:
        send_command(CommandVals.GameControl, [GameControlVal.Quit])
    elif args.pong_embedded:
        pong_embedded()
    elif args.eq is not None:
        eq(args.eq)
    elif args.random_eq:
        random_eq()
    elif args.clock:
        clock()
    elif args.string is not None:
        show_string(args.string)
    elif args.symbols is not None:
        show_symbols(args.symbols)
    elif args.disp_str is not None:
        display_string(args.disp_str)
    elif args.display_on is not None:
        display_on_cmd(args.display_on)
    elif args.invert_screen is not None:
        invert_screen_cmd(args.invert_screen)
    elif args.screen_saver is not None:
        screen_saver_cmd(args.screen_saver)
    elif args.set_fps is not None:
        set_fps_cmd(args.set_fps)
    elif args.set_power_mode is not None:
        set_power_mode_cmd(args.set_power_mode)
    elif args.get_fps:
        get_fps_cmd()
    elif args.get_power_mode:
        get_power_mode_cmd()
    elif args.b1image is not None:
        b1image_bl(args.b1image)
    elif args.version:
        version = get_version()
        print(f"Device version: {version}")
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


def bootloader():
    """Reboot into the bootloader to flash new firmware"""
    send_command(CommandVals.BootloaderReset, [0x00])


def percentage(p):
    """Fill a percentage of the screen. Bottom to top"""
    send_command(CommandVals.Pattern, [PatternVals.Percentage, p])


def brightness(b: int):
    """Adjust the brightness scaling of the entire screen.
    """
    send_command(CommandVals.Brightness, [b])


def get_brightness():
    """Adjust the brightness scaling of the entire screen.
    """
    res = send_command(CommandVals.Brightness, with_response=True)
    return int(res[0])


def get_version():
    """Get the device's firmware version"""
    res = send_command(CommandVals.Version, with_response=True)
    major = res[0]
    minor = (res[1] & 0xF0) >> 4
    patch = res[1] & 0xF
    pre_release = res[2]

    version = f"{major}.{minor}.{patch}"
    if pre_release:
        version += " (Pre-release)"
    return version


def animate(b: bool):
    """Tell the firmware to start/stop animation.
    Scrolls the currently saved grid vertically down."""
    send_command(CommandVals.Animate, [b])


def get_animate():
    """Tell the firmware to start/stop animation.
    Scrolls the currently saved grid vertically down."""
    res = send_command(CommandVals.Animate, with_response=True)
    return bool(res[0])


def b1image_bl(image_file):
    """ Display an image in black and white
    Confirmed working with PNG and GIF.
    Must be 300x400 in size.
    Sends one 400px column in a single commands and a flush at the end
    """

    from PIL import Image
    im = Image.open(image_file).convert("RGB")
    width, height = im.size
    assert (width == B1_WIDTH)
    assert (height == B1_HEIGHT)
    pixel_values = list(im.getdata())

    for x in range(B1_WIDTH):
        vals = [0 for _ in range(50)]

        byte = None
        for y in range(B1_HEIGHT):
            pixel = pixel_values[y*B1_WIDTH + x]
            brightness = sum(pixel) / 3
            black = brightness < 0xFF/2

            bit = y % 8

            if bit == 0:
                byte = 0
            if black:
                byte |= 1 << bit

            if bit == 7:
                vals[int(y/8)] = byte

        column_le = list((x).to_bytes(2, 'little'))
        command = FWK_MAGIC + [0x16] + column_le + vals
        send_command(command)

    # Flush
    command = FWK_MAGIC + [0x17]
    send_command(command)


def image_bl(image_file):
    """Display an image in black and white
    Confirmed working with PNG and GIF.
    Must be 9x34 in size.
    Sends everything in a single command
    """
    vals = [0 for _ in range(39)]

    from PIL import Image
    im = Image.open(image_file).convert("RGB")
    width, height = im.size
    assert (width == 9)
    assert (height == 34)
    pixel_values = list(im.getdata())
    for i, pixel in enumerate(pixel_values):
        brightness = sum(pixel) / 3
        if brightness > 0xFF/2:
            vals[int(i/8)] |= (1 << i % 8)

    send_command(CommandVals.Draw, vals)


def pixel_to_brightness(pixel):
    """Calculate pixel brightness from an RGB triple"""
    assert (len(pixel) == 3)
    brightness = sum(pixel) / len(pixel)

    # Poor man's scaling to make the greyscale pop better.
    # Should find a good function.
    if brightness > 200:
        brightness = brightness
    elif brightness > 150:
        brightness = brightness * 0.8
    elif brightness > 100:
        brightness = brightness * 0.5
    elif brightness > 50:
        brightness = brightness
    else:
        brightness = brightness * 2

    return int(brightness)


def image_greyscale(image_file):
    """Display an image in greyscale
    Sends each 1x34 column and then commits => 10 commands
    """
    with serial.Serial(SERIAL_DEV, 115200) as s:
        from PIL import Image
        im = Image.open(image_file).convert("RGB")
        width, height = im.size
        assert (width == 9)
        assert (height == 34)
        pixel_values = list(im.getdata())
        for x in range(0, WIDTH):
            vals = [0 for _ in range(HEIGHT)]

            for y in range(HEIGHT):
                vals[y] = pixel_to_brightness(pixel_values[x+y*WIDTH])

            send_col(s, x, vals)
        commit_cols(s)


def send_col(s, x, vals):
    """Stage greyscale values for a single column. Must be committed with commit_cols()"""
    command = FWK_MAGIC + [CommandVals.StageGreyCol, x] + vals
    send_serial(s, command)


def commit_cols(s):
    """Commit the changes from sending individual cols with send_col(), displaying the matrix.
    This makes sure that the matrix isn't partially updated."""
    command = FWK_MAGIC + [CommandVals.DrawGreyColBuffer, 0x00]
    send_serial(s, command)


def get_color():
    res = send_command(CommandVals.SetColor, with_response=True)
    return (int(res[0]), int(res[1]), int(res[2]))


def set_color(color):
    rgb = None
    if color == 'white':
        rgb = [0xFF, 0xFF, 0xFF]
    elif color == 'black':
        rgb = [0x00, 0x00, 0x00]
    elif color == 'red':
        rgb = [0xFF, 0x00, 0x00]
    elif color == 'green':
        rgb = [0x00, 0xFF, 0x00]
    elif color == 'blue':
        rgb = [0x00, 0x00, 0xFF]
    elif color == 'yellow':
        rgb = [0xFF, 0xFF, 0x00]
    elif color == 'cyan':
        rgb = [0x00, 0xFF, 0xFF]
    elif color == 'purple':
        rgb = [0xFF, 0x00, 0xFF]
    else:
        print(f"Unknown color: {color}")
        return

    if rgb:
        send_command(CommandVals.SetColor, rgb)


def all_brightnesses():
    """Increase the brightness with each pixel.
    Only 0-255 available, so it can't fill all 306 LEDs"""
    with serial.Serial(SERIAL_DEV, 115200) as s:
        for x in range(0, WIDTH):
            vals = [0 for _ in range(HEIGHT)]

            for y in range(HEIGHT):
                brightness = x + WIDTH * y
                if brightness > 255:
                    vals[y] = 0
                else:
                    vals[y] = brightness

            send_col(s, x, vals)
        commit_cols(s)


def countdown(seconds):
    """ Run a countdown timer. Lighting more LEDs every 100th of a seconds.
    Until the timer runs out and every LED is lit"""
    start = datetime.now()
    target = seconds * 1_000_000
    global STOP_THREAD
    while True:
        if STOP_THREAD:
            STOP_THREAD = False
            return
        now = datetime.now()
        passed_time = (now - start) / timedelta(microseconds=1)

        ratio = passed_time / target
        if passed_time >= target:
            break

        leds = int(306 * ratio)
        light_leds(leds)

        time.sleep(0.01)

    light_leds(306)
    # breathing()
    blinking()


def blinking():
    """Blink brightness high/off every second.
    Keeps currently displayed grid"""
    while True:
        brightness(0)
        time.sleep(0.5)
        brightness(200)
        time.sleep(0.5)


def breathing():
    """Animate breathing brightness.
    Keeps currently displayed grid"""
    # Bright ranges appear similar, so we have to go through those faster
    while True:
        # Go quickly from 250 to 50
        for i in range(10):
            time.sleep(0.03)
            brightness(250 - i*20)

        # Go slowly from 50 to 0
        for i in range(10):
            time.sleep(0.06)
            brightness(50 - i*5)

        # Go slowly from 0 to 50
        for i in range(10):
            time.sleep(0.06)
            brightness(i*5)

        # Go quickly from 50 to 250
        for i in range(10):
            time.sleep(0.03)
            brightness(50 + i*20)


direction = None
body = []


def opposite_direction(direction):
    from getkey import keys
    if direction == keys.RIGHT:
        return keys.LEFT
    elif direction == keys.LEFT:
        return keys.RIGHT
    elif direction == keys.UP:
        return keys.DOWN
    elif direction == keys.DOWN:
        return keys.UP
    return direction


def snake_keyscan():
    from getkey import getkey, keys
    global direction
    global body

    while True:
        current_dir = direction
        key = getkey()
        if key in [keys.RIGHT, keys.UP, keys.LEFT, keys.DOWN]:
            # Don't allow accidental suicide if we have a body
            if key == opposite_direction(current_dir) and body:
                continue
            direction = key


def snake_embedded_keyscan():
    from getkey import getkey, keys

    while True:
        key_arg = None
        key = getkey()
        if key == keys.UP:
            key_arg = GameControlVal.Up
        elif key == keys.DOWN:
            key_arg = GameControlVal.Down
        elif key == keys.LEFT:
            key_arg = GameControlVal.Left
        elif key == keys.RIGHT:
            key_arg = GameControlVal.Right
        elif key == 'q':
            # Quit
            key_arg = GameControlVal.Quit
        if key_arg is not None:
            send_command(CommandVals.GameControl, [key_arg])


def game_over():
    global body
    while True:
        show_string('GAME ')
        time.sleep(0.75)
        show_string('OVER!')
        time.sleep(0.75)
        score = len(body)
        show_string(f'{score:>3} P')
        time.sleep(0.75)


def pong_embedded():
    # Start game
    send_command(CommandVals.StartGame, [Game.Pong])

    from getkey import getkey, keys

    while True:
        key_arg = None
        key = getkey()
        if key == keys.LEFT:
            key_arg = ARG_LEFT
        elif key == keys.RIGHT:
            key_arg = ARG_RIGHT
        elif key == 'a':
            key_arg = ARG_2LEFT
        elif key == 'd':
            key_arg = ARG_2RIGHT
        elif key == 'q':
            # Quit
            key_arg = ARG_QUIT
        if key_arg is not None:
            send_command(CommandVals.GameControl, [key_arg])


def game_of_life_embedded(arg):
    # Start game
    # TODO: Add a way to stop it
    print("Game", int(arg))
    send_command(CommandVals.StartGame, [Game.GameOfLife, int(arg)])


def snake_embedded():
    # Start game
    send_command(CommandVals.StartGame, [Game.Snake])

    snake_embedded_keyscan()


def snake():
    from getkey import keys
    global direction
    global body
    head = (0, 0)
    direction = keys.DOWN
    food = (0, 0)
    while food == head:
        food = (random.randint(0, WIDTH-1),
                random.randint(0, HEIGHT-1))

    # Setting
    WRAP = False

    thread = threading.Thread(target=snake_keyscan, args=(), daemon=True)
    thread.start()

    prev = datetime.now()
    while True:
        now = datetime.now()
        delta = (now - prev) / timedelta(milliseconds=1)

        if delta > 200:
            prev = now
        else:
            continue

        # Update position
        (x, y) = head
        oldhead = head
        if direction == keys.RIGHT:
            head = (x+1, y)
        elif direction == keys.LEFT:
            head = (x-1, y)
        elif direction == keys.UP:
            head = (x, y-1)
        elif direction == keys.DOWN:
            head = (x, y+1)

        # Detect edge condition
        (x, y) = head
        if head in body:
            return game_over()
        elif x >= WIDTH or x < 0 or y >= HEIGHT or y < 0:
            if WRAP:
                if x >= WIDTH:
                    x = 0
                elif x < 0:
                    x = WIDTH-1
                elif y >= HEIGHT:
                    y = 0
                elif y < 0:
                    y = HEIGHT-1
                head = (x, y)
            else:
                return game_over()
        elif head == food:
            body.insert(0, oldhead)
            while food == head:
                food = (random.randint(0, WIDTH-1),
                        random.randint(0, HEIGHT-1))
        elif body:
            body.pop()
            body.insert(0, oldhead)

        # Draw on screen
        matrix = [[0 for _ in range(HEIGHT)] for _ in range(WIDTH)]
        matrix[x][y] = 1
        matrix[food[0]][food[1]] = 1
        for bodypart in body:
            (x, y) = bodypart
            matrix[x][y] = 1
        render_matrix(matrix)


def wpm_demo():
    """Capture keypresses and calculate the WPM of the last 10 seconds
    TODO: I'm not sure my calculation is right."""
    from getkey import getkey, keys
    start = datetime.now()
    keypresses = []
    while True:
        _ = getkey()

        now = datetime.now()
        keypresses = [x for x in keypresses if (now - x).total_seconds() < 10]
        keypresses.append(now)
        # Word is five letters
        wpm = (len(keypresses) / 5) * 6

        total_time = (now-start).total_seconds()
        if total_time < 10:
            wpm = wpm / (total_time / 10)

        show_string(' ' + str(int(wpm)))


def random_eq():
    """Display an equlizer looking animation with random values.
    """
    global STOP_THREAD
    while True:
        if STOP_THREAD:
            STOP_THREAD = False
            return
        # Lower values more likely, makes it look nicer
        weights = [i*i for i in range(33, 0, -1)]
        population = list(range(1, 34))
        vals = random.choices(population, weights=weights, k=9)
        eq(vals)
        time.sleep(0.2)


def eq(vals):
    """Display 9 values in equalizer diagram starting from the middle, going up and down"""
    matrix = [[0 for _ in range(34)] for _ in range(9)]

    for (col, val) in enumerate(vals[:9]):
        row = int(34 / 2)
        above = int(val / 2)
        below = val - above

        for i in range(above):
            matrix[col][row+i] = 0xFF
        for i in range(below):
            matrix[col][row-1-i] = 0xFF

    render_matrix(matrix)


def render_matrix(matrix):
    """Show a black/white matrix
    Send everything in a single command"""
    vals = [0x00 for _ in range(39)]

    for x in range(9):
        for y in range(34):
            i = x + 9*y
            if matrix[x][y]:
                vals[int(i/8)] = vals[int(i/8)] | (1 << i % 8)

    send_command(CommandVals.Draw, vals)


def light_leds(leds):
    """ Light a specific number of LEDs """
    vals = [0x00 for _ in range(39)]
    for byte in range(int(leds / 8)):
        vals[byte] = 0xFF
    for i in range(leds % 8):
        vals[int(leds / 8)] += 1 << i
    send_command(CommandVals.Draw, vals)


def pattern(p):
    """Display a pattern that's already programmed into the firmware"""
    if p == 'All LEDs on':
        send_command(CommandVals.Pattern, [PatternVals.FullBrightness])
    elif p == 'Gradient (0-13% Brightness)':
        send_command(CommandVals.Pattern, [PatternVals.Gradient])
    elif p == 'Double Gradient (0-7-0% Brightness)':
        send_command(CommandVals.Pattern, [PatternVals.DoubleGradient])
    elif p == '"LOTUS" sideways':
        send_command(CommandVals.Pattern, [PatternVals.DisplayLotus])
    elif p == 'Zigzag':
        send_command(CommandVals.Pattern, [PatternVals.ZigZag])
    elif p == '"PANIC"':
        send_command(CommandVals.Pattern, [PatternVals.DisplayPanic])
    elif p == '"LOTUS" Top Down':
        send_command(CommandVals.Pattern, [PatternVals.DisplayLotus2])
    elif p == 'All brightness levels (1 LED each)':
        all_brightnesses()
    else:
        print("Invalid pattern")


def show_string(s):
    """Render a string with up to five letters"""
    show_font([convert_font(letter) for letter in str(s)[:5]])


def show_font(font_items):
    """Render up to five 5x6 pixel font items"""
    vals = [0x00 for _ in range(39)]

    for digit_i, digit_pixels in enumerate(font_items):
        offset = digit_i * 7
        for pixel_x in range(5):
            for pixel_y in range(6):
                pixel_value = digit_pixels[pixel_x + pixel_y*5]
                i = (2+pixel_x) + (9*(pixel_y+offset))
                if pixel_value:
                    vals[int(i/8)] = vals[int(i/8)] | (1 << i % 8)

    send_command(CommandVals.Draw, vals)


def show_symbols(symbols):
    """Render a list of up to five symbols
    Can use letters/numbers or symbol names, like 'sun', ':)'"""
    font_items = []
    for symbol in symbols:
        s = convert_symbol(symbol)
        if not s:
            s = convert_font(symbol)
        font_items.append(s)

    show_font(font_items)


def clock():
    """Render the current time and display.
    Loops forever, updating every second"""
    global STOP_THREAD
    while True:
        if STOP_THREAD:
            STOP_THREAD = False
            return
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        print("Current Time =", current_time)

        show_string(current_time)
        time.sleep(1)


def send_command(command, parameters=[], with_response=False):
    return send_command_raw(FWK_MAGIC + [command] + parameters, with_response)


def send_command_raw(command, with_response=False):
    """Send a command to the device.
    Opens new serial connection every time"""
    # print(f"Sending command: {command}")
    global SERIAL_DEV
    with serial.Serial(SERIAL_DEV, 115200) as s:
        s.write(command)

        if with_response:
            res = s.read(RESPONSE_SIZE)
            # print(f"Received: {res}")
            return res


def send_serial(s, command):
    """Send serial command by using existing serial connection"""
    global SERIAL_DEV
    s.write(command)


def gui():
    import PySimpleGUI as sg

    layout = [
        [sg.Text("Bootloader")],
        [sg.Button("Bootloader")],

        [sg.Text("Brightness")],
        # TODO: Get default from device
        [sg.Slider((0, 255), orientation='h', default_value=120,
                   k='-BRIGHTNESS-', enable_events=True)],

        [sg.Text("Animation")],
        [sg.Button("Start Animation"), sg.Button("Stop Animation")],

        [sg.Text("Pattern")],
        [sg.Combo(PATTERNS, k='-PATTERN-', enable_events=True)],

        [sg.Text("Fill screen X% (could be volume indicator)")],
        [sg.Slider((0, 100), orientation='h',
                   k='-PERCENTAGE-', enable_events=True)],

        [sg.Text("Countdown Timer")],
        [
            sg.Spin([i for i in range(1, 60)],
                    initial_value=10, k='-COUNTDOWN-'),
            sg.Text("Seconds"),
            sg.Button("Start", k='-START-COUNTDOWN-'),
            sg.Button("Stop", k='-STOP-COUNTDOWN-'),
        ],

        [sg.Text("Black&White Image")],
        [sg.Button("Send stripe.gif", k='-SEND-BL-IMAGE-')],

        [sg.Text("Greyscale Image")],
        [sg.Button("Send greyscale.gif", k='-SEND-GREY-IMAGE-')],

        [sg.Text("Display Current Time")],
        [
            sg.Button("Start", k='-START-TIME-'),
            sg.Button("Stop", k='-STOP-TIME-')
        ],

        [sg.Text("Display Text with Symbols")],
        [sg.Button("Send '2 5 degC thunder'", k='-SEND-TEXT-')],

        # TODO
        # [sg.Text("Play Snake")],
        # [sg.Button("Start Game", k='-PLAY-SNAKE-')],

        [sg.Text("Equalizer")],
        [
            sg.Button("Start random equalizer", k='-RANDOM-EQ-'),
            sg.Button("Stop", k='-STOP-EQ-')
        ],

        [sg.Text("Sleep")],
        [sg.Button("Sleep"), sg.Button("Wake")],
        # [sg.Button("Panic")]

        [sg.Button("Quit")]
    ]
    window = sg.Window("LED Matrix Control", layout)
    global STOP_THREAD
    while True:
        event, values = window.read()
        # print('Event', event)
        # print('Values', values)

        if event == "Quit" or event == sg.WIN_CLOSED:
            break

        if event == "Bootloader":
            bootloader()

        if event == '-PATTERN-':
            pattern(values['-PATTERN-'])

        if event == 'Start Animation':
            animate(True)

        if event == 'Stop Animation':
            animate(False)

        if event == '-BRIGHTNESS-':
            brightness(int(values['-BRIGHTNESS-']))

        if event == '-PERCENTAGE-':
            percentage(int(values['-PERCENTAGE-']))

        if event == '-START-COUNTDOWN-':
            thread = threading.Thread(target=countdown, args=(
                int(values['-COUNTDOWN-']),), daemon=True)
            thread.start()
        if event == '-STOP-COUNTDOWN-':
            STOP_THREAD = True

        if event == '-SEND-BL-IMAGE-':
            image_bl('stripe.gif')

        if event == '-SEND-GREY-IMAGE-':
            image_greyscale('greyscale.gif')

        if event == '-START-TIME-':
            thread = threading.Thread(target=clock, args=(), daemon=True)
            thread.start()
        if event == '-STOP-TIME-':
            STOP_THREAD = True

        if event == '-SEND-TEXT-':
            show_symbols(['2', '5', 'degC', ' ', 'thunder'])

        if event == '-PLAY-SNAKE-':
            snake()

        if event == '-RANDOM-EQ-':
            thread = threading.Thread(target=random_eq, args=(), daemon=True)
            thread.start()
        if event == '-STOP-EQ-':
            STOP_THREAD = True

        if event == 'Sleep':
            send_command(CommandVals.Sleep, [True])

        if event == 'Wake':
            send_command(CommandVals.Sleep, [False])

    window.close()


def display_string(disp_str):
    b = [ord(x) for x in disp_str]
    send_command(CommandVals.SetText, [len(disp_str)] + b)


def display_on_cmd(on):
    send_command(CommandVals.DisplayOn, [on])


def invert_screen_cmd(invert):
    send_command(CommandVals.InvertScreen, [invert])


def screen_saver_cmd(on):
    send_command(CommandVals.ScreenSaver, [on])


def set_fps_cmd(mode):
    res = send_command(CommandVals.SetFps, with_response=True)
    current_fps = res[0]

    if mode == 'quarter':
        fps = current_fps & ~LOW_FPS_MASK
        fps |= 0b000
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('low')
    elif mode == 'half':
        fps = current_fps & ~LOW_FPS_MASK
        fps |= 0b001
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('low')
    elif mode == 'one':
        fps = current_fps & ~LOW_FPS_MASK
        fps |= 0b010
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('low')
    elif mode == 'two':
        fps = current_fps & ~LOW_FPS_MASK
        fps |= 0b011
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('low')
    elif mode == 'four':
        fps = current_fps & ~LOW_FPS_MASK
        fps |= 0b100
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('low')
    elif mode == 'eight':
        fps = current_fps & ~LOW_FPS_MASK
        fps |= 0b101
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('low')
    elif mode == 'sixteen':
        fps = current_fps & ~HIGH_FPS_MASK
        fps |= 0b00000000
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('high')
    elif mode == 'thirtytwo':
        fps = current_fps & ~HIGH_FPS_MASK
        fps |= 0b00010000
        send_command(CommandVals.SetFps, [fps])
        set_power_mode_cmd('high')


def set_power_mode_cmd(mode):
    if mode == 'low':
        send_command(CommandVals.SetPowerMode, [0])
    elif mode == 'high':
        send_command(CommandVals.SetPowerMode, [1])
    else:
        print("Unsupported power mode")
        sys.exit(1)

def get_power_mode_cmd():
    res = send_command(CommandVals.SetPowerMode, with_response=True)
    current_mode = int(res[0])
    if current_mode == 0:
        print(f"Current Power Mode: Low Power")
    elif current_mode == 1:
        print(f"Current Power Mode: High Power")

def get_fps_cmd():
    res = send_command(CommandVals.SetFps, with_response=True)
    current_fps = res[0]
    res = send_command(CommandVals.SetPowerMode, with_response=True)
    current_mode = int(res[0])

    if current_mode == 0:
        current_fps &= LOW_FPS_MASK
        if current_fps == 0:
            fps = 0.25
        elif current_fps == 1:
            fps = 0.5
        else:
            fps = 2 ** (current_fps - 2)
    elif current_mode == 1:
        if current_fps & HIGH_FPS_MASK:
            fps = 32
        else:
            fps = 16

    print(f"Current FPS: {fps}")


# 5x6 symbol font. Leaves 2 pixels on each side empty
# We can leave one row empty below and then the display fits 5 of these digits.


def convert_symbol(symbol):
    symbols = {
        'degC': [
            0, 0, 0, 1, 1,
            0, 0, 0, 1, 1,
            1, 1, 1, 0, 0,
            1, 0, 0, 0, 0,
            1, 0, 0, 0, 0,
            1, 1, 1, 0, 0,
        ],
        'degF': [
            0, 0, 0, 1, 1,
            0, 0, 0, 1, 1,
            1, 1, 1, 0, 0,
            1, 0, 0, 0, 0,
            1, 1, 1, 0, 0,
            1, 0, 0, 0, 0,
        ],
        'snow': [
            0, 0, 0, 0, 0,
            1, 0, 1, 0, 1,
            0, 1, 1, 1, 0,
            1, 1, 1, 1, 1,
            0, 1, 1, 1, 0,
            1, 0, 1, 0, 1,
        ],
        'sun': [
            0, 0, 0, 0, 0,
            0, 1, 1, 1, 0,
            1, 1, 1, 1, 1,
            1, 1, 1, 1, 1,
            1, 1, 1, 1, 1,
            0, 1, 1, 1, 0,
        ],
        'cloud': [
            0, 0, 0, 0, 0,
            0, 1, 1, 1, 0,
            1, 1, 1, 1, 1,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],
        'rain': [
            0, 1, 1, 1, 0,
            1, 1, 1, 1, 1,
            1, 1, 1, 1, 1,
            0, 1, 0, 0, 1,
            0, 0, 1, 0, 0,
            1, 0, 0, 1, 0,
        ],
        'thunder': [
            0, 1, 1, 1, 0,
            1, 1, 1, 1, 1,
            1, 1, 1, 1, 1,
            0, 0, 1, 0, 0,
            0, 1, 0, 0, 0,
            0, 0, 1, 0, 0,
        ],
        'batteryLow': [
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            1, 1, 1, 1, 0,
            1, 0, 0, 1, 1,
            1, 0, 0, 1, 1,
            1, 1, 1, 1, 0,
        ],
        '!!': [
            0, 1, 0, 1, 0,
            0, 1, 0, 1, 0,
            0, 1, 0, 1, 0,
            0, 0, 0, 0, 0,
            0, 1, 0, 1, 0,
            0, 1, 0, 1, 0,
        ],
        'heart': [
            0, 0, 0, 0, 0,
            1, 1, 0, 1, 1,
            1, 1, 1, 1, 1,
            0, 1, 1, 1, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
        ],
        'heart0': [
            1, 1, 0, 1, 1,
            1, 1, 1, 1, 1,
            0, 1, 1, 1, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],
        'heart2': [
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            1, 1, 0, 1, 1,
            1, 1, 1, 1, 1,
            0, 1, 1, 1, 0,
            0, 0, 1, 0, 0,
        ],
        ':)': [
            0, 0, 0, 0, 0,
            0, 1, 0, 1, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            1, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
        ],
        ':|': [
            0, 0, 0, 0, 0,
            0, 1, 0, 1, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 0,
        ],
        ':(': [
            0, 0, 0, 0, 0,
            0, 1, 0, 1, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 1,
        ],
        ';)': [
            0, 0, 0, 0, 0,
            1, 1, 0, 1, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            1, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
        ],
    }
    if symbol in symbols:
        return symbols[symbol]
    else:
        return None


def convert_font(num):
    """ 5x6 font. Leaves 2 pixels on each side empty
    We can leave one row empty below and then the display fits 5 of these digits."""
    font = {
        '0': [
            0, 1, 1, 0, 0,
            1, 0, 0, 1, 0,
            1, 0, 0, 1, 0,
            1, 0, 0, 1, 0,
            1, 0, 0, 1, 0,
            0, 1, 1, 0, 0,
        ],

        '1': [
            0, 0, 1, 0, 0,
            0, 1, 1, 0, 0,
            1, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            1, 1, 1, 1, 1,
        ],

        '2': [
            1, 1, 1, 1, 0,
            0, 0, 0, 0, 1,
            1, 1, 1, 1, 1,
            1, 0, 0, 0, 0,
            1, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
        ],

        '3': [
            1, 1, 1, 1, 0,
            0, 0, 0, 0, 1,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 1,
            0, 0, 0, 0, 1,
            1, 1, 1, 1, 0,
        ],

        '4': [
            0, 0, 0, 1, 0,
            0, 0, 1, 1, 0,
            0, 1, 0, 1, 0,
            1, 1, 1, 1, 1,
            0, 0, 0, 1, 0,
            0, 0, 0, 1, 0,
        ],

        '5': [
            1, 1, 1, 1, 1,
            1, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 1,
            0, 0, 0, 0, 1,
            1, 1, 1, 1, 0,
        ],

        '6': [
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
        ],

        '7': [
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 1,
            0, 0, 0, 1, 0,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
        ],

        '8': [
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
        ],

        '9': [
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 1,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 1,
            0, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
        ],

        ':': [
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
        ],

        ' ': [
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],

        '?': [
            0, 1, 1, 0, 0,
            0, 0, 0, 1, 0,
            0, 0, 0, 1, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 1, 0, 0,
        ],

        '.': [
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],

        ',': [
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],

        '!': [
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 1, 0, 0,
        ],

        '/': [
            0, 0, 0, 0, 1,
            0, 0, 0, 1, 1,
            0, 0, 1, 1, 0,
            0, 1, 1, 0, 0,
            1, 1, 0, 0, 0,
            1, 0, 0, 0, 0,
        ],

        '*': [
            0, 0, 0, 0, 0,
            0, 1, 0, 1, 0,
            0, 0, 1, 0, 0,
            0, 1, 0, 1, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],

        '%': [
            1, 1, 0, 0, 1,
            1, 1, 0, 1, 1,
            0, 0, 1, 1, 0,
            0, 1, 1, 0, 0,
            1, 1, 0, 1, 1,
            1, 0, 0, 1, 1,
        ],

        '+': [
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            1, 1, 1, 1, 1,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0,
        ],

        '-': [
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],

        '=': [
            0, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        ],
        'A': [
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 1,
            1, 1, 1, 1, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
        ],
        'D': [
            1, 1, 1, 1, 0,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            1, 1, 1, 1, 0,
        ],
        'O': [
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
        ],
        'V': [
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            0, 1, 0, 1, 1,
            0, 1, 0, 1, 1,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
        ],
        'E': [
            1, 1, 1, 1, 1,
            1, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
            1, 0, 0, 0, 0,
            1, 0, 0, 0, 0,
            1, 1, 1, 1, 1,
        ],
        'R': [
            1, 1, 1, 1, 0,
            1, 0, 0, 1, 0,
            1, 1, 1, 1, 0,
            1, 1, 0, 0, 0,
            1, 0, 1, 0, 0,
            1, 0, 0, 1, 0,
        ],
        'G': [
            0, 1, 1, 1, 0,
            1, 0, 0, 0, 0,
            1, 0, 1, 1, 1,
            1, 0, 0, 0, 1,
            1, 0, 0, 0, 1,
            0, 1, 1, 1, 0,
        ],
        'M': [
            0, 0, 0, 0, 0,
            0, 1, 0, 1, 0,
            1, 0, 1, 0, 1,
            1, 0, 1, 0, 1,
            1, 0, 1, 0, 1,
            1, 0, 1, 0, 1,
        ],
        'P': [
            1, 1, 1, 0, 0,
            1, 0, 0, 1, 0,
            1, 0, 0, 1, 0,
            1, 1, 1, 0, 0,
            1, 0, 0, 0, 0,
            1, 0, 0, 0, 0,
        ],
    }
    if num in font:
        return font[num]
    else:
        return font['?']


if __name__ == "__main__":
    main()
