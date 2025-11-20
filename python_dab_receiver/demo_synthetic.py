#!/usr/bin/env python3
"""
Demo: Synthetic DAB Signal
Test OFDM processing and constellation display WITHOUT RTL-SDR hardware

This script generates synthetic QPSK OFDM signals to demonstrate
the signal processing chain without requiring actual DAB reception.
"""

import numpy as np
import matplotlib.pyplot as plt
from ofdm_processor import OFDMProcessor, DABParams
from constellation_display import ConstellationDisplay, ConstellationPlotter
import time
import threading


def generate_synthetic_ofdm_symbol(params: DABParams, snr_db: float = 20.0) -> np.ndarray:
    """
    Generate synthetic OFDM symbol with QPSK constellation

    Args:
        params: DAB parameters
        snr_db: Signal-to-noise ratio in dB

    Returns:
        Complete OFDM symbol (guard + useful)
    """
    # QPSK constellation points
    qpsk_alphabet = np.array([
        1 + 1j,   # 00
        1 - 1j,   # 01
        -1 + 1j,  # 10
        -1 - 1j   # 11
    ]) / np.sqrt(2)  # Normalize to unit power

    # Create frequency domain signal
    freq_domain = np.zeros(params.T_u, dtype=np.complex64)

    # Get carrier indices
    half_carriers = params.carriers // 2
    carrier_indices = []

    # Negative frequencies
    for i in range(-half_carriers, 0):
        carrier_indices.append(i)

    # Positive frequencies (skip DC)
    for i in range(1, half_carriers + 1):
        carrier_indices.append(i)

    # Map to FFT indices
    for carrier in carrier_indices:
        fft_index = carrier if carrier >= 0 else carrier + params.T_u

        # Random QPSK symbol
        symbol = np.random.choice(qpsk_alphabet)
        freq_domain[fft_index] = symbol

    # IFFT to get time domain
    time_domain = np.fft.ifft(freq_domain)

    # Add cyclic prefix (guard interval)
    guard = time_domain[-params.T_g:]
    symbol_with_guard = np.concatenate([guard, time_domain])

    # Add AWGN noise
    signal_power = np.mean(np.abs(symbol_with_guard) ** 2)
    snr_linear = 10 ** (snr_db / 10)
    noise_power = signal_power / snr_linear
    noise_std = np.sqrt(noise_power / 2)  # Complex noise

    noise = noise_std * (np.random.randn(len(symbol_with_guard)) +
                         1j * np.random.randn(len(symbol_with_guard)))

    noisy_symbol = symbol_with_guard + noise

    return noisy_symbol


def demo_single_symbol():
    """Demo: Process single synthetic symbol"""
    print("=" * 60)
    print("DEMO 1: Single Symbol Processing")
    print("=" * 60)

    params = DABParams()
    processor = OFDMProcessor()

    # Generate two symbols (first for phase ref, second for constellation)
    print("\nGenerating synthetic OFDM symbols...")

    symbol1 = generate_synthetic_ofdm_symbol(params, snr_db=20)
    symbol2 = generate_synthetic_ofdm_symbol(params, snr_db=20)

    print(f"Symbol length: {len(symbol1)} samples")
    print(f"SNR: 20 dB")

    # Process first symbol (initializes phase reference)
    print("\nProcessing first symbol (phase reference initialization)...")
    constellation1 = processor.process_samples(symbol1)
    print(f"Result: {constellation1}")

    # Process second symbol (extracts constellation)
    print("\nProcessing second symbol (constellation extraction)...")
    constellation2 = processor.process_samples(symbol2)
    print(f"Constellation points: {len(constellation2) if constellation2 is not None else 0}")

    if constellation2 is not None and len(constellation2) > 0:
        print(f"I range: [{np.min(constellation2.real):.3f}, {np.max(constellation2.real):.3f}]")
        print(f"Q range: [{np.min(constellation2.imag):.3f}, {np.max(constellation2.imag):.3f}]")

        # Plot
        print("\nShowing constellation diagram...")
        ConstellationPlotter.plot(
            constellation2,
            title=f"Synthetic QPSK Constellation (SNR=20dB, {len(constellation2)} points)"
        )
    else:
        print("ERROR: No constellation extracted!")


def demo_multiple_snr():
    """Demo: Show constellations at different SNR levels"""
    print("\n" + "=" * 60)
    print("DEMO 2: Constellation at Different SNR Levels")
    print("=" * 60)

    params = DABParams()
    snr_levels = [5, 10, 15, 20, 25, 30]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()

    for idx, snr_db in enumerate(snr_levels):
        print(f"\nGenerating constellation for SNR = {snr_db} dB...")

        processor = OFDMProcessor()

        # Generate and process symbols
        symbol1 = generate_synthetic_ofdm_symbol(params, snr_db=snr_db)
        symbol2 = generate_synthetic_ofdm_symbol(params, snr_db=snr_db)

        processor.process_samples(symbol1)  # Phase ref
        constellation = processor.process_samples(symbol2)  # Constellation

        if constellation is not None and len(constellation) > 0:
            ax = axes[idx]

            # Plot constellation
            I = constellation.real
            Q = constellation.imag

            ax.scatter(I, Q, c='yellow', alpha=0.6, s=10, edgecolors='orange', linewidths=0.5)

            # Ideal QPSK
            ideal = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)
            ax.scatter(ideal.real, ideal.imag, c='green', marker='x', s=100, linewidths=2)

            # Formatting
            ax.set_xlim(-1.5, 1.5)
            ax.set_ylim(-1.5, 1.5)
            ax.set_aspect('equal')
            ax.grid(True, alpha=0.3)
            ax.axhline(0, color='red', linewidth=0.5, alpha=0.5)
            ax.axvline(0, color='red', linewidth=0.5, alpha=0.5)
            ax.set_title(f'SNR = {snr_db} dB', fontweight='bold')
            ax.set_xlabel('I')
            ax.set_ylabel('Q')

    plt.suptitle('QPSK Constellation at Different SNR Levels', fontsize=16, fontweight='bold')
    plt.tight_layout()
    print("\nShowing plot...")
    plt.show()


def demo_animated_live():
    """Demo: Animated live constellation (simulated)"""
    print("\n" + "=" * 60)
    print("DEMO 3: Animated Live Constellation (Simulated)")
    print("=" * 60)
    print("\nGenerating synthetic symbols continuously...")
    print("Close window to stop.")

    params = DABParams()
    processor = OFDMProcessor()
    display = ConstellationDisplay(figsize=(10, 10), max_points=1536)

    # Initialize phase reference
    init_symbol = generate_synthetic_ofdm_symbol(params, snr_db=20)
    processor.process_samples(init_symbol)

    # State for animation
    running = [True]
    frame_count = [0]

    def generate_symbols():
        """Generate symbols in background thread"""
        # Simulate varying SNR
        base_snr = 20
        snr_variation = 5

        while running[0]:
            # Vary SNR over time
            t = frame_count[0] * 0.1
            snr = base_snr + snr_variation * np.sin(t)

            # Generate symbol
            symbol = generate_synthetic_ofdm_symbol(params, snr_db=snr)

            # Process
            constellation = processor.process_samples(symbol)

            if constellation is not None and len(constellation) > 0:
                display.update_constellation(constellation)
                frame_count[0] += 1

            time.sleep(0.1)  # ~10 Hz update rate

    # Start generation thread
    gen_thread = threading.Thread(target=generate_symbols, daemon=True)
    gen_thread.start()

    # Show display (blocks)
    try:
        display.show(interval=100)
    except KeyboardInterrupt:
        pass
    finally:
        running[0] = False
        print("\nStopped")


def main():
    """Main demo menu"""
    print("\n" + "=" * 60)
    print("DAB OFDM CONSTELLATION DEMO (Synthetic Signals)")
    print("=" * 60)
    print("\nThis demo generates synthetic QPSK OFDM signals")
    print("No RTL-SDR hardware required!")
    print("\nSelect demo:")
    print("  1) Single symbol processing")
    print("  2) Multiple SNR comparison")
    print("  3) Animated live constellation")
    print("  4) All demos")
    print("=" * 60)

    choice = input("\nEnter choice [1-4]: ").strip()

    if choice == '1':
        demo_single_symbol()
    elif choice == '2':
        demo_multiple_snr()
    elif choice == '3':
        demo_animated_live()
    elif choice == '4':
        demo_single_symbol()
        demo_multiple_snr()
        demo_animated_live()
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    main()
