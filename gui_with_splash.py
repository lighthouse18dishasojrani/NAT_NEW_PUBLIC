import sys
import os
import threading
import time
from Flowchart import get_dataflow_steps, generate_flowchart
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QSplashScreen,
    QVBoxLayout, QHBoxLayout, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QProgressBar, QScrollArea, QDialog, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QFont, QIcon

from ai_engine import (
    analyze_code, analyze_diff, security_analysis, optimization_suggestions,
    review_for_production, extract_code_components, run_code_testcase_compare,
    generate_report
)

def load_file_safely(filepath):
    for enc in ("utf-8", "cp1252", "latin1"):
        try:
            with open(filepath, "r", encoding=enc, errors="strict") as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

class Worker(QObject):
    finished = pyqtSignal(object, object)
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
    def __init__(self, pixmap):
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.progress = QProgressBar(self)
        self.progress.setGeometry(30, pixmap.height() - 45, pixmap.width() - 60, 12)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.status_label = QLabel("Starting...", self)
        self.status_label.setStyleSheet(
            "color:#374151;font-size:15px;background:rgba(245,245,245,0.97);padding:4px 8px;border-radius:6px;")
        self.status_label.move(20, pixmap.height() - 95)
        self.status_label.resize(pixmap.width() - 40, 24)
    def update_progress(self, value, text=""):
        self.progress.setValue(value)
        if text:
            self.status_label.setText(text)
        QApplication.processEvents()

class ZoomableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.zoom = 1.0
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom = min(self.zoom * 1.17, 5.0)
        else:
            self.zoom = max(self.zoom * 0.85, 0.18)
        if hasattr(self.parent(), 'update_pixmap_to_label'):
            self.parent().update_pixmap_to_label()

class FlowchartDashboard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PL/SQL Flowchart Dashboard")
        self.setMinimumSize(1100, 700)
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "logo.png")))
        main_layout = QVBoxLayout(self)
        btn_layout = QHBoxLayout()
        self.btn_org = QPushButton("Flowchart for ORIGINAL")
        self.btn_mod = QPushButton("Flowchart for MODIFIED")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_org, self.btn_mod, self.btn_close):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet('''
                QPushButton { font-size:16px; font-weight:600; border-radius:9px; padding:11px 25px; background:#f6f7f9; border:2px solid #b6b8fb;}
                QPushButton:hover { background:#dbeafe; }
                QPushButton:pressed { background:#a5b4fc; }
            ''')
        btn_layout.addWidget(self.btn_org)
        btn_layout.addWidget(self.btn_mod)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)
        self.img_label = ZoomableLabel(self)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setWordWrap(True)
        self.img_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.img_label.setStyleSheet("border:2px dashed #c7d2fe; margin:10px; font-size:22px;background:#f5f7fb;")
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.img_label)
        main_layout.addWidget(scroll_area)
        self.btn_org.clicked.connect(lambda: self.display_flowchart("code1"))
        self.btn_mod.clicked.connect(lambda: self.display_flowchart("code2"))
        self.btn_close.clicked.connect(self.close)
        self.mainwin = parent
        self.pixmap = None

    def display_flowchart(self, code_which):
        self.img_label.zoom = 1.0
        code = self.mainwin.code1.toPlainText() if code_which == "code1" else self.mainwin.code2.toPlainText()
        label = "ORIGINAL" if code_which == "code1" else "MODIFIED"
        if not code:
            self.img_label.setText(f"Paste code for {label} block in main window before generating flowchart.")
            return
        self.img_label.setText(f"<span style='color:#aaa;font-size:18pt'>Generating flowchart for {label} code... please wait.</span>")
        def job():
            steps = get_dataflow_steps(code)
            image_path = generate_flowchart(steps, filename=f"{code_which}_dashboard_fc")
            return image_path
        def cb(res, err):
            if err:
                self.img_label.setText(f"<span style='color:red;'>{err}</span>")
                return
            if res and os.path.exists(res):
                px = QPixmap(res)
                self.pixmap = px
                self.update_pixmap_to_label()
                self.img_label.setStyleSheet("border:2px solid #7c3aed; background:white;")
            else:
                self.img_label.setText("Failed to load or generate flowchart image.")
        worker = Worker(job)
        worker.finished.connect(cb)
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pixmap_to_label()
    def update_pixmap_to_label(self):
        if self.pixmap:
            z = self.img_label.zoom
            w = int(self.pixmap.width() * z)
            h = int(self.pixmap.height() * z)
            scaled = self.pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_label.setPixmap(scaled)
            self.img_label.setAlignment(Qt.AlignCenter)

# --- New Detailed Window for Result Pane Clicks
class DetailWindow(QWidget):
    def __init__(self, content):
        super().__init__()
        self.setWindowTitle("Detailed Analysis Result")
        self.resize(720, 900)
        lay = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        if content.strip().startswith("<"):
            self.text.setHtml(content)
        else:
            self.text.setPlainText(content)
        lay.addWidget(self.text)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PL/SQL Analyzer Pro")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "logo.png")))
        self.resize(1280, 860)
        self.setStyleSheet('''
            QMainWindow { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #f0f7fa, stop:1 #e0e7ff); }
            QGroupBox { font-size:18px; font-weight:600; margin-top:20px; border-radius:17px; border:1.9px solid #dbeafe; padding:16px 12px 14px 12px; background:#fff; }
            QPushButton { font-weight:700; border-radius:7px; padding:13px 29px; background:#e0e7ff; }
            QPushButton:hover { background:#ddd6fe; }
            QLabel#Title { font-size:27px; font-weight:800; color:#4338ca }
            QTextEdit[readOnly=\"true\"] {background:#fff7ed;font-size:15px;}
        ''')
        self.results = {}
        self.detail_window_ref = None
        self._init_ui()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        title = QLabel("PL/SQL Analyzer Pro (Aesthetic Edition)")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        code_box = QGroupBox("✍ Input PL/SQL Code Blocks")
        code_layout = QHBoxLayout(code_box)

        code1_v = QVBoxLayout()
        self.code1 = QTextEdit()
        self.code1.setPlaceholderText("Paste or load ORIGINAL PL/SQL code block...")
        self.code1.setStyleSheet("background:#ecfeff; font-family:Consolas,monospace; font-size:15px;border-radius:5px;")
        analyze_code1 = QPushButton("Analyze Original")
        analyze_code1.setStyleSheet('background:#2563eb; color:#fff; padding:9px 28px; font-size:15px; border-radius:7px; font-weight:700; margin-bottom:11px;')
        analyze_code1.clicked.connect(self.analyze_code1_fn)
        code1_v.addWidget(analyze_code1)
        code1_v.addWidget(self.code1)
        self._add_file_button(code1_v, self.code1, "Load File #1")
        code2_v = QVBoxLayout()
        self.code2 = QTextEdit()
        self.code2.setPlaceholderText("Paste or load MODIFIED PL/SQL code block...")
        self.code2.setStyleSheet("background:#fdfde6; font-family:Consolas,monospace; font-size:15px;border-radius:5px;")
        analyze_code2 = QPushButton("Analyze Modified")
        analyze_code2.setStyleSheet('background:#eab308;color:#fff; padding:9px 26px; font-size:15px; border-radius:7px; font-weight:700; margin-bottom:11px;')
        analyze_code2.clicked.connect(self.analyze_code2_fn)
        code2_v.addWidget(analyze_code2)
        code2_v.addWidget(self.code2)
        self._add_file_button(code2_v, self.code2, "Load File #2")
        code_layout.addLayout(code1_v)
        code_layout.addLayout(code2_v)
        main_layout.addWidget(code_box)

        opt_box = QGroupBox("➡️ Analysis Tools & Actions")
        opt_layout = QHBoxLayout(opt_box)
        left_btns, right_btns = QVBoxLayout(), QVBoxLayout()
        left_btns.addWidget(self._styled_button("Compare (Semantic Diff)", self.run_diff, "#6366f1"))
        left_btns.addWidget(self._styled_button("Security Audit", self.run_security, "#059669"))
        left_btns.addWidget(self._styled_button("Optimization Suggestions", self.run_optimize, "#ea580c"))
        left_btns.addWidget(self._styled_button("Production Readiness", self.run_review, "#eab308"))
        right_btns.addWidget(self._styled_button("Runtime Comparison", self.run_runtime, "#e11d48"))
        right_btns.addWidget(self._styled_button("Extract Structure/Components", self.run_extract, "#f43f5e"))
        right_btns.addWidget(self._styled_button("Flowchart Dashboard", self.launch_flowchart_dashboard, "#7c3aed"))
        right_btns.addWidget(self._styled_button("Export Report to PDF", self.export_pdf, "#18181b"))
        opt_layout.addLayout(left_btns)
        opt_layout.addSpacing(60)
        opt_layout.addLayout(right_btns)
        opt_layout.addStretch()
        main_layout.addWidget(opt_box)

        results_box = QGroupBox("📊 Analysis Results")
        results_layout = QVBoxLayout(results_box)
        self.status = QLabel("Ready.")
        self.status.setStyleSheet("font-size:16px;padding:4px 0 7px 0; color:#6366f1;")
        self.status.setAlignment(Qt.AlignLeft)
        self.outbox = QTextEdit()
        self.outbox.setReadOnly(True)
        self.outbox.mousePressEvent = self.open_detail_window  # override for click!
        results_layout.addWidget(self.status)
        results_layout.addWidget(self.outbox)
        main_layout.addWidget(results_box)

    def _styled_button(self, label, func, color):
        btn = QPushButton(label)
        btn.setStyleSheet(f'background:{color}; color:#fff; padding:14px 26px; border-radius:9px; font-size:17px; font-weight:700;')
        btn.clicked.connect(func)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _add_file_button(self, layout, target_edit, label):
        btn = QPushButton(label)
        btn.setStyleSheet('background:#ffe082; font-weight:700; font-size:14px; border-radius:7px;')
        btn.setMaximumWidth(120)
        btn.clicked.connect(lambda: self.load_file(target_edit))
        layout.addWidget(btn)

    def launch_flowchart_dashboard(self):
        dash = FlowchartDashboard(self)
        dash.show()
        dash.raise_()
        dash.activateWindow()

    def load_file(self, textedit):
        fname, _ = QFileDialog.getOpenFileName(self, "Open File", "", "PL/SQL (*.sql *.pls *.txt);;All files (*)")
        if fname and os.path.exists(fname):
            text = load_file_safely(fname)
            textedit.setText(text)

    def status_msg(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{'#e11d48' if error else '#6366f1'}; font-weight:700; font-size:16px;")

    def out_set(self, text):
        self.outbox.setText(text)

    def run_thread(self, worker_fn, callback):
        self.status_msg("Working...")
        worker = Worker(worker_fn)
        worker.finished.connect(callback)
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()

    def get_codes(self):
        return self.code1.toPlainText().strip(), self.code2.toPlainText().strip()

    def analyze_code1_fn(self):
        code = self.code1.toPlainText().strip()
        if not code:
            self.status_msg("Provide code in the ORIGINAL block!", True)
            return
        self.status_msg("Analyzing ORIGINAL code...")
        def job():
            return analyze_code(code)
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.out_set("ORIGINAL BLOCK:\n" + res.get("summary", "No summary available."))
            self.status_msg("Original code analysis complete.")
        self.run_thread(job, cb)

    def analyze_code2_fn(self):
        code = self.code2.toPlainText().strip()
        if not code:
            self.status_msg("Provide code in the MODIFIED block!", True)
            return
        self.status_msg("Analyzing MODIFIED code...")
        def job():
            return analyze_code(code)
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.out_set("MODIFIED BLOCK:\n" + res.get("summary", "No summary available."))
            self.status_msg("Modified code analysis complete.")
        self.run_thread(job, cb)

    def run_diff(self):
        c1, c2 = self.get_codes()
        if not c1 or not c2:
            self.status_msg("Both code blocks required for diff!", True)
            return
        def job():
            return analyze_diff(c1, c2)
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.results['logical_diff'] = res
            self.out_set(res.get('summary', 'No summary available.'))
            self.code2.setHtml(res.get('mod_highlight_html', ''))
            self.status_msg("Diff analysis complete.")
        self.run_thread(job, cb)

    def run_security(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("At least one block required", True)
            return
        def job():
            out = {'code1': security_analysis(c1)}
            if c2:
                out['code2'] = security_analysis(c2)
            return out
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.results['security'] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1'].get('details', ''))
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2'].get('details', ''))
            self.out_set("\n\n".join(txt))
            self.status_msg("Security audit complete.")
        self.run_thread(job, cb)

    def run_optimize(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("At least one block required", True)
            return
        def job():
            out = {'code1': optimization_suggestions(c1)}
            if c2:
                out['code2'] = optimization_suggestions(c2)
            return out
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.results['optimization'] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1'].get('details', ''))
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2'].get('details', ''))
            self.out_set("\n\n".join(txt))
            self.status_msg("Optimization suggestions complete.")
        self.run_thread(job, cb)

    def run_review(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("At least one block required", True)
            return
        def job():
            out = {'code1': review_for_production(c1)}
            if c2:
                out['code2'] = review_for_production(c2)
            return out
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.results['review'] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1'].get('result', ''))
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2'].get('result', ''))
            self.out_set("\n\n".join(txt))
            self.status_msg("Production readiness review complete.")
        self.run_thread(job, cb)

    def run_runtime(self):
        c1, c2 = self.get_codes()
        if not c1 or not c2:
            self.status_msg("Both blocks required for runtime comparison", True)
            return
        def job():
            return run_code_testcase_compare(c1, c2, "")
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.results['runtime_test'] = res
            self.out_set(res.get('summary', 'No summary available.'))
            self.status_msg("Runtime output and side-effect comparison complete.")
        self.run_thread(job, cb)

    def run_extract(self):
        c1, c2 = self.get_codes()
        if not c1:
            self.status_msg("Provide at least one code block", True)
            return
        def job():
            out = {"code1": extract_code_components(c1)}
            if c2:
                out["code2"] = extract_code_components(c2)
            return out
        def cb(res, err):
            if err:
                self.status_msg(f"Error: {err}", True)
                return
            self.results["components"] = res
            txt = []
            if 'code1' in res: txt.append("ORIGINAL:\n" + res['code1'].get('details', ''))
            if 'code2' in res: txt.append("\nMODIFIED:\n" + res['code2'].get('details', ''))
            self.out_set("\n\n".join(txt))
            self.status_msg("Structure/components extraction complete.")
        self.run_thread(job, cb)

    def export_pdf(self):
        if not self.results:
            QMessageBox.warning(self, "Export error", "Run some analysis first.")
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save PDF", "analysis_report.pdf", "PDF Files (*.pdf)")
        if fname:
            try:
                generate_report(self.results, fname)
                QMessageBox.information(self, "Saved", f"PDF exported to:\n{fname}")
                self.status_msg("PDF report exported successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Export error", f"Failed to export PDF:\n{str(e)}")

    # --- NEW: open results in separate window on click
    def open_detail_window(self, event):
        content = self.outbox.toHtml() if self.outbox.toHtml().strip() else self.outbox.toPlainText()
        self.detail_window_ref = DetailWindow(content)
        self.detail_window_ref.show()

def main():
    app = QApplication(sys.argv)
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    splash_pix = QPixmap(logo_path).scaled(480, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    splash = SplashScreen(splash_pix)
    splash.show()
    stages = [
        (0, "Initializing..."), (13, "Setting up GUI..."), (27, "Loading modules..."),
        (48, "Connecting dependencies..."), (62, "Allocating memory..."),
        (79, "Starting code analysis engine..."), (100, "Ready!")
    ]
    for percent, message in stages:
        splash.update_progress(percent, text=message)
        time.sleep(0.36 if percent < 90 else 0.23)
    win = MainWindow()
    win.show()
    splash.finish(win)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
