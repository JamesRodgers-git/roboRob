#!/usr/bin/env python3
"""
CLI test for CRSF connection. Shows the same data as test_crsf_gui but in the terminal:
connection status, 16 channels, link statistics (uplink/downlink), and frame counts.
Uses CRSFConnection.start() so the connection runs its own reader thread.
"""

import os
import sys
import time

import config
from src.crsf_connection import CRSFConnection


def clear_screen() -> None:
    os.system("clear" if os.name != "nt" else "cls")


def move_cursor_up(lines: int) -> None:
    if lines > 0:
        print(f"\033[{lines}A", end="")


def main() -> None:
    port = config.CRSF_PORT
    if len(sys.argv) > 1:
        port = sys.argv[1]
    baud = config.CRSF_BAUD_RATE
    print(f"Connecting to {port} (baud {baud})...")

    crsf = CRSFConnection(port=port, baudrate=baud)
    try:
        crsf.start()
    except RuntimeError as e:
        print(f"Failed to start: {e}")
        print("Troubleshooting:")
        print("  1. Check if the serial port exists: ls -l /dev/tty*")
        print("  2. Ensure permissions: sudo usermod -a -G dialout $USER")
        print("  3. Verify UART is enabled in raspi-config")
        sys.exit(1)

    start_time = time.time()
    display_lines = 0

    try:
        while True:
            channels, last_update, ch_updates, stats_updates, link_stats = crsf.get_snapshot()
            age = time.time() - last_update if last_update > 0 else 999.0
            elapsed = time.time() - start_time

            move_cursor_up(display_lines)

            lines = []
            lines.append("=" * 70)
            lines.append("CRSF Connection Test (CLI) - Press Ctrl+C to stop")
            lines.append("=" * 70)
            lines.append("")
            # Connection status (like GUI)
            status = "CONNECTED (Receiving)" if age < 2.0 else "CONNECTED (No Data)"
            lines.append(f"Status: {status}  |  Runtime: {elapsed:6.1f}s  |  Last update: {age:5.2f}s ago")
            lines.append("")
            # Channels (4x4, like GUI)
            lines.append("Channels (16):")
            for row in range(4):
                ch_nums = [row * 4 + i + 1 for i in range(4)]
                ch_vals = [int(channels[i - 1]) for i in ch_nums]
                lines.append(
                    f"  CH{ch_nums[0]:2d}: {ch_vals[0]:4d}  CH{ch_nums[1]:2d}: {ch_vals[1]:4d}  "
                    f"CH{ch_nums[2]:2d}: {ch_vals[2]:4d}  CH{ch_nums[3]:2d}: {ch_vals[3]:4d}"
                )
            lines.append("")
            # Link statistics (like GUI: uplink / downlink)
            lines.append("Link Statistics:")
            if link_stats:
                ul_rssi = link_stats.get("uplink_rssi_ant1", 0)
                ul_lq = link_stats.get("uplink_link_quality", 0)
                ul_snr = link_stats.get("uplink_snr", 0)
                dl_rssi = link_stats.get("downlink_rssi", 0)
                dl_lq = link_stats.get("downlink_link_quality", 0)
                dl_snr = link_stats.get("downlink_snr", 0)
                lines.append(f"  Uplink:   RSSI: {ul_rssi:3d} dBm   LQ: {ul_lq:3d}%   SNR: {ul_snr:3d} dB")
                lines.append(f"  Downlink: RSSI: {dl_rssi:3d} dBm   LQ: {dl_lq:3d}%   SNR: {dl_snr:3d} dB")
            else:
                lines.append("  (none yet)")
            lines.append("")
            # Statistics (like GUI)
            total_frames = ch_updates + stats_updates
            lines.append("Statistics:")
            lines.append(f"  Frames: {total_frames:6d}  |  Channel updates: {ch_updates:6d}  |  Stats updates: {stats_updates:6d}")
            lines.append("")

            text = "\n".join(lines)
            print(text)
            display_lines = len(lines)

            time.sleep(0.05)

    except KeyboardInterrupt:
        move_cursor_up(display_lines)
        print("\n" * (display_lines + 2))

        crsf.stop()
        elapsed = time.time() - start_time
        channels, last_update, ch_updates, stats_updates, link_stats = crsf.get_snapshot()
        total = ch_updates + stats_updates

        print("=" * 70)
        print("Test stopped by user")
        print("=" * 70)
        print()
        print("Final statistics:")
        print(f"  Duration:     {elapsed:.1f}s")
        print(f"  Frames:       {total}")
        print(f"  Ch. updates:  {ch_updates}")
        print(f"  Stats updates:{stats_updates}")
        print()
        print("Final channel values:")
        for row in range(4):
            ch_nums = [row * 4 + i + 1 for i in range(4)]
            ch_vals = [int(channels[i - 1]) for i in ch_nums]
            print(
                f"  CH{ch_nums[0]:2d}: {ch_vals[0]:4d}  CH{ch_nums[1]:2d}: {ch_vals[1]:4d}  "
                f"CH{ch_nums[2]:2d}: {ch_vals[2]:4d}  CH{ch_nums[3]:2d}: {ch_vals[3]:4d}"
            )
        if link_stats:
            print()
            print("Final link statistics:")
            print(f"  Uplink:   RSSI: {link_stats.get('uplink_rssi_ant1', 0):3d} dBm   LQ: {link_stats.get('uplink_link_quality', 0):3d}%   SNR: {link_stats.get('uplink_snr', 0):3d} dB")
            print(f"  Downlink: RSSI: {link_stats.get('downlink_rssi', 0):3d} dBm   LQ: {link_stats.get('downlink_link_quality', 0):3d}%   SNR: {link_stats.get('downlink_snr', 0):3d} dB")
        print()
        print("Connection closed.")
        print()
        if total > 0:
            print("TEST PASSED: CRSF connection is working.")
        else:
            print("No frames received. Check transmitter, port, and wiring.")
        sys.exit(0)

    except Exception as e:
        crsf.stop()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
