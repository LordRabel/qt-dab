#!/usr/bin/env python3
"""
DAB Receiver - RTL-SDR to Constellation Diagram
Python implementation of qt-dab signal processing chain

Author: Based on qt-dab project analysis
License: Same as qt-dab
"""

import numpy as np
from typing import Optional, Tuple
import time


class RTLSDRHandler:
    """
    RTL-SDR Device Handler
    Equivalent to rtlsdr-handler.cpp
    """

    def __init__(self, device_index: int = 0):
        """
        Initialize RTL-SDR device

        Args:
            device_index: RTL-SDR device index (default: 0)
        """
        # First, try to import the module
        try:
            from rtlsdr import RtlSdr
        except ImportError as e:
            raise ImportError(
                f"pyrtlsdr package not found: {e}\n"
                f"Install with: pip install pyrtlsdr"
            )

        # Then, try to initialize the device
        try:
            self.sdr = RtlSdr(device_index)
        except (OSError, IOError) as e:
            # Device not found or access denied
            raise RuntimeError(
                f"Failed to open RTL-SDR device:\n{e}\n\n"
                f"Troubleshooting:\n"
                f"  • Is RTL-SDR dongle connected?\n"
                f"  • On Windows: Install librtlsdr.dll (see Zadig driver installation)\n"
                f"  • On Linux: Check USB permissions (udev rules)\n"
                f"  • Try different USB port\n"
                f"  • Check if another program is using the device"
            )
        except ImportError as e:
            # librtlsdr library not found (common on Windows)
            raise RuntimeError(
                f"RTL-SDR library (librtlsdr) not found:\n{e}\n\n"
                f"Windows Installation:\n"
                f"  1. Download Zadig: https://zadig.akeo.ie/\n"
                f"  2. Run Zadig, select your RTL-SDR device\n"
                f"  3. Install WinUSB driver (not libusb-win32!)\n"
                f"  4. Download librtlsdr.dll:\n"
                f"     https://ftp.osmocom.org/binaries/windows/rtl-sdr/\n"
                f"  5. Place librtlsdr.dll in Python directory or PATH\n\n"
                f"Alternative: Use SDR# to verify device works first"
            )
        except Exception as e:
            raise RuntimeError(f"Unexpected error initializing RTL-SDR: {e}")

        # DAB Mode I Parameters (same as qt-dab)
        self.SAMPLERATE = 2048000  # 2.048 MHz
        self.buffer_size = 8 * 1024 * 1024  # 8 MB buffer

        # Configure device
        self.sdr.sample_rate = self.SAMPLERATE
        self.sdr.gain = 'auto'

        # Conversion table (uint8 -> float)
        # Equivalent to: convTable[i] = (i - 127.38) / 128.0
        self.conv_table = np.arange(256, dtype=np.float32)
        self.conv_table = (self.conv_table - 127.38) / 128.0

        # DC offset tracking
        self.sum_i = 0.0
        self.sum_q = 0.0
        self.dc_remove_enabled = True

        print(f"RTL-SDR initialized: {self.SAMPLERATE} Hz")

    def set_frequency(self, freq_hz: int):
        """Set center frequency"""
        self.sdr.center_freq = freq_hz
        print(f"Frequency set to: {freq_hz / 1e6:.3f} MHz")

    def set_gain(self, gain_db: float):
        """Set RF gain"""
        if gain_db == 0:
            self.sdr.gain = 'auto'
        else:
            self.sdr.gain = gain_db

    def get_samples(self, num_samples: int) -> np.ndarray:
        """
        Read IQ samples from RTL-SDR

        Args:
            num_samples: Number of complex samples to read

        Returns:
            Complex numpy array of IQ samples
        """
        # Read samples (pyrtlsdr returns complex floats directly)
        samples = self.sdr.read_samples(num_samples)

        # Optional DC offset removal
        if self.dc_remove_enabled:
            dc_offset = np.mean(samples)
            samples = samples - dc_offset

        return samples

    def close(self):
        """Close RTL-SDR device"""
        if self.sdr:
            self.sdr.close()
            print("RTL-SDR closed")


class RingBuffer:
    """Simple ring buffer for sample storage"""

    def __init__(self, size: int):
        self.buffer = np.zeros(size, dtype=np.complex64)
        self.size = size
        self.write_pos = 0
        self.read_pos = 0
        self.available = 0

    def put(self, data: np.ndarray):
        """Put data into buffer"""
        data_len = len(data)

        # Handle wraparound
        if self.write_pos + data_len > self.size:
            first_chunk = self.size - self.write_pos
            self.buffer[self.write_pos:] = data[:first_chunk]
            self.buffer[:data_len - first_chunk] = data[first_chunk:]
            self.write_pos = data_len - first_chunk
        else:
            self.buffer[self.write_pos:self.write_pos + data_len] = data
            self.write_pos = (self.write_pos + data_len) % self.size

        self.available = min(self.available + data_len, self.size)

    def get(self, num_samples: int) -> Optional[np.ndarray]:
        """Get data from buffer"""
        if self.available < num_samples:
            return None

        result = np.zeros(num_samples, dtype=np.complex64)

        # Handle wraparound
        if self.read_pos + num_samples > self.size:
            first_chunk = self.size - self.read_pos
            result[:first_chunk] = self.buffer[self.read_pos:]
            result[first_chunk:] = self.buffer[:num_samples - first_chunk]
            self.read_pos = num_samples - first_chunk
        else:
            result = self.buffer[self.read_pos:self.read_pos + num_samples].copy()
            self.read_pos = (self.read_pos + num_samples) % self.size

        self.available -= num_samples
        return result

    def samples_available(self) -> int:
        """Return number of available samples"""
        return self.available


class FrequencyCorrector:
    """
    Frequency offset correction using NCO (Numerically Controlled Oscillator)
    Equivalent to sample-reader.cpp frequency correction
    """

    def __init__(self, samplerate: int):
        self.samplerate = samplerate
        self.current_phase = 0.0
        self.phase_step = 0.0

    def set_offset(self, offset_hz: float):
        """Set frequency offset to correct"""
        self.phase_step = 2.0 * np.pi * offset_hz / self.samplerate

    def correct(self, samples: np.ndarray) -> np.ndarray:
        """
        Apply frequency correction to samples

        Args:
            samples: Input complex samples

        Returns:
            Frequency-corrected samples
        """
        num_samples = len(samples)

        # Generate oscillator phase ramp
        phases = self.current_phase + np.arange(num_samples) * self.phase_step

        # Generate complex oscillator signal
        oscillator = np.exp(-1j * phases)

        # Apply correction (multiply by conjugate of offset)
        corrected = samples * oscillator

        # Update phase for next call
        self.current_phase = (self.current_phase + num_samples * self.phase_step) % (2 * np.pi)

        return corrected


class DABReceiver:
    """
    Main DAB Receiver class
    Orchestrates the complete signal chain
    """

    def __init__(self, device_index: int = 0):
        """
        Initialize DAB receiver

        Args:
            device_index: RTL-SDR device index
        """
        # RTL-SDR device
        self.rtlsdr = RTLSDRHandler(device_index)

        # Parameters
        self.SAMPLERATE = 2048000

        # Buffers
        self.sample_buffer = RingBuffer(8 * 1024 * 1024)

        # Frequency correction
        self.freq_corrector = FrequencyCorrector(self.SAMPLERATE)

        # OFDM Processor (will be initialized later)
        self.ofdm_processor = None

        print("DAB Receiver initialized")

    def tune(self, freq_hz: int):
        """Tune to DAB channel frequency"""
        self.rtlsdr.set_frequency(freq_hz)

    def set_gain(self, gain_db: float):
        """Set RF gain"""
        self.rtlsdr.set_gain(gain_db)

    def read_samples(self, num_samples: int) -> np.ndarray:
        """
        Read and process samples from RTL-SDR

        Args:
            num_samples: Number of samples to read

        Returns:
            Processed complex samples
        """
        # Get samples from device
        samples = self.rtlsdr.get_samples(num_samples)

        # Apply frequency correction
        samples = self.freq_corrector.correct(samples)

        return samples

    def close(self):
        """Cleanup and close"""
        self.rtlsdr.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Simple test
    print("DAB Receiver Test")
    print("-" * 50)

    try:
        receiver = DABReceiver()
        receiver.tune(220352000)  # 220.352 MHz (example DAB frequency)

        print("\nReading samples...")
        samples = receiver.read_samples(1024)
        print(f"Read {len(samples)} samples")
        print(f"Sample range: {np.min(np.abs(samples)):.3f} to {np.max(np.abs(samples)):.3f}")

        receiver.close()

    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: RTL-SDR device must be connected!")
