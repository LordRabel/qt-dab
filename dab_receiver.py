#!/usr/bin/env python3
"""
DAB Receiver - Python Implementation
Basierend auf qt-dab C++ Code
Dekodierung von IQ-Samples bis zum Konstellationsdiagramm
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk
from rtlsdr import RtlSdr
import threading
import time
from collections import deque

# ==================== DAB MODE I PARAMETER ====================
class DABParams:
    """DAB Transmission Mode I Parameter"""
    def __init__(self, mode=1):
        if mode == 1:
            self.mode = 1
            self.L = 76              # Blocks per frame (1 null + 75 data)
            self.K = 1536            # Number of carriers
            self.T_F = 196608        # Samples per frame
            self.T_null = 2656       # Null symbol length
            self.T_s = 2552          # OFDM symbol length (guard + useful)
            self.T_u = 2048          # FFT size (useful part)
            self.T_g = 504           # Guard interval
            self.carrierDiff = 1000  # Subcarrier spacing (Hz)
            self.sample_rate = 2048000  # 2.048 MHz
            self.CIFs = 4
        else:
            raise NotImplementedError(f"Mode {mode} not implemented")

# ==================== PHASE TABLE ====================
class PhaseTable:
    """
    Generiert Phase Reference Symbol (Block 0) für DAB
    Basiert auf h-tables aus dem DAB Standard
    """
    def __init__(self, params):
        self.params = params
        self.T_u = params.T_u
        self.carriers = params.K

        # h-tables (32 elements each, periodic)
        self.h0 = np.array([0, 2, 0, 0, 0, 0, 1, 1, 2, 0, 0, 0, 2, 2, 1, 1,
                           0, 2, 0, 0, 0, 0, 1, 1, 2, 0, 0, 0, 2, 2, 1, 1], dtype=np.int8)
        self.h1 = np.array([0, 3, 2, 3, 0, 1, 3, 0, 2, 1, 2, 3, 2, 3, 3, 0,
                           0, 3, 2, 3, 0, 1, 3, 0, 2, 1, 2, 3, 2, 3, 3, 0], dtype=np.int8)
        self.h2 = np.array([0, 0, 0, 2, 0, 2, 1, 3, 2, 2, 0, 2, 2, 0, 1, 3,
                           0, 0, 0, 2, 0, 2, 1, 3, 2, 2, 0, 2, 2, 0, 1, 3], dtype=np.int8)
        self.h3 = np.array([0, 1, 2, 1, 0, 3, 3, 2, 2, 3, 2, 1, 2, 1, 3, 2,
                           0, 1, 2, 1, 0, 3, 3, 2, 2, 3, 2, 1, 2, 1, 3, 2], dtype=np.int8)

        # Mode I table: (kmin, kmax, i, n)
        self.modeI_table = [
            (-768, -737, 0, 1), (-736, -705, 1, 2), (-704, -673, 2, 0), (-672, -641, 3, 1),
            (-640, -609, 0, 2), (-608, -577, 1, 3), (-576, -545, 2, 2), (-544, -513, 3, 2),
            (-512, -481, 0, 2), (-480, -449, 1, 3), (-448, -417, 2, 2), (-416, -385, 3, 3),
            (-384, -353, 0, 1), (-352, -321, 1, 2), (-320, -289, 2, 3), (-288, -257, 3, 3),
            (-256, -225, 0, 2), (-224, -193, 1, 2), (-192, -161, 2, 2), (-160, -129, 3, 1),
            (-128, -97, 0, 1), (-96, -65, 1, 3), (-64, -33, 2, 1), (-32, -1, 3, 2),
            (1, 32, 0, 3), (33, 64, 1, 1), (65, 96, 2, 1), (97, 128, 3, 3),
            (129, 160, 0, 0), (161, 192, 1, 2), (193, 224, 2, 1), (225, 256, 3, 2),
            (257, 288, 0, 3), (289, 320, 1, 2), (321, 352, 2, 3), (353, 384, 3, 0),
            (385, 416, 0, 1), (417, 448, 1, 0), (449, 480, 2, 2), (481, 512, 3, 1),
            (513, 544, 0, 2), (545, 576, 1, 0), (577, 608, 2, 0), (609, 640, 3, 3),
            (641, 672, 0, 0), (673, 704, 1, 1), (705, 736, 2, 3), (737, 768, 1, 1),
        ]

        self.refTable = self._generate_reference_table()

    def _get_h_value(self, i, k):
        """Lookup h value from h-table"""
        k_mod = k % 32
        if i == 0:
            return self.h0[k_mod]
        elif i == 1:
            return self.h1[k_mod]
        elif i == 2:
            return self.h2[k_mod]
        elif i == 3:
            return self.h3[k_mod]
        return 0

    def _get_phi(self, k):
        """Calculate phase for carrier k"""
        for kmin, kmax, i, n in self.modeI_table:
            if kmin <= k <= kmax:
                k_prime = kmin
                h_val = self._get_h_value(i, k - k_prime)
                # Phase = (π/2) × (h + n)
                return np.pi / 2 * (h_val + n)
        return 0

    def _generate_reference_table(self):
        """Generate Phase Reference Symbol (QPSK constellation for Block 0)"""
        refTable = np.zeros(self.T_u, dtype=np.complex128)

        # Fill positive and negative carriers
        for i in range(1, self.carriers // 2 + 1):
            phi_k = self._get_phi(i)
            refTable[i] = np.exp(1j * phi_k)

            phi_k = self._get_phi(-i)
            refTable[self.T_u - i] = np.exp(1j * phi_k)

        return refTable

# ==================== FREQUENCY INTERLEAVER ====================
class FrequencyInterleaver:
    """
    Frequency Interleaver für DAB Mode I
    Mappt logische Carrier-Indices auf physikalische OFDM Subcarrier
    """
    def __init__(self, params):
        self.params = params
        self.T_u = params.T_u
        self.carriers = params.K

        if params.mode == 1:
            self.permTable = self._create_mapper(self.T_u, 511, 256, 256 + 1536)
        else:
            raise NotImplementedError(f"Mode {params.mode} not implemented")

    def _create_mapper(self, T_u, V1, lwb, upb):
        """Generate pseudo-random permutation (DAB Standard 14.6)"""
        tmp = np.zeros(T_u, dtype=np.int32)
        tmp[0] = 0

        # Generate pseudo-random sequence
        for i in range(1, T_u):
            tmp[i] = (13 * tmp[i-1] + V1) % T_u

        # Extract values in range [lwb, upb], skip DC
        permTable = []
        for i in range(T_u):
            if tmp[i] == T_u // 2:  # Skip DC
                continue
            if lwb <= tmp[i] <= upb:
                # Map to [-T_u/2, T_u/2]
                permTable.append(tmp[i] - T_u // 2)

        return np.array(permTable, dtype=np.int32)

    def map_in(self, logical_index):
        """Map logical carrier index to physical subcarrier index"""
        if logical_index < 0 or logical_index >= len(self.permTable):
            return 0
        return self.permTable[logical_index]

# ==================== TIME SYNCHRONIZER ====================
class TimeSynchronizer:
    """
    Detektiert NULL Symbol für Frame-Synchronisation
    Sucht nach Energie-Einbruch (NULL period) gefolgt von Energie-Anstieg
    """
    def __init__(self, params, threshold_low=0.55, threshold_high=0.75):
        self.params = params
        self.T_null = params.T_null
        self.T_F = params.T_F
        self.threshold_low = threshold_low
        self.threshold_high = threshold_high
        self.C_LEVEL_SIZE = 50

    def find_null_symbol(self, samples, signal_level):
        """
        Findet NULL Symbol in IQ samples (optimierte vektorisierte Version)
        Returns: Index des ersten Samples nach NULL period
        """
        if len(samples) < self.T_F:
            return -1

        # Vektorisiert: Magnitude berechnen
        magnitudes = np.abs(samples)

        # Downsampling für schnellere Suche (jeden 4. Sample)
        step = 4
        search_magnitudes = magnitudes[::step]

        # Moving average mit Convolution (schneller als Loop)
        window = np.ones(self.C_LEVEL_SIZE // step) / (self.C_LEVEL_SIZE // step)
        if len(search_magnitudes) < len(window):
            return -1

        avg_levels = np.convolve(search_magnitudes, window, mode='valid')

        # Find NULL period (energy dip)
        null_threshold = self.threshold_low * signal_level
        rise_threshold = self.threshold_high * signal_level

        # Suche NULL start
        null_start_candidates = np.where(avg_levels < null_threshold)[0]
        if len(null_start_candidates) == 0:
            return -1

        null_start_idx = null_start_candidates[0] * step

        # Suche NULL end (ab null_start)
        search_start = null_start_idx + self.C_LEVEL_SIZE
        if search_start >= len(magnitudes):
            return -1

        search_end = min(search_start + self.T_null + 500, len(magnitudes) - self.C_LEVEL_SIZE)
        if search_end <= search_start:
            return -1

        # Moving average für Ende
        for pos in range(search_start, search_end, step):
            avg_level = np.mean(magnitudes[pos:pos + self.C_LEVEL_SIZE])
            if avg_level > rise_threshold:
                return pos

        return -1  # No end of NULL found

# ==================== OFDM DECODER ====================
class OFDMDecoder:
    """
    OFDM Decoder für DAB
    - Verarbeitet Block 0 (Phase Reference Symbol)
    - Dekodiert Data Blocks (DPSK Demodulation)
    - Generiert Konstellationspunkte
    """
    def __init__(self, params, phase_table, interleaver):
        self.params = params
        self.phase_table = phase_table
        self.interleaver = interleaver

        self.T_u = params.T_u
        self.T_g = params.T_g
        self.T_s = params.T_s
        self.carriers = params.K

        # Phase reference storage (from Block 0)
        self.phaseReference = np.zeros(self.T_u, dtype=np.complex128)

        # Statistics for soft bit generation
        self.meanLevel = np.ones(self.T_u) * 0.5
        self.sigmaSQ = np.ones(self.T_u) * 0.5
        self.ALPHA = 0.005  # Running average factor

        # Constellation storage for visualization
        self.constellation_points = []
        self.max_constellation_points = 1536  # One symbol worth

    def process_block_0(self, samples):
        """
        Verarbeitet Block 0 (Phase Reference Symbol)
        samples: T_u complex samples
        """
        if len(samples) < self.T_u:
            return False

        # FFT
        fft_out = np.fft.fft(samples[:self.T_u])

        # Store as phase reference
        self.phaseReference = fft_out.copy()

        return True

    def decode_symbol(self, samples):
        """
        Dekodiert ein OFDM Symbol (T_s samples)
        Returns: (constellation_points, soft_bits)
        """
        if len(samples) < self.T_s:
            return None, None

        # Skip guard interval, take useful part
        useful_samples = samples[self.T_g:self.T_g + self.T_u]

        # FFT to frequency domain
        fft_out = np.fft.fft(useful_samples)

        # Decode carriers
        constellation = []
        soft_bits = []

        for logical_idx in range(self.carriers):
            # Get physical index from interleaver
            phys_idx = self.interleaver.map_in(logical_idx)
            if phys_idx < 0:
                phys_idx += self.T_u

            # Get current symbol and phase reference
            current = fft_out[phys_idx]
            phase_ref = self.phaseReference[phys_idx]

            if np.abs(phase_ref) < 1e-6:
                continue

            # DPSK demodulation: current * conj(phase_ref) / |phase_ref|
            demod = current * np.conj(phase_ref) / np.abs(phase_ref)

            # Store constellation point
            constellation.append(demod)

            # Simple soft bit generation (for constellation diagram)
            # Real part -> I channel, Imag part -> Q channel
            soft_i = -np.real(demod) * 140
            soft_q = -np.imag(demod) * 140

            # Clip to [-127, 127]
            soft_i = np.clip(soft_i, -127, 127)
            soft_q = np.clip(soft_q, -127, 127)

            soft_bits.append(soft_i)
            soft_bits.append(soft_q)

        # Update phase reference for next symbol (differential)
        self.phaseReference = fft_out.copy()

        return np.array(constellation), np.array(soft_bits, dtype=np.int16)

# ==================== DAB RECEIVER ====================
class DABReceiver:
    """
    Haupt-DAB-Empfänger Klasse
    Koordiniert alle Komponenten
    """
    def __init__(self, mode=1):
        self.params = DABParams(mode)
        self.phase_table = PhaseTable(self.params)
        self.interleaver = FrequencyInterleaver(self.params)
        self.time_sync = TimeSynchronizer(self.params)
        self.decoder = OFDMDecoder(self.params, self.phase_table, self.interleaver)

        self.is_synced = False
        self.frame_count = 0

        # Buffer for IQ samples
        self.sample_buffer = np.array([], dtype=np.complex128)
        self.min_buffer_size = self.params.T_F * 1.5  # 1.5 frames worth für schnellere Verarbeitung

    def add_samples(self, samples):
        """Add new IQ samples to buffer"""
        self.sample_buffer = np.concatenate([self.sample_buffer, samples])

        # Keep buffer size manageable (aggressiver für Performance)
        max_buffer = int(self.min_buffer_size * 2)
        if len(self.sample_buffer) > max_buffer:
            self.sample_buffer = self.sample_buffer[-max_buffer:]

    def process_frame(self):
        """
        Verarbeitet einen DAB Frame
        Returns: (success, constellation_points)
        """
        if len(self.sample_buffer) < self.params.T_F:
            return False, None

        # Calculate signal level (for NULL detection)
        signal_level = np.mean(np.abs(self.sample_buffer[:10000]))

        # Find NULL symbol
        null_pos = self.time_sync.find_null_symbol(self.sample_buffer, signal_level)

        if null_pos < 0:
            # No sync, remove some samples and retry
            self.sample_buffer = self.sample_buffer[5000:]
            return False, None

        # Check if we have enough samples after NULL
        if null_pos + self.params.T_F - self.params.T_null > len(self.sample_buffer):
            return False, None

        # Extract frame data (after NULL symbol)
        frame_start = null_pos
        frame_data = self.sample_buffer[frame_start:frame_start + self.params.T_F - self.params.T_null]

        # Process Block 0 (Phase Reference Symbol)
        block0_samples = frame_data[:self.params.T_u]
        if not self.decoder.process_block_0(block0_samples):
            return False, None

        # Process data blocks (1-75)
        all_constellation = []
        pos = self.params.T_u

        # Process first few blocks for constellation diagram (nur 4 für Performance)
        for block_num in range(1, min(5, self.params.L)):  # Process first 4 blocks
            if pos + self.params.T_s > len(frame_data):
                break

            block_samples = frame_data[pos:pos + self.params.T_s]
            pos += self.params.T_s

            constellation, soft_bits = self.decoder.decode_symbol(block_samples)
            if constellation is not None:
                all_constellation.append(constellation)

        # Combine constellation points
        if all_constellation:
            all_constellation = np.concatenate(all_constellation)
        else:
            all_constellation = None

        # Remove processed samples (aggressiver cleanup für Performance)
        self.sample_buffer = self.sample_buffer[frame_start + self.params.T_s * 4:]

        self.is_synced = True
        self.frame_count += 1

        return True, all_constellation

# ==================== GUI MIT CONSTELLATION DIAGRAM ====================
class DABReceiverGUI:
    """GUI für DAB Receiver mit Konstellationsdiagramm"""

    def __init__(self, root):
        self.root = root
        self.root.title("DAB Receiver - Python Implementation")
        self.root.geometry("1400x900")

        # DAB Receiver
        self.receiver = DABReceiver(mode=1)

        # RTL-SDR
        self.sdr = None
        self.is_running = True

        # DAB Channels
        self.dab_channels = {
            '5C': 178.352e6, '5D': 180.064e6, '6A': 181.936e6, '6B': 183.648e6,
            '6C': 185.360e6, '6D': 187.072e6, '7A': 188.928e6, '7B': 190.640e6,
            '7C': 192.352e6, '7D': 194.064e6, '8A': 195.936e6, '8B': 197.648e6,
            '8C': 199.360e6, '8D': 201.072e6, '9A': 202.928e6, '9B': 204.640e6,
            '9C': 206.352e6, '9D': 208.064e6, '10A': 209.936e6, '10B': 211.648e6,
            '10C': 213.360e6, '10D': 215.072e6, '11A': 216.928e6, '11B': 218.640e6,
            '11C': 220.352e6, '11D': 222.064e6, '12A': 223.936e6, '12B': 225.648e6,
            '12C': 227.360e6, '12D': 229.072e6,
        }

        # Raw samples für Spektrum
        self.raw_samples = np.zeros(4096, dtype=np.complex128)
        self.raw_samples_lock = threading.Lock()

        self.setup_gui()
        self.init_rtlsdr()

    def setup_gui(self):
        """Setup GUI elements"""
        # Control frame (left)
        ctrl_frame = ttk.Frame(self.root, padding=10)
        ctrl_frame.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(ctrl_frame, text="DAB Receiver", font=('Arial', 14, 'bold')).pack(pady=10)

        # Frequency control
        ttk.Label(ctrl_frame, text="Frequenz (MHz)", font=('Arial', 12, 'bold')).pack(pady=5)
        self.freq_var = tk.DoubleVar(value=197.648)

        scale = ttk.Scale(ctrl_frame, from_=174.0, to=240.0, orient=tk.VERTICAL,
                         variable=self.freq_var, command=self.change_freq, length=300)
        scale.pack()

        self.freq_label = ttk.Label(ctrl_frame, text="197.648 MHz", font=('Arial', 12))
        self.freq_label.pack(pady=5)

        # Status
        self.status_label = ttk.Label(ctrl_frame, text="Status: Starting...",
                                      font=('Arial', 10), foreground='blue')
        self.status_label.pack(pady=10)

        self.sync_label = ttk.Label(ctrl_frame, text="Sync: No",
                                    font=('Arial', 10), foreground='red')
        self.sync_label.pack(pady=5)

        self.frame_label = ttk.Label(ctrl_frame, text="Frames: 0",
                                     font=('Arial', 10))
        self.frame_label.pack(pady=5)

        # DAB Channel buttons
        ttk.Label(ctrl_frame, text="DAB Kanäle", font=('Arial', 11, 'bold')).pack(pady=10)

        btn_frame = ttk.Frame(ctrl_frame)
        btn_frame.pack(pady=5)

        channels = list(self.dab_channels.keys())
        for i, ch in enumerate(channels):
            row = i // 6
            col = i % 6
            if col == 0:
                row_frame = ttk.Frame(btn_frame)
                row_frame.pack(side=tk.TOP, fill=tk.X, pady=1)
            btn = ttk.Button(row_frame, text=ch, width=5,
                           command=lambda c=ch: self.set_channel(c))
            btn.pack(side=tk.LEFT, padx=2)

        # Info
        info = (f"Mode: I\n"
                f"Sample Rate: 2.048 MSPS\n"
                f"FFT Size: 2048\n"
                f"Carriers: 1536\n"
                f"Frame: {self.receiver.params.T_F} samples")
        ttk.Label(ctrl_frame, text=info, justify=tk.LEFT,
                 font=('Arial', 9), foreground='gray').pack(pady=10)

        # Plot frame (right)
        plot_frame = ttk.Frame(self.root)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create plots
        self.fig, (self.ax_const, self.ax_spec) = plt.subplots(2, 1, figsize=(10, 8),
                                                                gridspec_kw={'height_ratios': [3, 2]})

        self.fig.suptitle('DAB Receiver - Konstellationsdiagramm & Spektrum',
                         fontsize=14, fontweight='bold')

        # Constellation diagram
        self.ax_const.set_xlabel('I (In-Phase)')
        self.ax_const.set_ylabel('Q (Quadrature)')
        self.ax_const.set_title('QPSK Konstellationsdiagramm')
        self.ax_const.grid(True, alpha=0.3)
        self.ax_const.set_xlim(-2, 2)
        self.ax_const.set_ylim(-2, 2)
        self.ax_const.axhline(y=0, color='k', linewidth=0.5)
        self.ax_const.axvline(x=0, color='k', linewidth=0.5)

        # Ideal QPSK points
        ideal_points = np.array([1+1j, -1+1j, -1-1j, 1-1j]) / np.sqrt(2)
        self.ax_const.scatter(ideal_points.real, ideal_points.imag,
                             c='red', s=100, marker='x', linewidths=2,
                             label='Ideal QPSK', zorder=10)
        self.ax_const.legend()

        self.scatter_const = self.ax_const.scatter([], [], alpha=0.3, s=5, c='blue')

        # Spectrum
        self.ax_spec.set_xlabel('Frequenz (MHz)')
        self.ax_spec.set_ylabel('Leistung (dB)')
        self.ax_spec.set_title('Spektrum')
        self.ax_spec.grid(True, alpha=0.3)
        self.line_spec, = self.ax_spec.plot([], [], 'b-', linewidth=1)

        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def init_rtlsdr(self):
        """Initialize RTL-SDR"""
        try:
            self.sdr = RtlSdr()
            time.sleep(0.1)

            self.sdr.sample_rate = 2.048e6
            time.sleep(0.05)

            self.sdr.center_freq = 197.648e6
            time.sleep(0.05)

            self.sdr.gain = 28
            time.sleep(0.05)

            self.status_label.config(text="Status: RTL-SDR OK", foreground='green')
        except Exception as e:
            self.status_label.config(text=f"Status: SDR Error: {e}", foreground='red')

    def change_freq(self, val=None):
        """Change frequency"""
        freq_mhz = float(self.freq_var.get())
        freq_hz = freq_mhz * 1e6
        self.freq_label.config(text=f"{freq_mhz:.3f} MHz")
        if self.sdr:
            self.sdr.center_freq = freq_hz
            time.sleep(0.05)

    def set_channel(self, channel):
        """Set DAB channel"""
        freq_hz = self.dab_channels[channel]
        freq_mhz = freq_hz / 1e6
        self.freq_var.set(freq_mhz)
        self.change_freq()
        self.receiver.is_synced = False
        self.receiver.frame_count = 0

    def receive_and_process(self):
        """Receive and process samples (separate thread)"""
        buffer_size = 65536  # Größerer Buffer für besseren Durchsatz

        while self.is_running:
            try:
                if self.sdr:
                    # Read samples
                    samples = self.sdr.read_samples(buffer_size)
                    samples = samples.astype(np.complex128)

                    # Speichere letzte Samples für Spektrum
                    with self.raw_samples_lock:
                        self.raw_samples = samples[:4096].copy()

                    # Add to receiver buffer
                    self.receiver.add_samples(samples)

                    # Try to process frame
                    success, constellation = self.receiver.process_frame()

                    if success:
                        self.update_constellation(constellation)
                        self.update_status()

                time.sleep(0.001)  # Minimal sleep für besseren Durchsatz
            except Exception as e:
                print(f"Receive error: {e}")
                time.sleep(0.1)

    def update_constellation(self, constellation):
        """Update constellation diagram"""
        if constellation is not None and len(constellation) > 0:
            # Normalize to unit circle approximately
            const_normalized = constellation / np.mean(np.abs(constellation))

            # Update scatter plot
            self.scatter_const.set_offsets(
                np.c_[const_normalized.real, const_normalized.imag]
            )

    def update_status(self):
        """Update status labels"""
        if self.receiver.is_synced:
            self.sync_label.config(text="Sync: YES", foreground='green')
        else:
            self.sync_label.config(text="Sync: NO", foreground='red')

        self.frame_label.config(text=f"Frames: {self.receiver.frame_count}")

    def update_plots(self):
        """Update plots periodically"""
        if not self.is_running:
            return

        # Update Spektrum
        try:
            with self.raw_samples_lock:
                samples = self.raw_samples.copy()

            if len(samples) > 0:
                # FFT für Spektrum
                window = np.hanning(len(samples))
                windowed = samples * window
                fft_data = np.fft.fftshift(np.fft.fft(windowed))
                power = np.abs(fft_data) ** 2
                power_db = 10 * np.log10(power + 1e-12)

                # Frequenz-Achse
                freqs = np.fft.fftshift(np.fft.fftfreq(len(samples), 1/2.048e6))
                freq_mhz = self.freq_var.get() + freqs / 1e6

                # Update Spektrum-Plot
                self.line_spec.set_data(freq_mhz, power_db)
                self.ax_spec.relim()
                self.ax_spec.autoscale_view()

            # Redraw canvas
            self.canvas.draw_idle()
        except Exception as e:
            pass

        # Schedule next update
        self.root.after(200, self.update_plots)

    def cleanup(self):
        """Cleanup on exit"""
        self.is_running = False
        time.sleep(0.3)
        if self.sdr:
            self.sdr.close()
        self.root.quit()
        self.root.destroy()

# ==================== MAIN ====================
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = DABReceiverGUI(root)

        # Start receiver thread
        rx_thread = threading.Thread(target=app.receive_and_process, daemon=True)
        rx_thread.start()

        # Start plot update
        app.update_plots()

        # Run GUI
        root.protocol("WM_DELETE_WINDOW", app.cleanup)
        root.mainloop()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
