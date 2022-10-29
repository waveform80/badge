class VCard:
    IMAGES = {
        'ubuntu':    ('ubuntu.bin',    64, 64),
        'canonical': ('canonical.bin', 64, 64),
        'face':      ('face.bin',      64, 64),
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
            with open(f'{fn}', 'rb') as f:
                self.image = (bytearray(f.read()), w, h)

    def __repr__(self):
        return (
            f'VCard({repr(self.given_names)}, {repr(self.family_names)}, ...)')

    def __str__(self):
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
        lines = '\n'.join(
            f'{field}:{quote_str(value) if isinstance(value, str) else quote_list(value)}'
            for field, value in fields.items()
            if value
        )
        return f"""\
BEGIN:VCARD
VERSION:4.0
{lines}
END:VCARD
"""
