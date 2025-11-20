#!/usr/bin/env python3
"""
Constellation Diagram Display
Equivalent to iqdisplay.cpp and display-widget.cpp

Visualizes IQ constellation points using matplotlib
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle
from typing import Optional, List
import threading
import queue


class ConstellationDisplay:
    """
    Constellation diagram display using matplotlib
    Equivalent to IQDisplay class in qt-dab
    """

    def __init__(self, figsize=(8, 8), max_points=2048):
        """
        Initialize constellation display

        Args:
            figsize: Figure size (width, height)
            max_points: Maximum points to display
        """
        self.max_points = max_points
        self.figsize = figsize

        # Display mode
        self.mode_log_magnitude = True  # True: log-mag, False: raw
        self.ncp_mode = False  # Nearest Center Point mode

        # Data queue for thread-safe updates
        self.data_queue = queue.Queue(maxsize=10)

        # Statistics
        self.frame_count = 0
        self.snr_estimate = 0.0

        print("Constellation Display initialized")

    def _setup_plot(self):
        """Setup matplotlib figure and axes"""
        self.fig, self.ax = plt.subplots(figsize=self.figsize)
        self.ax.set_xlim(-1.5, 1.5)
        self.ax.set_ylim(-1.5, 1.5)
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlabel('In-Phase (I)', fontsize=12)
        self.ax.set_ylabel('Quadrature (Q)', fontsize=12)
        self.ax.set_title('DAB Constellation Diagram', fontsize=14, fontweight='bold')

        # Crosshair at origin
        self.ax.axhline(0, color='red', linewidth=0.5, alpha=0.5)
        self.ax.axvline(0, color='red', linewidth=0.5, alpha=0.5)

        # Reference circle
        circle = Circle((0, 0), 1.0, fill=False, color='blue', linewidth=1, alpha=0.3)
        self.ax.add_patch(circle)

        # Ideal QPSK constellation points
        ideal_points = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)
        self.ax.scatter(ideal_points.real, ideal_points.imag,
                        c='green', marker='x', s=100, linewidths=2,
                        label='Ideal QPSK', zorder=10)

        # Scatter plot for constellation points
        self.scatter = self.ax.scatter([], [], c='yellow', alpha=0.6, s=20, edgecolors='orange', linewidths=0.5)

        # Text for statistics
        self.stats_text = self.ax.text(0.02, 0.98, '', transform=self.ax.transAxes,
                                        verticalalignment='top', fontsize=10,
                                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        self.ax.legend(loc='upper right')

        plt.tight_layout()

    def _transform_log_magnitude(self, constellation: np.ndarray) -> np.ndarray:
        """
        Transform to log-magnitude/phase representation
        Equivalent to displayWidget::showIQ() in display-widget.cpp:432-453

        Args:
            constellation: Raw constellation points

        Returns:
            Transformed constellation
        """
        # Calculate phase (angle) and magnitude
        phi = np.angle(constellation)
        mag = np.abs(constellation)

        # Log magnitude scaling (same formula as qt-dab)
        log_norm = np.log10(2.0)
        amp = np.log10(1.0 + mag) / log_norm

        # Reconstruct in polar form
        transformed = amp * np.exp(1j * phi)

        return transformed

    def _extract_center_points(self, constellation: np.ndarray) -> np.ndarray:
        """
        Extract 4 quadrant center points (NCP mode)
        Equivalent to IQDisplay::extract_centerPoints() in iqdisplay.cpp:217-248

        Args:
            constellation: Raw constellation points

        Returns:
            4 center points (one per quadrant)
        """
        centers = []
        quadrants = [
            (constellation.real > 0) & (constellation.imag > 0),  # Q1: (+, +)
            (constellation.real > 0) & (constellation.imag < 0),  # Q4: (+, -)
            (constellation.real < 0) & (constellation.imag > 0),  # Q2: (-, +)
            (constellation.real < 0) & (constellation.imag < 0),  # Q3: (-, -)
        ]

        for quadrant_mask in quadrants:
            points_in_quadrant = constellation[quadrant_mask]
            if len(points_in_quadrant) > 0:
                center = np.mean(points_in_quadrant)
                centers.append(center)
            else:
                centers.append(0 + 0j)

        return np.array(centers)

    def _calculate_snr_estimate(self, constellation: np.ndarray) -> float:
        """
        Estimate SNR from constellation clustering

        Args:
            constellation: Constellation points

        Returns:
            SNR estimate in dB
        """
        # Expected QPSK points
        ideal_qpsk = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)

        # Calculate distance to nearest ideal point
        errors = []
        for point in constellation:
            distances = np.abs(point - ideal_qpsk)
            min_dist = np.min(distances)
            errors.append(min_dist)

        if len(errors) == 0:
            return 0.0

        # Signal power (ideal constellation)
        signal_power = 1.0

        # Noise power (mean squared error)
        noise_power = np.mean(np.array(errors) ** 2)

        if noise_power > 1e-10:
            snr_linear = signal_power / noise_power
            snr_db = 10 * np.log10(snr_linear)
            return snr_db
        else:
            return 50.0  # Very high SNR

    def update_constellation(self, constellation: np.ndarray):
        """
        Update constellation display with new data

        Args:
            constellation: Complex array of constellation points
        """
        if len(constellation) == 0:
            return

        # Limit number of points
        if len(constellation) > self.max_points:
            # Downsample
            indices = np.random.choice(len(constellation), self.max_points, replace=False)
            constellation = constellation[indices]

        # Apply transformation based on mode
        if self.ncp_mode:
            display_data = self._extract_center_points(constellation)
        elif self.mode_log_magnitude:
            display_data = self._transform_log_magnitude(constellation)
        else:
            display_data = constellation

        # Calculate SNR
        self.snr_estimate = self._calculate_snr_estimate(constellation)
        self.frame_count += 1

        # Put data in queue
        try:
            self.data_queue.put_nowait({
                'constellation': display_data,
                'snr': self.snr_estimate,
                'frame_count': self.frame_count,
                'num_points': len(constellation)
            })
        except queue.Full:
            # Drop frame if queue is full
            pass

    def _animation_update(self, frame):
        """Animation update callback"""
        try:
            # Get latest data (non-blocking)
            data = self.data_queue.get_nowait()

            constellation = data['constellation']
            snr = data['snr']
            frame_count = data['frame_count']
            num_points = data['num_points']

            # Update scatter plot
            self.scatter.set_offsets(np.c_[constellation.real, constellation.imag])

            # Update statistics text
            stats_str = f"Frame: {frame_count}\n"
            stats_str += f"Points: {num_points}\n"
            stats_str += f"SNR: {snr:.1f} dB\n"
            stats_str += f"Mode: {'NCP' if self.ncp_mode else 'Log-Mag' if self.mode_log_magnitude else 'Raw'}"
            self.stats_text.set_text(stats_str)

        except queue.Empty:
            # No new data, keep current display
            pass

        return self.scatter, self.stats_text

    def show(self, interval=100):
        """
        Show constellation display with animation

        Args:
            interval: Update interval in milliseconds
        """
        self._setup_plot()

        # Create animation
        self.animation = FuncAnimation(self.fig, self._animation_update,
                                        interval=interval, blit=True, cache_frame_data=False)

        plt.show()

    def toggle_log_magnitude(self):
        """Toggle log-magnitude mode"""
        self.mode_log_magnitude = not self.mode_log_magnitude
        print(f"Log-magnitude mode: {'ON' if self.mode_log_magnitude else 'OFF'}")

    def toggle_ncp_mode(self):
        """Toggle NCP (Nearest Center Point) mode"""
        self.ncp_mode = not self.ncp_mode
        print(f"NCP mode: {'ON' if self.ncp_mode else 'OFF'}")


class ConstellationPlotter:
    """
    Simple static constellation plotter (non-animated)
    """

    @staticmethod
    def plot(constellation: np.ndarray, title: str = "Constellation Diagram",
             figsize=(8, 8), show_ideal=True):
        """
        Create static constellation plot

        Args:
            constellation: Complex constellation points
            title: Plot title
            figsize: Figure size
            show_ideal: Show ideal QPSK points
        """
        fig, ax = plt.subplots(figsize=figsize)

        # Extract I and Q
        I = constellation.real
        Q = constellation.imag

        # Plot constellation points
        ax.scatter(I, Q, c='yellow', alpha=0.6, s=20, edgecolors='orange', linewidths=0.5, label='Received')

        # Ideal QPSK points
        if show_ideal:
            ideal_points = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)
            ax.scatter(ideal_points.real, ideal_points.imag,
                       c='green', marker='x', s=200, linewidths=3,
                       label='Ideal QPSK', zorder=10)

        # Formatting
        max_val = max(np.max(np.abs(I)), np.max(np.abs(Q)), 1.5)
        ax.set_xlim(-max_val, max_val)
        ax.set_ylim(-max_val, max_val)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='red', linewidth=0.5, alpha=0.5)
        ax.axvline(0, color='red', linewidth=0.5, alpha=0.5)
        ax.set_xlabel('In-Phase (I)', fontsize=12)
        ax.set_ylabel('Quadrature (Q)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')

        # Reference circle
        circle = Circle((0, 0), 1.0, fill=False, color='blue', linewidth=1, alpha=0.3)
        ax.add_patch(circle)

        ax.legend()
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    # Test constellation display with synthetic data
    print("Constellation Display Test")
    print("-" * 50)

    # Generate synthetic QPSK constellation with noise
    np.random.seed(42)

    # Ideal QPSK points
    ideal_qpsk = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)

    # Generate random QPSK symbols
    num_symbols = 1000
    symbols = np.random.choice(ideal_qpsk, size=num_symbols)

    # Add AWGN noise
    noise_std = 0.2
    noise = noise_std * (np.random.randn(num_symbols) + 1j * np.random.randn(num_symbols))
    noisy_constellation = symbols + noise

    print(f"Generated {num_symbols} QPSK symbols with noise (σ={noise_std})")

    # Static plot
    print("\nShowing static plot...")
    ConstellationPlotter.plot(noisy_constellation, title="Test QPSK Constellation")
