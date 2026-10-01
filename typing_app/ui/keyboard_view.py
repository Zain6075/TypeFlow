"""On-screen keyboard that highlights the next key and the correct finger.

The whole keyboard is painted by hand (no child widgets) so it can highlight
keys instantly while typing and scale with the user's font-size setting.
Finger colours come from ``theme.FINGER_COLORS``.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from . import theme

LP, LR, LM, LI = "left-pinky", "left-ring", "left-middle", "left-index"
TB = "thumb"
RI, RM, RR, RP = "right-index", "right-middle", "right-ring", "right-pinky"

# (label, width in key units, finger)
KEY_ROWS: list[list[tuple[str, float, str]]] = [
    [("`", 1, LP), ("1", 1, LP), ("2", 1, LP), ("3", 1, LM), ("4", 1, LI), ("5", 1, LI),
     ("6", 1, RI), ("7", 1, RI), ("8", 1, RM), ("9", 1, RR), ("0", 1, RP), ("-", 1, RP),
     ("=", 1, RP), ("Back", 2, RP)],
    [("Tab", 1.5, LP), ("q", 1, LP), ("w", 1, LR), ("e", 1, LM), ("r", 1, LI), ("t", 1, LI),
     ("y", 1, RI), ("u", 1, RI), ("i", 1, RM), ("o", 1, RR), ("p", 1, RP), ("[", 1, RP),
     ("]", 1, RP), ("\\", 1.5, RP)],
    [("Caps", 1.75, LP), ("a", 1, LP), ("s", 1, LR), ("d", 1, LM), ("f", 1, LI), ("g", 1, LI),
     ("h", 1, RI), ("j", 1, RI), ("k", 1, RM), ("l", 1, RR), (";", 1, RP), ("'", 1, RP),
     ("Enter", 2.25, RP)],
    [("Shift", 2.25, LP), ("z", 1, LP), ("x", 1, LR), ("c", 1, LM), ("v", 1, LI), ("b", 1, LI),
     ("n", 1, RI), ("m", 1, RI), (",", 1, RM), (".", 1, RR), ("/", 1, RR), ("Shift", 2.75, RP)],
    [("", 7, TB), ("Space", 6, TB)],
]

# Characters produced with Shift on a US layout -> their base key.
SHIFTED_TO_BASE = {
    "~": "`", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
    ":": ";", '"': "'", "<": ",", ">": ".", "?": "/",
}

# Finger number badges (1 = left pinky ... 8 = right pinky).
FINGER_NUMBERS = {LP: "1", LR: "2", LM: "3", LI: "4", RI: "5", RM: "6", RR: "7", RP: "8", TB: ""}

HOME_KEYS = {"f", "j"}   # keys with the small tactile bump


class KeyboardView(QWidget):
    """Painted QWERTY keyboard; call :meth:`set_next_key` while typing."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.next_keys: set[str] = set()      # key labels to highlight
        self.show_fingers = True              # draw finger colours + numbers
        self.unit = 40.0                      # width of one key unit in px
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(int(self.unit * 5 + 52))   # rows + legend

    # -- public API ------------------------------------------------------------
    def set_next_key(self, char: str | None) -> None:
        """Highlight the key(s) needed to type ``char`` (None clears)."""
        self.next_keys = set()
        if char:
            base, needs_shift = _resolve(char)
            if base:
                self.next_keys.add(base)
                if needs_shift:
                    self.next_keys.add("Shift")  # both Shift keys share this label
        self.update()

    def set_show_fingers(self, visible: bool) -> None:
        self.show_fingers = visible
        self.update()

    def set_scale(self, scale: float) -> None:
        self.unit = max(26.0, min(64.0, 40.0 * scale))
        self.setMinimumHeight(int(self.unit * 5 + 52))   # rows + legend
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(int(self.unit * 15 + 40), int(self.unit * 5 + 52))

    # -- painting ----------------------------------------------------------------
    def paintEvent(self, event) -> None:
        pal = theme.palette(_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gap = max(3.0, self.unit * 0.12)
        key_height = self.unit
        y = 6.0
        total_width = self.unit * 15 + gap * 14
        x0 = (self.width() - total_width) / 2

        for row in KEY_ROWS:
            x = x0
            for label, width_units, finger in row:
                if label == "":          # leading spacer
                    x += width_units * self.unit + gap
                    continue
                width = width_units * self.unit - gap
                rect = QRectF(x, y, width, key_height)
                self._draw_key(painter, rect, label, finger, pal)
                x += width_units * self.unit + gap
            y += key_height + gap

        if self.show_fingers:
            self._draw_legend(painter, pal, x0, y)

    def _draw_key(self, painter: QPainter, rect: QRectF, label: str, finger: str, pal: dict) -> None:
        highlighted = label in self.next_keys
        is_shift = label == "Shift"
        path = QPainterPath()
        path.addRoundedRect(rect, 7, 7)

        if highlighted:
            fill = QColor(pal["accent"])
            border = QColor(pal["accent_hover"])
            text_color = QColor(pal["on_accent"])
        else:
            fill = QColor(pal["surface_alt"])
            border = QColor(pal["border"])
            text_color = QColor(pal["text"])

        painter.setPen(QPen(border, 1.4))
        painter.setBrush(fill)
        painter.drawPath(path)

        # Finger colour band along the bottom edge of every key.
        if self.show_fingers and finger != TB:
            band = QColor(theme.FINGER_COLORS[finger])
            band.setAlpha(210 if not highlighted else 90)
            painter.setPen(QPen(band, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            band_rect = QRectF(rect.left() + 5, rect.bottom() - 3.2, rect.width() - 10, 0)
            painter.drawLine(band_rect.topLeft(), band_rect.topRight())

        # Home-row bumps.
        if label in HOME_KEYS and not highlighted:
            painter.setPen(QPen(QColor(pal["text_dim"]), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            cx = rect.center().x()
            painter.drawLine(QPointF_(cx, rect.bottom() - 8), QPointF_(cx, rect.bottom() - 4.6))

        # Key label.
        font = QFont(theme.FONT_STACK)
        font.setPointSize(max(7, int(self.unit * 0.30)))
        font.setBold(highlighted or label in ("Space", "Enter", "Tab", "Caps", "Back", "Shift"))
        painter.setFont(font)
        painter.setPen(text_color)
        display = {"Back": "⌫", "Enter": "⏎", "Tab": "⇥", "Caps": "⇪", "Shift": "⇧"}.get(label, label)
        if label == "Space":
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "space")
        else:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, display)

        # Finger number badge.
        if self.show_fingers and finger != TB and not is_shift:
            number = FINGER_NUMBERS[finger]
            badge_font = QFont(theme.FONT_STACK)
            badge_font.setPointSize(max(6, int(self.unit * 0.20)))
            badge_font.setBold(True)
            painter.setFont(badge_font)
            painter.setPen(QColor(pal["text_dim"]) if not highlighted else QColor(pal["on_accent"]))
            painter.drawText(QRectF(rect.left(), rect.top() + 2, rect.width() - 4, rect.height() * 0.4),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, number)

    def _draw_legend(self, painter: QPainter, pal: dict, x0: float, y: float) -> None:
        font = QFont(theme.FONT_STACK)
        font.setPointSize(8)
        painter.setFont(font)
        x = x0
        for finger, color in theme.FINGER_COLORS.items():
            painter.setPen(QPen(QColor(pal["text_dim"]), 1))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x, y + 4, 9, 9), 2, 2)
            label = f"{FINGER_NUMBERS[finger]} {theme.FINGER_NAMES[finger].replace('Left ', 'L ').replace('Right ', 'R ')}"
            painter.setPen(QColor(pal["text_dim"]))
            painter.drawText(QRectF(x + 12, y, 120, 16), Qt.AlignmentFlag.AlignVCenter, label)
            x += 118


def QPointF_(x: float, y: float):
    from PyQt6.QtCore import QPointF
    return QPointF(x, y)


def _resolve(char: str) -> tuple[str | None, bool]:
    """Map a character to (base key label, needs shift)."""
    if char == " ":
        return "Space", False
    if char.isalpha():
        return char.lower(), char.isupper()
    if char in SHIFTED_TO_BASE:
        return SHIFTED_TO_BASE[char], True
    return char, False


def _finger_of(label: str) -> str | None:
    for row in KEY_ROWS:
        for key_label, _width, finger in row:
            if key_label == label:
                return finger
    return None


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
