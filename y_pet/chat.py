import json
import os
import sqlite3

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from . import PROJECT_ROOT
from .memory import ChatMemory
from .theme import CHAT_STYLE, paint_neon_frame


SYSTEM_PROMPT = PROJECT_ROOT / "config" / "system-prompt.txt"


class ChatDialog(QDialog):
    answered = Signal(str)
    memory_cleared = Signal()

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("和 Y 聊聊")
        self.resize(420, 320)
        self.setStyleSheet(CHAT_STYLE)
        self.history = []
        self.memory = None
        self.network = QNetworkAccessManager(self)
        self.messages = QTextBrowser()
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.input = QLineEdit(placeholderText="输入消息，按回车发送")
        self.send = QPushButton("发送")
        self.input.returnPressed.connect(self.submit)
        self.send.clicked.connect(self.submit)
        channel = QLabel("Y  /  对话")
        channel.setObjectName("channel")
        composer = QHBoxLayout()
        composer.addWidget(self.input, 1)
        composer.addWidget(self.send)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 14, 15, 15)
        layout.setSpacing(8)
        layout.addWidget(channel)
        layout.addWidget(self.messages, 1)
        layout.addWidget(self.status)
        layout.addLayout(composer)

        try:
            self.memory = ChatMemory()
            for question, answer in self.memory.read():
                self.record_turn(question, answer)
        except (OSError, sqlite3.Error):
            self.status.setText("无法读取本地聊天记录。")

    def record_turn(self, question, answer):
        self.history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])
        self.messages.moveCursor(self.messages.textCursor().MoveOperation.End)
        self.messages.insertPlainText(f"你：{question}\nY：{answer}\n\n")
        self.messages.ensureCursorVisible()

    def clear_memory(self):
        buttons = QMessageBox.StandardButton
        if QMessageBox.warning(
            self.parentWidget(),
            "清空记忆",
            "此操作会删除本地的全部历史对话记录，且无法撤销。确定清空吗？",
            buttons.Yes | buttons.Cancel,
            buttons.Cancel,
        ) != buttons.Yes:
            return
        try:
            if self.memory is None:
                self.memory = ChatMemory()
            self.memory.clear()
        except (OSError, sqlite3.Error):
            QMessageBox.warning(self.parentWidget(), "清空失败", "无法删除本地历史对话记录。")
            return
        self.history.clear()
        self.messages.clear()
        self.status.clear()
        self.memory_cleared.emit()

    def paintEvent(self, event):
        paint_neon_frame(self)

    def submit(self):
        message = self.input.text().strip()
        if not message or not self.send.isEnabled():
            return

        url = QUrl(os.getenv("ELYMS_CHAT_URL", "").strip())
        model = os.getenv("ELYMS_CHAT_MODEL", "").strip()
        if url.scheme() not in ("http", "https") or not url.host() or not model:
            self.status.setText("请先配置 ELYMS_CHAT_URL 和 ELYMS_CHAT_MODEL。")
            return

        path = url.path().rstrip("/")
        if path in ("", "/v1"):
            url.setPath(f"{path}/chat/completions")
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setTransferTimeout(30000)
        key = os.getenv("ELYMS_CHAT_API_KEY", "").strip()
        if key:
            request.setRawHeader(b"Authorization", f"Bearer {key}".encode())

        try:
            prompt = SYSTEM_PROMPT.read_text(encoding="utf-8").strip()
            if not prompt:
                raise ValueError("Empty system prompt")
        except (OSError, ValueError):
            self.status.setText("无法读取系统提示词，请检查 config/system-prompt.txt。")
            return

        turn = {"role": "user", "content": message}
        messages = [{"role": "system", "content": prompt}, *self.history[-12:], turn]
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        self.send.setEnabled(False)
        self.input.setReadOnly(True)
        self.status.setText("Y 正在想……")
        reply = self.network.post(request, body)
        reply.finished.connect(lambda: self.finish(reply, turn))

    def finish(self, reply, turn):
        self.send.setEnabled(True)
        self.input.setReadOnly(False)
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                self.status.setText(f"请求失败（HTTP {code}）。" if code else "连接失败或请求超时，请重试。")
                return
            payload = json.loads(bytes(reply.readAll()))
            answer = payload["choices"][0]["message"]["content"].strip()
            if not answer:
                raise ValueError("Empty reply")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            self.status.setText("模型返回了无法读取的回复，请重试。")
            return
        finally:
            reply.deleteLater()

        self.status.clear()
        try:
            if self.memory is None:
                self.memory = ChatMemory()
            self.memory.append(turn["content"], answer)
        except (OSError, sqlite3.Error):
            self.status.setText("这轮对话未能保存到本地。")
        self.record_turn(turn["content"], answer)
        self.input.clear()
        self.answered.emit(answer)
