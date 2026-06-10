import sys
import os
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTextEdit, QFileDialog, QMessageBox,
    QGroupBox, QSplashScreen
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer

# Import your modular analysis engine
from ai_engine import (
    analyze_code, analyze_diff, security_analysis, optimization_suggestions,
    review_for_production, extract_code_components, run_code_testcase_compare,
    generate_report
)

class Worker(QObject):
    finished = pyqtSignal(object, object)
    error = pyqtSignal(str)
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
    def run(self):
        try:
            result = self.fn(*self.args)
            self.finished.emit(result, None)
        except Exception as e:
            self.finished.emit(None, str(e))

class SplashScreen(QSplashScreen):
    """Simple splash screen with progress animation and logo."""
    def __init__(self, pixmap):
        super().__init__(pixmap)
        self.setMask(pixmap.mask())
        self.progress = 0
        self.setWindowFlags(Qt.SplashScreen | Qt.WindowStaysOnTopHint)
        self.text = QLabel("Loading...", self)
        self.text.setStyleSheet("color: #125ea2; font-size: 15px; font-weight:bold;")
        self.text.move(18, pixmap.height() - 35)
        self.text.resize(pixmap.width(), 24)
    def show_progress(self, percent):
        self.text.setText(f"Loading... {percent}%")
        QApplication.processEvents()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PL/SQL Code Analyzer")
        self.setFixedSize(1000, 750)
        # Set icon if exists
        if os.path.exists("logo.png"):
            self.setWindowIcon(QIcon("logo.png"))
        self.results = {}
        self._init_ui()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # --- Input Section ---
        code_box = QGroupBox("1. Input PL/SQL Code Blocks")
        code_layout = QHBoxLayout(code_box)
        self.code1 = QTextEdit()
        self.code1.setPlaceholderText("Paste or load ORIGINAL PL/SQL code block...")
        self.code2 = QTextEdit()
        self.code2.setPlaceholderText("Paste or load MODIFIED PL/SQL code block...")
        self._add_file_button(code_layout, self.code1, "Load File #1")
        self._add_file_button(code_layout, self.code2, "Load File #2")
        code_layout.addWidget(self.code1)
        code_layout.addWidget(self.code2)
        main_layout.addWidget(code_box)

        # --- Option Section ---
        opt_box = QGroupBox("2. Select Analysis Option")
        opt_layout = QVBoxLayout(opt_box)
        self.buttons = []
        options = [
            ("Compare two PL/SQL code blocks (semantic diff)", self.run_diff),
            ("Security audit", self.run_security),
            ("Optimization suggestions", self.run_optimize),
            ("Production readiness review", self.run_review),
            ("Static runtime output and side-effect comparison", self.run_runtime),
            ("Extract structure/components", self.run_extract),
            ("Export current report to PDF", self.export_pdf),
            ("Exit", self.close)
        ]
        for text, callback in options:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            opt_layout.addWidget(btn)
            self.buttons.append(btn)
        main_layout.addWidget(opt_box)

        # --- Results Section ---
        results_box = QGroupBox("3. Analysis Results")
        results_layout = QVBoxLayout(results_box)
        self.status = QLabel("Ready.")
        self.outbox = QTextEdit()
        self.outbox.setReadOnly(True)
        results_layout.addWidget(self.status)
        results_layout.addWidget(self.outbox)
        main_layout.addWidget(results_box)

    def _add_file_button(self, layout, target_edit, label):
        btn = QPushButton(label)
        btn.setMaximumWidth(100)
        btn.clicked.connect(lambda: self.load_file(target_edit))
        v_layout = QVBoxLayout()
        v_layout.addWidget(btn)
        v_layout.addWidget(target_edit)
        layout.addLayout(v_layout)

    def load_file(self, textedit):
        fname, _ = QFileDialog.getOpenFileName(self, "Open File", "", "PL/SQL (*.sql *.pls *.txt);;All files (*)")
        if fname and os.path.exists(fname):
            with open(fname, "r", encoding="utf-8", errors="ignore") as f:
                textedit.setText(f.read())

    def status_msg(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{'#b22' if error else '#1565c0'};font-weight:600")

    def out_set(self, text):
        self.outbox.setText(text)

    def run_thread(self, worker_fn, callback):
        """Run worker_fn in thread, call callback(result, error) when done."""
        self.status_msg("Working...")
        worker = Worker(worker_fn)
        worker.finished.connect(callback)
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()

    def get_codes(self):
        c1 = self.code1.toPlainText().strip()
        c2 = self.code2.toPlainText().strip()
        return c1, c2

    # ----- Button Callbacks -----
    def run_diff(self):
        c1, c2 = self.get_codes()
        if not c1 or not c2:
            self.status_msg("Both code blocks required for diff!", True)
            return
        self.run_thread(lambda: analyze_diff(c1, c2), self._cb_diff)

    def _cb_diff(self, res, err):
        if err: return self.status_msg(f"Error: {err}", True)
        self.results['logical_diff'] = res
        self.out_set(res['summary'])

    def run_security(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("At least one block required", True)
            return
        def job():
            out = {'code1': security_analysis(c1)}
            if c2: out['code2'] = security_analysis(c2)
            return out
        def cb(res, err):
            if err: return self.status_msg(f"Error: {err}", True)
            self.results['security'] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1']['details'])
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2']['details'])
            self.out_set("\n\n".join(txt))
        self.run_thread(job, cb)

    def run_optimize(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("At least one block required", True)
            return
        def job():
            out = {'code1': optimization_suggestions(c1)}
            if c2: out['code2'] = optimization_suggestions(c2)
            return out
        def cb(res, err):
            if err: return self.status_msg(f"Error: {err}", True)
            self.results['optimization'] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1']['details'])
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2']['details'])
            self.out_set("\n\n".join(txt))
        self.run_thread(job, cb)

    def run_review(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("At least one block required", True)
            return
        def job():
            out = {'code1': review_for_production(c1)}
            if c2: out['code2'] = review_for_production(c2)
            return out
        def cb(res, err):
            if err: return self.status_msg(f"Error: {err}", True)
            self.results['review'] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1']['result'])
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2']['result'])
            self.out_set("\n\n".join(txt))
        self.run_thread(job, cb)

    def run_runtime(self):
        c1, c2 = self.get_codes()
        if not c1 or not c2:
            self.status_msg("Both blocks required for runtime comparison", True)
            return
        # For simplicity, static input (custom dialog can be added)
        test_input = ""
        self.run_thread(lambda: run_code_testcase_compare(c1, c2, test_input or None), self._cb_runtime)

    def _cb_runtime(self, res, err):
        if err: return self.status_msg(f"Error: {err}", True)
        self.results['runtime_test'] = res
        self.out_set(res['summary'])

    def run_extract(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("Provide at least 1 code block", True)
            return
        def job():
            out = {"code1": extract_code_components(c1)}
            if c2: out["code2"] = extract_code_components(c2)
            return out
        def cb(res, err):
            if err: return self.status_msg(f"Error: {err}", True)
            self.results["components"] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1']['details'])
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2']['details'])
            self.out_set("\n\n".join(txt))
        self.run_thread(job, cb)

    def export_pdf(self):
        if not self.results:
            QMessageBox.warning(self, "Export error", "Run some analysis first.")
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save PDF", "analysis_report.pdf", "PDF Files (*.pdf)")
        if fname:
            generate_report(self.results, fname)
            QMessageBox.information(self, "Saved", f"PDF exported to:\n{fname}")

def main():
    app = QApplication(sys.argv)

    # Prepare splash
    splash_pix = QPixmap("logo.png") if os.path.exists("logo.png") else QPixmap(256, 256)
    if splash_pix.isNull():
        splash_pix = QPixmap(256, 256)
        splash_pix.fill(Qt.white)
    splash = SplashScreen(splash_pix)
    splash.show_progress(0)
    splash.show()
    QTimer.singleShot(350, lambda: splash.show_progress(35))
    QTimer.singleShot(700, lambda: splash.show_progress(70))
    QTimer.singleShot(1100, lambda: splash.show_progress(100))

    # Start up main window after splash
    def launch_main():
        win = MainWindow()
        win.show()
        splash.finish(win)

    QTimer.singleShot(1400, launch_main)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
