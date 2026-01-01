# wombat_gui.py

import sys
from datetime import datetime
import os
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QHBoxLayout, QWidget, QComboBox, QLabel, 
                             QCheckBox, QPushButton, QFileDialog, QMessageBox, QSizePolicy, QTabWidget)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker


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
        top_controls = QHBoxLayout()
        
        # Load Button
        self.load_btn = QPushButton("📂 Load Combat Log")
        self.load_btn.clicked.connect(self.open_file_dialog)
        
        # Filters
        self.skill_combo = QComboBox()
        self.skill_combo.addItem("All Skills")
        self.skill_combo.setEnabled(False)
        self.skill_combo.currentTextChanged.connect(self.update_all_charts)

        self.crit_check = QCheckBox("Show Critical Hits Only")
        self.crit_check.setEnabled(False)
        self.crit_check.stateChanged.connect(self.update_all_charts)

        self.heavy_check = QCheckBox("Show Heavy Attacks Only")
        self.heavy_check.setEnabled(False)
        self.heavy_check.stateChanged.connect(self.update_all_charts)

        # Add to layout
        top_controls.addWidget(self.load_btn)
        top_controls.addWidget(QLabel(" | Filter:"))
        top_controls.addWidget(self.skill_combo)
        top_controls.addWidget(self.crit_check)
        top_controls.addWidget(self.heavy_check)
        top_controls.addStretch()

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


    def open_file_dialog(self):
        # Open Explorer in the log directory used by TnL
        log_dir = os.path.join(os.getenv('LOCALAPPDATA'),'TL','Saved','CombatLogs')
        fname, _ = QFileDialog.getOpenFileName(self, "Open Combat Log", log_dir, "Text Files (*.txt)")
        if fname:
            try:
                self.df = pd.read_csv(fname, header=0, names=['Timestamp','LogType','SkillName','SkillId','DamageAmount','CriticalHit','HeavyHit','DamageType','CasterName','TargetName'])
                
                # PRE-PROCESS TIMESTAMP for DPS Calculation
                # Format: 20251207-13:04:08:490
                # We need to parse this to a datetime object
                if 'Timestamp' in self.df.columns:
                    self.df['DT'] = pd.to_datetime(self.df['Timestamp'], format='%Y%m%d-%H:%M:%S:%f', errors='coerce')

                # Update UI
                self.skill_combo.blockSignals(True)
                self.skill_combo.clear()
                self.skill_combo.addItem("All Skills")
                if 'SkillName' in self.df.columns:
                    skills = sorted(self.df['SkillName'].dropna().unique().astype(str))
                    self.skill_combo.addItems(skills)
                self.skill_combo.blockSignals(False)
                
                self.skill_combo.setEnabled(True)
                self.crit_check.setEnabled(True)
                self.heavy_check.setEnabled(True)

                font_style = "font-size: 24px; font-weight: bold; color: #e5e5e5;"
                self.lbl_total_damage.setStyleSheet(font_style)
                self.lbl_dps.setStyleSheet(font_style)
                self.lbl_duration.setStyleSheet("font-size: 18px; color: #cccccc;")
                self.lbl_top_skill.setStyleSheet("font-size: 18px; color: #cccccc;")
                
                self.update_all_charts()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error reading file:\n{e}")

    def get_filtered_data(self):
        """Helper to get current dataframe based on filters"""
        if self.df.empty: return pd.DataFrame()
        
        temp_df = self.df.copy()
        if self.skill_combo.currentText() != "All Skills":
            temp_df = temp_df[temp_df['SkillName'] == self.skill_combo.currentText()]
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