import time
import machine
import badger2040
from array import array
from qrcode import QRCode
from micropython import schedule
from vcard import VCard


def scale(input, in_min, in_max, out_min, out_max):
    return (((input - in_min) * (out_max - out_min)) / (in_max - in_min)) + out_min


class BadgeButtons:
    BUTTONS = {
        badger2040.BUTTON_A,
        badger2040.BUTTON_B,
        badger2040.BUTTON_C,
        badger2040.BUTTON_UP,
        badger2040.BUTTON_DOWN,
    }

    def __init__(self, bounce_ms=250, queue_len=8):
        buttons = [
            (pin, machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN))
            for pin in self.BUTTONS
        ]
        last_ticks = {}
        queue = array('I', [0] * (queue_len * 2))
        queue_pos = 0
        self._handlers = {}

        # Closure to work around the inability to call a bound method from an
        # interrupt handler. This is also the reason we're using a
        # pre-allocated array as a rudimentary queue. The interrupt handler
        # here just pushes the time and pin of the button pressed to the
        # "queue" and schedules another callback to deal with it later
        def pressed(btn):
            nonlocal queue_pos
            t = time.ticks_ms()
            for pin, obj in buttons:
                if obj is btn:
                    if queue_pos < len(queue):
                        queue[queue_pos] = t
                        queue[queue_pos + 1] = pin
                        queue_pos += 2
                        schedule(dispatch, None)
                    break

        # The actual dispatcher. Another closure, but this one is only called
        # from the main "thread". Handles popping times and pins off the
        # "queue" and executing the associated handler if the last call-time
        # was within the bounce timeout
        def dispatch(arg):
            nonlocal queue_pos
            while True:
                # Disable interrupts while we mess with the queue pointer
                state = machine.disable_irq()
                try:
                    if not queue_pos:
                        break
                    ticks = queue[0]
                    pin = queue[1]
                    queue[:-2] = queue[2:]
                    queue_pos -= 2
                finally:
                    machine.enable_irq(state)
                try:
                    last = last_ticks[pin]
                except KeyError:
                    pass
                else:
                    diff = time.ticks_diff(ticks, last)
                    if diff < bounce_ms:
                        continue
                last_ticks[pin] = ticks
                try:
                    handler = self._handlers[pin]
                except KeyError:
                    pass
                else:
                    handler()

        for pin, btn in buttons:
            btn.irq(pressed, machine.Pin.IRQ_RISING, hard=True)

    def __getitem__(self, key):
        return self._handlers[key]

    def __setitem__(self, key, value):
        self._handlers[key] = value

    def __delitem__(self, key):
        del self._handlers[key]


class Badge:
    BATTERY_MIN_V = 3.2
    BATTERY_MAX_V = 4.0
    FONT_HEIGHT = 28

    def __init__(self):
        self.vbat_adc = machine.ADC(badger2040.PIN_BATTERY)
        self.vref_adc = machine.ADC(badger2040.PIN_1V2_REF)
        self.vref_en = machine.Pin(badger2040.PIN_VREF_POWER, machine.Pin.OUT,
                                   value=0)
        self.handlers = BadgeButtons()
        self._screen = badger2040.Badger2040()
        self._screen.update_speed(badger2040.UPDATE_FAST)

    @property
    def battery_v(self):
        self.vref_en.value(1)
        try:
            # Calculate the logic supply voltage, as will be lower that the
            # usual 3.3V when running off low batteries
            vdd = 1.24 * (65535 / self.vref_adc.read_u16())
            # 3 in this is a gain, not rounding of 3.3V
            return (self.vbat_adc.read_u16() / 65535) * 3 * vdd
        finally:
            self.vref_en.value(0)

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
            level = scale(
                self.battery_v, self.BATTERY_MIN_V, self.BATTERY_MAX_V, 0, 4)
        # Outline
        self._screen.thickness(1)
        self._screen.pen(15)
        self._screen.rectangle(x, y, 19, 10)
        # Terminal
        self._screen.rectangle(x + 19, y + 3, 2, 4)
        self._screen.pen(0)
        self._screen.rectangle(x + 1, y + 1, 17, 8)
        if level < 1:
            self._screen.pen(0)
            self._screen.line(x + 3, y, x + 3 + 10, y + 10)
            self._screen.line(x + 3 + 1, y, x + 3 + 11, y + 10)
            self._screen.pen(15)
            self._screen.line(x + 2 + 2, y - 1, x + 4 + 12, y + 11)
            self._screen.line(x + 2 + 3, y - 1, x + 4 + 13, y + 11)
            return
        # Battery Bars
        self._screen.pen(15)
        for i in range(4):
            if level / 4 > (1.0 * i) / 4:
                self._screen.rectangle(i * 4 + x + 2, y + 2, 3, 6)


def main():
    cards = [
        VCard(
            given_names='Dave',
            family_names='Jones',
            nickname='waveform',
            org=['Canonical', 'Foundations'],
            email='dave.jones@canonical.com',
            url='https://waldorf.waveform.org.uk/',
            image='canonical'),
        VCard(
            given_names='Dave',
            family_names='Jones',
            nickname='waveform',
            org=['Canonical', 'Foundations'],
            email='waveform@ubuntu.com',
            url='https://waldorf.waveform.org.uk/',
            image='ubuntu'),
        VCard(
            given_names='Dave',
            family_names='Jones',
            nickname='waveform',
            email='dave@waveform.org.uk',
            url='https://github.com/waveform80/',
            image='face'),
    ]
    card = 0
    show_qr = False
    badge = Badge()

    def refresh():
        badge.clear()
        if show_qr:
            badge.draw_qrcode(cards[card])
        else:
            badge.draw_card(cards[card])
        badge.update()

    def prior_card():
        nonlocal card, show_qr
        show_qr = False
        card = (card - 1) % len(cards)
        refresh()

    def next_card():
        nonlocal card, show_qr
        show_qr = False
        card = (card + 1) % len(cards)
        refresh()

    def toggle_qr():
        nonlocal show_qr
        show_qr = not show_qr
        refresh()

    def clean():
        badge.clean()
        refresh()

    badge.handlers[badger2040.BUTTON_UP] = prior_card
    badge.handlers[badger2040.BUTTON_DOWN] = next_card
    badge.handlers[badger2040.BUTTON_B] = toggle_qr
    badge.handlers[badger2040.BUTTON_C] = clean
    refresh()


main()
