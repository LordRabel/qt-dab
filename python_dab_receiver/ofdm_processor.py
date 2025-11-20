#!/usr/bin/env python3
"""
OFDM Processor for DAB
Equivalent to ofdm-decoder.cpp and ofdm-handler.cpp

Implements:
- OFDM symbol extraction
- FFT processing
- Phase reference and equalization
- Constellation point generation
"""

import numpy as np
from typing import Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class DABParams:
    """DAB Mode I Parameters (same as dab-constants.h)"""
    # OFDM parameters
    T_null: int = 2656      # Null period samples
    T_u: int = 2048         # Useful symbol samples (FFT size)
    T_g: int = 504          # Guard period samples
    T_s: int = 2552         # Symbol length (T_u + T_g)
    T_F: int = 196608       # Frame length

    # Carriers
    carriers: int = 1536    # Number of active carriers

    # Frame structure
    symbols_per_frame: int = 76  # 1 null + 3 FIC + 72 MSC


class OFDMDecoder:
    """
    OFDM Decoder - Core signal processing
    Equivalent to ofdm-decoder.cpp
    """

    def __init__(self, params: Optional[DABParams] = None):
        """
        Initialize OFDM decoder

        Args:
            params: DAB parameters (default: Mode I)
        """
        self.params = params if params else DABParams()

        # FFT size
        self.fft_size = self.params.T_u

        # Buffers
        self.fft_buffer = np.zeros(self.fft_size, dtype=np.complex64)
        self.phase_reference = np.zeros(self.fft_size, dtype=np.complex64)

        # Initialize phase reference (will be updated)
        self.phase_reference_initialized = False

        # Equalized symbols (constellation points)
        self.conj_vector = np.zeros(self.fft_size, dtype=np.complex64)

        # Statistics
        self.mean_level = 1.0
        self.max_amp = 1.0

        # Frame counter for display updates
        self.frame_counter = 0
        self.display_update_rate = 10  # Update every 10 frames

        print(f"OFDM Decoder initialized (Mode I)")
        print(f"  FFT Size: {self.fft_size}")
        print(f"  Carriers: {self.params.carriers}")
        print(f"  Symbol length: {self.params.T_s}")

    def decode_symbol(self, symbol_samples: np.ndarray, symbol_number: int) -> Tuple[np.ndarray, dict]:
        """
        Decode one OFDM symbol

        Args:
            symbol_samples: T_s samples containing guard + useful symbol
            symbol_number: Symbol number in frame (0-75)

        Returns:
            Tuple of (constellation_points, statistics)
        """
        # Extract useful symbol (skip guard period)
        # symbol_samples[0:T_g] = guard (discard)
        # symbol_samples[T_g:T_s] = useful symbol
        useful_samples = symbol_samples[self.params.T_g:self.params.T_s]

        if len(useful_samples) != self.params.T_u:
            raise ValueError(f"Invalid symbol length: {len(useful_samples)}, expected {self.params.T_u}")

        # Copy to FFT buffer
        self.fft_buffer = useful_samples.copy()

        # Perform FFT (Time domain -> Frequency domain)
        fft_output = np.fft.fft(self.fft_buffer)

        # Extract carriers (centered around DC)
        # DAB carriers: -768 to +768 (excluding DC)
        carrier_indices = self._get_carrier_indices()

        # Initialize phase reference with first symbol
        if not self.phase_reference_initialized:
            self.phase_reference = fft_output.copy()
            self.phase_reference_initialized = True
            # Return empty constellation for first symbol
            return np.array([]), {}

        # Equalization and phase correction
        # This is the CORE of DQPSK demodulation!
        sum_level = 0.0
        max_amplitude = 0.0

        for i, carrier_idx in enumerate(carrier_indices):
            # Current symbol FFT bin
            current = fft_output[carrier_idx]

            # Previous symbol (phase reference)
            prev_symbol = self.phase_reference[carrier_idx]

            # DQPSK Demodulation
            # Information is encoded in the PHASE DIFFERENCE between symbols
            # Formula: fftBin = current * conj(prev) / |prev|
            if np.abs(prev_symbol) > 1e-10:
                normalized_prev = prev_symbol / np.abs(prev_symbol)
                fft_bin = current * np.conj(normalized_prev)
            else:
                fft_bin = current

            # Store equalized symbol
            self.conj_vector[carrier_idx] = fft_bin

            # Update statistics
            bin_abs = np.abs(fft_bin)
            sum_level += bin_abs
            max_amplitude = max(max_amplitude, bin_abs)

            # Update phase reference for next symbol
            self.phase_reference[carrier_idx] = current

        # Calculate mean level
        self.mean_level = sum_level / len(carrier_indices) if len(carrier_indices) > 0 else 1.0
        self.max_amp = max_amplitude if max_amplitude > 0 else 1.0

        # Extract constellation points for display
        constellation = self._extract_constellation(carrier_indices)

        # Statistics
        stats = {
            'mean_level': self.mean_level,
            'max_amp': self.max_amp,
            'symbol_number': symbol_number
        }

        return constellation, stats

    def _get_carrier_indices(self) -> np.ndarray:
        """
        Get FFT bin indices for active carriers

        DAB Mode I: 1536 carriers centered around DC
        Range: -768 to +768 (excluding DC at 0)
        """
        # Carriers from -carriers/2 to +carriers/2
        half_carriers = self.params.carriers // 2

        # Create carrier list (excluding DC)
        carriers_neg = np.arange(-half_carriers, 0)  # -768 to -1
        carriers_pos = np.arange(1, half_carriers + 1)  # +1 to +768
        carriers = np.concatenate([carriers_neg, carriers_pos])

        # Convert to FFT bin indices
        # FFT output: [0, 1, 2, ..., N/2-1, -N/2, ..., -2, -1]
        # Remap: negative frequencies wrap around
        carrier_indices = np.where(carriers < 0, carriers + self.fft_size, carriers)

        return carrier_indices

    def _extract_constellation(self, carrier_indices: np.ndarray) -> np.ndarray:
        """
        Extract normalized constellation points for display

        Args:
            carrier_indices: Active carrier FFT indices

        Returns:
            Normalized complex constellation points
        """
        # Extract equalized symbols
        constellation = self.conj_vector[carrier_indices]

        # Normalize by max amplitude (same as qt-dab)
        if self.max_amp > 0:
            constellation = constellation / self.max_amp

        return constellation

    def should_update_display(self) -> bool:
        """
        Check if constellation display should be updated

        Returns:
            True if display should update this frame
        """
        self.frame_counter += 1
        if self.frame_counter >= self.display_update_rate:
            self.frame_counter = 0
            return True
        return False


class FrameSynchronizer:
    """
    Frame synchronization using null symbol correlation
    Equivalent to correlator.cpp
    """

    def __init__(self, params: Optional[DABParams] = None):
        self.params = params if params else DABParams()
        self.fft_size = self.params.T_u

        # Null symbol reference pattern (all zeros in frequency domain)
        self.null_reference = np.zeros(self.fft_size, dtype=np.complex64)

        print("Frame Synchronizer initialized")

    def find_null_symbol(self, samples: np.ndarray) -> Optional[int]:
        """
        Find null symbol position using energy detection

        Args:
            samples: Input samples buffer

        Returns:
            Index of null symbol start, or None if not found
        """
        if len(samples) < self.params.T_F:
            return None

        # Simple energy-based null detection
        # Null symbol has significantly lower energy than data symbols

        window_size = self.params.T_null
        threshold = 0.3  # Energy threshold (relative)

        # Calculate energy in sliding windows
        energies = []
        for i in range(len(samples) - window_size):
            window = samples[i:i + window_size]
            energy = np.mean(np.abs(window) ** 2)
            energies.append(energy)

        energies = np.array(energies)

        # Find minima (null symbol has minimum energy)
        if len(energies) == 0:
            return None

        # Normalize energies
        max_energy = np.max(energies)
        if max_energy > 0:
            energies = energies / max_energy

        # Find positions below threshold
        null_candidates = np.where(energies < threshold)[0]

        if len(null_candidates) > 0:
            # Return first candidate
            return null_candidates[0]

        return None


class OFDMProcessor:
    """
    High-level OFDM processing orchestrator
    Combines synchronization, decoding, and constellation extraction
    """

    def __init__(self):
        """Initialize OFDM processor"""
        self.params = DABParams()
        self.decoder = OFDMDecoder(self.params)
        self.synchronizer = FrameSynchronizer(self.params)

        # State
        self.is_synchronized = False
        self.sample_offset = 0

        print("OFDM Processor initialized")

    def process_samples(self, samples: np.ndarray) -> Optional[np.ndarray]:
        """
        Process samples and extract constellation points

        Args:
            samples: Input IQ samples

        Returns:
            Constellation points (complex array) or None
        """
        # Check if we have enough samples for at least one symbol
        if len(samples) < self.params.T_s:
            return None

        # Simple processing: extract first symbol and decode
        # (Real implementation would do proper frame sync)

        # Extract one OFDM symbol
        symbol_samples = samples[:self.params.T_s]

        # Decode symbol
        constellation, stats = self.decoder.decode_symbol(symbol_samples, 0)

        # Return constellation if available
        if len(constellation) > 0:
            return constellation

        return None

    def process_frame(self, samples: np.ndarray, start_offset: int = 0) -> List[np.ndarray]:
        """
        Process complete DAB frame

        Args:
            samples: Input samples (should contain complete frame)
            start_offset: Starting offset in samples

        Returns:
            List of constellation arrays (one per symbol)
        """
        constellations = []

        # Skip null symbol
        offset = start_offset + self.params.T_null

        # Process each symbol in frame
        for symbol_num in range(1, self.params.symbols_per_frame):
            # Check if enough samples available
            if offset + self.params.T_s > len(samples):
                break

            # Extract symbol
            symbol_samples = samples[offset:offset + self.params.T_s]

            # Decode
            constellation, stats = self.decoder.decode_symbol(symbol_samples, symbol_num)

            if len(constellation) > 0:
                constellations.append(constellation)

            # Advance to next symbol
            offset += self.params.T_s

        return constellations


if __name__ == "__main__":
    # Test OFDM processor with synthetic data
    print("OFDM Processor Test")
    print("-" * 50)

    # Create test signal (simplified QPSK-like constellation)
    processor = OFDMProcessor()

    # Generate synthetic OFDM symbol
    T_s = processor.params.T_s
    T_g = processor.params.T_g
    T_u = processor.params.T_u

    # Create random QPSK-like symbols
    np.random.seed(42)
    num_carriers = processor.params.carriers

    # Generate symbol in frequency domain
    freq_domain = np.zeros(T_u, dtype=np.complex64)

    # Add QPSK constellation points to carriers
    carrier_indices = processor.decoder._get_carrier_indices()
    qpsk_symbols = np.random.choice([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j], size=len(carrier_indices))
    freq_domain[carrier_indices] = qpsk_symbols

    # IFFT to get time-domain signal
    time_domain = np.fft.ifft(freq_domain)

    # Add guard interval (cyclic prefix)
    guard = time_domain[-T_g:]
    symbol_with_guard = np.concatenate([guard, time_domain])

    # Add some noise
    noise_level = 0.1
    symbol_with_guard += noise_level * (np.random.randn(len(symbol_with_guard)) +
                                         1j * np.random.randn(len(symbol_with_guard)))

    print(f"\nGenerated test symbol: {len(symbol_with_guard)} samples")

    # Process twice (first for phase ref init, second for constellation)
    constellation1 = processor.process_samples(symbol_with_guard)
    print(f"First decode: {constellation1}")

    constellation2 = processor.process_samples(symbol_with_guard)
    print(f"Second decode: {len(constellation2) if constellation2 is not None else 0} points")

    if constellation2 is not None:
        print(f"Constellation range: I=[{np.min(constellation2.real):.2f}, {np.max(constellation2.real):.2f}], "
              f"Q=[{np.min(constellation2.imag):.2f}, {np.max(constellation2.imag):.2f}]")
