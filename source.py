import sys
import os
from pathlib import Path
import pygame
from PyQt6.QtCore import Qt, QPoint, QSize, QTimer
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QToolButton, QSlider, QLabel,
    QSystemTrayIcon, QMenu
)

BASE_DIR = Path(__file__).resolve().parent
ICONS = BASE_DIR / "icons"

DESIGN_SIZE = (150, 20)

COORDS_DESIGN = {
    "minimize": (3, 0),
    "prev":     (40, 0),
    "play":     (65, 0),
    "next":     (90, 0),
    "volume":   (125, 0),
    "slider_offset": (0, 0),
    "icon_size": (20, 20),
}

pygame.mixer.init()


class VolumeSlider(QWidget):
    def __init__(self, parent=None, width=None, height=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.bg = QPixmap(str(ICONS / "slider_bg.png"))
        if width is not None and height is not None:
            self.bg = self.bg.scaled(width, height,
                                     Qt.AspectRatioMode.IgnoreAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        self.setFixedSize(self.bg.size())

        self.slider = QSlider(Qt.Orientation.Vertical, self)
        self.slider.setRange(0, 100)
        self.slider.setValue(70)
        padding_x, padding_y = 5, 5
        self.slider.setGeometry(padding_x, padding_y,
                                self.width() - 2*padding_x,
                                self.height() - 2*padding_y)

        self.label = QLabel(str(self.slider.value()) + "%")
        self.label.setWindowFlags(Qt.WindowType.ToolTip)
        self.label.setStyleSheet(
            "color: white; font-weight: bold; background: rgba(0,0,0,150); padding: 2px; border-radius: 3px;"
        )
        self.label.adjustSize()

        self.slider.valueChanged.connect(self.update_label)
        self.slider.valueChanged.connect(self.set_volume)
        self.update_label(self.slider.value())

    def set_volume(self, value):
        pygame.mixer.music.set_volume(value / 100)

    def update_label(self, value):
        if not self.isVisible():
            return
        self.label.setText(f"{value}%")
        self.label.adjustSize()
        slider_height = self.slider.height()
        handle_y = slider_height - (slider_height * value / 100)
        global_pos = self.mapToGlobal(self.slider.pos())
        x = global_pos.x() + self.slider.width() + 5
        y = global_pos.y() + handle_y - self.label.height() / 2
        self.label.move(int(x), int(y))
        self.label.show()

    def hideEvent(self, event):
        self.label.hide()
        super().hideEvent(event)

    def showEvent(self, event):
        self.update_label(self.slider.value())
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self.bg.isNull():
            painter.drawPixmap(0, 0, self.bg)


class MiniPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.bg = QPixmap(str(ICONS / "background.png"))
        if self.bg.isNull():
            raise RuntimeError("Нет icons/background.png")
        self.setFixedSize(self.bg.size())

        self.scale_x = self.bg.width() / DESIGN_SIZE[0]
        self.scale_y = self.bg.height() / DESIGN_SIZE[1]
        self.scale = int(round(self.scale_x))

        self.coords = {
            key: (int(values[0] * self.scale), int(values[1] * self.scale))
            if key not in ("icon_size", "slider_offset")
            else (int(values[0] * self.scale), int(values[1] * self.scale))
            for key, values in COORDS_DESIGN.items()
        }

        self.btn_min = self.make_button("minimize.png", self.coords["minimize"], self.showMinimized)
        self.btn_prev = self.make_button("prev.png", self.coords["prev"], self.on_prev)
        self.btn_play = self.make_button("play.png", self.coords["play"], self.toggle_play)
        self._is_playing = False
        self.btn_next = self.make_button("next.png", self.coords["next"], self.on_next)
        self.btn_volume = self.make_button("volume.png", self.coords["volume"], self.toggle_slider)

        self.slider_widget = VolumeSlider(width=25, height=90)
        self.slider_widget.hide()

        self.music_dir = str(BASE_DIR / "music")
        self.playlist = []
        self.current_index = 0
        self.track_pos = 0

        if os.path.exists(self.music_dir):
            self.playlist = [os.path.join(self.music_dir, f)
                             for f in os.listdir(self.music_dir)
                             if f.lower().endswith((".mp3", ".wav", ".ogg"))]

        if self.playlist:
            pygame.mixer.music.load(self.playlist[self.current_index])

        self.tray_icon = QSystemTrayIcon(QIcon(str(ICONS / "icon.png")), self)
        self.tray_icon.setToolTip("Mini Player")
        self.tray_icon.activated.connect(self.tray_icon_clicked)

        self.tray_menu = QMenu()
        exit_action = self.tray_menu.addAction("Выход")
        exit_action.triggered.connect(QApplication.quit)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        self.is_in_tray = False
        self.setStyleSheet("QToolButton { background: transparent; border: none; }")
        self._drag_pos = QPoint()

        self.playlist_timer = QTimer()
        self.playlist_timer.timeout.connect(self.check_track_end)
        self.playlist_timer.start(500)

    def make_button(self, icon_name, pos, slot):
        btn = QToolButton(self)
        btn.setIcon(QIcon(str(ICONS / icon_name)))
        btn.setIconSize(QSize(*self.coords["icon_size"]))
        btn.setAutoRaise(True)
        btn.move(*pos)
        btn.clicked.connect(slot)
        return btn

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self.bg)

    def toggle_play(self):
        if not self.playlist:
            return
        if self._is_playing:
            self.track_pos += pygame.mixer.music.get_pos() / 1000
            pygame.mixer.music.pause()
            self._is_playing = False
        else:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(self.playlist[self.current_index])
            pygame.mixer.music.play(start=self.track_pos)
            self._is_playing = True
        icon = "pause.png" if self._is_playing else "play.png"
        self.btn_play.setIcon(QIcon(str(ICONS / icon)))

    def on_prev(self):
        if not self.playlist:
            return
        self.track_pos = 0
        self.current_index = (self.current_index - 1) % len(self.playlist)
        pygame.mixer.music.load(self.playlist[self.current_index])
        pygame.mixer.music.play()
        self._is_playing = True
        self.btn_play.setIcon(QIcon(str(ICONS / "pause.png")))

    def on_next(self):
        if not self.playlist:
            return
        self.track_pos = 0
        self.current_index = (self.current_index + 1) % len(self.playlist)
        pygame.mixer.music.load(self.playlist[self.current_index])
        pygame.mixer.music.play()
        self._is_playing = True
        self.btn_play.setIcon(QIcon(str(ICONS / "pause.png")))

    def check_track_end(self):
        if not self.playlist or not self._is_playing:
            return
        if not pygame.mixer.music.get_busy():
            self.track_pos = 0
            self.current_index = (self.current_index + 1) % len(self.playlist)
            pygame.mixer.music.load(self.playlist[self.current_index])
            pygame.mixer.music.play()
            self.btn_play.setIcon(QIcon(str(ICONS / "pause.png")))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
            if self.slider_widget.isVisible():
                x = self.x() + self.width() + 5
                y = self.y() + self.coords["slider_offset"][1]
                self.slider_widget.move(x, y)
                self.slider_widget.update_label(self.slider_widget.slider.value())

    def toggle_slider(self):
        if self.slider_widget.isVisible():
            self.slider_widget.hide()
        else:
            if not self.isVisible():
                return
            x = self.x() + self.width() + 5
            y = self.y() + self.coords["slider_offset"][1]
            self.slider_widget.move(x, y)
            self.slider_widget.show()
            self.slider_widget.update_label(self.slider_widget.slider.value())

    def showMinimized(self):
        if self.slider_widget.isVisible():
            self.slider_widget.hide()
        self.hide()
        self.is_in_tray = True
        self.tray_icon.showMessage(
            "Mini Player",
            "Приложение свернуто в трей",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def tray_icon_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger and self.is_in_tray:
            self.showNormal()
            self.is_in_tray = False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()


def main():
    app = QApplication(sys.argv)
    w = MiniPlayer()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
