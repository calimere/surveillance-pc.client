from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSystemTrayIcon,
    QMenu,
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QTabWidget,
    QPushButton,
    QHBoxLayout,
    QComboBox,
    QLabel,
)
from PySide6.QtGui import QAction, QIcon, QTextCursor
from PySide6.QtCore import Qt, QTimer, Signal, QThread
import sys
from pathlib import Path
from core.component.logger import get_latest_log_file, get_log_files, read_log_file


class LogReaderThread(QThread):
    """Thread pour lire les logs en temps réel."""

    new_log_line = Signal(str)

    def __init__(self, log_file):
        super().__init__()
        self.log_file = log_file
        self.running = True

    def run(self):
        """Surveille le fichier de log et émet les nouvelles lignes."""
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                # Va à la fin du fichier
                f.seek(0, 2)

                while self.running:
                    line = f.readline()
                    if line:
                        self.new_log_line.emit(line.rstrip("\n"))
                    else:
                        # Attendre 100ms avant de réessayer
                        self.msleep(100)
        except Exception as e:
            self.new_log_line.emit(f"Erreur de lecture du fichier de log: {e}")

    def stop(self):
        """Arrête le thread."""
        self.running = False


class LogViewer(QWidget):
    """Widget pour afficher les logs en temps réel."""

    def __init__(self):
        super().__init__()
        self.log_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Barre de contrôle
        control_layout = QHBoxLayout()

        # Sélecteur de fichier de log
        control_layout.addWidget(QLabel("Fichier de log:"))
        self.log_file_combo = QComboBox()
        self.refresh_log_files()
        self.log_file_combo.currentIndexChanged.connect(self.on_log_file_changed)
        control_layout.addWidget(self.log_file_combo, 1)

        # Bouton refresh
        self.refresh_button = QPushButton("🔄 Actualiser")
        self.refresh_button.clicked.connect(self.refresh_log_files)
        control_layout.addWidget(self.refresh_button)

        # Bouton clear
        self.clear_button = QPushButton("🗑️ Effacer")
        self.clear_button.clicked.connect(self.clear_logs)
        control_layout.addWidget(self.clear_button)

        # Bouton pause/resume
        self.pause_button = QPushButton("⏸️ Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self.toggle_pause)
        control_layout.addWidget(self.pause_button)

        layout.addLayout(control_layout)

        # Zone de texte pour afficher les logs
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.log_text)

        self.setLayout(layout)

        # Charger les logs initiaux
        self.load_initial_logs()

        # Démarrer la surveillance en temps réel
        self.start_log_monitoring()

    def refresh_log_files(self):
        """Actualise la liste des fichiers de logs."""
        current_file = self.log_file_combo.currentData()
        self.log_file_combo.clear()

        log_files = get_log_files(limit=20)  # Limiter aux 20 derniers fichiers
        for log_file in log_files:
            if log_file.name == "surveillance.log":
                self.log_file_combo.addItem(f"📄 {log_file.name} (actuel)", log_file)
            else:
                self.log_file_combo.addItem(f"📋 {log_file.name}", log_file)

        # Restaurer la sélection si possible
        if current_file:
            for i in range(self.log_file_combo.count()):
                if self.log_file_combo.itemData(i) == current_file:
                    self.log_file_combo.setCurrentIndex(i)
                    break

    def on_log_file_changed(self):
        """Appelé quand l'utilisateur change de fichier de log."""
        self.stop_log_monitoring()
        self.log_text.clear()
        self.load_initial_logs()

        # Ne surveiller que le fichier actuel
        current_file = self.log_file_combo.currentData()
        if current_file and current_file == get_latest_log_file():
            self.start_log_monitoring()

    def load_initial_logs(self):
        """Charge le contenu initial du fichier de log."""
        log_file = self.log_file_combo.currentData()
        if log_file:
            content = read_log_file(log_file, lines=500)  # Dernières 500 lignes
            self.log_text.setPlainText(content)
            self.scroll_to_bottom()

    def start_log_monitoring(self):
        """Démarre la surveillance du fichier de log en temps réel."""
        if self.log_thread is not None:
            return

        log_file = self.log_file_combo.currentData()
        if not log_file or log_file != get_latest_log_file():
            return

        self.log_thread = LogReaderThread(log_file)
        self.log_thread.new_log_line.connect(self.append_log_line)
        self.log_thread.start()

    def stop_log_monitoring(self):
        """Arrête la surveillance du fichier de log."""
        if self.log_thread is not None:
            self.log_thread.stop()
            self.log_thread.wait()
            self.log_thread = None

    def append_log_line(self, line):
        """Ajoute une nouvelle ligne de log."""
        if not self.pause_button.isChecked():
            self.log_text.append(line)
            self.scroll_to_bottom()

    def scroll_to_bottom(self):
        """Fait défiler jusqu'en bas du texte."""
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def clear_logs(self):
        """Efface le contenu affiché."""
        self.log_text.clear()

    def toggle_pause(self):
        """Pause/reprend la mise à jour des logs."""
        if self.pause_button.isChecked():
            self.pause_button.setText("▶️ Reprendre")
        else:
            self.pause_button.setText("⏸️ Pause")

    def closeEvent(self, event):
        """Appelé à la fermeture du widget."""
        self.stop_log_monitoring()
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Companion - Surveillance PC")
        self.resize(1000, 600)

        # Créer l'interface avec onglets
        self.tabs = QTabWidget()

        # Onglet Logs
        self.log_viewer = LogViewer()
        self.tabs.addTab(self.log_viewer, "📋 Logs")

        # TODO: Ajouter d'autres onglets (Dashboard, Processus, etc.)

        self.setCentralWidget(self.tabs)
        self.create_tray()

    def create_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon("icon.ico"))
        self.tray.setToolTip("Companion - Surveillance PC")

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
        self.log_viewer.stop_log_monitoring()
        self.tray.hide()  # très important
        QApplication.quit()  # ferme le process

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
