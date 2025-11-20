#!/usr/bin/env python3
"""
DAB FIC (Fast Information Channel) Decoder
Dekodiert Service-Informationen aus FIC Blocks
"""

import numpy as np
from typing import List, Dict, Tuple, Optional

# ==================== CONSTANTS ====================
FIC_BLOCKSIZE = 3072    # Motherword size after depuncturing
FIC_RESIDU = 24         # Tail bits
FIC_INPUT = 2304        # Input soft bits per FIC block
FIB_SIZE = 256          # Bits per FIB
FIBS_PER_CIF = 3        # 3 FIBs per CIF

# Viterbi parameters
VITERBI_K = 7           # Constraint length
VITERBI_RATE = 4        # Code rate 1/4
VITERBI_STATES = 64     # 2^(K-1)

# ==================== PRBS FOR ENERGY DISPERSAL ====================
def generate_prbs(length=768):
    """Generate PRBS sequence for energy dispersal (x^9 + x^5 + 1)"""
    shift_register = [1] * 9
    prbs = np.zeros(length, dtype=np.uint8)

    for i in range(length):
        prbs[i] = shift_register[8] ^ shift_register[4]
        # Shift
        for j in range(8, 0, -1):
            shift_register[j] = shift_register[j-1]
        shift_register[0] = prbs[i]

    return prbs

PRBS = generate_prbs(768)

# ==================== CRC-16 ====================
def crc16_check(bits):
    """
    Check CRC-16 for FIB (256 bits including 16-bit CRC)
    Polynomial: x^16 + x^12 + x^5 + 1
    """
    if len(bits) != 256:
        return False

    # Generator polynomial (MSB first)
    # x^16 + x^12 + x^5 + 1 = 0x1021
    poly = 0x1021

    # Convert bits to bytes
    data = np.packbits(bits[:240])  # 30 bytes data
    crc_received = int(np.packbits(bits[240:256])[0]) << 8 | int(np.packbits(bits[240:256])[1])

    # Calculate CRC
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc = crc << 1
            crc &= 0xFFFF

    # Invert result
    crc ^= 0xFFFF

    return crc == crc_received

# ==================== SIMPLIFIED VITERBI DECODER ====================
class SimplifiedViterbiDecoder:
    """
    Vereinfachter Viterbi Decoder für DAB FIC
    K=7, Rate=1/4, Polynomials: [0o155, 0o117, 0o123, 0o155]

    HINWEIS: Dies ist eine vereinfachte Implementation!
    Für Produktion sollte eine optimierte Viterbi-Library verwendet werden.
    """

    def __init__(self):
        self.K = 7
        self.rate = 4
        self.num_states = 2 ** (self.K - 1)  # 64 states

        # Generator polynomials (octal)
        self.polys = [0o155, 0o117, 0o123, 0o155]

        # Pre-compute branch table
        self.branch_table = self._build_branch_table()

    def _build_branch_table(self):
        """Build branch metric lookup table"""
        table = np.zeros((self.num_states, 2, self.rate), dtype=np.uint8)

        for state in range(self.num_states):
            for input_bit in [0, 1]:
                # New state after input bit
                new_state = ((state << 1) | input_bit) & (self.num_states - 1)

                # Calculate output for each polynomial
                for i, poly in enumerate(self.polys):
                    # Count 1s in (state | input_bit) & polynomial
                    val = ((state << 1) | input_bit) & poly
                    output_bit = bin(val).count('1') % 2
                    table[state, input_bit, i] = output_bit

        return table

    def decode(self, soft_bits, output_length):
        """
        Simplified Viterbi decoding

        Args:
            soft_bits: Array of soft bits (0-255, where 128=uncertain)
            output_length: Number of output bits (768 for FIC)

        Returns:
            Decoded hard bits (0/1)
        """
        # This is a PLACEHOLDER implementation
        # Real Viterbi would use:
        # - Path metrics (ACS operations)
        # - Traceback
        # - Branch metrics

        # For demonstration: use hard decision
        # TODO: Implement proper Viterbi with ACS and traceback

        # Depunctured soft bits come in groups of 4 (rate 1/4)
        output_bits = np.zeros(output_length, dtype=np.uint8)

        for i in range(output_length):
            # Take majority vote from 4 symbols
            idx = i * self.rate
            if idx + self.rate <= len(soft_bits):
                symbols = soft_bits[idx:idx + self.rate]
                # Hard decision: 128 = threshold
                hard_symbols = (symbols > 128).astype(int)
                # Majority vote
                output_bits[i] = 1 if np.sum(hard_symbols) >= 2 else 0

        return output_bits

# ==================== DEPUNCTURING ====================
class Depuncturer:
    """Depuncturing for FIC (PI_16, PI_15, PI_X patterns)"""

    def __init__(self):
        self.puncture_table = self._build_puncture_table()

    def _build_puncture_table(self):
        """Build puncture table for FIC"""
        table = []

        # PI_16 pattern (21 blocks of 128 bits each)
        # Pattern: [1,1,1,0] repeated (rate 3/4)
        pi_16 = [1, 1, 1, 0] * 32  # 128 bits
        for _ in range(21):
            table.extend(pi_16)

        # PI_15 pattern (3 blocks of 128 bits)
        pi_15 = [1, 1, 1, 0] * 32
        for _ in range(3):
            table.extend(pi_15)

        # PI_X pattern (24 tail bits)
        pi_x = [1, 1, 0, 0, 1, 0, 0, 0] * 3
        table.extend(pi_x)

        return np.array(table[:FIC_BLOCKSIZE + FIC_RESIDU], dtype=np.uint8)

    def depuncture(self, soft_bits):
        """
        Depuncture soft bits

        Args:
            soft_bits: 2304 soft bits

        Returns:
            3096 depunctured soft bits (zeros inserted)
        """
        if len(soft_bits) != FIC_INPUT:
            raise ValueError(f"Expected {FIC_INPUT} soft bits, got {len(soft_bits)}")

        output = np.zeros(FIC_BLOCKSIZE + FIC_RESIDU, dtype=np.int16)
        input_idx = 0

        for i in range(len(self.puncture_table)):
            if self.puncture_table[i] == 1:
                if input_idx < len(soft_bits):
                    output[i] = soft_bits[input_idx]
                    input_idx += 1
            else:
                output[i] = 0  # Insert zero for punctured bit

        return output

# ==================== FIC HANDLER ====================
class FICHandler:
    """Handles FIC block processing and decoding"""

    def __init__(self):
        self.depuncturer = Depuncturer()
        self.viterbi = SimplifiedViterbiDecoder()
        self.fic_input = np.zeros(FIC_INPUT, dtype=np.int16)
        self.index = 0
        self.ficno = 0

        # Storage for decoded FIBs
        self.fibs = []

    def process_fic_block(self, soft_bits, block_no):
        """
        Process one FIC block (blocks 1, 2, or 3)

        Args:
            soft_bits: Array of soft bits (1536 × 2 = 3072 bits)
            block_no: Block number (1, 2, or 3)

        Returns:
            List of valid FIBs (256 bits each)
        """
        if block_no == 1:
            self.index = 0
            self.ficno = 0
            self.fibs = []

        # Collect soft bits
        bits_per_block = len(soft_bits)

        for i in range(min(bits_per_block, FIC_INPUT - self.index)):
            self.fic_input[self.index] = soft_bits[i]
            self.index += 1

            # Process when we have 2304 bits
            if self.index >= FIC_INPUT:
                fib_list = self._process_fic_input()
                self.fibs.extend(fib_list)
                self.index = 0
                self.ficno += 1

        return self.fibs

    def _process_fic_input(self):
        """
        Process 2304 soft bits -> 3 FIBs (768 bits total)

        Returns:
            List of valid FIBs
        """
        # 1. Depuncture: 2304 -> 3096 bits
        depunctured = self.depuncturer.depuncture(self.fic_input)

        # 2. Map soft bits from [-127, 127] to [0, 255]
        mapped = np.clip(depunctured + 127, 0, 255).astype(np.uint8)

        # 3. Viterbi decode: 3096 -> 768 bits
        hard_bits = self.viterbi.decode(mapped, 768)

        # 4. Energy dispersal (XOR with PRBS)
        hard_bits ^= PRBS

        # 5. Split into 3 FIBs and check CRC
        valid_fibs = []
        for i in range(3):
            fib = hard_bits[i * FIB_SIZE:(i + 1) * FIB_SIZE]
            if crc16_check(fib):
                valid_fibs.append(fib)

        return valid_fibs

# ==================== FIG PARSER ====================
def get_bits(data, start, length):
    """Extract bits from bit array"""
    return int(''.join(str(int(b)) for b in data[start:start+length]), 2)

class FIGParser:
    """Parse FIGs (Fast Information Groups) from FIBs"""

    def __init__(self):
        self.ensemble_id = None
        self.ensemble_name = ""
        self.subchannels = {}  # subChId -> subchannel info
        self.services = {}     # SId -> service info

    def parse_fib(self, fib):
        """
        Parse one FIB (256 bits = 32 bytes)
        First 30 bytes: FIG data
        Last 2 bytes: CRC
        """
        processed_bytes = 0
        bit_offset = 0

        while processed_bytes < 30:
            # FIG header
            if bit_offset + 8 > 240:  # Only 30 bytes available
                break

            fig_type = get_bits(fib, bit_offset, 3)
            fig_length = get_bits(fib, bit_offset + 3, 5)

            # End marker
            if fig_type == 0x07 and fig_length == 0x1F:
                break

            # Process FIG
            fig_data_start = bit_offset + 8
            fig_data_end = fig_data_start + fig_length * 8

            if fig_data_end > 240:
                break

            fig_data = fib[fig_data_start:fig_data_end]

            if fig_type == 0:
                self._parse_fig0(fig_data)
            elif fig_type == 1:
                self._parse_fig1(fig_data)

            processed_bytes += fig_length + 1
            bit_offset = processed_bytes * 8

    def _parse_fig0(self, data):
        """Parse FIG type 0 (MCI - Multiplex Configuration Info)"""
        if len(data) < 8:
            return

        extension = get_bits(data, 0, 5)

        if extension == 0:
            self._parse_fig0_ext0(data)  # Ensemble info
        elif extension == 1:
            self._parse_fig0_ext1(data)  # Sub-channel organization
        elif extension == 2:
            self._parse_fig0_ext2(data)  # Service organization

    def _parse_fig0_ext0(self, data):
        """FIG 0/0: Ensemble information"""
        if len(data) < 32:
            return

        self.ensemble_id = get_bits(data, 8, 16)

    def _parse_fig0_ext1(self, data):
        """FIG 0/1: Sub-channel organization"""
        bit_offset = 8

        while bit_offset + 24 <= len(data):
            subch_id = get_bits(data, bit_offset, 6)
            start_addr = get_bits(data, bit_offset + 6, 10)

            # Short/Long form flag
            is_long_form = get_bits(data, bit_offset + 16, 1)

            if is_long_form == 0:  # Short form (UEP)
                table_index = get_bits(data, bit_offset + 18, 6)
                # UEP protection levels (simplified)
                bit_offset += 24
            else:  # Long form (EEP)
                option = get_bits(data, bit_offset + 17, 3)
                prot_level = get_bits(data, bit_offset + 20, 2)
                subchannel_size = get_bits(data, bit_offset + 22, 10)
                bit_offset += 32

                # Calculate bit rate (simplified)
                if option == 0:  # EEP-A
                    bit_rate = subchannel_size * 8 // (12 * (prot_level + 1))
                else:  # EEP-B
                    bit_rate = subchannel_size * 32 // (27 - 3 * prot_level)

                self.subchannels[subch_id] = {
                    'start_addr': start_addr,
                    'size': subchannel_size,
                    'bit_rate': bit_rate,
                    'prot_level': prot_level
                }

    def _parse_fig0_ext2(self, data):
        """FIG 0/2: Service organization (link SId to subchannel)"""
        bit_offset = 8

        while bit_offset + 32 <= len(data):
            sid = get_bits(data, bit_offset, 16)
            num_components = get_bits(data, bit_offset + 20, 4)

            bit_offset += 24

            for _ in range(num_components):
                if bit_offset + 16 > len(data):
                    break

                tmid = get_bits(data, bit_offset, 2)

                if tmid == 0:  # Audio
                    ascty = get_bits(data, bit_offset + 2, 6)
                    subch_id = get_bits(data, bit_offset + 8, 6)
                    ps_flag = get_bits(data, bit_offset + 14, 1)

                    if sid not in self.services:
                        self.services[sid] = {
                            'name': f"Service {sid:04X}",
                            'subch_id': subch_id,
                            'audio_type': ascty
                        }
                    else:
                        self.services[sid]['subch_id'] = subch_id

                    bit_offset += 16
                else:
                    bit_offset += 16

    def _parse_fig1(self, data):
        """Parse FIG type 1 (Labels)"""
        if len(data) < 8:
            return

        extension = get_bits(data, 0, 3)

        if extension == 0:
            self._parse_fig1_ext0(data)  # Ensemble label
        elif extension == 1:
            self._parse_fig1_ext1(data)  # Service label

    def _parse_fig1_ext0(self, data):
        """FIG 1/0: Ensemble label"""
        if len(data) < 24 + 16 * 8:
            return

        charset = get_bits(data, 8, 4)
        eid = get_bits(data, 16, 16)

        # Extract label (16 characters = 128 bits)
        label = ""
        for i in range(16):
            char_byte = get_bits(data, 32 + i * 8, 8)
            if char_byte >= 32 and char_byte < 127:
                label += chr(char_byte)
            else:
                label += " "

        self.ensemble_name = label.strip()

    def _parse_fig1_ext1(self, data):
        """FIG 1/1: Service label (station name)"""
        if len(data) < 24 + 16 * 8:
            return

        charset = get_bits(data, 8, 4)
        sid = get_bits(data, 16, 16)

        # Extract label (16 characters)
        label = ""
        for i in range(16):
            char_byte = get_bits(data, 32 + i * 8, 8)
            if char_byte >= 32 and char_byte < 127:
                label += chr(char_byte)
            else:
                label += " "

        label = label.strip()

        if sid in self.services:
            self.services[sid]['name'] = label
        else:
            self.services[sid] = {'name': label}

    def get_service_list(self):
        """Get list of services with names"""
        services = []
        for sid, info in self.services.items():
            service = {
                'sid': sid,
                'name': info.get('name', f"Service {sid:04X}"),
                'subch_id': info.get('subch_id', None),
                'audio_type': info.get('audio_type', None)
            }

            # Add subchannel info if available
            subch_id = service.get('subch_id')
            if subch_id is not None and subch_id in self.subchannels:
                service['subchannel'] = self.subchannels[subch_id]

            services.append(service)

        return services

# ==================== SERVICE SCANNER ====================
class ServiceScanner:
    """Scan for DAB services in a channel"""

    def __init__(self):
        self.fic_handler = FICHandler()
        self.fig_parser = FIGParser()
        self.frames_processed = 0
        self.fibs_valid = 0

    def process_fic_blocks(self, soft_bits_block1, soft_bits_block2, soft_bits_block3):
        """
        Process 3 FIC blocks from one frame

        Args:
            soft_bits_block1, 2, 3: Soft bits from OFDM decoder (3072 bits each)

        Returns:
            Number of valid FIBs processed
        """
        all_fibs = []

        # Process each block
        for block_no, soft_bits in enumerate([soft_bits_block1, soft_bits_block2, soft_bits_block3], 1):
            fibs = self.fic_handler.process_fic_block(soft_bits, block_no)
            all_fibs.extend(fibs)

        # Parse FIBs
        for fib in all_fibs:
            self.fig_parser.parse_fib(fib)
            self.fibs_valid += 1

        self.frames_processed += 1

        return len(all_fibs)

    def get_results(self):
        """Get scan results"""
        return {
            'ensemble_name': self.fig_parser.ensemble_name or "Unknown",
            'ensemble_id': self.fig_parser.ensemble_id,
            'services': self.fig_parser.get_service_list(),
            'frames_processed': self.frames_processed,
            'fibs_valid': self.fibs_valid
        }

    def reset(self):
        """Reset scanner state"""
        self.fic_handler = FICHandler()
        self.fig_parser = FIGParser()
        self.frames_processed = 0
        self.fibs_valid = 0
