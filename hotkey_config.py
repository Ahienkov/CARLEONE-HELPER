"""Portable Qt key combinations mapped to Windows RegisterHotKey values."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from i18n import tr


SPECIAL_KEYS = {
    Qt.Key.Key_Escape: 0x1B, Qt.Key.Key_Tab: 0x09, Qt.Key.Key_Backspace: 0x08,
    Qt.Key.Key_Return: 0x0D, Qt.Key.Key_Enter: 0x0D, Qt.Key.Key_Space: 0x20,
    Qt.Key.Key_Insert: 0x2D, Qt.Key.Key_Delete: 0x2E, Qt.Key.Key_Home: 0x24,
    Qt.Key.Key_End: 0x23, Qt.Key.Key_PageUp: 0x21, Qt.Key.Key_PageDown: 0x22,
    Qt.Key.Key_Left: 0x25, Qt.Key.Key_Up: 0x26, Qt.Key.Key_Right: 0x27, Qt.Key.Key_Down: 0x28,
    Qt.Key.Key_Pause: 0x13, Qt.Key.Key_Print: 0x2C, Qt.Key.Key_CapsLock: 0x14,
    Qt.Key.Key_NumLock: 0x90, Qt.Key.Key_ScrollLock: 0x91, Qt.Key.Key_Menu: 0x5D,
    Qt.Key.Key_Semicolon: 0xBA, Qt.Key.Key_Equal: 0xBB, Qt.Key.Key_Comma: 0xBC,
    Qt.Key.Key_Minus: 0xBD, Qt.Key.Key_Period: 0xBE, Qt.Key.Key_Slash: 0xBF,
    Qt.Key.Key_QuoteLeft: 0xC0, Qt.Key.Key_BracketLeft: 0xDB, Qt.Key.Key_Backslash: 0xDC,
    Qt.Key.Key_BracketRight: 0xDD, Qt.Key.Key_Apostrophe: 0xDE,
    Qt.Key.Key_VolumeMute: 0xAD, Qt.Key.Key_VolumeDown: 0xAE, Qt.Key.Key_VolumeUp: 0xAF,
    Qt.Key.Key_MediaNext: 0xB0, Qt.Key.Key_MediaPrevious: 0xB1,
    Qt.Key.Key_MediaStop: 0xB2, Qt.Key.Key_MediaPlay: 0xB3,
}
KEYPAD_KEYS = {Qt.Key.Key_Plus: 0x6B, Qt.Key.Key_Minus: 0x6D, Qt.Key.Key_Asterisk: 0x6A,
               Qt.Key.Key_Slash: 0x6F, Qt.Key.Key_Period: 0x6E, Qt.Key.Key_Comma: 0x6E}
MODIFIERS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr}


def parse_hotkey(value):
    if value == 'disabled':
        return 'disabled', 0, 0
    if not isinstance(value, str) or not value.strip():
        raise ValueError(tr('Нажмите клавишу или сочетание клавиш.'))
    sequence = QKeySequence.fromString(value, QKeySequence.SequenceFormat.PortableText)
    if sequence.count() != 1:
        raise ValueError(tr('Используйте одно сочетание клавиш, а не последовательность.'))
    combination = sequence[0]
    key, modifiers = combination.key(), combination.keyboardModifiers()
    if key in MODIFIERS or key == Qt.Key.Key_unknown:
        raise ValueError(tr('Добавьте основную клавишу к Ctrl, Alt, Shift или Win.'))
    flags = 0
    for modifier, flag in ((Qt.KeyboardModifier.AltModifier, 1), (Qt.KeyboardModifier.ControlModifier, 2),
                           (Qt.KeyboardModifier.ShiftModifier, 4), (Qt.KeyboardModifier.MetaModifier, 8)):
        if modifiers & modifier:
            flags |= flag
    if modifiers & Qt.KeyboardModifier.KeypadModifier and Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        virtual_key = 0x60 + int(key) - int(Qt.Key.Key_0)
    elif modifiers & Qt.KeyboardModifier.KeypadModifier and key in KEYPAD_KEYS:
        virtual_key = KEYPAD_KEYS[key]
    elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        virtual_key = int(key)
    elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        virtual_key = 0x70 + int(key) - int(Qt.Key.Key_F1)
    elif key == Qt.Key.Key_Plus:
        virtual_key, flags = 0xBB, flags | 4
    elif key in SPECIAL_KEYS:
        virtual_key = SPECIAL_KEYS[key]
    else:
        raise ValueError(tr('Эту клавишу нельзя использовать как глобальную. Выберите другую.'))
    return sequence.toString(QKeySequence.SequenceFormat.PortableText), flags, virtual_key


def event_hotkey(event):
    key, modifiers = event.key(), event.modifiers()
    if key in MODIFIERS:
        return None
    native = event.nativeVirtualKey()
    # Use physical Windows letter keys so switching the keyboard language does
    # not change the saved shortcut or prevent recording it in a Cyrillic layout.
    if 0x41 <= native <= 0x5A or 0x30 <= native <= 0x39:
        key = native
    elif 0x60 <= native <= 0x69:
        key = int(Qt.Key.Key_0) + native - 0x60
        modifiers |= Qt.KeyboardModifier.KeypadModifier
    elif native in (0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE):
        key = next(int(qt_key) for qt_key, vk in SPECIAL_KEYS.items() if vk == native)
    sequence = QKeySequence(modifiers.value | int(key))
    return parse_hotkey(sequence.toString(QKeySequence.SequenceFormat.PortableText))[0]


def display_hotkey(value):
    if value == 'disabled':
        return tr('Отключена')
    return QKeySequence.fromString(value, QKeySequence.SequenceFormat.PortableText).toString(QKeySequence.SequenceFormat.NativeText)
