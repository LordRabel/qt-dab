# DAB Receiver - Python Implementation

## Übersicht

Dies ist eine Python-Implementierung eines DAB (Digital Audio Broadcasting) Empfängers, die auf dem qt-dab C++ Code basiert. Der Empfänger dekodiert DAB Transmission Mode I Signale bis zum Konstellationsdiagramm.

## Features

✅ **DAB Mode I Unterstützung**
- Vollständige Parameter für Transmission Mode I
- 2.048 MSPS Sample Rate
- 1536 Carrier, 2048 FFT Size

✅ **OFDM Demodulation**
- Null-Symbol-Detektion für Frame-Synchronisation
- Block 0 (Phase Reference Symbol) Verarbeitung
- FFT-basierte OFDM-Demodulation
- Frequency Interleaving (DAB Standard 14.6)

✅ **DPSK Demodulation**
- Differential Phase Shift Keying
- Phase Reference basierte Dekodierung
- QPSK Konstellationsdiagramm

✅ **Visualisierung**
- Live Konstellationsdiagramm (I/Q Plot)
- Spektrum-Anzeige
- Sync-Status
- Frame-Counter

## Architektur

### Haupt-Komponenten

1. **DABParams**: Mode I Parameter (T_F, T_u, T_g, T_s, etc.)
2. **PhaseTable**: Generiert Phase Reference Symbol (Block 0) aus h-tables
3. **FrequencyInterleaver**: Pseudo-random Carrier Mapping
4. **TimeSynchronizer**: Null-Symbol-Detektion
5. **OFDMDecoder**: FFT + DPSK Demodulation
6. **DABReceiver**: Koordiniert alle Komponenten

### Signal Processing Pipeline

```
IQ Samples (RTL-SDR @ 2.048 MSPS)
    ↓
[NULL Detection] → Frame Boundary gefunden
    ↓
[Block 0 Processing] → Phase Reference Symbol → FFT
    ↓
[Blocks 1-75] → Für jedes OFDM Symbol:
    - Skip Guard Interval (504 samples)
    - FFT (2048 samples)
    - Frequency De-Interleaving
    - DPSK Demodulation (current × conj(phase_ref))
    - Konstellationspunkte extrahieren
    ↓
[Constellation Diagram] → I/Q Visualisierung
```

## Installation

### Voraussetzungen

```bash
pip install numpy matplotlib pyrtlsdr
```

### Hardware

- RTL-SDR V4 (oder kompatibel)
- DAB Antenne (VHF Band III: 174-240 MHz)

## Verwendung

### Standalone DAB Receiver

```bash
python3 dab_receiver.py
```

Die GUI zeigt:
- Konstellationsdiagramm (oben) mit idealen QPSK Punkten
- Spektrum (unten)
- Frequenz-Regler (links)
- DAB Kanal-Buttons (5C - 12D)
- Status-Informationen (Sync, Frame Count)

### Integration mit bestehendem Scanner

Der DAB Receiver kann auch in deinen bestehenden Scanner integriert werden:

```python
from dab_receiver import DABReceiver

# Initialize
receiver = DABReceiver(mode=1)

# Add samples from RTL-SDR
samples = sdr.read_samples(32768)
receiver.add_samples(samples)

# Process frame
success, constellation = receiver.process_frame()

if success:
    # constellation enthält komplexe Zahlen (I + jQ)
    print(f"Decoded {len(constellation)} constellation points")

    # Visualisiere
    plt.scatter(constellation.real, constellation.imag)
    plt.show()
```

## DAB Mode I Parameter

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| **T_F** | 196608 | Samples pro Frame |
| **T_null** | 2656 | Null-Symbol-Länge |
| **T_s** | 2552 | OFDM-Symbol-Länge (mit Guard) |
| **T_u** | 2048 | FFT-Größe (Useful Part) |
| **T_g** | 504 | Guard Interval (Cyclic Prefix) |
| **L** | 76 | Blöcke pro Frame (1 Null + 75 Data) |
| **K** | 1536 | Anzahl Carrier |
| **Sample Rate** | 2.048 MHz | IQ Sample Rate |
| **Carrier Spacing** | 1 kHz | Subcarrier-Abstand |

## Frame-Struktur

```
[NULL] [Block 0] [Block 1] [Block 2] [Block 3] [Blocks 4-75]
2656    2552      2552      2552      2552      2552×72
samples samples   samples   samples   samples   samples

 ↓       ↓         ↓         ↓         ↓         ↓
Sync   Phase     FIC       FIC       FIC       MSC
       Ref       Data      Data      Data      (Payload)
```

- **NULL**: Synchronisation (niedriges Signal)
- **Block 0**: Phase Reference Symbol (QPSK Referenz)
- **Blocks 1-3**: Fast Information Channel (FIC) - Service-Info
- **Blocks 4-75**: Main Service Channel (MSC) - Audio/Data

## Implementierungs-Details

### Phase Reference Symbol (Block 0)

Das Phase Reference Symbol ist im DAB-Standard definiert und verwendet h-tables:

```python
# h-tables (32 elements, periodic)
h0 = [0, 2, 0, 0, 0, 0, 1, 1, 2, 0, 0, 0, 2, 2, 1, 1, ...]
h1 = [0, 3, 2, 3, 0, 1, 3, 0, 2, 1, 2, 3, 2, 3, 3, 0, ...]
h2 = [0, 0, 0, 2, 0, 2, 1, 3, 2, 2, 0, 2, 2, 0, 1, 3, ...]
h3 = [0, 1, 2, 1, 0, 3, 3, 2, 2, 3, 2, 1, 2, 1, 3, 2, ...]

# Phase calculation for carrier k
Φ_k = (π/2) × (h(i, k) + n)

# Generate QPSK reference
refTable[k] = exp(j × Φ_k)
```

### Frequency Interleaving

Pseudo-random Permutation (DAB Standard 14.6):

```python
# Generate sequence
tmp[0] = 0
for i in range(1, T_u):
    tmp[i] = (13 × tmp[i-1] + 511) mod 2048

# Map to carriers (skip DC, extract range [256, 1792])
```

### DPSK Demodulation

Differential Phase Shift Keying:

```python
# For each carrier k:
current = FFT[k]                    # Current symbol
phase_ref = phaseReference[k]       # From Block 0

# Differential decoding
demod = current × conj(phase_ref) / |phase_ref|

# Extract I/Q
I = real(demod)  # In-Phase
Q = imag(demod)  # Quadrature

# QPSK Constellation:
#   (1, 1)   → bits [0, 0]
#   (-1, 1)  → bits [1, 0]
#   (-1, -1) → bits [1, 1]
#   (1, -1)  → bits [0, 1]
```

## Konstellationsdiagramm

Das Konstellationsdiagramm zeigt die QPSK-Symbole:

- **Ideal**: 4 Punkte auf dem Einheitskreis bei ±1/√2 ± j/√2
- **Real**: Punktwolken um ideale Positionen (Rauschen, Mehrwegeausbreitung)

**Gute Signalqualität**: Kompakte Cluster um ideale Punkte
**Schlechte Signalqualität**: Verstreute, überlappende Cluster

## Debugging & Troubleshooting

### Kein Sync

- **Problem**: "Sync: NO" bleibt rot
- **Ursache**:
  - Schwaches Signal (Antenne prüfen)
  - Falsche Frequenz (anderen DAB-Kanal testen)
  - Frequenz-Offset zu groß (RTL-SDR PPM korrigieren)
- **Lösung**:
  - Bessere Antenne / Position
  - DAB-Kanal-Buttons durchprobieren (5C-12D)
  - `threshold_low/high` in TimeSynchronizer anpassen

### Constellation Diagram leer

- **Problem**: Keine Punkte im Diagramm
- **Ursache**: Frame-Verarbeitung schlägt fehl
- **Lösung**:
  - Prüfe ob `process_block_0()` erfolgreich
  - Prüfe Buffer-Größe (mind. T_F samples)
  - Erhöhe `max_constellation_points`

### Verzerrte Constellation

- **Problem**: Punkte nicht auf Einheitskreis
- **Ursache**:
  - Gain zu hoch/niedrig
  - DC-Offset
  - Frequenz-Offset
- **Lösung**:
  - RTL-SDR Gain anpassen (28 dB → 15-35 dB testen)
  - DC-Offset-Korrektur einbauen
  - Fine Frequency Correction implementieren

## Nächste Schritte / Erweiterungen

Dieser Empfänger dekodiert bis zum Konstellationsdiagramm. Für vollständigen DAB-Empfang:

1. **Frequency Synchronization** (Coarse + Fine)
   - Cyclic Prefix Correlation
   - Carrier Offset Estimation

2. **FIC Decoder** (Blocks 1-3)
   - Viterbi Decoder (Convolutional Code)
   - CRC Check
   - Service Information (Ensemble, Services)

3. **MSC Decoder** (Blocks 4-75)
   - Time/Frequency Interleaving
   - Viterbi Decoder
   - Energy Dispersal
   - Reed-Solomon Decoder

4. **Audio Decoder**
   - MPEG-1 Layer 2 (MP2)
   - DAB+ (HE-AAC v2)

5. **SNR Berechnung**
   - Cyclic Prefix Correlation Level
   - NULL Period Level
   - `SNR = 20 × log10(prefix_level / null_level)`

## Referenzen

- **DAB Standard**: ETSI EN 300 401 (Digital Audio Broadcasting)
- **qt-dab Source**: https://github.com/JvanKatwijk/qt-dab
- **Basis-Code**: qt-dab C++ Implementation von JvanKatwijk

## Lizenz

Basierend auf qt-dab (GPL-2.0)

## Autor

Python-Port erstellt basierend auf qt-dab C++ Code.

---

**Status**: ✅ Funktional bis Konstellationsdiagramm
**Getestet mit**: RTL-SDR V4, DAB Band III (Deutschland)
**Python Version**: 3.8+
