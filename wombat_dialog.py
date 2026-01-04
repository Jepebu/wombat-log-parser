# wombat_dialog.py
# Dialog menus for wombat parser

from PyQt6.QtWidgets import  (QDialog, QLineEdit, QDialogButtonBox, QFileDialog,
                              QVBoxLayout, QLabel, QPushButton, QCheckBox, QTextEdit, QListWidget,
                              QMessageBox)
from PyQt6.QtCore import Qt
import os

class TagLoadDialog(QDialog):
    def __init__(self, parent=None, tag_name="", tag_log_files=None):
        super().__init__(parent)
        self.setWindowTitle("Loading Tag")
        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5;"
        layout = QVBoxLayout()

        name_label = QLabel("Tag Name")
        name_label.setStyleSheet(base_font_style)
        self.name_input = QLineEdit(tag_name)
        self.name_input.setEnabled(False)
        self.files_label = QLabel("Files From Tag")
        self.files_label.setStyleSheet('text-align: center;')
        self.file_list = QListWidget(self)
        if tag_log_files is not None:
          self.file_list.addItems(tag_log_files)

        self.merge_check = QCheckBox("Merge with current data")
        self.adjust_timestamp_check = QCheckBox("Adjust timestamps")
        self.adjust_timestamp_check.setChecked(True)

        

        # Standard OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept) # Closes dialog with "Success" result
        buttons.rejected.connect(self.reject) # Closes dialog with "Failure" result

        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(self.files_label)
        layout.addWidget(self.file_list)
        layout.addWidget(self.merge_check)
        layout.addWidget(self.adjust_timestamp_check)
        layout.addSpacing(20)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_name(self):
      return self.name_input.text()

    def get_merge_check(self):
      return self.merge_check.isChecked()

    def get_timestamp_check(self):
      return self.adjust_timestamp_check.isChecked()



class TagEditDialog(QDialog):
    def __init__(self, parent=None, tag_name="", tag_notes="", tag_log_files=None):
        super().__init__(parent)
        self.setWindowTitle("Edit a Tag")
        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5;"
        layout = QVBoxLayout()
        self.delete_tag_bool = False
        self.log_files = tag_log_files if tag_log_files is not None else []

        name_label = QLabel("Tag Name")
        name_label.setStyleSheet(base_font_style)
        self.name_input = QLineEdit(tag_name)
        desc_label = QLabel("Tag Notes")
        self.desc_input = QTextEdit(tag_notes)
        self.files_button = QPushButton("Add Log Files")
        self.files_button.clicked.connect(self.open_file_dialog)
        self.file_list = QListWidget(self)
        if tag_log_files is not None:
          self.file_list.addItems(tag_log_files)
        self.file_list.itemClicked.connect(self.remove_log_file)

        self.delete_tag_button = QPushButton("Delete Tag")
        self.delete_tag_button.setMinimumWidth(150)
        self.delete_tag_button.setStyleSheet('text-align: center;')
        self.delete_tag_button.clicked.connect(self.confirm_delete)
        

        # Standard OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept) # Closes dialog with "Success" result
        buttons.rejected.connect(self.reject) # Closes dialog with "Failure" result

        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(desc_label)
        layout.addWidget(self.desc_input)
        layout.addWidget(self.files_button)
        layout.addWidget(self.file_list)
        layout.addSpacing(10)
        layout.addWidget(self.delete_tag_button)
        layout.addSpacing(20)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_name(self):
      return self.name_input.text()

    def get_description(self):
      return self.desc_input.toPlainText()

    def open_file_dialog(self):
      log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
      log_files, _ = QFileDialog.getOpenFileNames(self, "Open Combat Log", log_dir, "Text Files (*.txt)")
      self.log_files.extend(log_files)
      self.file_list.addItems(log_files)

    def remove_log_file(self, file):
      row = self.file_list.row(file)
      self.file_list.takeItem(row)

    def get_delete_bool(self):
      return self.delete_tag_bool

    def confirm_delete(self):
        reply = QMessageBox.question(
            self,
            'Confirmation Deletion',
            f'Do you want to delete this tag?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No # Combine buttons with a bitwise OR |
        )
        if reply == QMessageBox.StandardButton.Yes:
          self.delete_tag_bool = True
          self.close()

    def get_log_files(self):
      return self.log_files



class TagSaveDialog(QDialog):
    def __init__(self, tag_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Changes")
        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5;"
        layout = QVBoxLayout()

        message_label = QLabel(f"Would you like to save changes for tag '{tag_name}'?")
        message_label.setStyleSheet(base_font_style)

        # Standard Yes/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | 
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept) # Closes dialog with "Success" result
        buttons.rejected.connect(self.reject) # Closes dialog with "Failure" result

        layout.addWidget(message_label)
        layout.addWidget(buttons)
        self.setLayout(layout)




class TagCreateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create a New tag")
        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5;"
        layout = QVBoxLayout()

        name_label = QLabel("Tag Name")
        name_label.setStyleSheet(base_font_style)
        self.name_input = QLineEdit()
        desc_label = QLabel("Tag Notes")
        self.desc_input = QTextEdit()
        self.files_button = QPushButton("Add Log Files")
        self.files_button.clicked.connect(self.open_file_dialog)
        file_list_label = QLabel("Selected Files")
        self.file_list = QListWidget(self)
          
        # Standard OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept) # Closes dialog with "Success" result
        buttons.rejected.connect(self.reject) # Closes dialog with "Failure" result

        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(desc_label)
        layout.addWidget(self.desc_input)
        layout.addWidget(file_list_label)
        layout.addWidget(self.file_list)
        layout.addWidget(self.files_button)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_name(self):
      return self.name_input.text()

    def get_description(self):
      return self.desc_input.toPlainText()

    def open_file_dialog(self):
      log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
      self.log_files, _ = QFileDialog.getOpenFileNames(self, "Open Combat Log", log_dir, "Text Files (*.txt)")
      self.file_list.addItems(self.log_files)

    def get_files(self):
      return self.log_files


class FileShareDialog(QDialog):
    def __init__(self, parent=None, fname=None, session_code=None):
        super().__init__(parent)
        self.setWindowTitle("Log File Sharing")
        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5; text-align: center;"
        code_font_style = "font-size: 12px; font-weight: bold; color: #e5e5e5; border: 2px solid black;"
        layout = QVBoxLayout()

        file_message = QLabel(f"Sharing current view, close this window to stop sharing.")
        file_message.setStyleSheet(base_font_style)

        session_code_pre = QLabel(f"Send this code to the receiver:")
        session_code_pre.setStyleSheet(base_font_style)

        session_code_message = QLabel(session_code)
        session_code_message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        session_code_message.setStyleSheet(code_font_style)

        end_button = QPushButton("Stop Sharing")
        end_button.setMaximumWidth(200)
        end_button.clicked.connect(self.reject)

        layout.addWidget(file_message)
        layout.addWidget(session_code_pre)
        layout.addWidget(session_code_message)
        layout.addWidget(end_button)

        self.setLayout(layout)

class FileImportDialog(QDialog):
    def __init__(self, parent=None, method='local'):
        super().__init__(parent)
        self.setWindowTitle("File Import Dialog")

        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5;"
        layout = QVBoxLayout()

        if method == 'by_code':

          message = QLabel("Enter session code:")
          message.setStyleSheet(base_font_style)
          self.session_code_input = QLineEdit()
          layout.addWidget(message)
          layout.addWidget(self.session_code_input)
        
        elif method == 'local':

          self.files_button = QPushButton("Select Log File(s)")
          self.files_button.clicked.connect(self.open_file_dialog)

          self.file_list = QListWidget(self)
          file_list_label = QLabel("Selected Files")

          layout.addWidget(self.files_button)
          layout.addWidget(file_list_label)
          layout.addWidget(self.file_list)

        self.merge_check = QCheckBox("Merge with current data")
        self.adjust_timestamp_check = QCheckBox("Adjust timestamps")
        self.adjust_timestamp_check.setChecked(True)


        # Standard OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept) # Closes dialog with "Success" result
        buttons.rejected.connect(self.reject) # Closes dialog with "Failure" result


        layout.addWidget(self.adjust_timestamp_check)
        layout.addWidget(self.merge_check)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_input(self):
        return self.session_code_input.text()

    def get_merge_check(self):
        return self.merge_check.isChecked()

    def get_timestamp_check(self):
        return self.adjust_timestamp_check.isChecked()

    def get_files(self):
      return self.log_files


    def open_file_dialog(self):
      log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
      self.log_files, _ = QFileDialog.getOpenFileNames(self, "Open Combat Log", log_dir, "Text Files (*.txt)")
      self.file_list.addItems(self.log_files)