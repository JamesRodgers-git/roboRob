#!/usr/bin/env python3
"""
Drive loop with GUI: displays CRSF channels, motor outputs, and brake states.
Uses a reader thread that drains buffered data so the UI and control loop use
the most recent radio inputs.
"""

import argparse
import threading
import time
import tkinter as tk
from typing import Dict, List

import config
from src.brake_controller import BrakeController
from src.crsf_connection import CRSFConnection
from src.motor_controller import MotorController
from src.movement_algorithms import LateralLimitedMovementAlgorithm

_MPH_TO_MPS = 0.44704


class DriveGUI:
    def __init__(self, root: tk.Tk, port: str):
        self.root = root
        self.port = port
        self.running = False
        self.reader_thread = None
        self.control_thread = None
        self.data_lock = threading.Lock()

        self.channels: List[int] = [1500] * 16
        self.link_stats: Dict = {}
        self.last_rx_time = 0.0
        self.frame_count = 0
        self.channel_updates = 0
        self.stats_updates = 0

        self.left_output_mph = 0.0
        self.right_output_mph = 0.0
        self.left_brake = 0.0
        self.right_brake = 0.0
        self.yaw_rate_rad = 0.0
        self.lat_accel = 0.0

        self.crsf = CRSFConnection(port=self.port, baudrate=config.CRSF_BAUD_RATE)
        if not self.crsf.connect():
            raise RuntimeError("Failed to connect to CRSF receiver.")

        self.motor_left = MotorController(
            address=config.MOTOR_CONTROLLER1_ADDRESS,
            min_speed=config.MOTOR_CONTROLLER_MIN_SPEED,
            max_speed=config.MOTOR_CONTROLLER_MAX_SPEED,
            reset_speed=config.MOTOR_CONTROLLER_RESET_SPEED,
            max_speed_mph=config.MAX_SPEED,
        )
        self.motor_right = MotorController(
            address=config.MOTOR_CONTROLLER2_ADDRESS,
            min_speed=config.MOTOR_CONTROLLER_MIN_SPEED,
            max_speed=config.MOTOR_CONTROLLER_MAX_SPEED,
            reset_speed=config.MOTOR_CONTROLLER_RESET_SPEED,
            max_speed_mph=config.MAX_SPEED,
        )
        self.brakes = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)

        self.algorithm = LateralLimitedMovementAlgorithm(
            max_speed_mph=config.MAX_SPEED,
            max_acceleration=config.MAX_ACCELERATION,
            max_turn_rate=config.MAX_TURN_RATE,
            max_lateral_acceleration=config.MAX_LATERAL_ACCELERATION,
            wheel_base_meters=config.WHEEL_BASE_METERS,
            input_min=config.CRSF_CHANNEL_MIN,
            input_max=config.CRSF_CHANNEL_MAX,
            input_center=1500,
            input_deadband=config.CRSF_CHANNEL_DEADBAND,
        )

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.root.title("RoboWheels Drive GUI")
        self.root.geometry("900x720")
        self.root.configure(bg="#2b2b2b")

        main_frame = tk.Frame(self.root, bg="#2b2b2b", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Label(
            main_frame,
            text="RoboWheels Drive Monitor",
            font=("Arial", 18, "bold"),
            bg="#2b2b2b",
            fg="#ffffff",
        )
        header.pack(pady=(0, 10))

        status_frame = tk.LabelFrame(
            main_frame,
            text="Status",
            font=("Arial", 12, "bold"),
            bg="#2b2b2b",
            fg="#ffffff",
            padx=10,
            pady=10,
        )
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = tk.Label(
            status_frame,
            text="Connecting...",
            font=("Arial", 11),
            bg="#2b2b2b",
            fg="#ffaa00",
        )
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.runtime_label = tk.Label(
            status_frame,
            text="Runtime: 0.0s",
            font=("Arial", 11),
            bg="#2b2b2b",
            fg="#aaaaaa",
        )
        self.runtime_label.pack(side=tk.LEFT, padx=20)

        self.last_update_label = tk.Label(
            status_frame,
            text="Last update: --",
            font=("Arial", 11),
            bg="#2b2b2b",
            fg="#aaaaaa",
        )
        self.last_update_label.pack(side=tk.LEFT, padx=20)

        channels_frame = tk.LabelFrame(
            main_frame,
            text="Channels (16)",
            font=("Arial", 12, "bold"),
            bg="#2b2b2b",
            fg="#ffffff",
            padx=10,
            pady=10,
        )
        channels_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.channel_labels = []
        for row in range(4):
            row_frame = tk.Frame(channels_frame, bg="#2b2b2b")
            row_frame.pack(fill=tk.X, pady=2)
            for col in range(4):
                ch_num = row * 4 + col + 1
                ch_frame = tk.Frame(row_frame, bg="#2b2b2b")
                ch_frame.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.BOTH)

                tk.Label(
                    ch_frame,
                    text=f"CH{ch_num:02d}",
                    font=("Arial", 9),
                    bg="#2b2b2b",
                    fg="#aaaaaa",
                ).pack()

                value_label = tk.Label(
                    ch_frame,
                    text="1500",
                    font=("Arial", 14, "bold"),
                    bg="#1e1e1e",
                    fg="#00ff00",
                    width=6,
                    relief=tk.RAISED,
                    borderwidth=2,
                )
                value_label.pack(pady=2)
                self.channel_labels.append(value_label)

        outputs_frame = tk.LabelFrame(
            main_frame,
            text="Outputs",
            font=("Arial", 12, "bold"),
            bg="#2b2b2b",
            fg="#ffffff",
            padx=10,
            pady=10,
        )
        outputs_frame.pack(fill=tk.X, pady=(0, 10))

        self.outputs_left_label = self._create_stat(outputs_frame, "Motor L:", "0.00 mph (0.0%)")
        self.outputs_right_label = self._create_stat(outputs_frame, "Motor R:", "0.00 mph (0.0%)")
        self.brake_left_label = self._create_stat(outputs_frame, "Brake L:", "0.0%")
        self.brake_right_label = self._create_stat(outputs_frame, "Brake R:", "0.0%")
        self.yaw_rate_label = self._create_stat(outputs_frame, "Yaw rate:", "0.00 deg/s")
        self.lat_accel_label = self._create_stat(outputs_frame, "Lat accel:", "0.00 m/s^2")

        stats_frame = tk.LabelFrame(
            main_frame,
            text="Statistics",
            font=("Arial", 12, "bold"),
            bg="#2b2b2b",
            fg="#ffffff",
            padx=10,
            pady=10,
        )
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        self.frames_label = tk.Label(stats_frame, text="Frames: 0", bg="#2b2b2b", fg="#aaaaaa")
        self.frames_label.pack(side=tk.LEFT, padx=10)
        self.channel_updates_label = tk.Label(stats_frame, text="Channel Updates: 0", bg="#2b2b2b", fg="#aaaaaa")
        self.channel_updates_label.pack(side=tk.LEFT, padx=10)
        self.stats_updates_label = tk.Label(stats_frame, text="Stats Updates: 0", bg="#2b2b2b", fg="#aaaaaa")
        self.stats_updates_label.pack(side=tk.LEFT, padx=10)

        button_frame = tk.Frame(main_frame, bg="#2b2b2b")
        button_frame.pack(fill=tk.X, pady=(10, 0))

        quit_button = tk.Button(
            button_frame,
            text="Quit",
            command=self.quit_app,
            font=("Arial", 10),
            bg="#8b0000",
            fg="#ffffff",
            activebackground="#aa0000",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            borderwidth=2,
        )
        quit_button.pack(side=tk.RIGHT, padx=5)

    def _create_stat(self, parent, label_text, value_text):
        frame = tk.Frame(parent, bg="#2b2b2b")
        frame.pack(fill=tk.X, pady=2)

        label = tk.Label(
            frame,
            text=label_text,
            font=("Arial", 9),
            bg="#2b2b2b",
            fg="#aaaaaa",
            width=12,
            anchor="w",
        )
        label.pack(side=tk.LEFT)

        value = tk.Label(
            frame,
            text=value_text,
            font=("Arial", 10, "bold"),
            bg="#1e1e1e",
            fg="#00aaff",
            width=18,
            anchor="w",
        )
        value.pack(side=tk.LEFT, padx=(5, 0))
        return value

    def start(self) -> None:
        self.running = True
        self.start_time = time.time()
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.reader_thread.start()
        self.control_thread.start()
        self._update_display()

    def _read_loop(self) -> None:
        while self.running:
            if not self.crsf.is_connected():
                time.sleep(0.05)
                continue

            frame = self.crsf.read_latest_frame()
            if frame:
                with self.data_lock:
                    self.frame_count += 1
                    frame_type = frame.get("type", 0)
                    if frame_type == CRSFConnection.FRAME_TYPE_CHANNELS:
                        self.channels = frame.get("channels", self.channels)
                        self.channel_updates += 1
                        self.last_rx_time = time.time()
                    elif frame_type == CRSFConnection.FRAME_TYPE_LINK_STATISTICS:
                        self.link_stats = frame.get("link_statistics", self.link_stats)
                        self.stats_updates += 1
            else:
                time.sleep(0.002)

    def _control_loop(self) -> None:
        loop_delay = 1.0 / max(1, config.CONTROL_LOOP_HZ)
        while self.running:
            with self.data_lock:
                channels = list(self.channels)
                last_rx = self.last_rx_time

            if time.time() - last_rx > config.SIGNAL_STALE_TIMEOUT_S:
                self.motor_left.set_speed_mph(0)
                self.motor_right.set_speed_mph(0)
                self.brakes.set_brake(100, 100)
                time.sleep(loop_delay)
                continue

            left_input = channels[config.CRSF_LEFT_CHANNEL - 1]
            right_input = channels[config.CRSF_RIGHT_CHANNEL - 1]

            left_mph, right_mph, left_brake, right_brake = self.algorithm.compute(
                left_input,
                right_input,
                self.motor_left.get_speed_mph(),
                self.motor_right.get_speed_mph(),
                *self.brakes.get_brake(),
            )

            self.motor_left.set_speed_mph(left_mph)
            self.motor_right.set_speed_mph(right_mph)
            self.brakes.set_brake(left_brake, right_brake)

            left_mps = left_mph * _MPH_TO_MPS
            right_mps = right_mph * _MPH_TO_MPS
            v_avg = 0.5 * (left_mps + right_mps)
            yaw_rate = (right_mps - left_mps) / max(0.01, config.WHEEL_BASE_METERS)
            lat_accel = v_avg * yaw_rate

            with self.data_lock:
                self.left_output_mph = left_mph
                self.right_output_mph = right_mph
                self.left_brake = left_brake
                self.right_brake = right_brake
                self.yaw_rate_rad = yaw_rate
                self.lat_accel = lat_accel

            time.sleep(loop_delay)

    def _update_display(self) -> None:
        elapsed = time.time() - self.start_time
        self.runtime_label.config(text=f"Runtime: {elapsed:0.1f}s")

        with self.data_lock:
            channels = list(self.channels)
            last_rx = self.last_rx_time
            frames = self.frame_count
            ch_updates = self.channel_updates
            stats_updates = self.stats_updates
            left_mph = self.left_output_mph
            right_mph = self.right_output_mph
            left_brake = self.left_brake
            right_brake = self.right_brake
            yaw_rate = self.yaw_rate_rad
            lat_accel = self.lat_accel

        age = time.time() - last_rx if last_rx > 0 else 999
        if age < config.SIGNAL_STALE_TIMEOUT_S:
            self.status_label.config(text="✅ Connected (Receiving)", fg="#00ff00")
        else:
            self.status_label.config(text="⚠️ Connected (No Data)", fg="#ffaa00")
        self.last_update_label.config(text=f"Last update: {age:0.2f}s ago")

        for i, label in enumerate(self.channel_labels):
            if i < len(channels):
                value = channels[i]
                label.config(text=str(int(value)))
                if value == 1500:
                    label.config(fg="#00ff00", bg="#1e1e1e")
                elif 1400 <= value <= 1600:
                    label.config(fg="#ffff00", bg="#1e1e1e")
                else:
                    label.config(fg="#ff8800", bg="#1e1e1e")

        self.outputs_left_label.config(
            text=f"{left_mph:0.2f} mph ({self.motor_left.get_speed_percentage():0.1f}%)"
        )
        self.outputs_right_label.config(
            text=f"{right_mph:0.2f} mph ({self.motor_right.get_speed_percentage():0.1f}%)"
        )
        self.brake_left_label.config(text=f"{left_brake:0.1f}%")
        self.brake_right_label.config(text=f"{right_brake:0.1f}%")
        self.yaw_rate_label.config(text=f"{yaw_rate * 57.2958:0.2f} deg/s")
        self.lat_accel_label.config(text=f"{lat_accel:0.2f} m/s^2")

        self.frames_label.config(text=f"Frames: {frames}")
        self.channel_updates_label.config(text=f"Channel Updates: {ch_updates}")
        self.stats_updates_label.config(text=f"Stats Updates: {stats_updates}")

        self.root.after(20, self._update_display)

    def quit_app(self) -> None:
        self.running = False
        try:
            self.brakes.cleanup()
            self.crsf.disconnect()
        finally:
            self.root.quit()
            self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive loop with GUI display")
    parser.add_argument("--port", default=config.CRSF_PORT)
    args = parser.parse_args()

    root = tk.Tk()
    app = DriveGUI(root, port=args.port)
    app.start()
    root.mainloop()


if __name__ == "__main__":
    main()
