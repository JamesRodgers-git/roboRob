#!/usr/bin/env python3
"""
GUI test script for CRSF connection on Raspberry Pi 5
Displays connection status and received data in a graphical interface
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import sys
from src.crsf_connection import CRSFConnection


class CRSFGUI:
    """GUI application for CRSF connection testing"""
    
    def __init__(self, root, port='/dev/ttyAMA0'):
        self.root = root
        self.port = port
        self.crsf = None
        self.running = False
        self.read_thread = None
        self.data_lock = threading.Lock()  # Lock for thread-safe data access
        
        # Data storage (will be updated from CRSF connection)
        self.frame_count = 0
        self.channel_updates = 0
        self.stats_updates = 0
        self.start_time = time.time()
        self.connected = False
        
        self.setup_ui()
        self.connect()
    
    def setup_ui(self):
        """Setup the user interface"""
        self.root.title("CRSF Connection Test - Raspberry Pi 5")
        self.root.geometry("800x700")
        self.root.configure(bg='#2b2b2b')
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#2b2b2b', padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = tk.Frame(main_frame, bg='#2b2b2b')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = tk.Label(
            header_frame,
            text="CRSF Connection Test",
            font=('Arial', 18, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff'
        )
        title_label.pack()
        
        # Status frame
        status_frame = tk.LabelFrame(
            main_frame,
            text="Connection Status",
            font=('Arial', 12, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff',
            padx=10,
            pady=10
        )
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(
            status_frame,
            text="Connecting...",
            font=('Arial', 11),
            bg='#2b2b2b',
            fg='#ffaa00'
        )
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.runtime_label = tk.Label(
            status_frame,
            text="Runtime: 0.0s",
            font=('Arial', 11),
            bg='#2b2b2b',
            fg='#aaaaaa'
        )
        self.runtime_label.pack(side=tk.LEFT, padx=20)
        
        self.last_update_label = tk.Label(
            status_frame,
            text="Last update: --",
            font=('Arial', 11),
            bg='#2b2b2b',
            fg='#aaaaaa'
        )
        self.last_update_label.pack(side=tk.LEFT, padx=20)
        
        # Channels frame
        channels_frame = tk.LabelFrame(
            main_frame,
            text="Channels (16)",
            font=('Arial', 12, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff',
            padx=10,
            pady=10
        )
        channels_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Channel grid (4x4)
        self.channel_labels = []
        for row in range(4):
            row_frame = tk.Frame(channels_frame, bg='#2b2b2b')
            row_frame.pack(fill=tk.X, pady=2)
            for col in range(4):
                ch_num = row * 4 + col + 1
                ch_frame = tk.Frame(row_frame, bg='#2b2b2b')
                ch_frame.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.BOTH)
                
                ch_label = tk.Label(
                    ch_frame,
                    text=f"CH{ch_num:2d}",
                    font=('Arial', 9),
                    bg='#2b2b2b',
                    fg='#aaaaaa'
                )
                ch_label.pack()
                
                value_label = tk.Label(
                    ch_frame,
                    text="1500",
                    font=('Arial', 14, 'bold'),
                    bg='#1e1e1e',
                    fg='#00ff00',
                    width=6,
                    relief=tk.RAISED,
                    borderwidth=2
                )
                value_label.pack(pady=2)
                self.channel_labels.append(value_label)
        
        # Link statistics frame
        stats_frame = tk.LabelFrame(
            main_frame,
            text="Link Statistics",
            font=('Arial', 12, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff',
            padx=10,
            pady=10
        )
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Stats grid
        stats_grid = tk.Frame(stats_frame, bg='#2b2b2b')
        stats_grid.pack(fill=tk.X)
        
        # Uplink stats
        uplink_frame = tk.Frame(stats_grid, bg='#2b2b2b')
        uplink_frame.pack(side=tk.LEFT, padx=10, expand=True)
        
        tk.Label(
            uplink_frame,
            text="Uplink",
            font=('Arial', 10, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff'
        ).pack()
        
        self.uplink_rssi_label = self.create_stat_label(uplink_frame, "RSSI:", "0 dBm")
        self.uplink_lq_label = self.create_stat_label(uplink_frame, "Link Quality:", "0%")
        self.uplink_snr_label = self.create_stat_label(uplink_frame, "SNR:", "0 dB")
        
        # Downlink stats
        downlink_frame = tk.Frame(stats_grid, bg='#2b2b2b')
        downlink_frame.pack(side=tk.LEFT, padx=10, expand=True)
        
        tk.Label(
            downlink_frame,
            text="Downlink",
            font=('Arial', 10, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff'
        ).pack()
        
        self.downlink_rssi_label = self.create_stat_label(downlink_frame, "RSSI:", "0 dBm")
        self.downlink_lq_label = self.create_stat_label(downlink_frame, "Link Quality:", "0%")
        self.downlink_snr_label = self.create_stat_label(downlink_frame, "SNR:", "0 dB")
        
        # Statistics frame
        info_frame = tk.LabelFrame(
            main_frame,
            text="Statistics",
            font=('Arial', 12, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff',
            padx=10,
            pady=10
        )
        info_frame.pack(fill=tk.X)
        
        stats_info_frame = tk.Frame(info_frame, bg='#2b2b2b')
        stats_info_frame.pack(fill=tk.X)
        
        self.frames_label = self.create_info_label(stats_info_frame, "Frames:", "0")
        self.channel_updates_label = self.create_info_label(stats_info_frame, "Channel Updates:", "0")
        self.stats_updates_label = self.create_info_label(stats_info_frame, "Stats Updates:", "0")
        
        # Control buttons
        button_frame = tk.Frame(main_frame, bg='#2b2b2b')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.connect_button = tk.Button(
            button_frame,
            text="Reconnect",
            command=self.reconnect,
            font=('Arial', 10),
            bg='#4a4a4a',
            fg='#ffffff',
            activebackground='#5a5a5a',
            activeforeground='#ffffff',
            relief=tk.RAISED,
            borderwidth=2
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        quit_button = tk.Button(
            button_frame,
            text="Quit",
            command=self.quit_app,
            font=('Arial', 10),
            bg='#8b0000',
            fg='#ffffff',
            activebackground='#aa0000',
            activeforeground='#ffffff',
            relief=tk.RAISED,
            borderwidth=2
        )
        quit_button.pack(side=tk.RIGHT, padx=5)
    
    def create_stat_label(self, parent, label_text, value_text):
        """Create a statistics label"""
        frame = tk.Frame(parent, bg='#2b2b2b')
        frame.pack(fill=tk.X, pady=2)
        
        label = tk.Label(
            frame,
            text=label_text,
            font=('Arial', 9),
            bg='#2b2b2b',
            fg='#aaaaaa',
            width=12,
            anchor='w'
        )
        label.pack(side=tk.LEFT)
        
        value = tk.Label(
            frame,
            text=value_text,
            font=('Arial', 10, 'bold'),
            bg='#1e1e1e',
            fg='#00aaff',
            width=10,
            anchor='w'
        )
        value.pack(side=tk.LEFT, padx=(5, 0))
        
        return value
    
    def create_info_label(self, parent, label_text, value_text):
        """Create an info label"""
        frame = tk.Frame(parent, bg='#2b2b2b')
        frame.pack(side=tk.LEFT, padx=10)
        
        label = tk.Label(
            frame,
            text=f"{label_text} {value_text}",
            font=('Arial', 10),
            bg='#2b2b2b',
            fg='#aaaaaa'
        )
        label.pack()
        
        return label
    
    def connect(self):
        """Connect to CRSF receiver"""
        self.crsf = CRSFConnection(port=self.port)
        if self.crsf.connect():
            self.connected = True
            self.running = True
            self.start_time = time.time()
            self.frame_count = 0
            self.channel_updates = 0
            self.stats_updates = 0
            self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
            self.read_thread.start()
            self.status_label.config(text="✅ Connected", fg='#00ff00')
        else:
            self.connected = False
            self.status_label.config(
                text="❌ Connection Failed",
                fg='#ff0000'
            )
    
    def reconnect(self):
        """Reconnect to CRSF receiver"""
        if self.crsf:
            self.running = False
            if self.read_thread:
                self.read_thread.join(timeout=1.0)
            self.crsf.disconnect()
        self.connect()
    
    def read_loop(self):
        """Background thread to read CRSF frames - reads continuously for lowest latency"""
        while self.running:
            if self.crsf and self.crsf.is_connected():
                frame = self.crsf.read_latest_frame()
                if frame:
                    with self.data_lock:
                        self.frame_count += 1
                        frame_type = frame.get('type', 0)
                        
                        if frame_type == CRSFConnection.FRAME_TYPE_CHANNELS:
                            self.channel_updates += 1
                        elif frame_type == CRSFConnection.FRAME_TYPE_LINK_STATISTICS:
                            self.stats_updates += 1
            else:
                # If not connected, sleep a bit to avoid busy waiting
                time.sleep(0.1)
    
    def update_display(self):
        """Update the GUI display - reads directly from CRSF connection for latest data"""
        # Update status
        if self.connected and self.crsf:
            elapsed = time.time() - self.start_time
            self.runtime_label.config(text=f"Runtime: {elapsed:.1f}s")
            
            # Get latest update time directly from CRSF connection
            last_update = self.crsf.get_last_update_time()
            if last_update > 0:
                time_since = time.time() - last_update
                self.last_update_label.config(text=f"Last update: {time_since:.2f}s ago")
                
                if time_since < 2.0:
                    self.status_label.config(text="✅ Connected (Receiving)", fg='#00ff00')
                else:
                    self.status_label.config(text="⚠️ Connected (No Data)", fg='#ffaa00')
            else:
                self.last_update_label.config(text="Last update: --")
        else:
            self.runtime_label.config(text="Runtime: --")
            self.last_update_label.config(text="Last update: --")
        
        # Read channels directly from CRSF connection (always latest)
        if self.crsf and self.crsf.is_connected():
            channels = self.crsf.get_channels()
            for i, label in enumerate(self.channel_labels):
                if i < len(channels):
                    value = channels[i]
                    label.config(text=str(value))
                    # Color coding: green for center (1500), yellow for active
                    if value == 1500:
                        label.config(fg='#00ff00', bg='#1e1e1e')
                    elif 1400 <= value <= 1600:
                        label.config(fg='#ffff00', bg='#1e1e1e')
                    else:
                        label.config(fg='#ff8800', bg='#1e1e1e')
            
            # Read link statistics directly from CRSF connection (always latest)
            link_stats = self.crsf.get_link_statistics()
            if link_stats:
                uplink_rssi = link_stats.get('uplink_rssi_ant1', 0)
                uplink_lq = link_stats.get('uplink_link_quality', 0)
                uplink_snr = link_stats.get('uplink_snr', 0)
                downlink_rssi = link_stats.get('downlink_rssi', 0)
                downlink_lq = link_stats.get('downlink_link_quality', 0)
                downlink_snr = link_stats.get('downlink_snr', 0)
                
                self.uplink_rssi_label.config(text=f"{uplink_rssi} dBm")
                self.uplink_lq_label.config(text=f"{uplink_lq}%")
                self.uplink_snr_label.config(text=f"{uplink_snr} dB")
                
                self.downlink_rssi_label.config(text=f"{downlink_rssi} dBm")
                self.downlink_lq_label.config(text=f"{downlink_lq}%")
                self.downlink_snr_label.config(text=f"{downlink_snr} dB")
        
        # Update statistics (thread-safe access)
        with self.data_lock:
            frames = self.frame_count
            ch_updates = self.channel_updates
            stats_updates = self.stats_updates
        
        self.frames_label.config(text=f"Frames: {frames}")
        self.channel_updates_label.config(text=f"Channel Updates: {ch_updates}")
        self.stats_updates_label.config(text=f"Stats Updates: {stats_updates}")
        
        # Schedule next update - faster updates for more responsive display
        self.root.after(20, self.update_display)  # Update every 20ms (~50 FPS)
    
    def quit_app(self):
        """Clean up and quit application"""
        self.running = False
        if self.crsf:
            self.crsf.disconnect()
        self.root.quit()
        self.root.destroy()


def main():
    """Main function"""
    port = '/dev/ttyAMA0'
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    root = tk.Tk()
    app = CRSFGUI(root, port=port)
    app.update_display()  # Start the update loop
    root.mainloop()


if __name__ == "__main__":
    main()

