# Python DAB Receiver - Schnellstart

## 🚀 Sofort loslegen (ohne Hardware!)

Teste die Signal-Verarbeitung mit synthetischen Daten:

```bash
cd python_dab_receiver
pip install -r requirements.txt
python demo_synthetic.py
```

Wähle Option **3** für animierte Live-Anzeige!

## 📡 Mit RTL-SDR Hardware

### Installation

```bash
pip install -r requirements.txt
```

### DAB Empfang starten

```bash
# Liste verfügbare Frequenzen
python dab_constellation_viewer.py --list-frequencies

# Starte Empfang (Beispiel: Kanal 11C)
python dab_constellation_viewer.py --freq 220352000 --gain 30
```

### Wichtige Frequenzen (Deutschland)

- **11C**: 220.352 MHz (häufig aktiv)
- **12D**: 229.072 MHz
- **5C**: 178.352 MHz

## 📂 Datei-Übersicht

| Datei | Beschreibung |
|-------|--------------|
| `dab_receiver.py` | RTL-SDR Interface & Basis-Verarbeitung |
| `ofdm_processor.py` | OFDM Dekodierung (FFT, Equalisierung) |
| `constellation_display.py` | Konstellationsdiagramm-Anzeige |
| `dab_constellation_viewer.py` | **Hauptprogramm** (alles zusammen) |
| `demo_synthetic.py` | **Demo ohne Hardware** |
| `requirements.txt` | Python-Abhängigkeiten |

## 🎯 Beispiele

### Beispiel 1: Statischer Plot (Synthetic)

```python
from ofdm_processor import OFDMProcessor, DABParams
from constellation_display import ConstellationPlotter
import numpy as np

# Processor erstellen
processor = OFDMProcessor()

# Synthetisches QPSK Signal generieren
# (siehe demo_synthetic.py für vollständigen Code)

# Konstellationsdiagramm anzeigen
ConstellationPlotter.plot(constellation)
```

### Beispiel 2: Live-Empfang

```python
from dab_receiver import DABReceiver
from ofdm_processor import OFDMProcessor
from constellation_display import ConstellationDisplay

# RTL-SDR initialisieren
receiver = DABReceiver()
receiver.tune(220352000)  # 220.352 MHz

# Processor & Display
processor = OFDMProcessor()
display = ConstellationDisplay()

# Hauptloop
while True:
    samples = receiver.read_samples(2552)
    constellation = processor.process_samples(samples)
    if constellation is not None:
        display.update_constellation(constellation)
```

## 🔧 Troubleshooting

### RTL-SDR nicht gefunden?

```bash
# Test RTL-SDR
rtl_test

# USB Permissions (Linux)
sudo usermod -a -G plugdev $USER
```

### Kein Signal?

1. **DAB-Abdeckung prüfen**: Nur in Regionen mit DAB+ verfügbar
2. **Antenne**: Externe DVB-T Antenne empfohlen
3. **Gain anpassen**: Probiere verschiedene Werte (20-40)
4. **Frequenz**: Mehrere Kanäle testen

### Python-Pakete?

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 📊 Was Sie sehen sollten

**Gutes Signal** (SNR > 15 dB):
```
       Q
       ↑
   •   |   •    <- Enge Cluster
-------+--------  I
   •   |   •
```

**Schlechtes Signal** (SNR < 10 dB):
```
       Q
       ↑
   ⁕⁕  |  ⁕⁕   <- Breite Streuung
-------+--------  I
   ⁕⁕  |  ⁕⁕
```

## 🎓 Technische Konzepte

### Was ist ein Konstellationsdiagramm?

- **I-Achse** (horizontal): In-Phase Komponente
- **Q-Achse** (vertikal): Quadratur Komponente
- **Punkte**: Empfangene Symbole
- **4 Cluster**: QPSK Modulation (2 Bits pro Symbol)

### Signal-Kette

```
RTL-SDR → IQ Samples → Freq. Korrektur → OFDM Decoder
         → FFT → Equalisierung → Konstellation → Display
```

### DQPSK Demodulation

```python
# Kern-Algorithmus (ofdm_processor.py)
fftBin = current_symbol × conj(phase_reference) / |phase_reference|
```

Die Information steckt in der **Phasendifferenz** zwischen aufeinanderfolgenden Symbolen!

## 📚 Weitere Infos

- Vollständige Dokumentation: `README.md`
- Technische Details: Siehe Code-Kommentare
- qt-dab Projekt: https://github.com/JvanKatwijk/qt-dab

## 💡 Tipps

1. **Starte mit Demo**: Verstehe die Verarbeitung ohne Hardware
2. **SNR beachten**: > 15 dB ist gut
3. **Gain optimieren**: Zu hoch = Übersteuerung, zu niedrig = Rauschen
4. **Antenne**: Externe Antenne macht großen Unterschied
5. **Position**: Nähe zum Fenster, vertikale Ausrichtung

## ❓ Hilfe

Fragen oder Probleme? Überprüfe:
- [ ] Python >= 3.7?
- [ ] Alle Pakete installiert?
- [ ] RTL-SDR angeschlossen?
- [ ] DAB-Signal verfügbar in Ihrer Region?

Viel Erfolg! 🎉
