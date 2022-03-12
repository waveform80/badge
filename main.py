import machine
import badger2040


def scale(input, in_min, in_max, out_min, out_max):
    return (((input - in_min) * (out_max - out_min)) / (in_max - in_min)) + out_min


class Card:
    IMAGES = {
        'ubuntu':    ('ubuntu.bin', 64, 64),
        'canonical': ('canonical.bin', 64, 64),
    }

    def __init__(self, *, given_names, family_names, middle_names=None,
                 prefixes=None, suffixes=None, nickname=None, title=None,
                 position=None, org=None, address=None, email=None,
                 url=None, tel=None, impp=None, gender=None, image=None,
                 notes=None):
        as_tuple = lambda v: () if v is None else (v,) if isinstance(v, str) else tuple(v)
        as_str = lambda v: '' if v is None else str(v)

        self.given_names = as_tuple(given_names)
        self.family_names = as_tuple(family_names)
        self.middle_names = as_tuple(middle_names)
        self.prefixes = as_tuple(prefixes)
        self.suffixes = as_tuple(suffixes)
        self.nickname = as_str(nickname)
        self.title = as_str(title)
        self.position = as_str(position)
        self.org = as_tuple(org)
        self.address = as_str(address)
        self.email = as_str(email)
        self.url = as_str(url)
        self.tel = as_str(tel)
        self.impp = as_str(impp)
        self.gender = as_str(gender)
        self.notes = as_str(notes)
        if image is None:
            self.image = None
        else:
            fn, w, h = self.IMAGES[image]
            with open('/images/{fn}'.format(fn=fn), 'rb') as f:
                self.image = (bytearray(f.read()), w, h)

    def as_vcard(self):
        def quote_str(s, special='\n,'):
            if isinstance(s, str):
                s = s.replace('\\', '\\\\')
                for c in special:
                    s = s.replace(c, '\\' + c)
                return s
            else:
                return ','.join(quote_str(elem, special) for elem in s)

        def quote_list(l):
            return ';'.join(quote_str(item, special='\n,;') for item in l)

        fields = {
            'FN': ' '.join(
                s for s in (
                    ', '.join(self.prefixes),
                    ' '.join(self.given_names),
                    ' '.join(self.middle_names),
                    ' '.join(self.family_names),
                    ', '.join(self.suffixes),
                ) if s
            ),
            'N': [
                self.family_names,
                self.given_names,
                self.middle_names,
                self.prefixes,
                self.suffixes,
            ],
            'NICKNAME': self.nickname,
            'GENDER':   self.gender,
            'TEL':      self.tel,
            'EMAIL':    self.email,
            'IMPP':     self.impp,
            'URL':      self.url,
            'TITLE':    self.position,
            'ORG':      list(self.org),
            'NOTE':     self.notes,
        }
        return """\
BEGIN:VCARD
VERSION:4.0
{fields}
END:VCARD
""".format(fields='\n'.join(
    '{field}:{value}'.format(
        field=field,
        value=quote_str(value) if isinstance(value, str) else quote_list(value)
    )
    for field, value in fields.items()
    if value
))


class Badge:
    BATTERY_MIN_V = 3.2
    BATTERY_MAX_V = 4.0

    BUTTONS = {
        'a':    badger2040.BUTTON_A,
        'b':    badger2040.BUTTON_B,
        'c':    badger2040.BUTTON_C,
        'up':   badger2040.BUTTON_UP,
        'down': badger2040.BUTTON_DOWN,
    }

    def __init__(self):
        self.vbat_adc = machine.ADC(badger2040.PIN_BATTERY)
        self.vref_adc = machine.ADC(badger2040.PIN_1V2_REF)
        self.vref_en = machine.Pin(badger2040.PIN_VREF_POWER, machine.Pin.OUT,
                                   value=0)
        self.buttons = {
            key: machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
            for key, pin in self.BUTTONS.items()
        }
        self.screen = badger2040.Badger2040()

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

    def clear(self):
        self.screen.image(bytearray(b'\x00' * (296 * 128 // 8)))

    def update(self):
        self.screen.update()

    def draw_image(self, x, y, image):
        buf, w, h = self.images[image]
        self.screen.image(buf, w, h, x, y)

    def draw_card(self, x, y, card):
        if card.image:
            buf, w, h = card.image
            self.screen.image(buf, w, h, x, y)
            x += w + 4
        lines = (
            card.given_names[0] + ' ' + card.family_names[0],
            '"' + card.nickname + '"',
            card.org[-1],
            card.email,
        )
        thicknesses = (3, 1, 2, 1)
        sizes = (1, 0.8, 0.8, 0.5)
        self.screen.font('sans')
        self.screen.pen(0)
        for thickness, size, line in zip(thicknesses, sizes, lines):
            y += int(12 * size)
            self.screen.thickness(thickness)
            self.screen.text(line, x, y, size)
            y += int(12 * size) + 6

    def draw_battery(self, x, y, level=None):
        if level is None:
            level = scale(
                self.battery_v, self.BATTERY_MIN_V, self.BATTERY_MAX_V, 0, 4)
        # Outline
        self.screen.thickness(1)
        self.screen.pen(15)
        self.screen.rectangle(x, y, 19, 10)
        # Terminal
        self.screen.rectangle(x + 19, y + 3, 2, 4)
        self.screen.pen(0)
        self.screen.rectangle(x + 1, y + 1, 17, 8)
        if level < 1:
            self.screen.pen(0)
            self.screen.line(x + 3, y, x + 3 + 10, y + 10)
            self.screen.line(x + 3 + 1, y, x + 3 + 11, y + 10)
            self.screen.pen(15)
            self.screen.line(x + 2 + 2, y - 1, x + 4 + 12, y + 11)
            self.screen.line(x + 2 + 3, y - 1, x + 4 + 13, y + 11)
            return
        # Battery Bars
        self.screen.pen(15)
        for i in range(4):
            if level / 4 > (1.0 * i) / 4:
                self.screen.rectangle(i * 4 + x + 2, y + 2, 3, 6)


card = Card(
    given_names='Dave',
    family_names='Jones',
    nickname='waveform',
    org=['Canonical', 'Foundations'],
    email='dave.jones@canonical.com',
    image='ubuntu')

badge = Badge()

badge.clear()
badge.draw_card(8, 8, card)
badge.update()


#def render():
#    display.pen(15)
#    display.clear()
#    display.pen(0)
#    display.thickness(2)
#
#    max_icons = min(3, len(examples[(page * 3):]))
#
#    for i in range(max_icons):
#        x = centers[i]
#        label, icon = examples[i + (page * 3)]
#        label = label[1:]
#        display.pen(0)
#        display.icon(icons, icon, 512, 64, x - 32, 24)
#        w = display.measure_text(label, font_sizes[font_size])
#        display.text(label, x - int(w / 2), 16 + 80, font_sizes[font_size])
#
#    for i in range(MAX_PAGE):
#        x = 286
#        y = int((128 / 2) - (MAX_PAGE * 10 / 2) + (i * 10))
#        display.pen(0)
#        display.rectangle(x, y, 8, 8)
#        if page != i:
#            display.pen(15)
#            display.rectangle(x + 1, y + 1, 6, 6)
#
#    display.pen(0)
#    display.rectangle(0, 0, WIDTH, 16)
#    display.thickness(1)
#    draw_disk_usage(90)
#    draw_battery(get_battery_level(), WIDTH - 22 - 3, 3)
#    display.pen(15)
#    display.text("badgerOS", 3, 8, 0.4)
#
#    display.update()
#
#
#
#def button(pin):
#    global page, font_size, inverted
#
#    if button_user.value():  # User button is NOT held down
#        if pin == button_a:
#            launch_example(0)
#        if pin == button_b:
#            launch_example(1)
#        if pin == button_c:
#            launch_example(2)
#        if pin == button_up:
#            if page > 0:
#                page -= 1
#                render()
#        if pin == button_down:
#            if page < MAX_PAGE - 1:
#                page += 1
#                render()
#    else:  # User button IS held down
#        if pin == button_up:
#            font_size += 1
#            if font_size == len(font_sizes):
#                font_size = 0
#            render()
#        if pin == button_down:
#            font_size -= 1
#            if font_size < 0:
#                font_size = 0
#            render()
#        if pin == button_a:
#            inverted = not inverted
#            display.invert(inverted)
#            render()
#
#
#display.update_speed(badger2040.UPDATE_MEDIUM)
#render()
#display.update_speed(badger2040.UPDATE_FAST)
#
#
## Wait for wakeup button to be released
#while button_a.value() or button_b.value() or button_c.value() or button_up.value() or button_down.value():
#    pass
#
#
#while True:
#    if button_a.value():
#        button(button_a)
#    if button_b.value():
#        button(button_b)
#    if button_c.value():
#        button(button_c)
#
#    if button_up.value():
#        button(button_up)
#    if button_down.value():
#        button(button_down)
#
#    time.sleep(0.01)
