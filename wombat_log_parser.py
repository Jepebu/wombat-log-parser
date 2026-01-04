# wombat_gui.py

import sys
from datetime import datetime, timedelta
import os
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QHBoxLayout, QWidget, QComboBox, QLabel, 
                             QCheckBox, QPushButton, QFileDialog, QMessageBox, QTabWidget, QComboBox,
                             QMenu)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

import threading # For non-blocking file share setups
from io import StringIO # For treating CSV strings as text files
import random # For randomized file names when sharing files.

### Custom libraries
from wombat_session import GroupSession
from wombat_dialog import FileImportDialog, FileShareDialog, TagCreateDialog, TagEditDialog, TagLoadDialog
from wombat_tags import Tag


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
            text = "All Items"
        elif len(items) == 1:
            text = items[0]
        elif len(items) == self.model.rowCount():
            text = "All Items"
        else:
            text = f"{len(items)} Items Selected"
        
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
        app_dir = os.path.join(os.getenv('LOCALAPPDATA'),'WombatLogs')
        if not os.path.exists(app_dir):
            os.makedirs(app_dir)

        # Some vars attached to the main window so we can keep track of our state
        self.group_mode = 'SkillName'
        self.loaded_logs = []
        current_tags = Tag.get_tags()



        self.setWindowTitle("Damage Log Analytics")
        self.resize(1000, 600)

        # Initialize with a placeholder
        self.df = pd.DataFrame(columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])

        # Main Layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

# --- 1. TOP TOOLBAR AND SUBMENUS ---
        self.top_controls = QVBoxLayout()

        ### Widgets for row one
        row_1 = QHBoxLayout()
        
        ### --- LOAD MENU --- ###
        self.load_btn = QPushButton("📂 Load ")

        # Context menu for loading options
        # Will appear with 'Log' and 'Profile' when clicked
        load_options = QMenu(self)

        load_log_submenu = QMenu("Log", self)
        
        ## Option for loading from a file
        load_log_action_file = QAction("From File", self)
        load_log_action_file.triggered.connect(self.import_logs)
        load_log_submenu.addAction(load_log_action_file)

        ## Option for importing by code
        load_log_action_code = QAction("From Code", self)
        load_log_action_code.triggered.connect(self.receive_file)
        load_log_submenu.addAction(load_log_action_code)

        # Option for loading all logs with a specific tag
        self.load_tag_submenu = QMenu("Tag", self)
        self.load_tag_submenu_actions = {}
        for tag in current_tags:
            this_action = QAction(tag.name, self)
            this_action.triggered.connect(lambda checked, name_to_load=tag.name: self.load_logs_by_tag(name_to_load))
            self.load_tag_submenu.addAction(this_action)
            self.load_tag_submenu_actions[this_action.text()] = this_action
        
        if len(current_tags) == 0:
            no_tags_action = QAction("No Tags Found", self)
            no_tags_action.setEnabled(False)
            self.load_tag_submenu.addAction(no_tags_action)
            self.load_tag_submenu_actions["No Tags Found"] = no_tags_action

        
        
        


        load_options.addMenu(load_log_submenu)
        load_options.addMenu(self.load_tag_submenu)
        self.load_btn.setMenu(load_options)

        ### --- VIEW MENU --- ###
        self.view_btn = QPushButton('▼ View ')
        view_options = QMenu(self)

        view_group_options = QMenu("Group Data By", self)
        
        view_group_source = QAction("Source", self)
        view_group_source.triggered.connect(lambda  : self.set_group_mode('SkillName'))
        view_group_options.addAction(view_group_source)

        view_group_player = QAction("Player", self)
        view_group_player.triggered.connect(lambda : self.set_group_mode('CasterName'))
        view_group_options.addAction(view_group_player)

        view_group_tag = QAction("Tag", self)
        view_group_tag.triggered.connect(lambda : self.set_group_mode('Tag'))
        view_group_options.addAction(view_group_tag)

        view_timestamp_adjust = QAction("Adjust Timestamps", self)
        view_timestamp_adjust.triggered.connect(self.adjust_timestamps)



        view_options.addMenu(view_group_options)
        view_options.addAction(view_timestamp_adjust)

        self.view_btn.setMenu(view_options)
        self.view_btn.setEnabled(False)


        ### --- NEW MENU --- ###
        self.new_btn = QPushButton('➕ New')
        new_options = QMenu(self)


        new_tag_action = QAction("Tag", self)
        new_tag_action.triggered.connect(self.create_tag)
        new_options.addAction(new_tag_action)

        self.new_btn.setMenu(new_options)


        ### --- EDIT MENU --- ###
        self.edit_btn = QPushButton(' Edit ')
        edit_options = QMenu(self)

        self.edit_tag_submenu = QMenu("Tag", self)
        self.edit_tag_submenu_actions = {}
        
        for tag in current_tags:
            this_action = QAction(tag.name, self)
            this_action.triggered.connect(lambda checked, name_to_load=tag.name: self.edit_tag(name_to_load))
            self.edit_tag_submenu.addAction(this_action)
            self.edit_tag_submenu_actions[tag.name] = this_action
        
        if len(current_tags) == 0:
            no_tags_action = QAction("No Tags Found", self)
            no_tags_action.setEnabled(False)
            self.edit_tag_submenu.addAction(no_tags_action)
            self.edit_tag_submenu_actions["No Tags Found"] = no_tags_action

        edit_options.addMenu(self.edit_tag_submenu)
        self.edit_btn.setMenu(edit_options)


        ### --- EXPORT MENU --- ###
        self.export_btn = QPushButton(' Export Current View ')
        self.export_options = QMenu(self)

        export_to_file_action = QAction('To File', self)
        export_to_file_action.triggered.connect(lambda checked : self.export_log_file())
        self.export_options.addAction(export_to_file_action)

        export_to_code_action = QAction('By Code', self)
        export_to_code_action.triggered.connect(self.share_file)
        self.export_options.addAction(export_to_code_action)


        self.export_btn.setMenu(self.export_options)
        self.export_btn.setEnabled(False)


        row_1.addWidget(self.load_btn)
        row_1.addWidget(self.view_btn)
        row_1.addWidget(self.new_btn)
        row_1.addWidget(self.edit_btn)
        row_1.addWidget(self.export_btn)
        row_1.addStretch()

        ### Widgets for row two
        row_2 = QHBoxLayout()
        # Filters
        # Create the skill filter
        self.skill_combo = CheckableComboBox()
        self.skill_combo.setEnabled(False)
        self.skill_combo.setMinimumWidth(150)       # Button width
        self.skill_combo.view().setMinimumWidth(400) # Popup list width
        self.skill_combo.selectionChanged.connect(self.update_all_charts)

        # Create the target filter
        self.target_combo = CheckableComboBox()
        self.target_combo.setEnabled(False)
        self.target_combo.setMinimumWidth(150)       # Button width
        self.target_combo.view().setMinimumWidth(400) # Popup list width
        self.target_combo.selectionChanged.connect(self.update_all_charts)

        # Create the caster filter
        self.caster_combo = CheckableComboBox()
        self.caster_combo.setEnabled(False)
        self.caster_combo.setMinimumWidth(150)       # Button width
        self.caster_combo.view().setMinimumWidth(400) # Popup list width
        self.caster_combo.selectionChanged.connect(self.update_all_charts)

        # Create the tag filter
        self.tag_combo = CheckableComboBox()
        self.tag_combo.setEnabled(False)
        self.tag_combo.setMinimumWidth(150)       # Button width
        self.tag_combo.view().setMinimumWidth(400) # Popup list width
        self.tag_combo.selectionChanged.connect(self.update_all_charts)

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



        # row_2.addWidget(self.crit_check)
        # row_2.addWidget(self.heavy_check)
        row_2.addWidget(QLabel("Filter by skill(s)"))
        row_2.addWidget(self.skill_combo)
        row_2.addSpacing(15) # Spacing
        row_2.addWidget(QLabel("Filter by targets(s)"))
        row_2.addWidget(self.target_combo)
        row_2.addSpacing(15) # Spacing
        row_2.addWidget(QLabel("Filter by player(s)"))
        row_2.addWidget(self.caster_combo)
        row_2.addSpacing(15) # Spacing
        row_2.addWidget(QLabel("Filter by tags(s)"))
        row_2.addWidget(self.tag_combo)
        row_2.addSpacing(30) # Spacing
        row_2.addWidget(self.reset_btn)
        row_2.addStretch()


        self.top_controls.addLayout(row_1)
        self.top_controls.addLayout(row_2)

        self.layout.addLayout(self.top_controls)


    # --- TAB WIDGETS ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # --- Tab 1: Overview (The Dashboard) ---
        self.tab_overview = QWidget()
        self.tab_overview_layout = QVBoxLayout(self.tab_overview)

        # Create Labels for the stats (Start with placeholder text)
        self.lbl_total_damage = QLabel("Total Damage: 0")
        self.lbl_dps = QLabel("Overall DPS: 0")
        self.lbl_duration = QLabel("Fight Duration: 0s")
        self.lbl_top_skill = QLabel(f"Top {self.group_mode}: None")

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


        # -- Tab 4: Heavy/Crit Ratio
        self.tab_heavy_crit = QWidget()
        self.tab_heavy_crit_layout = QVBoxLayout(self.tab_heavy_crit)

        self.fig_heavy_crit = Figure(figsize=(5,4),dpi=100)
        self.canvas_heavy_crit = FigureCanvas(self.fig_heavy_crit)
        self.tab_heavy_crit_layout.addWidget(self.canvas_heavy_crit)


        self.tabs.addTab(self.tab_heavy_crit, "Crit/Heavy Rate")

        self.tabs.currentChanged.connect(self.on_tab_change)


    def share_file(self, current=False):
        """
        Session manager for sharing a log file via session code.
        Generates UPnP session and session code, then sets up a listening port.
        """

        tmp_file_path = os.path.join(os.getenv('LOCALAPPDATA'),'WombatLogs','tmplogshare.' + str(random.randint(0,9999)))
        self.export_log_file(filepath=tmp_file_path, noconfirm=True)

        session = GroupSession()
        try:
            session_code = session.generate_session_code()
            file_share_thread = threading.Thread(target=session.share, args=(tmp_file_path,))
            file_share_thread.start()
            dialog = FileShareDialog(parent=self, session_code=session_code)
            dialog.exec()
            if file_share_thread.is_alive():
                session.server_sock.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error while sharing log file.\n{session.status}")
        finally:
            if not session.server_sock._closed:
                session.server_sock.close()
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)


    def receive_file(self):
        """
        Session manager for receiving a log file via session code.
        Establishes connection and authenticates to the person sharing the file, then imports the data directly.
        """
        dialog = FileImportDialog(parent=self, method='by_code')
        if not dialog.exec():
            return
        session_code = dialog.get_input()
        merge_files = dialog.get_merge_check()
        session = GroupSession()
        received_data = session.connect_by_code(session_code)
        if received_data is not None:
            self.load_log(csv_data=received_data, merge=merge_files)
        else:
            QMessageBox.critical(self, "Error", f"Unable to download log file from remote user.\n{session.status}")

    def export_log_file(self, filepath=None, noconfirm=False):
        """
        Export a current filtered/merged view as a single re-usable log file.
        """

        if filepath is not None:
            file_path = filepath
        else:
            log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
            export_dir = QFileDialog.getExistingDirectory(self, "Select Save Location", log_dir)
            fname = "WombatLogExport.txt"
            file_path = os.path.join(export_dir, fname)
        try:
            tmpdf = self.get_filtered_data()
            with open(file_path, 'w') as outfile:
                outfile.write("WombatLogVersion,1\n")
            tmpdf.to_csv(file_path, index=False, header=False, mode='a', columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])
            if not noconfirm:
                QMessageBox.information(self, "Success", f"Log file written to\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error '{e}' while exporting current view.")

    def import_logs(self):
        """
        Creates file importing dialog and uses the results to add log files.
        """
        dialog = FileImportDialog(parent=self, method='local')
        if not dialog.exec():
            return

        log_files = dialog.get_files()
        merge_files = dialog.get_merge_check()
        adjust_timestamps = dialog.get_timestamp_check()

        self.load_log(merge=merge_files, adjust_timestamps=adjust_timestamps, filepaths=log_files)

            

    def on_tab_change(self, index):
        """
        Event listener for tab switching. 
        Forces a layout refresh because charts drawn on hidden tabs 
        often have broken margins until redrawn.
        """
        # index 0 is overview, index 1 is damage by skill, index 2 is DPS, index 3 is heavy/crit
        if index == 3:
            self.fig_heavy_crit.tight_layout()
            self.canvas_heavy_crit.draw()

        if index == 2:
            self.fig_dps.tight_layout()
            self.canvas_dps.draw()

        elif index == 1:             
            self.fig_total.tight_layout()
            self.canvas_total.draw()

        # We don't have a canvas for the overview page so no reformatting is needed.
        elif index == 0:
            pass

    def reset_filters(self):
            self.skill_combo.clear()
            # Refill with unchecked items or just clear selection
            if not self.df.empty:
                skills = sorted(self.df['SkillName'].dropna().unique().astype(str))
                for skill in skills:
                    self.skill_combo.add_item(skill)
            self.update_all_charts()


    ### Load the log files from a specific tag into the current view.
    def load_logs_by_tag(self, tag_name):

        this_tag = Tag.load(tag_name)
        dialog = TagLoadDialog(tag_name=tag_name, tag_log_files=this_tag.log_files)
        if dialog.exec():
            self.load_log(filepaths=this_tag.log_files, tag=tag_name, merge=dialog.get_merge_check, adjust_timestamps=dialog.adjust_timestamp_check)
        else:
            return False



    def create_tag(self):

        dialog = TagCreateDialog(self)
        if not dialog.exec():
            return False
        

        tag_name = dialog.get_name()
        if tag_name in [T.name for T in Tag.get_tags()]:
            QMessageBox.critical(self, "Error", f"The tag {tag_name} already exists.")
            return False
        
        tag_description = dialog.get_description()
        tag_log_files = dialog.get_files()
        new_tag = Tag(name=tag_name, notes=tag_description, log_files=tag_log_files)
        new_tag.save()

        if self.load_tag_submenu_actions.get("No Tags Found") is not None:
            # Remove 'No Tags Found' action from drop-down list and from the dict of actions.
            no_tags_action = self.load_tag_submenu_actions.get("No Tags Found")
            self.load_tag_submenu.removeAction(no_tags_action)
            self.load_tag_submenu_actions.pop("No Tags Found")
            self.edit_tag_submenu.removeAction(no_tags_action)
            self.edit_tag_submenu_actions.pop("No Tags Found")

        # Create and add a new action for the tag
        this_tag_load_action = QAction(new_tag.name, self)
        this_tag_load_action.triggered.connect(lambda checked, tag_name=new_tag.name : self.load_logs_by_tag(tag_name))
        self.load_tag_submenu_actions[new_tag.name] = this_tag_load_action
        self.load_tag_submenu.addAction(this_tag_load_action)

        this_tag_edit_action = QAction(new_tag.name, self)
        this_tag_edit_action.triggered.connect(lambda checked, name_to_load=new_tag.name: self.edit_tag(name_to_load))
        self.edit_tag_submenu_actions[new_tag.name] = this_tag_edit_action
        self.edit_tag_submenu.addAction(this_tag_edit_action)

        self.df = pd.DataFrame(columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])
        #if len(new_tag.log_files) > 0:
        #    self.load_log(filepaths=new_tag.log_files, adjust_timestamps=True)
                



    def edit_tag(self, tag):
        current = Tag.load(tag)
        dialog = TagEditDialog(self, tag_name=current.name, tag_notes=current.notes, tag_log_files=current.log_files)
        if not dialog.exec():
            if dialog.get_delete_bool():
                current.delete_tag()
                tag_edit_action = self.edit_tag_submenu_actions.get(tag)
                tag_load_action = self.load_tag_submenu_actions.get(tag)
                self.edit_tag_submenu.removeAction(tag_edit_action)
                self.load_tag_submenu.removeAction(tag_load_action)
                if len(self.edit_tag_submenu.actions()) == 0 and len(self.load_tag_submenu.actions()) == 0:
                    no_tags_action = QAction("No Tags Found", self)
                    no_tags_action.setEnabled(False)
                    self.edit_tag_submenu.addAction(no_tags_action)
                    self.edit_tag_submenu_actions["No Tags Found"] = no_tags_action
                    self.load_tag_submenu.addAction(no_tags_action)
                    self.load_tag_submenu_actions["No Tags Found"] = no_tags_action

                return True

            return False

        tag_name = dialog.get_name()        
        tag_description = dialog.get_description()
        tag_log_files = dialog.get_log_files()
        new_tag_data = Tag(name=tag_name, notes=tag_description, log_files=tag_log_files)
        new_tag_data.save()

        # self.df = pd.DataFrame(columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])
        # self.load_log(filepaths=tag_log_files)
        

    ### Adjusts timestamps to have all logs start at the same time
    def adjust_timestamps(self):
        temp_df = pd.DataFrame(columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])
        base_start_timestamp = self.df['DT'].iloc[0]
        entries_by_log = self.df.groupby("LogFile")
        for data_set in entries_by_log:
            new_start_timestamp = data_set[1]['DT'].iloc[0]
            time_shift = base_start_timestamp - new_start_timestamp
            data_set[1]['DT'] = data_set[1]['DT'] + time_shift
            temp_df = pd.concat([temp_df, data_set[1]], ignore_index=True)

        self.df = temp_df
        self.update_all_charts()





    def load_log(self, merge=False, adjust_timestamps=False, csv_data=None, filepaths=[], tag="Untagged"):
        # Open Explorer in the log directory used by TnL
        if (csv_data is None and filepaths == []):
            QMessageBox.critical(self, "Error", "Logic error while attempting to load log.")

        self.loaded_logs.extend(filepaths)

        if csv_data is not None:
            filepaths.append(StringIO(csv_data))

        
        base_start_timestamp = None if self.df.empty else self.df['DT'].iloc[0]

        if not merge:
            self.skill_combo.clear()
            self.target_combo.clear()
            self.caster_combo.clear()
            self.df = pd.DataFrame(columns=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])

        for fname in filepaths:
            try:
                this_df = pd.read_csv(fname, header=0, names=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])

                # PRE-PROCESS TIMESTAMP for DPS Calculation
                # Format: 20251207-13:04:08:490
                # We need to parse this to a datetime object

                if 'Timestamp' in this_df.columns:
                    this_df['DT'] = pd.to_datetime(this_df['Timestamp'], format='%Y%m%d-%H:%M:%S:%f', errors='coerce')

                if base_start_timestamp is None:
                    base_start_timestamp = this_df['DT'].iloc[0]
                elif adjust_timestamps:
                    new_start_timestamp = this_df['DT'].iloc[0]
                    time_shift = base_start_timestamp - new_start_timestamp
                    this_df['DT'] = this_df['DT'] + time_shift

                this_df['Tag'] = tag
                if csv_data is None:
                    this_df['LogFile'] = fname
                else:
                    this_df['LogFile'] = "Web Imported"

                self.df = pd.concat([self.df, this_df], ignore_index=True)

                    
                    

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

                # Add tags to drop down
                self.tag_combo.blockSignals(True)
                current_tags = self.tag_combo.get_all_items()
                if 'Tag' in self.df.columns:
                    tags = sorted(self.df['Tag'].dropna().unique().astype(str))
                    for tag in [T for T in tags if T not in current_tags]:
                        self.tag_combo.add_item(tag) # Use our custom add_item method


                # Enable menu options that require loaded data
                self.skill_combo.setEnabled(True)
                self.target_combo.setEnabled(True)
                self.caster_combo.setEnabled(True)
                self.tag_combo.setEnabled(True)
                self.view_btn.setEnabled(True)
                self.export_btn.setEnabled(True)
                self.crit_check.setEnabled(True)
                self.heavy_check.setEnabled(True)

                font_style = "font-size: 24px; font-weight: bold; color: #e5e5e5;"
                self.lbl_total_damage.setStyleSheet(font_style)
                self.lbl_dps.setStyleSheet(font_style)
                self.lbl_duration.setStyleSheet("font-size: 18px; color: #cccccc;")
                self.lbl_top_skill.setStyleSheet("font-size: 18px; color: #cccccc;")

                # Unblock signals from the combo boxes
                self.skill_combo.blockSignals(False)
                self.target_combo.blockSignals(False)
                self.caster_combo.blockSignals(False)
                self.tag_combo.blockSignals(False)
                
                

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error reading file:\n{e}")
        
        self.update_all_charts()

    def set_group_mode(self, group_mode):
        self.group_mode = group_mode
        self.update_all_charts()


    def get_filtered_data(self):
        """Helper to get current dataframe based on filters"""
        if self.df.empty: return pd.DataFrame()
        
        temp_df = self.df.copy()
        selected_skills = self.skill_combo.get_checked_items()
        selected_targets = self.target_combo.get_checked_items()
        selected_casters = self.caster_combo.get_checked_items()
        selected_tags = self.tag_combo.get_checked_items()


        # Filter by selected skills
        if selected_skills:
            temp_df = temp_df[temp_df['SkillName'].isin(selected_skills)]

        # Filter by selected targets
        if selected_targets:
            temp_df = temp_df[temp_df['TargetName'].isin(selected_targets)]

        # Filter by selected casters
        if selected_casters:
            temp_df = temp_df[temp_df['CasterName'].isin(selected_casters)]

        if selected_tags:
            temp_df = temp_df[temp_df['Tag'].isin(selected_tags)]

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

        # Update Tab 4
        self.plot_heavy_crit(data)

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
            top_skill_series = data.groupby(self.group_mode)['DamageAmount'].sum().sort_values(ascending=False)
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
        self.lbl_top_skill.setText(f"Top {self.group_mode}: {top_skill_txt}")

    def plot_total_damage(self, data):
        self.fig_total.clear()
        ax = self.fig_total.add_subplot(111)

        if not data.empty:
            chart_data = data.groupby(self.group_mode)['DamageAmount'].sum().sort_values(ascending=True)

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
            dps_df = data.groupby([pd.Grouper(key='DT', freq='1s'), self.group_mode])['DamageAmount'].sum().unstack().fillna(0)
            
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

    def plot_heavy_crit(self, data):
        self.fig_heavy_crit.clear()
        ax = self.fig_heavy_crit.add_subplot(111)

        if not data.empty:
            crit_rate = round(data['CriticalHit'].mean() * 100, 2)
            heavy_rate = round(data['HeavyHit'].mean() * 100, 2)
            crit_heavy_data = data[(data['CriticalHit'] == 1) & (data['HeavyHit'] == 1)]
            crit_heavy_rate = round((len(crit_heavy_data) / len(data)) * 100, 2)
            normal_data = data[(data['CriticalHit'] == 0) & (data['HeavyHit'] == 0)]
            normal_rate = round((len(normal_data) / len(data)) * 100, 2)
            if normal_rate < 0:
                QMessageBox.critical(self, "Error", f"Error while plotting ratios for {crit_rate}c {heavy_rate}h and {crit_heavy_rate}ch")
                return
            percentages = [normal_rate, crit_rate, heavy_rate, crit_heavy_rate]

            ax.pie(percentages, labels=["Normal","Critical","Heavy","Crit+Heavy"],
                radius=3, center=(4, 4), frame=True, autopct='%1.1f%%', startangle=90,
                wedgeprops={"linewidth": 1, "edgecolor": "white"}
            )

            ax.set_title("Critical and Heavy Hit Ratios")
            ax.axis('off')
            self.fig_heavy_crit.tight_layout()
        else:
            ax.text(0.5, 0.5, "No Data", ha='center')
        
        self.canvas_heavy_crit.draw()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DamageAnalyzer()
    window.show()
    sys.exit(app.exec())