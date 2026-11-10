import random
import sys

from dotenv import load_dotenv
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap, QPolygon, QTransform
from PySide6.QtWidgets import QApplication, QLabel, QMenu

from . import PROJECT_ROOT
from .chat import ChatDialog
from .theme import ReplyBubble


WALK_STEPS = 90
WALK_MAX_WAIT_MS = 120_000

ASSETS = PROJECT_ROOT / "assets" / "y"

# Hit areas are traced in the 1024 × 1536 idle sprite coordinate space.
REACTION_AREAS = {
    "pat": (
        ((320, 0), (675, 0), (675, 330), (585, 378), (416, 378), (320, 330)),
        ((403, 391), (463, 405), (426, 581), (362, 763), (328, 828),
         (283, 910), (220, 901), (249, 798), (247, 694), (313, 594), (330, 523)),
        ((566, 399), (617, 389), (668, 521), (688, 596), (756, 704),
         (760, 792), (784, 908), (724, 914), (680, 826), (644, 770), (599, 595)),
    ),
    "flustered": (
        ((382, 375), (638, 375), (646, 619), (692, 865), (635, 893), (361, 893),
         (323, 847), (375, 613)),
        ((375, 854), (629, 854), (607, 1040), (643, 1190), (633, 1280),
         (705, 1300), (705, 1390), (652, 1528), (360, 1528), (302, 1390),
         (302, 1300), (373, 1280), (368, 1170), (402, 1030)),
    ),
}
REACTION_REGIONS = {
    name: tuple(QPolygon([QPoint(*vertex) for vertex in outline]) for outline in outlines)
    for name, outlines in REACTION_AREAS.items()
}


class DesktopPet(QLabel):
    def __init__(self):
        # Cocoa maps Tool to a panel that can hide on deactivation and join
        # fullscreen Spaces. Keep the pet in a regular desktop window.
        window_type = Qt.WindowType.Window if sys.platform == "darwin" else Qt.WindowType.Tool
        super().__init__(
            None,
            window_type
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Y")
        self.original_frames = {}
        self.frame_name = "idle"
        for name in ("idle", "blink", "talk", "pat", "flustered", "drag", "land"):
            path = ASSETS / f"{name}.png"
            sprite = QPixmap(str(path))
            if sprite.isNull():
                raise RuntimeError(f"无法加载角色素材：{path}")
            self.original_frames[name] = sprite

        sheet = QPixmap(str(ASSETS / "walk-sheet.png"))
        passing = QPixmap(str(ASSETS / "walk-pass.png"))
        if sheet.isNull() or passing.isNull():
            raise RuntimeError("无法加载步行素材")
        for name, drawing, sole_y in (
            ("walk-a", sheet.copy(0, 0, 768, 1024), 993),
            ("walk-b", sheet.copy(768, 0, 768, 1024), 993),
            ("walk-pass", passing, 1481),
        ):
            canvas = QPixmap(self.original_frames["idle"].size())
            canvas.fill(Qt.GlobalColor.transparent)
            scale = 1525 / sole_y
            width = round(drawing.width() * scale)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(
                QRect((canvas.width() - width) // 2, 0, width, round(drawing.height() * scale)),
                drawing,
            )
            painter.end()
            self.original_frames[f"{name}-right"] = canvas
            self.original_frames[f"{name}-left"] = canvas.transformed(QTransform().scale(-1, 1))

        self.resize_sprite(360)
        self.press_position = None
        self.window_origin = None
        self.dragging = False

        self.reset_timer = QTimer(self, singleShot=True)
        self.reset_timer.timeout.connect(lambda: self.set_frame("idle"))
        self.reaction_timer = QTimer(self, singleShot=True)
        self.pending_reaction = "pat"
        self.reaction_timer.timeout.connect(lambda: self.show_expression(self.pending_reaction, 900))
        self.suppress_click = False
        self.wheel_delta = 0
        self.blink_timer = QTimer(self, interval=4200)
        self.blink_timer.timeout.connect(self.blink)
        self.blink_timer.start()
        self.walk_timer = QTimer(self, interval=30)
        self.walk_timer.timeout.connect(self.walk_step)
        self.walk_ticks = 0
        self.walk_direction = 1
        self.walk_schedule = QTimer(self, singleShot=True)
        self.walk_schedule.setTimerType(Qt.TimerType.PreciseTimer)
        self.walk_schedule.timeout.connect(self.start_walk)
        self.schedule_walk()

        self.chat = ChatDialog(self)
        self.chat.answered.connect(self.say)
        self.bubble = ReplyBubble(self)
        self.chat.memory_cleared.connect(self.bubble.hide)
        self.bubble_timer = QTimer(self, singleShot=True)
        self.bubble_timer.timeout.connect(self.bubble.hide)
        self.mouth_timer = QTimer(self, interval=280)
        self.mouth_timer.timeout.connect(self.animate_mouth)
        self.mouth_stop = QTimer(self, singleShot=True)
        self.mouth_stop.timeout.connect(self.stop_speaking)

        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.right() + 1 - self.width() - 16,
            available.bottom() + 1 - self.height() - 16,
        )

    def set_frame(self, name):
        self.frame_name = name
        sprite = self.frames[name]
        self.setPixmap(sprite)
        self.setMask(self.masks[name])

    def resize_sprite(self, height):
        self.frames = {
            name: sprite.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
            for name, sprite in self.original_frames.items()
        }
        landing = self.frames["land"]
        aligned = QPixmap(landing.size())
        aligned.fill(Qt.GlobalColor.transparent)
        painter = QPainter(aligned)
        # The landing drawing's soles are 10 source pixels above the idle baseline.
        painter.drawPixmap(0, round(height * 10 / 1536), landing)
        painter.end()
        self.frames["land"] = aligned
        self.masks = {name: sprite.mask() for name, sprite in self.frames.items()}
        self.setFixedSize(self.frames["idle"].size())
        self.set_frame(self.frame_name)

    def wheelEvent(self, event):
        self.wheel_delta += event.angleDelta().y()
        steps = abs(self.wheel_delta) // 120
        if self.wheel_delta < 0:
            steps = -steps
        self.wheel_delta -= steps * 120
        if steps:
            height = max(180, min(600, self.height() + steps * 30))
            if height != self.height():
                old_size = self.size()
                self.resize_sprite(height)
                self.move(self.pos() + QPoint((old_size.width() - self.width()) // 2,
                                              old_size.height() - self.height()))
                if self.bubble.isVisible():
                    self.bubble.move(self.panel_position(self.bubble))
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseDoubleClickEvent(event)
        self.stop_walk()
        self.reaction_timer.stop()
        self.press_position = None
        self.window_origin = None
        self.dragging = False
        self.suppress_click = True
        self.open_chat()
        event.accept()

    def schedule_walk(self):
        # A uniform deadline makes the conditional chance rise as time passes.
        self.walk_schedule.start(random.randint(1, WALK_MAX_WAIT_MS - 1))

    def walk_speed(self):
        return max(1, round(self.height() / 180))

    def start_walk(self):
        if (
            not self.isVisible()
            or self.press_position is not None
            or self.walk_timer.isActive()
            or self.chat.isVisible()
            or QApplication.activePopupWidget() is not None
            or self.reaction_timer.isActive()
            or self.mouth_timer.isActive()
            or self.frame_name in ("pat", "flustered", "land", "talk")
        ):
            # Keep the due walk pending while the user is interacting.
            self.walk_schedule.start(500)
            return
        screen = QApplication.screenAt(self.geometry().center()) or self.screen()
        area = screen.availableGeometry()
        left = area.left()
        right = area.right() + 1 - self.width()
        if right <= left:
            self.walk_schedule.start(500)
            return
        x = max(left, min(right, self.x()))
        room = {-1: x - left, 1: right - x}
        distance = self.walk_speed() * WALK_STEPS
        directions = [direction for direction, space in room.items() if space >= distance]
        if not directions:
            directions = [direction for direction, space in room.items() if space == max(room.values())]
        self.walk_direction = random.choice(directions)
        self.move(x, self.y())
        self.schedule_walk()
        self.walk_ticks = 0
        self.reaction_timer.stop()
        self.reset_timer.stop()
        self.mouth_timer.stop()
        self.mouth_stop.stop()
        self.walk_timer.start()
        self.walk_step()

    def walk_step(self):
        if self.walk_ticks >= WALK_STEPS:
            self.stop_walk()
            return
        area = self.screen().availableGeometry()
        left = area.left()
        right = area.right() + 1 - self.width()
        if right <= left:
            self.stop_walk()
            return
        x = max(left, min(right, self.x() + self.walk_direction * self.walk_speed()))
        if x == self.x():
            self.stop_walk()
            return
        self.move(x, self.y())
        if self.bubble.isVisible():
            self.bubble.move(self.panel_position(self.bubble))
        sequence = ("walk-a", "walk-pass", "walk-b", "walk-pass")
        pose = sequence[self.walk_ticks // 5 % len(sequence)]
        direction = "right" if self.walk_direction > 0 else "left"
        self.set_frame(f"{pose}-{direction}")
        self.walk_ticks += 1

    def stop_walk(self):
        if self.walk_timer.isActive():
            self.walk_timer.stop()
            self.set_frame("idle")

    def open_chat(self):
        self.chat.move(self.panel_position(self.chat))
        self.chat.show()
        self.chat.raise_()
        self.chat.activateWindow()
        self.chat.input.setFocus()

    def panel_position(self, panel):
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return self.pos()
        area = screen.availableGeometry()
        x = self.x() - panel.width() - 12
        if x < area.left():
            x = self.geometry().right() + 12
        x = max(area.left(), min(x, area.right() + 1 - panel.width()))
        y = max(area.top(), min(self.y(), area.bottom() + 1 - panel.height()))
        return QPoint(x, y)

    def say(self, answer):
        self.bubble.setText(answer[:160] + ("…" if len(answer) > 160 else ""))
        self.bubble.adjustSize()
        self.bubble.move(self.panel_position(self.bubble))
        self.bubble.show()
        self.bubble_timer.start(6500)
        if self.walk_timer.isActive() or self.frame_name in ("drag", "land"):
            return
        self.reset_timer.stop()
        self.set_frame("talk")
        self.mouth_timer.start()
        self.mouth_stop.start(min(3200, max(850, len(answer) * 65)))

    def animate_mouth(self):
        if not self.reset_timer.isActive():
            is_open = self.frame_name == "talk"
            self.set_frame("idle" if is_open else "talk")

    def stop_speaking(self):
        self.mouth_timer.stop()
        if not self.reset_timer.isActive():
            self.set_frame("idle")

    def show_expression(self, frame, duration):
        if self.dragging or self.walk_timer.isActive():
            return
        self.set_frame(frame)
        self.reset_timer.start(duration)

    def blink(self):
        if self.press_position is None and not self.reset_timer.isActive() and not self.mouth_timer.isActive():
            self.show_expression("blink", 140)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.stop_walk()
        self.suppress_click = False
        self.press_position = event.globalPosition().toPoint()
        self.window_origin = self.pos()
        self.dragging = False
        event.accept()

    def mouseMoveEvent(self, event):
        if self.press_position is None:
            return super().mouseMoveEvent(event)
        offset = event.globalPosition().toPoint() - self.press_position
        if not self.dragging and offset.manhattanLength() >= QApplication.startDragDistance():
            self.dragging = True
            self.reaction_timer.stop()
            self.reset_timer.stop()
            self.mouth_timer.stop()
            self.mouth_stop.stop()
            self.set_frame("drag")
        if self.dragging:
            self.move(self.window_origin + offset)
            if self.bubble.isVisible():
                self.bubble.move(self.panel_position(self.bubble))
        event.accept()

    def reaction_at(self, point):
        if not self.mask().contains(point.toPoint()):
            return None
        source_size = self.original_frames["idle"].size()
        source_point = QPoint(
            int(point.x() * source_size.width() / self.width()),
            int(point.y() * source_size.height() / self.height()),
        )
        for reaction, regions in REACTION_REGIONS.items():
            if any(region.containsPoint(source_point, Qt.FillRule.OddEvenFill) for region in regions):
                return reaction
        return None

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.suppress_click:
            self.suppress_click = False
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton or self.press_position is None:
            return super().mouseReleaseEvent(event)
        point = event.position()
        if self.dragging:
            self.dragging = False
            self.show_expression("land", 220)
        else:
            reaction = self.reaction_at(point)
            if reaction is not None:
                self.pending_reaction = reaction
                self.reaction_timer.start(QApplication.doubleClickInterval())
        self.press_position = None
        self.window_origin = None
        self.dragging = False
        event.accept()

    def contextMenuEvent(self, event):
        self.stop_walk()
        menu = QMenu(self)
        menu.addAction("对话", self.open_chat)
        clear_memory = menu.addAction("清空记忆", self.chat.clear_memory)
        clear_memory.setEnabled(self.chat.send.isEnabled())
        menu.addAction("退出", QApplication.instance().quit)
        menu.exec(event.globalPos())


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    app = QApplication(sys.argv)
    app.setApplicationName("Y")
    pet = DesktopPet()
    pet.show()
    return app.exec()
