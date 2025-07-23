import sys
import pyautogui
import pyperclip
import os
import time
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QInputDialog, QMessageBox, QHBoxLayout, QFileDialog, QListWidget, QListWidgetItem, QLabel
)
import signal
from PyQt6.QtCore import Qt
import keyboard  # pip install keyboard
import json
import functools
from PyQt6.QtGui import QImage, QPixmap, QGuiApplication, QIcon
import sqlite3
from PyQt6.QtWidgets import QPushButton

# 移除自动删除数据库的代码

class QuickReplyAutoInsert(QWidget):
    def __init__(self):
        super().__init__()
        self.current_group = None
        self.setWindowTitle("快捷回复（自动插入）")
        self.is_on_top = False  # 默认不置顶
        self.reply_area_expanded = True  # 新增属性，控制回复区块显示
        self._expanded_width = None  # 记录展开时窗口宽度
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)
        # 分组区（列表+添加按钮）
        self.group_area = QVBoxLayout()
        # 分组区最大宽度限制
        self.group_area_widget = QWidget()
        self.group_area_widget.setLayout(self.group_area)
        self.group_area_widget.setMaximumWidth(360)  # 可根据实际调整
        self.group_list = QListWidget()
        self.group_list.setMinimumWidth(340)
        self.group_list.setMaximumWidth(550)
        self.group_list.itemClicked.connect(self.on_group_selected)
        self.group_area.addWidget(self.group_list)
        self.add_group_btn = QPushButton("+ 添加分组")
        self.add_group_btn.setFixedHeight(32)
        self.add_group_btn.setStyleSheet("font-size: 14px;")
        self.add_group_btn.clicked.connect(self.add_group)
        self.group_area.addWidget(self.add_group_btn)
        self.main_layout.addWidget(self.group_area_widget, 1)
        # 展开/收缩按钮放在分组区和快捷回复区之间
        self.toggle_reply_area_btn = QPushButton("<")
        self.toggle_reply_area_btn.setFixedSize(28, 60)
        self.toggle_reply_area_btn.setToolTip("收起/展开快捷回复区块")
        self.toggle_reply_area_btn.clicked.connect(self.toggle_reply_area)
        self.main_layout.addWidget(self.toggle_reply_area_btn, 0)
        # 右侧回复区
        self.reply_area_widget = QWidget()
        self.layout = QVBoxLayout()
        self.reply_area_widget.setLayout(self.layout)
        self.main_layout.addWidget(self.reply_area_widget, 4)
        self.init_db()
        self.load_replies()
        self.load_group_hotkeys()
        self.update_groups()
        self.current_group = self.groups[0][0] if self.groups else None  # 默认选中第一个分组id
        self.init_ui()
        self.register_hotkeys()

    def init_db(self):
        self.conn = sqlite3.connect('quick_replies.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_hotkeys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT UNIQUE,
                hotkey TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                text TEXT,
                image_path TEXT,
                group_id INTEGER,
                FOREIGN KEY(group_id) REFERENCES group_hotkeys(id)
            )
        ''')
        # 确保有默认分组
        self.cursor.execute('INSERT OR IGNORE INTO group_hotkeys (group_name, hotkey) VALUES (?, ?)', ("默认", None))
        self.conn.commit()

    def load_groups(self):
        self.cursor.execute('SELECT id, group_name FROM group_hotkeys ORDER BY id ASC')
        self.groups = [(row[0], row[1]) for row in self.cursor.fetchall()]

    def load_replies(self):
        self.cursor.execute('SELECT id, type, text, image_path, group_id, sort FROM replies ORDER BY group_id, sort ASC, id ASC')
        rows = self.cursor.fetchall()
        self.replies = []
        for row in rows:
            group_id = row[4]
            group_name = self.get_group_name_by_id(group_id)
            if row[1] == 'image':
                self.replies.append({
                    "id": row[0],
                    "type": "image",
                    "image_path": row[3],
                    "group_id": group_id,
                    "group": group_name,
                    "sort": row[5]
                })
            else:
                self.replies.append({
                    "id": row[0],
                    "type": "text",
                    "text": row[2],
                    "group_id": group_id,
                    "group": group_name,
                    "sort": row[5]
                })

    def get_group_id_by_name(self, group_name):
        self.cursor.execute('SELECT id FROM group_hotkeys WHERE group_name=?', (group_name,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_group_name_by_id(self, group_id):
        self.cursor.execute('SELECT group_name FROM group_hotkeys WHERE id=?', (group_id,))
        row = self.cursor.fetchone()
        return row[0] if row else "默认"

    def load_group_hotkeys(self):
        self.cursor.execute('SELECT group_name, hotkey FROM group_hotkeys')
        self.group_hotkeys = {row[0]: row[1] for row in self.cursor.fetchall() if row[1]}

    def save_group_hotkey(self, group, hotkey):
        print(f"保存分组热键: {group} -> {hotkey}")
        self.cursor.execute('UPDATE group_hotkeys SET hotkey=? WHERE group_name=?', (hotkey, group))
        self.conn.commit()

    def add_group(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        group, ok = QInputDialog.getText(self, "添加分组", "输入新分组名：")
        group = group.strip()
        if ok and group:
            if any(gname == group for gid, gname in self.groups):
                QMessageBox.warning(self, "分组已存在", f"分组 [{group}] 已存在！")
                return
            self.cursor.execute('INSERT INTO group_hotkeys (group_name, hotkey) VALUES (?, ?)', (group, None))
            self.conn.commit()
            print(f"已添加分组到数据库: {group}")
            self.update_groups()

    def edit_group(self, old_group):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        new_group, ok = QInputDialog.getText(self, "编辑分组", f"将分组 [{old_group}] 修改为：", text=old_group)
        new_group = new_group.strip()
        if ok and new_group and new_group != old_group:
            self.cursor.execute('UPDATE group_hotkeys SET group_name=? WHERE group_name=?', (new_group, old_group))
            self.conn.commit()
            QMessageBox.information(self, "分组已修改", f"分组 [{old_group}] 已修改为 [{new_group}]。")
            self.update_groups()
            self.update_buttons()

    def delete_group(self, group):
        from PyQt6.QtWidgets import QMessageBox
        group_id = self.get_group_id_by_name(group)
        reply = QMessageBox.question(self, "确认删除", f"确定要删除分组 [{group}] 及其所有内容吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes and group_id:
            self.cursor.execute('DELETE FROM group_hotkeys WHERE id=?', (group_id,))
            self.cursor.execute('DELETE FROM replies WHERE group_id=?', (group_id,))
            self.conn.commit()
            self.update_groups()
            self.current_group = self.get_default_group_id()  # 用分组id
            self.update_buttons()
            self.register_hotkeys()

    def register_hotkeys(self):
        if not hasattr(self, '_registered_hotkeys'):
            self._registered_hotkeys = set()
        for reply in self.replies:
            hotkey = reply.get("hotkey")
            # 注册时将 F1~F12 转换为小写 f1~f12
            reg_hotkey = hotkey.lower() if hotkey and hotkey.startswith("F") else hotkey
            if reg_hotkey and reg_hotkey not in self._registered_hotkeys:
                if reply.get("type", "text") == "image":
                    print(f"注册图片热键: {reg_hotkey} -> {reply.get('image_path')}")
                    keyboard.add_hotkey(reg_hotkey, functools.partial(self.send_image, reply["image_path"]))
                else:
                    print(f"注册文本热键: {reg_hotkey} -> {reply.get('text')}")
                    keyboard.add_hotkey(reg_hotkey, functools.partial(self.send_reply, reply["text"]))
                self._registered_hotkeys.add(reg_hotkey)

    def init_ui(self):
        # 右上角置顶图标按钮
        top_btn_layout = QHBoxLayout()
        top_btn_layout.addStretch()
        self.top_icon_btn = QPushButton()
        self.top_icon_btn.setFixedSize(28, 28)
        self.update_top_icon()
        self.top_icon_btn.clicked.connect(self.toggle_on_top)
        top_btn_layout.addWidget(self.top_icon_btn)
        self.layout.addLayout(top_btn_layout)
        # 其余 UI
        self.button_layout = QVBoxLayout()
        self.update_buttons()
        self.layout.addLayout(self.button_layout)

        manage_layout = QHBoxLayout()
        add_btn = QPushButton("添加回复")
        add_btn.clicked.connect(self.add_reply)
        manage_layout.addWidget(add_btn)

        # self.toggle_top_btn = QPushButton("取消置顶" if self.is_on_top else "置顶")
        # self.toggle_top_btn.clicked.connect(self.toggle_on_top)
        # manage_layout.addWidget(self.toggle_top_btn)

        self.layout.addLayout(manage_layout)

    def update_groups(self):
        self.load_groups()
        if not hasattr(self, 'group_hotkeys'):
            self.group_hotkeys = {}
        print("当前 group_hotkeys:", self.group_hotkeys)
        self.group_list.clear()
        self.group_list.setSpacing(4)
        self.group_list.setStyleSheet("QListWidget::item:selected { background: transparent; }")
        
        for group_id, group in self.groups:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, group_id)
            widget = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(8, 2, 8, 2)
            layout.setSpacing(8)
            label = QLabel(group)
            label.setMinimumWidth(120)
            label.setMaximumWidth(180)
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            # 高亮当前分组
            if group_id == getattr(self, 'current_group', None):
                label.setStyleSheet("font-size: 13px; color: #1976d2; font-weight: bold;")
            else:
                label.setStyleSheet("font-size: 13px; color: #222;")
            group_hotkey = self.group_hotkeys.get(group)
            del_btn = QPushButton("删除")
            del_btn.setFixedSize(60, 28)
            del_btn.setStyleSheet("font-size: 12px;")
            del_btn.clicked.connect(lambda checked, g=group: self.delete_group(g))
            edit_btn = QPushButton("编辑")
            edit_btn.setFixedSize(60, 28)
            edit_btn.setStyleSheet("font-size: 12px;")
            edit_btn.clicked.connect(lambda checked, g=group: self.edit_group(g))
            hotkey_btn = QPushButton(f"快捷键({group_hotkey})" if group_hotkey else "设置快捷键")
            hotkey_btn.setFixedSize(90, 28)
            hotkey_btn.setStyleSheet("font-size: 12px;")
            hotkey_btn.clicked.connect(lambda checked, g=group: self.add_group_hotkey(g))
            layout.addWidget(label, 1)
            layout.addWidget(edit_btn, 0)
            layout.addWidget(del_btn, 0)
            layout.addWidget(hotkey_btn, 0)
            widget.setLayout(layout)
            widget.setFixedHeight(40)
            # 事件过滤器：点击行空白区域切换分组
            widget.installEventFilter(self)
            widget._group_id = group_id  # 记录分组id
            self.group_list.addItem(item)
            self.group_list.setItemWidget(item, widget)
        # 默认选中第一个分组
        if self.groups:
            if self.current_group is None or self.current_group not in [gid for gid, _ in self.groups]:
                self.current_group = self.groups[0][0]
            for i, (group_id, group) in enumerate(self.groups):
                if group_id == self.current_group:
                    self.group_list.setCurrentRow(i)
                    break
        self.register_group_hotkeys()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            # 判断是否为分组行widget
            if hasattr(obj, '_group_id'):
                # 如果点击的是按钮则不处理
                if self.childAt(event.globalPosition().toPoint()) and isinstance(self.childAt(event.globalPosition().toPoint()), QPushButton):
                    return False
                self.current_group = obj._group_id
                self.update_buttons()
                self.update_groups()
                return True
        return super().eventFilter(obj, event)

    def register_group_hotkeys(self):
        import keyboard
        # 先清除已注册的分组热键，避免重复
        if hasattr(self, '_registered_group_hotkeys'):
            for hotkey in self._registered_group_hotkeys:
                try:
                    keyboard.remove_hotkey(hotkey)
                except Exception:
                    pass
            self._registered_group_hotkeys.clear()
        else:
            self._registered_group_hotkeys = set()
        for group, hotkey in self.group_hotkeys.items():
            if hotkey and hotkey not in self._registered_group_hotkeys:
                print(f"注册分组热键: {hotkey} -> {group}")
                group_id = self.get_group_id_by_name(group)
                keyboard.add_hotkey(hotkey, lambda gid=group_id: self.send_group(gid))
                self._registered_group_hotkeys.add(hotkey)

    def send_current_group(self):
        group_id = self.current_group
        print("触发分组热键，当前分组id:", group_id)
        self.send_group(group_id)

    def add_group_hotkey(self, group):
        from PyQt6.QtWidgets import QInputDialog
        hotkey, ok = QInputDialog.getText(self, "设置分组热键", f"为分组 [{group}] 设置一键发送热键：")
        if ok and hotkey:
            self.group_hotkeys[group] = hotkey
            self.save_group_hotkey(group, hotkey)
            self.update_groups()
            self.register_group_hotkeys()

    def on_group_selected(self, item):
        group_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_group = group_id
        self.update_buttons()
        self.update_groups()

    def update_buttons(self):
        import functools
        # 清空旧按钮和布局
        while self.button_layout.count():
            item = self.button_layout.takeAt(0)
            widget = item.widget()
            layout = item.layout()
            if widget:
                widget.setParent(None)
            if layout:
                while layout.count():
                    sub_item = layout.takeAt(0)
                    sub_widget = sub_item.widget()
                    if sub_widget:
                        sub_widget.setParent(None)
        # 只显示当前分组 id 下的回复，按sort排序
        group_replies = [r for r in self.replies if r.get("group_id") == self.current_group]
        group_replies.sort(key=lambda r: r.get("sort", 0))
        for idx, reply in enumerate(group_replies):
            group = reply.get("group", "默认")
            if reply.get("type", "text") == "image":
                btn = QPushButton(f"[{group}] [图片] {reply['image_path']}")
                btn.clicked.connect(lambda checked, r=reply['image_path']: self.set_current_reply(r))
            else:
                btn = QPushButton(f"[{group}] {reply['text']}")
                btn.clicked.connect(lambda checked, r=reply['text']: self.set_current_reply(r))
            # 设置按钮最大宽度和自动换行
            btn.setMinimumWidth(300)  # 可根据实际调整
            btn.setMaximumWidth(300)  # 可根据实际调整
            btn.setStyleSheet("text-align: left; padding: 6px 8px; font-size: 14px; white-space: normal;")
            # sort输入框
            from PyQt6.QtWidgets import QLineEdit
            sort_edit = QLineEdit(str(reply.get("sort", 0)))
            sort_edit.setFixedWidth(40)
            sort_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sort_edit.setToolTip("排序，数字越小越靠前")
            sort_edit.reply_id = reply["id"]
            def save_sort(edit, rid):
                try:
                    val = int(edit.text())
                except Exception:
                    return
                self.cursor.execute('UPDATE replies SET sort=? WHERE id=?', (val, rid))
                self.conn.commit()
                self.update_groups()
                self.update_buttons()
            sort_edit.editingFinished.connect(functools.partial(save_sort, sort_edit, reply["id"]))
            # 编辑按钮
            global_idx = self.replies.index(reply)
            edit_btn = QPushButton("编辑")
            edit_btn.clicked.connect(lambda checked, i=global_idx: self.edit_reply(i))
            # 删除按钮
            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda checked, i=global_idx: self.delete_reply(i))
            row_layout = QHBoxLayout()
            row_layout.addWidget(btn)
            row_layout.addWidget(sort_edit)
            row_layout.addWidget(edit_btn)
            row_layout.addWidget(del_btn)
            self.button_layout.addLayout(row_layout)

        # 在分组栏右键菜单添加“设置热键”
        self.group_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(self.show_group_context_menu)

    def show_group_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        item = self.group_list.itemAt(pos)
        if item:
            group = item.data(Qt.ItemDataRole.UserRole)
            menu = QMenu()
            set_hotkey_action = menu.addAction("设置一键发送热键")
            set_hotkey_action.triggered.connect(lambda: self.add_group_hotkey(group))
            menu.exec(self.group_list.mapToGlobal(pos))

    def set_current_reply(self, text):
        self.current_reply = text
        # 判断是否为图片路径
        import os
        from PyQt6.QtGui import QImage, QGuiApplication
        import pyperclip
        is_image = False
        if isinstance(text, str) and os.path.isfile(text):
            ext = os.path.splitext(text)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
                is_image = True
        if is_image:
            image = QImage(text)
            if not image.isNull():
                clipboard = QGuiApplication.clipboard()
                clipboard.setImage(image)
                toast_msg = f"图片已复制到剪贴板"
            else:
                toast_msg = f"图片读取失败"
        else:
            pyperclip.copy(text)
            toast_msg = f"已复制: {text}"
        # 弹出短暂提示（toast），1秒后自动消失
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import QTimer
        toast = QLabel(toast_msg, self)
        toast.setStyleSheet("background: #333; color: #fff; border-radius: 6px; padding: 8px 18px; font-size: 15px;")
        toast.setWindowFlags(Qt.WindowType.ToolTip)
        toast.adjustSize()
        # 居中显示在主窗口
        x = self.geometry().center().x() - toast.width() // 2
        y = self.geometry().center().y() - toast.height() // 2
        toast.move(x, y)
        toast.show()
        QTimer.singleShot(1000, toast.close)

    def send_reply(self, text):
        # 防抖：0.8秒内只响应一次
        now = time.time()
        if hasattr(self, '_last_send_time') and now - self._last_send_time < 0.8:
            print("防抖：忽略本次触发")
            return
        self._last_send_time = now
        print("热键触发，内容：", text)
        pyperclip.copy(text)
        # 检查剪贴板内容，最多等1秒
        for _ in range(20):
            if pyperclip.paste() == text:
                break
            time.sleep(0.05)
        else:
            print("警告：剪贴板内容未及时同步，取消粘贴")
            return
        print("剪贴板内容：", pyperclip.paste())
        # 用 AppleScript 方式粘贴 command+v
        import subprocess
        applescript = 'tell application "System Events" to keystroke "v" using command down'
        subprocess.run(['osascript', '-e', applescript])
        time.sleep(0.5)
        self.send_enter()

    def auto_insert(self, text):
        pyperclip.copy(text)
        time.sleep(0.1)  # 确保剪贴板内容已更新
        # 粘贴
        pyautogui.keyDown('command')
        pyautogui.press('v')
        pyautogui.keyUp('command')
        # 可选：再次粘贴一次，防止失效
        # time.sleep(0.1)
        # pyautogui.keyDown('command')
        # pyautogui.press('v')
        # pyautogui.keyUp('command')

    def add_reply(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QLineEdit, QPushButton, QLabel, QFileDialog
        from PyQt6.QtCore import Qt
        class AddReplyDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("添加快捷回复")
                self.resize(360, 160)
                self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
                layout = QVBoxLayout()
                self.type_text = QRadioButton("文本")
                self.type_image = QRadioButton("图片")
                self.type_text.setChecked(True)
                type_layout = QHBoxLayout()
                type_layout.addWidget(QLabel("类型："))
                type_layout.addWidget(self.type_text)
                type_layout.addWidget(self.type_image)
                layout.addLayout(type_layout)
                # 文本输入
                self.text_input = QLineEdit()
                self.text_input.setPlaceholderText("输入回复内容")
                self.text_input.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
                layout.addWidget(self.text_input)
                # 图片选择
                self.image_path = None
                self.image_btn = QPushButton("选择图片")
                self.image_label = QLabel("")
                self.image_btn.hide()
                self.image_label.hide()
                layout.addWidget(self.image_btn)
                layout.addWidget(self.image_label)
                # 按类型切换输入
                def on_type_change():
                    if self.type_text.isChecked():
                        self.text_input.show()
                        self.image_btn.hide()
                        self.image_label.hide()
                        self.text_input.setFocus()
                    else:
                        self.text_input.hide()
                        self.image_btn.show()
                        self.image_label.show()
                self.type_text.toggled.connect(on_type_change)
                self.type_image.toggled.connect(on_type_change)
                # 选择图片
                def choose_image():
                    file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
                    if file_path:
                        self.image_path = file_path
                        self.image_label.setText(file_path)
                self.image_btn.clicked.connect(choose_image)
                # 确定/取消
                btn_layout = QHBoxLayout()
                ok_btn = QPushButton("确定")
                cancel_btn = QPushButton("取消")
                btn_layout.addWidget(ok_btn)
                btn_layout.addWidget(cancel_btn)
                layout.addLayout(btn_layout)
                self.setLayout(layout)
                ok_btn.clicked.connect(self.accept)
                cancel_btn.clicked.connect(self.reject)
            def showEvent(self, event):
                super().showEvent(event)
                if self.type_text.isChecked():
                    self.text_input.setFocus()
            def get_result(self):
                if self.type_text.isChecked():
                    return "文本", self.text_input.text()
                else:
                    return "图片", self.image_path
        # 弹窗
        dlg = AddReplyDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            type_choice, content = dlg.get_result()
            group_id = self.current_group
            group = self.get_group_name_by_id(group_id)
            if type_choice == "文本":
                if content:
                    reply = {"type": "text", "text": content, "group_id": group_id, "group": group}
                    self.replies.append(reply)
                    self.save_reply(reply)
                    self.update_groups()
                    self.update_buttons()
                    self.register_hotkeys()
            else:
                if content:
                    reply = {"type": "image", "image_path": content, "group_id": group_id, "group": group}
                    self.replies.append(reply)
                    self.save_reply(reply)
                    self.update_groups()
                    self.update_buttons()
                    self.register_hotkeys()

    def save_reply(self, reply):
        group_id = reply.get("group_id")
        if reply["type"] == "image":
            self.cursor.execute('INSERT INTO replies (type, image_path, group_id) VALUES (?, ?, ?)',
                                (reply["type"], reply["image_path"], group_id))
        else:
            self.cursor.execute('INSERT INTO replies (type, text, group_id) VALUES (?, ?, ?)',
                                (reply["type"], reply["text"], group_id))
        self.conn.commit()
        reply["id"] = self.cursor.lastrowid  # 加这一行，保证reply有id
        print(f"已添加回复到数据库: {reply}")

    def toggle_on_top(self):
        self.is_on_top = not self.is_on_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.is_on_top)
        self.show()
        self.update_top_icon()

    def update_top_icon(self):
        if self.is_on_top:
            self.top_icon_btn.setText("📌")
            self.top_icon_btn.setToolTip("当前已置顶，点击取消置顶")
        else:
            self.top_icon_btn.setText("📍")
            self.top_icon_btn.setToolTip("当前未置顶，点击置顶窗口")

    def closeEvent(self, event):
        event.accept()

    def send_image(self, image_path):
        print("热键触发，发送图片：", image_path)
        image = QImage(image_path)
        if image.isNull():
            print("图片读取失败")
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setImage(image)
        print("图片已写入剪贴板，等待同步...")
        import time
        time.sleep(0.5)
        import subprocess
        applescript = 'tell application "System Events" to keystroke "v" using command down'
        subprocess.run(['osascript', '-e', applescript])
        self.send_enter()
        
        
    # 参考 send_image 这个，封装一个回车触发
    def send_enter(self):
        print("热键触发，发送回车")
        import subprocess
        applescript = 'tell application "System Events" to key code 36'
        subprocess.run(['osascript', '-e', applescript])

    def delete_reply(self, idx):
        reply = self.replies[idx]
        # 从数据库删除
        if reply["type"] == "image":
            self.cursor.execute('DELETE FROM replies WHERE type=? AND image_path=? AND group_id=?',
                                (reply["type"], reply["image_path"], reply.get("group_id")))
        else:
            self.cursor.execute('DELETE FROM replies WHERE type=? AND text=? AND group_id=?',
                                (reply["type"], reply["text"], reply.get("group_id")))
        self.conn.commit()
        # 从内存删除
        self.replies.pop(idx)
        self.update_groups()
        self.update_buttons()
        self.register_hotkeys()

    def edit_reply(self, idx):
        from PyQt6.QtWidgets import QInputDialog, QFileDialog
        reply = self.replies[idx]
        group_id = reply.get("group_id")
        group = reply.get("group", "默认")
        # 先查出原始id
        if reply.get("type") == "image":
            old_path = reply["image_path"]
            self.cursor.execute('SELECT id FROM replies WHERE type=? AND image_path=? AND group_id=?', (reply["type"], old_path, group_id))
        else:
            old_text = reply["text"]
            self.cursor.execute('SELECT id FROM replies WHERE type=? AND text=? AND group_id=?', (reply["type"], old_text, group_id))
        row = self.cursor.fetchone()
        reply_id = row[0] if row else None
        if not reply_id:
            print("未找到原始回复，无法编辑")
            return
        if reply.get("type") == "image":
            file_path, _ = QFileDialog.getOpenFileName(self, "选择新图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
            if file_path:
                # 更新内存
                reply["image_path"] = file_path
                # 更新数据库
                self.cursor.execute('UPDATE replies SET image_path=? WHERE id=?', (file_path, reply_id))
                self.conn.commit()
                self.update_groups()
                self.update_buttons()
        else:
            text, ok = QInputDialog.getText(self, "编辑回复", "修改回复内容：", text=reply.get("text", ""))
            if ok and text:
                reply["text"] = text
                self.cursor.execute('UPDATE replies SET text=? WHERE id=?', (text, reply_id))
                self.conn.commit()
                self.update_groups()
                self.update_buttons()

    def get_reply_id(self, reply):
        # 通过内容和分组查找id
        if reply.get("type") == "image":
            self.cursor.execute('SELECT id FROM replies WHERE type=? AND image_path=? AND group_id=?', (reply["type"], reply["image_path"], reply["group_id"]))
        else:
            self.cursor.execute('SELECT id FROM replies WHERE type=? AND text=? AND group_id=?', (reply["type"], reply["text"], reply["group_id"]))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def send_group(self, group_id):
        print("触发分组热键", group_id)
        # 依次发送该分组id下所有快捷回复，按sort排序
        import time
        group_replies = [r for r in self.replies if r.get("group_id") == group_id]
        group_replies.sort(key=lambda r: r.get("sort", 0))
        for reply in group_replies:
            if reply.get("type", "text") == "image":
                self.send_image(reply["image_path"])
            else:
                self.send_reply(reply["text"])
            time.sleep(0.5)  # 每条间隔0.5秒，防止粘贴冲突

    def get_default_group_id(self):
        self.cursor.execute('SELECT id FROM group_hotkeys WHERE group_name=?', ("默认",))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def toggle_reply_area(self):
        self.reply_area_expanded = not self.reply_area_expanded
        self.reply_area_widget.setVisible(self.reply_area_expanded)
        if self.reply_area_expanded:
            self.toggle_reply_area_btn.setText("<")
            # 恢复窗口宽度限制
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            if self._expanded_width:
                self.resize(self._expanded_width, self.height())
        else:
            self.toggle_reply_area_btn.setText(">")
            if not self._expanded_width:
                self._expanded_width = self.width()
            group_width = self.group_area_widget.width()
            btn_width = self.toggle_reply_area_btn.width()
            margin = 50
            shrink_width = group_width + btn_width + margin
            self.setMinimumWidth(shrink_width)
            self.setMaximumWidth(shrink_width)
            self.resize(shrink_width, self.height())

if __name__ == "__main__":
    import sys
    import signal
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("tb.icns"))
    window = QuickReplyAutoInsert()
    window.show()
    # 让 Ctrl+C 能终止程序
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    sys.exit(app.exec()) 