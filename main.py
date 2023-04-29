import time
import machine
import badger2040
from qrcode import QRCode
from vcard import VCard


def scale(input, in_min, in_max, out_min, out_max):
    return (((input - in_min) * (out_max - out_min)) / (in_max - in_min)) + out_min


class Badge:
    BATTERY_MIN_V = 3.2
    BATTERY_MAX_V = 4.0
    FONT_HEIGHT = 28

    def __init__(self):
        self.vbat_adc = machine.ADC(badger2040.PIN_BATTERY)
        self.vref_adc = machine.ADC(badger2040.PIN_1V2_REF)
        self.vref_en = machine.Pin(badger2040.PIN_VREF_POWER, machine.Pin.OUT,
                                   value=0)
        # Read the state of all buttons into a "pressed" set. This is a
        # one-shot programme so we expect one or more buttons woke us up. We'll
        # update the display in response then halt
        self.pressed = {
            pin
            for pin in (
                badger2040.BUTTON_A,
                badger2040.BUTTON_B,
                badger2040.BUTTON_C,
                badger2040.BUTTON_UP,
                badger2040.BUTTON_DOWN,
            )
            if machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN).value()
        }
        self._screen = badger2040.Badger2040()
        self._screen.update_speed(badger2040.UPDATE_FAST)

    @property
    def battery_v(self):
        self.vref_en.value(1)
        try:
            # Calculate the logic supply voltage, as will be lower than the
            # usual 3.3V when running off low batteries
            vdd = 1.24 * (65535 / self.vref_adc.read_u16())
            # 3 in this is a gain, not rounding of 3.3V
            return (self.vbat_adc.read_u16() / 65535) * 3 * vdd
        finally:
            self.vref_en.value(0)

    @property
    def battery_level(self):
        return scale(
            self.battery_v, self.BATTERY_MIN_V, self.BATTERY_MAX_V, 0, 4)

    def clean(self):
        self._screen.update_speed(badger2040.UPDATE_MEDIUM)
        self.clear()
        self.update()
        self._screen.update_speed(badger2040.UPDATE_FAST)

    def clear(self):
        blank = bytearray(b'\x00' * (badger2040.WIDTH * badger2040.HEIGHT // 8))
        self._screen.image(blank)

    def update(self):
        self._screen.update()

    def halt(self):
        # On battery this switches off power; we light the LED to "prove" we've
        # actually halted. On USB this will continue to the infinite loop with
        # the LED lit
        self._screen.halt()
        self._screen.led(255)
        while True:
            self._screen.halt()

    def draw_error(self, msg):
        self._screen.font('sans')
        self._screen.pen(0)
        self._screen.thickness(2)
        self._screen.text(msg, 0, 0, 0.5)

    def draw_qrcode(self, card):
        code = QRCode()
        code.set_text(str(card))
        size = code.get_size()[0] # it's square ... why return two values?
        scale = min(badger2040.WIDTH, badger2040.HEIGHT) // size
        if scale < 1:
            raise ValueError('QR Code too big to display')
        w = h = size * scale
        x = (badger2040.WIDTH - w) // 2
        y = (badger2040.HEIGHT - h) // 2
        w += -w % 8 # pad to next multiple of 8
        buf = bytearray(
            sum(
                code.get_module((x + (7 - bit)) // scale, y // scale) << bit
                for bit in range(8)
            )
            for y in range(h)
            for x in range(0, w, 8)
        )
        self._screen.image(buf, w, h, x, y)

    def draw_card(self, card):
        lines = [
            # (pen-weight, size, text)
            (3, 1.0, f'{card.given_names[0]} {card.family_names[0]}'),
            (1, 0.8, f'"{card.nickname}"'),
            (2, 0.8, f'{card.org[-1] if card.org else ""}'),
            (1, 0.5, card.email),
        ]
        self._screen.font('sans')
        self._screen.pen(0)
        if card.image:
            buf, w, h = card.image
            card_width = w + 4
            card_height = h
        else:
            card_width = card_height = 0
        card_width += max(
            self._screen.measure_text(text, size)
            for weight, size, text in lines
        )
        card_height = max(card_height, sum(
            int(self.FONT_HEIGHT * size)
            for weight, size, text in lines
            if text
        ))
        x = (badger2040.WIDTH - card_width) // 2
        y = (badger2040.HEIGHT - card_height) // 2
        if card.image:
            buf, w, h = card.image
            self._screen.image(buf, w, h, x, y)
            x += w + 4
        for weight, size, text in lines:
            if text:
                h = int(self.FONT_HEIGHT * size) // 2
                y += h
                self._screen.thickness(weight)
                self._screen.text(text, x, y, size)
                y += int(self.FONT_HEIGHT * size) - h

    def draw_battery(self, x, y, level=None):
        if level is None:
            level = self.battery_level
        # Outline
        self._screen.thickness(1)
        self._screen.pen(0)
        self._screen.rectangle(x, y, 19, 10)
        # Terminal
        self._screen.rectangle(x + 19, y + 3, 2, 4)
        self._screen.pen(15)
        self._screen.rectangle(x + 1, y + 1, 17, 8)
        if level < 1:
            self._screen.pen(15)
            self._screen.line(x + 3, y, x + 3 + 10, y + 10)
            self._screen.line(x + 3 + 1, y, x + 3 + 11, y + 10)
            self._screen.pen(0)
            self._screen.line(x + 2 + 2, y - 1, x + 4 + 12, y + 11)
            self._screen.line(x + 2 + 3, y - 1, x + 4 + 13, y + 11)
            return
        # Battery Bars
        self._screen.pen(0)
        for i in range(4):
            if level / 4 > (1.0 * i) / 4:
                self._screen.rectangle(i * 4 + x + 2, y + 2, 3, 6)


cards = {
    badger2040.BUTTON_A: VCard(
        given_names='Dave',
        family_names='Jones',
        nickname='waveform',
        email='dave@waveform.org.uk',
        url='https://github.com/waveform80/',
        image='face'),
    badger2040.BUTTON_B: VCard(
        given_names='Dave',
        family_names='Jones',
        nickname='waveform',
        org=['Canonical', 'Foundations'],
        email='waveform@ubuntu.com',
        url='https://waldorf.waveform.org.uk/',
        image='new-ubuntu'),
    badger2040.BUTTON_C: VCard(
        given_names='Dave',
        family_names='Jones',
        nickname='waveform',
        org=['Canonical', 'Foundations'],
        email='dave.jones@canonical.com',
        url='https://waldorf.waveform.org.uk/',
        image='canonical'),
}
print('Starting up')
badge = Badge()
try:
    show_qr = bool(
        {badger2040.BUTTON_DOWN, badger2040.BUTTON_UP} & badge.pressed)
    identity = set(cards) & badge.pressed
    if len(identity) > 1:
        raise RuntimeError('More than one identity selected!')
    elif len(identity) == 0:
        raise RuntimeError('No identity selected!')
    identity = identity.pop()
    badge.clear()
    if show_qr:
        print(f'Showing QR code for {cards[identity].email}')
        badge.draw_qrcode(cards[identity])
    else:
        print(f'Showing badge for {cards[identity].email}')
        badge.draw_card(cards[identity])
    level = badge.battery_level
    if show_qr or level < 3:
        badge.draw_battery(275, 1, level=level)
    badge.update()
finally:
    time.sleep(1)
    badge.halt()
