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

✅ **FIC Decoding & Service Scanner** 🆕
- Viterbi Decoder (K=7, Rate 1/4)
- Depuncturing (PI_16/PI_15/PI_X patterns)
- Energy Dispersal (PRBS)
- CRC-16 Check
- FIG Parser (0/0, 0/1, 0/2, 1/0, 1/1)
- **Findet Sender im Kanal** (z.B. Deutschlandfunk, WDR, etc.)

✅ **Visualisierung**
- Live Konstellationsdiagramm (I/Q Plot)
- Spektrum-Anzeige
- Sync-Status
- Frame-Counter
- **Service-Liste mit Sender-Namen** 🆕

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
- **Service Scanner** (neu): "Scan for Services" Button 🆕

### Service Scanner benutzen

1. **Kanal wählen**: Klicke auf DAB-Kanal-Button (z.B. "8B")
2. **Warten auf Sync**: Status zeigt "Sync: YES" (grün)
3. **Scan starten**: Klicke "Scan for Services"
4. **Warten**: Scanner läuft ~5 Sekunden (50 Frames)
5. **Ergebnisse**: Service-Liste zeigt:
   - Ensemble-Name (z.B. "WDR Muenster")
   - Ensemble-ID (z.B. "d31d")
   - Sender-Namen (z.B. "Deutschlandfunk", "WDR 2", "1LIVE")
   - Service-IDs (SId)

**Beispiel Output (Kanal 8B):**
```
=== WDR Muenster ===
EId: D31D

Deutschlandfunk (SId: D312)
WDR 2 Rheinland (SId: D314)
1LIVE (SId: D315)
WDR 3 (SId: D316)
WDR 4 (SId: D317)
WDR 5 (SId: D318)
KIRAKA (SId: D319)
...
```

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

## FIC Decoding Details 🆕

Der Service Scanner dekodiert FIC (Fast Information Channel) um Sender zu finden:

### Pipeline

```
FIC Blocks 1, 2, 3 (je 3072 soft bits)
  ↓
[Depuncturing] → PI_16/PI_15/PI_X patterns → 3096 bits
  ↓
[Viterbi K=7] → Convolutional decode, rate 1/4 → 768 hard bits
  ↓
[Energy Dispersal] → XOR mit PRBS (x^9 + x^5 + 1)
  ↓
[Split to FIBs] → 3 FIBs à 256 bits (30 bytes data + 2 bytes CRC)
  ↓
[CRC-16 Check] → Nur valide FIBs weiter
  ↓
[FIG Parser] → Extract service info:
  - FIG 0/0: Ensemble ID
  - FIG 0/1: Subchannel organization
  - FIG 0/2: Service organization (SId → subchannel)
  - FIG 1/0: Ensemble label (name)
  - FIG 1/1: Service labels (station names)
  ↓
[Service List] → Anzeige in GUI
```

### Viterbi Decoder Hinweis

**WICHTIG**: Die aktuelle Implementation ist **vereinfacht**:
- Hard Decision (Majority Vote)
- **Keine** ACS (Add-Compare-Select) Operations
- **Kein** optimaler Traceback
- Funktioniert für **Demonstration**, aber nicht optimal

**Für bessere Ergebnisse** (bei schwachen Signalen):
- Nutze optimierte Viterbi-Library (z.B. `libfec` via Python bindings)
- Mit Soft-Decision ACS und Traceback
- SIMD-Optimierung

### FIG Types

| FIG | Ext | Beschreibung | Inhalt |
|-----|-----|--------------|--------|
| 0/0 | 0 | Ensemble Info | Ensemble ID, CIF counter |
| 0/1 | 1 | Sub-channel Org | Start address, size, bitrate |
| 0/2 | 2 | Service Org | SId → subchannel mapping |
| 1/0 | 0 | Ensemble Label | Ensemble name (16 chars) |
| 1/1 | 1 | Service Label | Station name (16 chars) |

## Nächste Schritte / Erweiterungen

✅ **Bereits implementiert:**
- OFDM Demodulation bis Konstellationsdiagramm
- **FIC Decoder für Service-Scanning** 🆕
- **Service-Liste mit Sender-Namen** 🆕

⏳ **Für vollständigen DAB-Empfang (mit Audio) fehlt noch:**

1. **Frequency Synchronization** (Coarse + Fine)
   - Cyclic Prefix Correlation
   - Carrier Offset Estimation

2. **MSC Decoder** (Blocks 4-75)
   - Time/Frequency Interleaving
   - Viterbi Decoder
   - Energy Dispersal
   - Reed-Solomon Decoder

3. **Audio Decoder**
   - MPEG-1 Layer 2 (MP2)
   - DAB+ (HE-AAC v2)

4. **SNR Berechnung**
   - Cyclic Prefix Correlation Level
   - NULL Period Level

## Referenzen

- **DAB Standard**: ETSI EN 300 401 (Digital Audio Broadcasting)
- **qt-dab Source**: https://github.com/JvanKatwijk/qt-dab
- **Basis-Code**: qt-dab C++ Implementation von JvanKatwijk

## Lizenz

Basierend auf qt-dab (GPL-2.0)

## Autor

Python-Port erstellt basierend auf qt-dab C++ Code.

---

**Status**: ✅ Funktional bis Service-Scanning (FIC Decoder)
**Features**: Konstellationsdiagramm + Spektrum + **Sender-Liste** 🆕
**Getestet mit**: RTL-SDR V4, DAB Band III (Deutschland), Kanal 8B
**Python Version**: 3.8+
