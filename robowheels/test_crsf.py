#!/usr/bin/env python3
"""
Test script for CRSF connection on Raspberry Pi 5
Outputs connection status and received data
"""

import time
import sys
import os
from src.crsf_connection import CRSFConnection


class CLIDisplay:
    """Manages updating CLI display in place"""
    
    def __init__(self):
        self.lines_written = 0
        self.stats = {}
        self.channels = [1500] * 16
        self.frame_count = 0
        self.channel_updates = 0
        self.stats_updates = 0
        self.start_time = time.time()
        self.last_update_time = 0
    
    def clear_screen(self):
        """Clear screen and move cursor to top"""
        os.system('clear' if os.name != 'nt' else 'cls')
        self.lines_written = 0
    
    def move_to_start(self):
        """Move cursor back to start of display area"""
        if self.lines_written > 0:
            print(f"\033[{self.lines_written}A", end="")
    
    def update_display(self):
        """Update the entire display in place"""
        self.move_to_start()
        
        # Header (static)
        print("=" * 70)
        print("CRSF Connection Test - Press Ctrl+C to stop")
        print("=" * 70)
        print()
        
        # Status line
        elapsed = time.time() - self.start_time
        time_since_update = time.time() - self.last_update_time if self.last_update_time > 0 else 0
        status = "🟢 CONNECTED" if time_since_update < 2.0 else "🟡 NO DATA"
        print(f"Status: {status} | Runtime: {elapsed:6.1f}s | Last update: {time_since_update:5.2f}s ago")
        print()
        
        # Channels (4 rows of 4 channels)
        print("📡 Channels:")
        for row in range(4):
            ch_nums = [row * 4 + i + 1 for i in range(4)]
            ch_values = [self.channels[i-1] for i in ch_nums]
            print(f"  CH{ch_nums[0]:2d}: {ch_values[0]:4d}  CH{ch_nums[1]:2d}: {ch_values[1]:4d}  "
                  f"CH{ch_nums[2]:2d}: {ch_values[2]:4d}  CH{ch_nums[3]:2d}: {ch_values[3]:4d}")
        print()
        
        # Link Statistics
        print("📊 Link Statistics:")
        if self.stats:
            uplink_rssi = self.stats.get('uplink_rssi_ant1', 0)
            uplink_lq = self.stats.get('uplink_link_quality', 0)
            uplink_snr = self.stats.get('uplink_snr', 0)
            downlink_rssi = self.stats.get('downlink_rssi', 0)
            downlink_lq = self.stats.get('downlink_link_quality', 0)
            downlink_snr = self.stats.get('downlink_snr', 0)
            
            print(f"  Uplink:   RSSI: {uplink_rssi:3d} dBm  LQ: {uplink_lq:3d}%  SNR: {uplink_snr:3d} dB")
            print(f"  Downlink: RSSI: {downlink_rssi:3d} dBm  LQ: {downlink_lq:3d}%  SNR: {downlink_snr:3d} dB")
        else:
            print("  No statistics available")
        print()
        
        # Statistics
        print("📈 Statistics:")
        print(f"  Frames: {self.frame_count:6d}  |  Channel updates: {self.channel_updates:6d}  |  "
              f"Stats updates: {self.stats_updates:6d}")
        print()
        
        # Calculate total lines written
        self.lines_written = 18  # Header + status + channels + stats + spacing
        print()  # Extra line for spacing


def main():
    """Main test function"""
    # Default port for Raspberry Pi UART
    port = '/dev/ttyAMA0'
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    print(f"Attempting to connect to: {port} (baudrate: 420000)...")
    
    # Create and connect
    crsf = CRSFConnection(port=port)
    
    if not crsf.connect():
        print("❌ FAILED: Could not establish serial connection")
        print()
        print("Troubleshooting:")
        print("  1. Check if the serial port exists: ls -l /dev/tty*")
        print("  2. Ensure you have permissions: sudo usermod -a -G dialout $USER")
        print("  3. Verify UART is enabled in raspi-config")
        print("  4. Check if another process is using the port")
        sys.exit(1)
    
    # Initialize display
    display = CLIDisplay()
    display.clear_screen()
    display.start_time = time.time()
    
    try:
        while True:
            frame = crsf.read_frame()
            
            if frame:
                display.frame_count += 1
                frame_type = frame.get('type', 0)
                
                # Handle channel frames
                if frame_type == CRSFConnection.FRAME_TYPE_CHANNELS:
                    display.channel_updates += 1
                    display.channels = frame.get('channels', display.channels)
                    display.last_update_time = time.time()
                
                # Handle link statistics frames
                elif frame_type == CRSFConnection.FRAME_TYPE_LINK_STATISTICS:
                    display.stats_updates += 1
                    display.stats = frame.get('link_statistics', {})
                    display.last_update_time = time.time()
            
            # Update display every loop iteration (it will update in place)
            display.update_display()
            
            # Small delay to prevent CPU spinning
            time.sleep(0.05)  # ~20 updates per second
            
    except KeyboardInterrupt:
        # Clear the updating display and show final results
        print("\n" * 20)  # Clear the update area
        print("=" * 70)
        print("Test stopped by user")
        print("=" * 70)
        print()
        print("Final Statistics:")
        elapsed = time.time() - display.start_time
        print(f"   Test duration: {elapsed:.1f} seconds")
        print(f"   Total frames received: {display.frame_count}")
        print(f"   Channel updates: {display.channel_updates}")
        print(f"   Link stats updates: {display.stats_updates}")
        print()
        
        if crsf.is_connected():
            print("Final channel values:")
            for row in range(4):
                ch_nums = [row * 4 + i + 1 for i in range(4)]
                ch_values = [display.channels[i-1] for i in ch_nums]
                print(f"  CH{ch_nums[0]:2d}: {ch_values[0]:4d}  CH{ch_nums[1]:2d}: {ch_values[1]:4d}  "
                      f"CH{ch_nums[2]:2d}: {ch_values[2]:4d}  CH{ch_nums[3]:2d}: {ch_values[3]:4d}")
            print()
            
            if display.stats:
                print("Final link statistics:")
                uplink_rssi = display.stats.get('uplink_rssi_ant1', 0)
                uplink_lq = display.stats.get('uplink_link_quality', 0)
                uplink_snr = display.stats.get('uplink_snr', 0)
                downlink_rssi = display.stats.get('downlink_rssi', 0)
                downlink_lq = display.stats.get('downlink_link_quality', 0)
                downlink_snr = display.stats.get('downlink_snr', 0)
                print(f"  Uplink:   RSSI: {uplink_rssi:3d} dBm  LQ: {uplink_lq:3d}%  SNR: {uplink_snr:3d} dB")
                print(f"  Downlink: RSSI: {downlink_rssi:3d} dBm  LQ: {downlink_lq:3d}%  SNR: {downlink_snr:3d} dB")
                print()
        
        crsf.disconnect()
        print("✅ Connection closed")
        print()
        
        # Determine test result
        if display.frame_count > 0:
            print("✅ TEST PASSED: CRSF connection is working!")
            print(f"   Successfully received {display.frame_count} frames")
        else:
            print("⚠️  TEST INCONCLUSIVE: No frames received")
            print("   This could mean:")
            print("   - Transmitter is not powered on")
            print("   - Wrong serial port")
            print("   - Wiring issue")
            print("   - CRSF device not configured correctly")
        
        sys.exit(0)
    
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        crsf.disconnect()
        sys.exit(1)


if __name__ == "__main__":
    main()

