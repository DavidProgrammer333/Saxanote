import sys
import sqlite3
import librosa
import sounddevice as sd
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QMessageBox
from PyQt6.QtCore import Qt

class SaxophoneApp(QWidget):
    def __init__(self):
        super().__init__()
        self.language = "en"
        self.db_connection = sqlite3.connect("saxophone_analysis.db")
        self.create_tables()
        self.file_path = None
        self.audio_data = None
        self.sample_rate = None
        self.is_recording = False
        self.translations = {
            "en": {
                "window_title": "Saxophone Note Analyzer",
                "upload_button": "Upload Audio File",
                "record_button": "Record",
                "stop_button": "Stop Recording",
                "analyze_button": "Analyze Notes",
                "language_button": "Switch to Russian",
                "selected_file": "Selected File:",
                "export_button": "Export Results",
                "analysis_completed": "Analysis completed successfully!",
                "export_success": "Results have been exported successfully.",
                "export_error": "Error exporting results.",
                "analysis_error": "Error analyzing audio.",
                "upload_error": "Please upload or record audio first!"
            },
            "ru": {
                "window_title": "Анализатор нот для саксофона",
                "upload_button": "Загрузить аудиофайл",
                "record_button": "Запись",
                "stop_button": "Остановить запись",
                "analyze_button": "Анализировать ноты",
                "language_button": "Переключить на английский",
                "selected_file": "Выбранный файл:",
                "export_button": "Экспорт результатов",
                "analysis_completed": "Анализ успешно завершен!",
                "export_success": "Результаты успешно экспортированы.",
                "export_error": "Ошибка при экспорте результатов.",
                "analysis_error": "Ошибка анализа аудио.",
                "upload_error": "Пожалуйста, сначала загрузите или запишите аудио!"
            }
        }
        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.translations[self.language]["window_title"])
        self.setGeometry(1920, 1080, 1920, 1080)
        self.setStyleSheet("""
            QWidget {
                background-color: #edf6f9;
                font-family: Arial, sans-serif;
            }
            QPushButton {
                background-color: #e85d04;
                color: white;
                font-size: 24px;
                padding: 16px 64px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #dc2f02;
            }
            QLabel {
                font-size: 24px;
                color: #333;
            }
        """)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.languageButton = QPushButton(self.translations[self.language]["language_button"])
        self.languageButton.clicked.connect(self.toggle_language)
        layout.addWidget(self.languageButton)

        self.uploadButton = QPushButton(self.translations[self.language]["upload_button"])
        self.uploadButton.clicked.connect(self.upload_audio)
        layout.addWidget(self.uploadButton)

        self.recordButton = QPushButton(self.translations[self.language]["record_button"])
        self.recordButton.clicked.connect(self.toggle_recording)
        layout.addWidget(self.recordButton)

        self.analyzeButton = QPushButton(self.translations[self.language]["analyze_button"])
        self.analyzeButton.clicked.connect(self.analyze_audio)
        layout.addWidget(self.analyzeButton)

        self.exportButton = QPushButton(self.translations[self.language]["export_button"])
        self.exportButton.clicked.connect(self.export_results)
        layout.addWidget(self.exportButton)

        self.fileLabel = QLabel(self.translations[self.language]["selected_file"])
        layout.addWidget(self.fileLabel)

        self.setLayout(layout)

    def create_tables(self):
        cursor = self.db_connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                timestamp TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                analysis_id INTEGER,
                note TEXT,
                duration REAL,
                FOREIGN KEY (analysis_id) REFERENCES analysis(id)
            )
        """)
        self.db_connection.commit()

    def toggle_language(self):
        self.language = "ru" if self.language == "en" else "en"
        self.update_ui_texts()

    def update_ui_texts(self):
        self.setWindowTitle(self.translations[self.language]["window_title"])
        self.languageButton.setText(self.translations[self.language]["language_button"])
        self.uploadButton.setText(self.translations[self.language]["upload_button"])
        self.recordButton.setText(self.translations[self.language]["record_button"] if not self.is_recording else self.translations[self.language]["stop_button"])
        self.analyzeButton.setText(self.translations[self.language]["analyze_button"])
        self.exportButton.setText(self.translations[self.language]["export_button"])
        self.fileLabel.setText(self.translations[self.language]["selected_file"])

    def upload_audio(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "", "", "Audio Files (*.wav *.mp3)")
        if file_path:
            self.file_path = file_path
            self.audio_data = None
            self.fileLabel.setText(f"{self.translations[self.language]['selected_file']} {file_path}")

    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.recordButton.setText(self.translations[self.language]["stop_button"])
            self.record_audio()
        else:
            self.is_recording = False
            self.recordButton.setText(self.translations[self.language]["record_button"])
            self.stop_recording()

    def record_audio(self):
        self.audio_data = []
        self.sample_rate = 44100
        self.recording_stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=self.audio_callback)
        self.recording_stream.start()

    def audio_callback(self, indata, frames, time, status):
        self.audio_data.append(indata.copy())

    def stop_recording(self):
        self.recording_stream.stop()
        self.recording_stream.close()
        self.audio_data = np.concatenate(self.audio_data, axis=0).flatten()

    def analyze_audio(self):
        if not self.file_path and self.audio_data is None:
            QMessageBox.warning(self, "Error", self.translations[self.language]["upload_error"])
            return

        try:
            if self.file_path:
                y, sr = librosa.load(self.file_path, sr=None)
            elif self.audio_data is not None:
                y = self.audio_data.flatten()
                sr = 44100

            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            threshold = 0.5

            notes_durations = []
            previous_note = None
            note_start_time = None

            for i in range(pitches.shape[1]):
                index = magnitudes[:, i].argmax()
                pitch = pitches[index, i]
                magnitude = magnitudes[index, i]

                if magnitude > threshold:
                    note = librosa.hz_to_note(pitch)

                    if note != previous_note:
                        if previous_note is not None:
                            duration = (i / sr) - note_start_time
                            notes_durations.append((previous_note, duration))
                        previous_note = note
                        note_start_time = i / sr

            if previous_note:
                final_duration = (pitches.shape[1] / sr) - note_start_time
                notes_durations.append((previous_note, final_duration))

            cursor = self.db_connection.cursor()
            cursor.execute("INSERT INTO analysis (file_path, timestamp) VALUES (?, datetime('now'))",
                           (self.file_path,))
            analysis_id = cursor.lastrowid
            for note, duration in notes_durations:
                cursor.execute("INSERT INTO notes (analysis_id, note, duration) VALUES (?, ?, ?)",
                               (analysis_id, note, duration))
            self.db_connection.commit()

            QMessageBox.information(self, "Success", self.translations[self.language]["analysis_completed"])

        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"{self.translations[self.language]['analysis_error']}: {e}")

    def export_results(self):
        file_dialog = QFileDialog()
        export_path, _ = file_dialog.getSaveFileName(self, "Export Results", "", "Text Files (*.txt)")
        if export_path:
            try:
                with open(export_path, 'w') as file:
                    cursor = self.db_connection.cursor()
                    cursor.execute("SELECT * FROM analysis ORDER BY id DESC LIMIT 1")
                    analysis = cursor.fetchone()
                    if analysis:
                        file.write(f"Analysis ID: {analysis[0]}, File: {analysis[1]}, Date: {analysis[2]}\n")
                        cursor.execute("SELECT note, duration FROM notes WHERE analysis_id = ?", (analysis[0],))
                        notes = cursor.fetchall()
                        for note, duration in notes:
                            file.write(f" - Note: {note}, Duration: {duration:.2f} seconds\n")
                QMessageBox.information(self, "Export Complete", self.translations[self.language]["export_success"])
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"{self.translations[self.language]['export_error']}: {e}")


app = QApplication(sys.argv)
window = SaxophoneApp()
window.show()
sys.exit(app.exec())
