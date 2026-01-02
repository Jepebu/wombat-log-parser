# wombat_gui.py

import sys
from datetime import datetime
import os
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QHBoxLayout, QWidget, QComboBox, QLabel, 
                             QCheckBox, QPushButton, QFileDialog, QMessageBox, QTabWidget, QComboBox,
                             QDialog, QLineEdit, QDialogButtonBox)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

import threading # For non-blocking file share setups
from io import StringIO # For treating CSV strings as text files

from wombat_session import GroupSession


class FileShareDialog(QDialog):
    def __init__(self, parent=None, fname=None, session_code=None):
        super().__init__(parent)
        self.setWindowTitle("Log File Sharing")
        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5;"
        code_font_style = "font-size: 12px; font-weight: bold; color: #e5e5e5; border: 2px solid black;"
        layout = QVBoxLayout()

        file_message = QLabel(f"Sharing file \"{fname}\".")
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Import Dialog")

        base_font_style = "font-size: 14px; font-weight: bold; color: #e5e5e5;"
        layout = QVBoxLayout()

        message = QLabel("Enter session code:")
        message.setStyleSheet(base_font_style)
        self.session_code_input = QLineEdit()
        self.merge_check = QCheckBox("Merge with current data")


        # Standard OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept) # Closes dialog with "Success" result
        buttons.rejected.connect(self.reject) # Closes dialog with "Failure" result


        layout.addWidget(message)
        layout.addWidget(self.session_code_input)
        layout.addWidget(self.merge_check)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_input(self):
        return self.session_code_input.text()

    def get_merge(self):
        return self.merge_check.checkState()






class CheckableComboBox(QComboBox):
    # Define the custom signal at the class level
    selectionChanged = pyqtSignal()

    def __init__(self, placeholder_text=None):
        super().__init__()
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        if placeholder_text is not None:
            self.lineEdit().setPlaceholderText(placeholder_text)
        else:
            self.lineEdit().setPlaceholderText("Select Options...")
        
        self.model = QStandardItemModel(self)
        self.setModel(self.model)
        
        # Listen to the MODEL for changes, not the mouse.
        # This fires whenever a checkbox is toggled.
        self.model.itemChanged.connect(self.on_item_changed)
        
        # Install event filter to keep the popup open
        self.view().viewport().installEventFilter(self)

    def on_item_changed(self, item):
        # Update the text box to summarize selection
        self.update_display_text()
        # Fire our custom signal to tell the Main Window to update the graph
        self.selectionChanged.emit()

    def eventFilter(self, obj, event):
        # We still need this filter ONLY to stop the popup from closing
        if obj == self.view().viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            index = self.view().indexAt(event.pos())
            if index.isValid():
                item = self.model.itemFromIndex(index)
                
                # Toggle state manually (because we consume the event below)
                if item.checkState() == Qt.CheckState.Checked:
                    item.setCheckState(Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(Qt.CheckState.Checked)
                
                # Prevent the dropdown from closing
                return True
                
        return super().eventFilter(obj, event)

    def update_display_text(self):
        items = self.get_checked_items()
        text = ""
        if not items:
            text = ""
        elif len(items) == 1:
            text = items[0]
        elif len(items) == self.model.rowCount():
            text = "All Skills"
        else:
            text = f"{len(items)} Skills Selected"
        
        self.lineEdit().setText(text)

    def add_item(self, text):
        item = QStandardItem(text)
        item.setCheckable(True)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.model.appendRow(item)
        
    def get_checked_items(self):
        checked_items = []
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_items.append(item.text())
        return checked_items

    def get_all_items(self):
        all_items = []
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            all_items.append(item.text())
        return all_items

    def clear(self):
        self.model.clear()
        self.lineEdit().clear()

class DamageAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Damage Log Analytics")
        self.resize(1000, 600)

        # Initialize with a placeholder
        self.df = pd.DataFrame(columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])

        # Main Layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

# --- 1. TOP TOOLBAR & FILTERS (Shared) ---
        top_controls = QVBoxLayout()

        ### Widgets for row one
        row_1 = QHBoxLayout()
        
        # Load Button
        self.load_btn = QPushButton("📂 Load Combat Log")
        self.load_btn.clicked.connect(self.open_file_dialog)

        self.load_extra_log_btn = QPushButton("➕ Add Another Log")
        self.load_extra_log_btn.setEnabled(False)
        self.load_extra_log_btn.clicked.connect(lambda : self.open_file_dialog(merge=True))

        self.send_log_btn = QPushButton("➡️ Share a Log File by code")
        self.send_log_btn.setEnabled(True) # We want sharing to be enabled without needing to load a log file.
        self.send_log_btn.clicked.connect(self.share_file)

        self.import_log_btn = QPushButton("⬇️ Import a Log File by code")
        self.import_log_btn.setEnabled(True) # We want importing to be enabled without needing to load a log file.
        self.import_log_btn.clicked.connect(self.receive_file)
        
        self.export_log_btn = QPushButton("📑 Export Current View to File")
        self.export_log_btn.setEnabled(False)
        self.export_log_btn.clicked.connect(self.export_log_file)


        row_1.addWidget(self.load_btn)
        row_1.addWidget(self.load_extra_log_btn)
        row_1.addWidget(self.send_log_btn)
        row_1.addWidget(self.import_log_btn)
        row_1.addWidget(self.export_log_btn)
        row_1.addStretch()

        ### Widgets for row two
        row_2 = QHBoxLayout()
        # Filters
        # Create the skill filter
        self.skill_combo = CheckableComboBox()
        self.skill_combo.setEnabled(False)
        self.skill_combo.setMinimumWidth(100)       # Button width
        self.skill_combo.view().setMinimumWidth(400) # Popup list width
        self.skill_combo.selectionChanged.connect(self.update_all_charts)

        # Create the target filter
        self.target_combo = CheckableComboBox()
        self.target_combo.setEnabled(False)
        self.target_combo.setMinimumWidth(100)       # Button width
        self.target_combo.view().setMinimumWidth(400) # Popup list width
        self.target_combo.selectionChanged.connect(self.update_all_charts)

        # Create the caster filter
        self.caster_combo = CheckableComboBox()
        self.caster_combo.setEnabled(False)
        self.caster_combo.setMinimumWidth(100)       # Button width
        self.caster_combo.view().setMinimumWidth(400) # Popup list width
        self.caster_combo.selectionChanged.connect(self.update_all_charts)

        # Create the filter reset button
        self.reset_btn = QPushButton("Reset Filter")
        self.reset_btn.setFixedSize(80, 25)
        self.reset_btn.clicked.connect(self.reset_filters)

        self.crit_check = QCheckBox("Show Critical Hits Only")
        self.crit_check.setEnabled(False)
        self.crit_check.stateChanged.connect(self.update_all_charts)

        self.heavy_check = QCheckBox("Show Heavy Attacks Only")
        self.heavy_check.setEnabled(False)
        self.heavy_check.stateChanged.connect(self.update_all_charts)

        self.grouping_check = QCheckBox("Group Stats by Player")
        self.grouping_check.setEnabled(False)
        self.grouping_check.stateChanged.connect(self.update_all_charts)


        row_2.addWidget(self.crit_check)
        row_2.addWidget(self.heavy_check)
        row_2.addWidget(self.grouping_check)
        row_2.addWidget(QLabel("Filter by skill(s)"))
        row_2.addWidget(self.skill_combo)
        row_2.addSpacing(15) # Spacing
        row_2.addWidget(QLabel("Filter by targets(s)"))
        row_2.addWidget(self.target_combo)
        row_2.addSpacing(15) # Spacing
        row_2.addWidget(QLabel("Filter by player(s)"))
        row_2.addWidget(self.caster_combo)
        row_2.addSpacing(30) # Spacing
        row_2.addWidget(self.reset_btn)
        row_2.addStretch()


        top_controls.addLayout(row_1)
        top_controls.addLayout(row_2)

        self.layout.addLayout(top_controls)

        

# --- 2. THE TAB WIDGET ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # --- Tab 1: Overview (The Dashboard) ---
        self.tab_overview = QWidget()
        self.tab_overview_layout = QVBoxLayout(self.tab_overview)

        # Create Labels for the stats (Start with placeholder text)
        self.lbl_total_damage = QLabel("Total Damage: 0")
        self.lbl_dps = QLabel("Overall DPS: 0")
        self.lbl_duration = QLabel("Fight Duration: 0s")
        self.lbl_top_skill = QLabel("Top Skill: None")

        # Style the labels (CSS-like styling in PyQt)
        # We make them large and bold
        # Make the colors 'greyed out' until a combat log is imported.
        font_style = "font-size: 24px; font-weight: bold; color: #333;"
        self.lbl_total_damage.setStyleSheet(font_style)
        self.lbl_dps.setStyleSheet(font_style)
        self.lbl_duration.setStyleSheet("font-size: 18px; color: #555;")
        self.lbl_top_skill.setStyleSheet("font-size: 18px; color: #555;")

        # Add them to the layout with some spacing
        self.tab_overview_layout.addStretch()
        self.tab_overview_layout.addWidget(self.lbl_total_damage)
        self.tab_overview_layout.addWidget(self.lbl_dps)
        self.tab_overview_layout.addWidget(self.lbl_duration)
        self.tab_overview_layout.addWidget(self.lbl_top_skill)
        self.tab_overview_layout.addStretch()

        # Center align the text
        for lbl in [self.lbl_total_damage, self.lbl_dps, self.lbl_duration, self.lbl_top_skill]:
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add to the Tab Widget
        self.tabs.addTab(self.tab_overview, "Overview")

        # --- Tab 2: Total Damage ---
        self.tab_total = QWidget()
        self.tab_total_layout = QVBoxLayout(self.tab_total)
        
        self.fig_total = Figure(figsize=(5, 4), dpi=100)
        self.canvas_total = FigureCanvas(self.fig_total)
        self.tab_total_layout.addWidget(self.canvas_total)
        
        self.tabs.addTab(self.tab_total, "Damage By Source")

        # --- Tab 3: DPS (Damage Per Second) ---
        self.tab_dps = QWidget()
        self.tab_dps_layout = QVBoxLayout(self.tab_dps)
        
        self.fig_dps = Figure(figsize=(5, 4), dpi=100)
        self.canvas_dps = FigureCanvas(self.fig_dps)
        self.tab_dps_layout.addWidget(self.canvas_dps)
        
        self.tabs.addTab(self.tab_dps, "Damage Per Second (DPS)")

        self.tabs.currentChanged.connect(self.on_tab_change)


    def share_file(self):
        """
        Session manager for sharing a log file via session code.
        Generates UPnP session and session code, then sets up a listening port.
        """
        log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
        fname, _ = QFileDialog.getOpenFileName(self, "Open Combat Log", log_dir, "Text Files (*.txt)")
        session = GroupSession()
        try:
            session_code = session.generate_session_code()
            file_share_thread = threading.Thread(target=session.share, args=(fname,))
            file_share_thread.start()
            dialog = FileShareDialog(parent=self, fname=fname, session_code=session_code)
            dialog.exec()
            if file_share_thread.is_alive():
                session.server_sock.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error while sharing log file.\n{session.status}")
        finally:
            if not session.server_sock._closed:
                session.server_sock.close()



    def receive_file(self):
        """
        Session manager for receiving a log file via session code.
        Establishes connection and authenticates to the person sharing the file, then imports the data directly.
        """
        dialog = FileImportDialog(parent=self)
        if not dialog.exec():
            return
        session_code = dialog.get_input()
        merge_files = dialog.get_merge()
        session = GroupSession()
        received_data = session.connect_by_code(session_code)
        if received_data is not None:
            self.open_file_dialog(csv_data=received_data, merge=merge_files)
        else:
            QMessageBox.critical(self, "Error", f"Unable to download log file from remote user.\n{session.status}")

    def export_log_file(self):
        """
        Export a current filtered/merged view as a single re-usable log file.
        """
        log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
        fname = "WombatLogMerged.txt"
        file_path = os.path.join(log_dir, fname)
        with open(file_path, 'w') as outfile:
            outfile.write("WombatLogVersion,1\n")
        tmpdf = self.get_filtered_data()
        tmpdf.to_csv(os.path.join(log_dir, fname), index=False, header=False, mode='a', columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])
        QMessageBox.information(self, "Success", f"Combined log file written to {file_path}")
            
            

    def on_tab_change(self, index):
        """
        Event listener for tab switching. 
        Forces a layout refresh because charts drawn on hidden tabs 
        often have broken margins until redrawn.
        """
        # index 0 is overview, index 1 is damage by skill, index 2 is DPS
        if index == 2:
            self.fig_dps.tight_layout()
            self.canvas_dps.draw()

        elif index == 1:             
            self.fig_total.tight_layout()
            self.canvas_total.draw()

        # We don't have a canvas for the overview page so no reformatting is needed.
        elif index == 0:
            pass

        # Add this method:
    def reset_filters(self):
            self.skill_combo.clear()
            # Refill with unchecked items or just clear selection
            if not self.df.empty:
                skills = sorted(self.df['SkillName'].dropna().unique().astype(str))
                for skill in skills:
                    self.skill_combo.add_item(skill)
            self.update_all_charts()

    def open_file_dialog(self, merge=False, csv_data=None):
        # Open Explorer in the log directory used by TnL
        if csv_data is not None:
            fname = StringIO(csv_data)
        else:
            log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
            fname, _ = QFileDialog.getOpenFileName(self, "Open Combat Log", log_dir, "Text Files (*.txt)")
        if fname:
            try:
                this_df = pd.read_csv(fname, header=0, names=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])

                # PRE-PROCESS TIMESTAMP for DPS Calculation
                # Format: 20251207-13:04:08:490
                # We need to parse this to a datetime object
                if 'Timestamp' in this_df.columns:
                    this_df['DT'] = pd.to_datetime(this_df['Timestamp'], format='%Y%m%d-%H:%M:%S:%f', errors='coerce')


                # Handle merging multiple log files together
                if merge:
                    self.df = pd.concat([self.df, this_df], ignore_index=True)
                else:
                    self.df = this_df
                    self.skill_combo.clear()
                    self.target_combo.clear()
                    self.caster_combo.clear()
                    
                    

                # Add skills to drop down
                self.skill_combo.blockSignals(True)
                current_skills = self.skill_combo.get_all_items()
                if 'SkillName' in self.df.columns:
                    skills = sorted(self.df['SkillName'].dropna().unique().astype(str))
                    for skill in [S for S in skills if S not in current_skills]:
                        self.skill_combo.add_item(skill) # Use our custom add_item method

                    
                # Add targets to drop down
                self.target_combo.blockSignals(True)
                current_targets = self.target_combo.get_all_items()
                if 'TargetName' in self.df.columns:
                    targets = sorted(self.df['TargetName'].dropna().unique().astype(str))
                    for target in [T for T in targets if T not in current_targets]:
                        self.target_combo.add_item(target) # Use our custom add_item method

                # Add casters to drop down
                self.caster_combo.blockSignals(True)
                current_casters = self.caster_combo.get_all_items()
                if 'CasterName' in self.df.columns:
                    casters = sorted(self.df['CasterName'].dropna().unique().astype(str))
                    for caster in [C for C in casters if C not in current_casters]:
                        self.caster_combo.add_item(caster) # Use our custom add_item method


                self.skill_combo.setEnabled(True)
                self.target_combo.setEnabled(True)
                self.caster_combo.setEnabled(True)
                self.load_extra_log_btn.setEnabled(True)
                self.export_log_btn.setEnabled(True)
                self.crit_check.setEnabled(True)
                self.heavy_check.setEnabled(True)
                self.grouping_check.setEnabled(True)

                font_style = "font-size: 24px; font-weight: bold; color: #e5e5e5;"
                self.lbl_total_damage.setStyleSheet(font_style)
                self.lbl_dps.setStyleSheet(font_style)
                self.lbl_duration.setStyleSheet("font-size: 18px; color: #cccccc;")
                self.lbl_top_skill.setStyleSheet("font-size: 18px; color: #cccccc;")

                # Unblock signals from the combo boxes
                self.skill_combo.blockSignals(False)
                self.target_combo.blockSignals(False)
                self.caster_combo.blockSignals(False)
                
                self.update_all_charts()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error reading file:\n{e}")

    def get_filtered_data(self):
        """Helper to get current dataframe based on filters"""
        if self.df.empty: return pd.DataFrame()
        
        temp_df = self.df.copy()
        selected_skills = self.skill_combo.get_checked_items()
        selected_targets = self.target_combo.get_checked_items()
        selected_casters = self.caster_combo.get_checked_items()


        # Filter by selected skills
        if selected_skills:
            temp_df = temp_df[temp_df['SkillName'].isin(selected_skills)]

        # Filter by selected targets
        if selected_targets:
            temp_df = temp_df[temp_df['TargetName'].isin(selected_targets)]

        # Filter by selected casters
        if selected_casters:
            temp_df = temp_df[temp_df['CasterName'].isin(selected_targets)]

        if self.crit_check.isChecked():
            temp_df = temp_df[temp_df['CriticalHit'] == 1]
        if self.heavy_check.isChecked():
            temp_df = temp_df[temp_df['HeavyHit'] == 1]
        return temp_df

    def format_k_m(self, x, pos):
        """Formatter for 1K, 1M"""
        if x >= 1e6: return f'{x*1e-6:.1f}M'
        if x >= 1e3: return f'{x*1e-3:.0f}K'
        return f'{x:.0f}'

    def update_all_charts(self):
        data = self.get_filtered_data()

        # Update Tab 1
        self.update_overview(data)
        
        # Update Tab 2
        self.plot_total_damage(data)
        
        # Update Tab 3
        self.plot_dps(data)

    def update_overview(self, data):
        if data.empty:
            self.lbl_total_damage.setText("Total Damage: 0")
            self.lbl_dps.setText("Overall DPS: 0")
            return

        # 1. Total Damage
        total_dmg = data['DamageAmount'].sum()
        
        # 2. Duration & DPS
        # We use the full DF for duration so filtering doesn't skew the time
        if 'DT' in self.df.columns and not self.df.empty:
            start = self.df['DT'].min()
            end = self.df['DT'].max()
            duration = (end - start).total_seconds()
            if duration < 1: duration = 1
        else:
            duration = 1
            
        dps = total_dmg / duration

        # 3. Top Skill
        # Get the skill with the highest sum of damage
        if not data.empty:
            top_skill_series = data.groupby('SkillName')['DamageAmount'].sum().sort_values(ascending=False)
            # Hide the 'Top Skill' line if we're filtered to one skill.
            if top_skill_series.size == 1:
                self.lbl_top_skill.setStyleSheet("font-size: 18px; color: #2d2d2d;")
            else:
                self.lbl_top_skill.setStyleSheet("font-size: 18px; color: #cccccc;")

            if not top_skill_series.empty:
                top_skill_name = top_skill_series.index[0]
                top_skill_val = top_skill_series.iloc[0]
                top_skill_txt = f"{top_skill_name} ({self.format_k_m(top_skill_val, 0)})"
            else:
                top_skill_txt = "None"
        else:
            top_skill_txt = "None"

        # 4. Update Labels with Formatted Text
        # {:,.0f} puts commas in the numbers (e.g. 1,200,500)
        self.lbl_total_damage.setText(f"Total Damage: {total_dmg:,.0f}")
        self.lbl_dps.setText(f"Overall DPS: {dps:,.0f}")
        self.lbl_duration.setText(f"Fight Duration: {duration:.1f}s")
        self.lbl_top_skill.setText(f"Top Skill: {top_skill_txt}")

    def plot_total_damage(self, data):
        self.fig_total.clear()
        ax = self.fig_total.add_subplot(111)

        if not data.empty:
            if self.grouping_check.isChecked():
                chart_data = data.groupby('CasterName')['DamageAmount'].sum().sort_values(ascending=True)
            else:
                chart_data = data.groupby('SkillName')['DamageAmount'].sum().sort_values(ascending=True)
            
            chart_data.plot(kind='barh', ax=ax, color='#4f81bd')
            ax.xaxis.set_major_formatter(ticker.FuncFormatter(self.format_k_m))
            ax.set_title("Total Damage Breakdown")
            self.fig_total.tight_layout()
        else:
            ax.text(0.5, 0.5, "No Data", ha='center')
        
        self.canvas_total.draw()

    def plot_dps(self, data):
        self.fig_dps.clear()
        ax = self.fig_dps.add_subplot(111)

        # Ensure we have data and the 'DT' column (created in open_file_dialog)
        if not data.empty and 'DT' in self.df.columns:
            
            # --- 1. PREPARE THE DATA ---
            # Group by 1-Second intervals ('1s') and SkillName
            # .unstack() moves SkillName from rows to columns
            # .fillna(0) ensures seconds with no hits drop to 0 damage
            if self.grouping_check.isChecked():
                dps_df = data.groupby([pd.Grouper(key='DT', freq='1s'), 'CasterName'])['DamageAmount'].sum().unstack().fillna(0)
            else:
                dps_df = data.groupby([pd.Grouper(key='DT', freq='1s'), 'SkillName'])['DamageAmount'].sum().unstack().fillna(0)
            
            # --- 2. CONVERT TO RELATIVE TIME ---
            # Currently, the index is timestamps (2025-12-07 13:04:08). 
            # We want "Seconds since fight start".
            start_time = dps_df.index.min()
            dps_df.index = (dps_df.index - start_time).total_seconds()

            # --- 3. HANDLE "TOO MANY LINES" CLUTTER ---
            # If "All Skills" is selected, plotting 50+ lines is messy.
            # If > 10 skills are present, plot only the Top 5 damage sources
            if len(dps_df.columns) > 10:
                # Find top 5 skills by total damage
                top_5 = dps_df.sum().sort_values(ascending=False).head(5).index
                dps_df = dps_df[top_5] # Filter to only keep top 5 columns
                ax.set_title("DPS Over Time (Top 5 Skills)")
            else:
                ax.set_title("DPS Over Time")

            # --- 4. PLOT ---
            # 'chart_data.plot' uses the DataFrame index (Seconds) as X 
            # and Columns (Skills) as the lines.
            dps_df.plot(kind='line', ax=ax, linewidth=1.5)
            
            # --- 5. FORMATTING ---
            ax.set_ylabel("Damage")
            ax.set_xlabel("Time Elapsed (Seconds)")
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Fix Legend: Put it outside the graph if there are many items
            ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='small')
            
            # Use the K/M formatter for the Y-axis (Damage)
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(self.format_k_m))
            
            self.fig_dps.tight_layout()

        else:
            ax.text(0.5, 0.5, "No Data or Timestamps", ha='center')
        
        self.canvas_dps.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DamageAnalyzer()
    window.show()
    sys.exit(app.exec())