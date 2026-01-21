from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt
import sys


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Companion")
        self.resize(800, 500)

        self.create_tray()

    def create_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon("icon.ico"))
        self.tray.setToolTip("Companion")

        # --- Menu clic droit ---
        menu = QMenu()

        action_open = QAction("Ouvrir", self)
        action_open.triggered.connect(self.show_window)

        action_quit = QAction("Quitter", self)
        action_quit.triggered.connect(self.quit_app)

        menu.addAction(action_open)
        menu.addSeparator()
        menu.addAction(action_quit)

        self.tray.setContextMenu(menu)

        # Clic gauche
        self.tray.activated.connect(self.on_tray_activated)

        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # clic gauche
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def quit_app(self):
        self.tray.hide()      # très important
        QApplication.quit()   # ferme le process

    def closeEvent(self, event):
        # Empêche la fermeture réelle via la croix
        event.ignore()
        self.hide()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
