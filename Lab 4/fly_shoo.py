"""Press the Qwiic joystick button to sweep channel 0 and display SHOO."""
import signal
import time

import board
import adafruit_ssd1306
import pi_servo_hat
import qwiic_joystick

# Small built-in font: no external font file is needed.
FONT = {
    'S': ('01111', '10000', '10000', '01110', '00001', '00001', '11110'),
    'H': ('10001', '10001', '10001', '11111', '10001', '10001', '10001'),
    'O': ('01110', '10001', '10001', '10001', '10001', '10001', '01110'),
    'R': ('11110', '10001', '10001', '11110', '10100', '10010', '10001'),
    'E': ('11111', '10000', '10000', '11110', '10000', '10000', '11111'),
    'A': ('01110', '10001', '10001', '11111', '10001', '10001', '10001'),
    'D': ('11110', '10001', '10001', '10001', '10001', '10001', '11110'),
    'Y': ('10001', '10001', '01010', '00100', '00100', '00100', '00100'),
}


def show(screen, word):
    scale = 4
    x0 = (128 - (len(word) * 6 - 1) * scale) // 2
    screen.fill(0)
    for index, letter in enumerate(word):
        for y, row in enumerate(FONT[letter]):
            for x, pixel in enumerate(row):
                if pixel == '1':
                    screen.fill_rect(x0 + (index * 6 + x) * scale,
                                     2 + y * scale, scale, scale, 1)
    screen.show()


def main():
    joystick = qwiic_joystick.QwiicJoystick()
    if not joystick.connected:
        raise RuntimeError('Qwiic joystick not detected; check its cable.')
    joystick.begin()
    screen = adafruit_ssd1306.SSD1306_I2C(128, 32, board.I2C())
    servo = pi_servo_hat.PiServoHat()
    servo.restart()

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        servo.move_servo_position(0, 60)
        show(screen, 'READY')
        print('READY: press joystick straight down. Ctrl+C to stop.', flush=True)
        armed = False
        released_since = None
        while True:
            pressed = joystick.button == 0
            if not pressed:
                if released_since is None:
                    released_since = time.monotonic()
                if time.monotonic() - released_since >= 0.1:
                    armed = True
            else:
                released_since = None
                if armed:
                    time.sleep(0.03)
                    if joystick.button == 0:
                        armed = False
                        show(screen, 'SHOO')
                        print('SHOO: sweeping', flush=True)
                        position = 60
                        for target in (30, 90, 30, 90, 30, 90, 60):
                            step = 3 if target > position else -3
                            for angle in range(position, target, step):
                                servo.move_servo_position(0, angle)
                                time.sleep(0.02)
                            servo.move_servo_position(0, target)
                            position = target
                        time.sleep(0.4)
                        show(screen, 'READY')
                        print('READY', flush=True)
            time.sleep(0.02)
    except KeyboardInterrupt:
        print('Stopping demo.', flush=True)
    finally:
        try:
            servo.move_servo_position(0, 60)
        finally:
            show(screen, 'READY')


if __name__ == '__main__':
    main()
