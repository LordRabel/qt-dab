#!/usr/bin/env python3
"""
DAB Constellation Viewer
Complete application: RTL-SDR -> OFDM Processing -> Constellation Display

Usage:
    python dab_constellation_viewer.py --freq 220352000 --gain 30

This script demonstrates the complete signal chain from qt-dab in Python:
    RTL-SDR -> IQ Samples -> Frequency Correction -> OFDM Decoding -> Constellation Display
"""

import numpy as np
import argparse
import sys
import time
import threading
from typing import Optional

# Import our modules
from dab_receiver import DABReceiver
from ofdm_processor import OFDMProcessor, DABParams
from constellation_display import ConstellationDisplay


class DABConstellationViewer:
    """
    Complete DAB constellation viewer application
    Orchestrates receiver, processor, and display
    """

    def __init__(self, frequency: int, gain: float = 30.0, device_index: int = 0):
        """
        Initialize DAB constellation viewer

        Args:
            frequency: DAB channel frequency in Hz
            gain: RF gain in dB (0 = auto)
            device_index: RTL-SDR device index
        """
        self.frequency = frequency
        self.gain = gain

        print("=" * 60)
        print("DAB CONSTELLATION VIEWER")
        print("=" * 60)
        print(f"Frequency: {frequency / 1e6:.3f} MHz")
        print(f"Gain: {gain} dB")
        print("=" * 60)

        # Initialize components
        try:
            self.receiver = DABReceiver(device_index)
            self.processor = OFDMProcessor()
            self.display = ConstellationDisplay(figsize=(10, 10), max_points=1536)
        except Exception as e:
            print(f"\nERROR: Failed to initialize: {e}")
            print("\nTroubleshooting:")
            print("  1. Is RTL-SDR dongle connected?")
            print("  2. Is pyrtlsdr installed? (pip install pyrtlsdr)")
            print("  3. Check USB permissions (may need udev rules)")
            sys.exit(1)

        # Configure receiver
        self.receiver.tune(frequency)
        self.receiver.set_gain(gain)

        # Processing thread control
        self.running = False
        self.processing_thread: Optional[threading.Thread] = None

        # Statistics
        self.samples_processed = 0
        self.frames_displayed = 0
        self.start_time = 0

        print("\nInitialization complete!")

    def _processing_loop(self):
        """
        Main processing loop (runs in separate thread)
        Continuously reads samples, processes OFDM, and updates display
        """
        params = self.processor.params

        # Buffer for accumulating samples
        sample_buffer = np.array([], dtype=np.complex64)
        symbols_per_update = 10  # Process 10 symbols, then update display

        print("\nProcessing started...")
        print("Press Ctrl+C to stop")

        while self.running:
            try:
                # Read samples (multiple symbols)
                num_samples = params.T_s * symbols_per_update
                new_samples = self.receiver.read_samples(num_samples)

                # Accumulate samples
                sample_buffer = np.concatenate([sample_buffer, new_samples])

                # Process available symbols
                while len(sample_buffer) >= params.T_s:
                    # Extract one symbol
                    symbol_samples = sample_buffer[:params.T_s]
                    sample_buffer = sample_buffer[params.T_s:]

                    # Process symbol
                    constellation = self.processor.process_samples(symbol_samples)

                    self.samples_processed += params.T_s

                    # Update display if constellation available
                    if constellation is not None and len(constellation) > 0:
                        self.display.update_constellation(constellation)
                        self.frames_displayed += 1

                        # Print status every 100 frames
                        if self.frames_displayed % 100 == 0:
                            elapsed = time.time() - self.start_time
                            rate = self.samples_processed / elapsed / 1e6
                            print(f"Frames: {self.frames_displayed}, "
                                  f"Rate: {rate:.2f} MSamples/s, "
                                  f"Constellation: {len(constellation)} points")

            except KeyboardInterrupt:
                print("\nStopping...")
                self.running = False
                break
            except Exception as e:
                print(f"\nProcessing error: {e}")
                import traceback
                traceback.print_exc()
                break

        print("Processing stopped")

    def start(self):
        """Start receiver and display"""
        self.running = True
        self.start_time = time.time()

        # Start processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()

        # Start display (blocks until window closed)
        try:
            self.display.show(interval=100)  # Update display every 100ms
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        finally:
            self.stop()

    def stop(self):
        """Stop receiver and cleanup"""
        print("\nShutting down...")
        self.running = False

        # Wait for processing thread
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

        # Close receiver
        self.receiver.close()

        # Print statistics
        if self.start_time > 0:
            elapsed = time.time() - self.start_time
            print(f"\nStatistics:")
            print(f"  Runtime: {elapsed:.1f} seconds")
            print(f"  Samples processed: {self.samples_processed / 1e6:.1f} M")
            print(f"  Frames displayed: {self.frames_displayed}")
            print(f"  Average rate: {self.samples_processed / elapsed / 1e6:.2f} MSamples/s")

        print("\nGoodbye!")


def list_dab_frequencies():
    """Print common DAB frequencies in Germany"""
    # DAB+ Band III frequencies (Germany)
    dab_channels = {
        '5A': 174928000,
        '5B': 176640000,
        '5C': 178352000,
        '5D': 180064000,
        '6A': 181936000,
        '6B': 183648000,
        '6C': 185360000,
        '6D': 187072000,
        '7A': 188928000,
        '7B': 190640000,
        '7C': 192352000,
        '7D': 194064000,
        '8A': 195936000,
        '8B': 197648000,
        '8C': 199360000,
        '8D': 201072000,
        '9A': 202928000,
        '9B': 204640000,
        '9C': 206352000,
        '9D': 208064000,
        '10A': 209936000,
        '10B': 211648000,
        '10C': 213360000,
        '10D': 215072000,
        '11A': 216928000,
        '11B': 218640000,
        '11C': 220352000,
        '11D': 222064000,
        '12A': 223936000,
        '12B': 225648000,
        '12C': 227360000,
        '12D': 229072000,
    }

    print("\nCommon DAB+ Channels (Band III - Germany):")
    print("-" * 50)
    for channel, freq in sorted(dab_channels.items()):
        print(f"  {channel:4s}: {freq:9d} Hz ({freq / 1e6:.3f} MHz)")
    print("-" * 50)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='DAB Constellation Viewer - RTL-SDR to Constellation Diagram',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View DAB channel 11C (220.352 MHz) with auto gain
  python dab_constellation_viewer.py --freq 220352000

  # With manual gain
  python dab_constellation_viewer.py --freq 220352000 --gain 35

  # List common DAB frequencies
  python dab_constellation_viewer.py --list-frequencies

Notes:
  - RTL-SDR dongle must be connected
  - DAB signal must be present at specified frequency
  - Use --list-frequencies to see common DAB channels
  - Try different gain values if constellation is noisy
        """
    )

    parser.add_argument('--freq', '--frequency', type=int,
                        help='DAB frequency in Hz (e.g., 220352000 for 220.352 MHz)')
    parser.add_argument('--gain', type=float, default=30.0,
                        help='RF gain in dB (default: 30, use 0 for auto)')
    parser.add_argument('--device', type=int, default=0,
                        help='RTL-SDR device index (default: 0)')
    parser.add_argument('--list-frequencies', action='store_true',
                        help='List common DAB frequencies and exit')

    args = parser.parse_args()

    # List frequencies and exit
    if args.list_frequencies:
        list_dab_frequencies()
        sys.exit(0)

    # Check required arguments
    if not args.freq:
        parser.print_help()
        print("\n" + "=" * 60)
        list_dab_frequencies()
        print("\nERROR: --freq is required!")
        print("Example: python dab_constellation_viewer.py --freq 220352000")
        sys.exit(1)

    # Validate frequency range
    if args.freq < 100e6 or args.freq > 300e6:
        print(f"WARNING: Frequency {args.freq / 1e6:.3f} MHz is outside typical DAB range (174-230 MHz)")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            sys.exit(0)

    # Create and start viewer
    try:
        viewer = DABConstellationViewer(
            frequency=args.freq,
            gain=args.gain,
            device_index=args.device
        )
        viewer.start()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
