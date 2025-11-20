# DAB Constellation Viewer (Python)

Python-Implementation der qt-dab Signal-Verarbeitungskette: Von RTL-SDR Samples bis zum Konstellationsdiagramm.

## Übersicht

Dieses Projekt implementiert die Hauptfunktionalität von qt-dab in Python:

```
RTL-SDR Dongle
    ↓ uint8_t IQ @ 2.048 MHz
[RTL-SDR Handler]
    ↓ complex float (DC removal, filtering)
[Frequency Correction]
    ↓ corrected samples
[OFDM Processing]
    ↓ FFT → Equalization → DQPSK
[Constellation Points]
    ↓
[Matplotlib Display]
```

## Features

- ✅ **RTL-SDR Interface**: Direkte Anbindung an RTL-SDR Dongle
- ✅ **Signal Processing**: Frequenzkorrektur, DC-Offset Entfernung
- ✅ **OFDM Decoder**: FFT, Equalisierung, DQPSK Demodulation
- ✅ **Konstellationsdiagramm**: Live-Anzeige mit matplotlib
- ✅ **SNR Schätzung**: Automatische Signal-Qualitäts-Bewertung
- ✅ **Modi**: Log-Magnitude und NCP (Nearest Center Point)

## Installation

### Voraussetzungen

- Python 3.7 oder höher
- RTL-SDR Dongle (z.B. RTL2832U)
- Linux/macOS/Windows mit USB-Zugriff

### 1. Python-Pakete installieren

```bash
cd python_dab_receiver
pip install -r requirements.txt
```

**⚠️ WINDOWS BENUTZER:** Nach der Installation von `pyrtlsdr` müssen Sie noch zusätzliche Schritte durchführen!

➡️ **Siehe [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) für vollständige Windows-Installationsanleitung**

Kurz:
1. Zadig installieren und WinUSB-Treiber für RTL-SDR installieren
2. librtlsdr.dll herunterladen und ins Python-Verzeichnis kopieren

**Test:** Führen Sie `python test_rtlsdr.py` aus, um Ihre Installation zu überprüfen!

### 2. RTL-SDR Treiber (Linux)

```bash
# Ubuntu/Debian
sudo apt-get install rtl-sdr librtlsdr-dev

# Fedora
sudo dnf install rtl-sdr

# Test
rtl_test
```

### 3. USB-Berechtigungen (Linux)

Erstelle udev-Regel für RTL-SDR:

```bash
sudo nano /etc/udev/rules.d/20-rtlsdr.rules
```

Inhalt:
```
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0666"
```

Neu laden:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Verwendung

### Schnellstart

```bash
# DAB Kanal 11C (220.352 MHz) mit Auto-Gain
python dab_constellation_viewer.py --freq 220352000

# Mit manuellem Gain
python dab_constellation_viewer.py --freq 220352000 --gain 35

# Liste verfügbare DAB Frequenzen
python dab_constellation_viewer.py --list-frequencies
```

### Verfügbare DAB Kanäle (Deutschland)

| Kanal | Frequenz | MHz |
|-------|----------|-----|
| 5A | 174928000 Hz | 174.928 MHz |
| 11C | 220352000 Hz | 220.352 MHz |
| 12D | 229072000 Hz | 229.072 MHz |

Vollständige Liste: `--list-frequencies`

### Argumente

```
--freq FREQUENCY    DAB Frequenz in Hz (erforderlich)
--gain GAIN         RF Gain in dB (Standard: 30, 0=auto)
--device INDEX      RTL-SDR Device Index (Standard: 0)
--list-frequencies  Zeige DAB Frequenzen
```

## Module

### 1. `dab_receiver.py`

RTL-SDR Interface und Basis-Signal-Verarbeitung:

- **RTLSDRHandler**: RTL-SDR Geräte-Interface
- **FrequencyCorrector**: Frequenz-Offset Korrektur
- **DABReceiver**: Haupt-Empfänger-Klasse

```python
from dab_receiver import DABReceiver

receiver = DABReceiver()
receiver.tune(220352000)  # 220.352 MHz
samples = receiver.read_samples(2048)
```

### 2. `ofdm_processor.py`

OFDM Signal-Verarbeitung und Dekodierung:

- **DABParams**: DAB Mode I Parameter
- **OFDMDecoder**: FFT, Equalisierung, DQPSK
- **OFDMProcessor**: High-Level Orchestrator

```python
from ofdm_processor import OFDMProcessor

processor = OFDMProcessor()
constellation = processor.process_samples(samples)
```

### 3. `constellation_display.py`

Konstellationsdiagramm-Anzeige:

- **ConstellationDisplay**: Animierte Anzeige
- **ConstellationPlotter**: Statische Plots

```python
from constellation_display import ConstellationDisplay

display = ConstellationDisplay()
display.update_constellation(constellation)
display.show()
```

### 4. `dab_constellation_viewer.py`

Vollständige Anwendung (alles zusammen):

- Integriert Receiver + Processor + Display
- Threading für Live-Verarbeitung
- Kommandozeilen-Interface

## Technische Details

### DAB Mode I Parameter

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| Samplerate | 2.048 MHz | RTL-SDR Sampling-Rate |
| T_null | 2656 | Null-Symbol Samples |
| T_u | 2048 | FFT Größe |
| T_g | 504 | Guard-Intervall |
| T_s | 2552 | Symbol-Länge (T_u + T_g) |
| Carriers | 1536 | Aktive Träger |

### OFDM Verarbeitungsschritte

1. **Sample Reading**: RTL-SDR → IQ Samples
2. **DC Removal**: Gleichspannungs-Offset entfernen
3. **Frequency Correction**: NCO-basierte Korrektur
4. **Symbol Extraction**: Guard-Intervall überspringen
5. **FFT**: Zeit-Domäne → Frequenz-Domäne (2048 Punkte)
6. **Equalization**: DQPSK Demodulation
   ```
   fftBin = current × conj(phaseRef) / |phaseRef|
   ```
7. **Normalization**: Skalierung für Display
8. **Display Update**: Konstellationsdiagramm

### DQPSK Konstellation

Ideale QPSK-Punkte:

```
       Q
       ↑
   Q2  |  Q1
  (-,+)|(+,+)
-------+-------- I
  (-,-)|(+,-)
   Q3  |  Q4
```

Positionen: `(±1/√2, ±1/√2)`

## Demo ohne Hardware

Test mit synthetischen Daten (kein RTL-SDR nötig):

```bash
# Teste OFDM Processor
python ofdm_processor.py

# Teste Konstellationsdiagramm
python constellation_display.py
```

## Troubleshooting

### "Failed to initialize RTL-SDR"

**Problem**: RTL-SDR nicht gefunden

**Lösung**:
1. RTL-SDR Dongle anschließen
2. Treiber prüfen: `rtl_test`
3. USB-Berechtigungen prüfen
4. Anderen USB-Port probieren

### "No module named 'rtlsdr'"

**Problem**: pyrtlsdr nicht installiert

**Lösung**:
```bash
pip install pyrtlsdr
```

### Kein Signal / Leeres Konstellationsdiagramm

**Problem**: Kein DAB Signal empfangen

**Lösung**:
1. DAB-Abdeckung prüfen (nur in DAB-Regionen verfügbar)
2. Antenne verbessern (externe DVB-T Antenne)
3. Andere Frequenz probieren (`--list-frequencies`)
4. Gain anpassen (`--gain 40`)
5. Nähe zum Fenster

### Konstellation zu verrauscht

**Problem**: Schlechtes SNR

**Lösung**:
1. Gain erhöhen: `--gain 40`
2. Bessere Antenne
3. Position ändern
4. Gain senken bei Übersteuerung

## Performance

**Benchmark** (Intel i5, RTL-SDR):
- Sample-Rate: ~2 MSamples/s
- CPU-Last: ~15-25%
- Display-Update: 10 fps
- Latenz: ~100ms

## Vergleich mit qt-dab

| Feature | qt-dab (C++) | Python Version |
|---------|--------------|----------------|
| RTL-SDR Interface | ✅ | ✅ |
| OFDM Decoder | ✅ | ✅ (vereinfacht) |
| Konstellationsdiagramm | ✅ | ✅ |
| Audio Decoder | ✅ | ❌ |
| FIC/MSC Decoder | ✅ | ❌ |
| Frame Sync | ✅ | ✅ (vereinfacht) |
| Performance | Sehr schnell | Akzeptabel |

**Fokus**: Diese Python-Version demonstriert die **Signal-Verarbeitung bis zum Konstellationsdiagramm**. Für vollständige DAB-Dekodierung (Audio) verwenden Sie qt-dab.

## Weiterführende Links

- [qt-dab Projekt](https://github.com/JvanKatwijk/qt-dab)
- [RTL-SDR Documentation](https://www.rtl-sdr.com/)
- [DAB Standard](https://www.etsi.org/deliver/etsi_en/300400_300499/300401/)

## Lizenz

Gleiche Lizenz wie qt-dab.

## Autor

Basierend auf qt-dab von Jan van Katwijk
Python-Implementation zur Demonstration der Signal-Verarbeitungskette
