# Windows Installation Guide

## Problem: "RTL-SDR library (librtlsdr) not found"

Auf Windows benötigt `pyrtlsdr` die **librtlsdr.dll** und einen **WinUSB-Treiber**.

---

## Lösung 1: Schnelle Installation (Empfohlen)

### Schritt 1: Zadig Driver Installation

1. **Download Zadig**: https://zadig.akeo.ie/
2. RTL-SDR Dongle anschließen
3. Zadig als Administrator ausführen
4. **Options → List All Devices** aktivieren
5. Ihr RTL-SDR Gerät auswählen (meist "Bulk-In, Interface (Interface 0)")
6. Treiber auswählen: **WinUSB** (wichtig: NICHT libusb-win32!)
7. **"Replace Driver"** oder **"Install Driver"** klicken
8. Warten bis Installation abgeschlossen

### Schritt 2: librtlsdr.dll installieren

**Option A: Pre-compiled Binary (Einfach)**

1. Download: https://ftp.osmocom.org/binaries/windows/rtl-sdr/
   - Datei: `rtl-sdr-64bit.zip` (für 64-bit Python)
   - Oder: `rtl-sdr-32bit.zip` (für 32-bit Python)

2. Entpacken Sie die ZIP-Datei

3. Kopieren Sie **alle .dll Dateien** nach:
   ```
   C:\Users\<IhrName>\AppData\Local\Programs\Python\Python313\
   ```

   Oder in Ihr Python Scripts Verzeichnis:
   ```
   C:\Users\<IhrName>\AppData\Local\Programs\Python\Python313\Scripts\
   ```

   **Wichtige DLLs:**
   - `rtlsdr.dll`
   - `libusb-1.0.dll`
   - `pthreadVC2.dll` (optional)

4. Python neu starten und testen:
   ```powershell
   python -c "from rtlsdr import RtlSdr; print('Success!')"
   ```

---

## Lösung 2: Conda Installation (Alternative)

Falls Sie Anaconda/Miniconda verwenden:

```bash
conda install -c conda-forge pyrtlsdr
```

Dies installiert automatisch alle benötigten Bibliotheken.

---

## Test: RTL-SDR Funktioniert?

### Test 1: Python Import

```powershell
python -c "from rtlsdr import RtlSdr; sdr = RtlSdr(); print(f'Device found: {sdr.get_tuner_type()}'); sdr.close()"
```

**Erfolg** wenn: "Device found: ..." angezeigt wird
**Fehler** wenn: ImportError oder RuntimeError

### Test 2: Mit rtl_test (Optional)

Wenn Sie die rtl-sdr Tools installiert haben:

```powershell
rtl_test -t
```

Sollte Ihr Gerät erkennen und Informationen anzeigen.

---

## Häufige Probleme & Lösungen

### Problem 1: "usb_open error -12"

**Ursache:** Falscher Treiber installiert

**Lösung:**
1. Zadig erneut öffnen
2. **WinUSB** Treiber installieren (nicht libusb-win32!)
3. Computer neu starten

### Problem 2: "No devices found"

**Ursache:** Gerät nicht erkannt oder von anderem Programm verwendet

**Lösung:**
- Anderen USB-Port probieren
- Andere Programme schließen (SDR#, HDSDR, etc.)
- Gerät ab- und wieder anstecken
- Geräte-Manager überprüfen (sollte als "Bulk-In" erscheinen)

### Problem 3: "ImportError: DLL load failed"

**Ursache:** librtlsdr.dll oder Abhängigkeiten fehlen

**Lösung:**
1. Alle DLLs aus rtl-sdr-64bit.zip kopieren
2. **Visual C++ Redistributable** installieren:
   - Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
3. Python neu starten

### Problem 4: "Access is denied"

**Ursache:** Keine Berechtigung oder Gerät in Verwendung

**Lösung:**
- PowerShell/CMD als Administrator ausführen
- Alle anderen SDR-Programme schließen
- Gerät neu anschließen

---

## Verifizierung: Schritt-für-Schritt

```powershell
# 1. Python Version prüfen
python --version

# 2. pyrtlsdr prüfen
pip show pyrtlsdr

# 3. RTL-SDR Import testen
python -c "from rtlsdr import RtlSdr; print('Import OK')"

# 4. Gerät öffnen testen
python -c "from rtlsdr import RtlSdr; sdr = RtlSdr(); print('Device OK'); sdr.close()"

# 5. DAB Viewer starten
python python_dab_receiver\dab_constellation_viewer.py --freq 220352000
```

---

## Alternative: SDR# zum Testen

Um zu verifizieren, dass Ihr RTL-SDR grundsätzlich funktioniert:

1. **Download SDR#**: https://airspy.com/download/
2. Entpacken und `sdrsharp.exe` ausführen
3. Wenn SDR# Ihr Gerät erkennt → Treiber ist korrekt
4. Dann sollte auch Python funktionieren

---

## Vollständige Installations-Checkliste

- [ ] Zadig installiert
- [ ] WinUSB Treiber für RTL-SDR installiert (in Zadig)
- [ ] rtl-sdr-64bit.zip heruntergeladen
- [ ] Alle .dll Dateien nach Python-Verzeichnis kopiert
- [ ] Visual C++ Redistributable installiert (falls DLL-Fehler)
- [ ] Python neu gestartet
- [ ] RTL-SDR angeschlossen (grünes LED leuchtet)
- [ ] Import-Test erfolgreich
- [ ] Device-Open-Test erfolgreich

---

## Windows-spezifische Python-Pfade

Finden Sie Ihr Python-Verzeichnis:

```powershell
python -c "import sys; print(sys.executable)"
```

Beispiel-Ausgabe:
```
C:\Users\KarlR\AppData\Local\Programs\Python\Python313\python.exe
```

Kopieren Sie DLLs nach:
```
C:\Users\KarlR\AppData\Local\Programs\Python\Python313\
```

Oder ins Scripts-Verzeichnis:
```
C:\Users\KarlR\AppData\Local\Programs\Python\Python313\Scripts\
```

---

## Weitere Hilfe

**Dokumentation:**
- pyrtlsdr: https://pyrtlsdr.readthedocs.io/
- RTL-SDR: https://www.rtl-sdr.com/
- Zadig: https://github.com/pbatard/libwdi/wiki/Zadig

**Test-Script:**

Speichern Sie als `test_rtlsdr.py`:

```python
#!/usr/bin/env python3
import sys

print("Testing RTL-SDR...")
print(f"Python: {sys.version}")

# Test 1: Import
try:
    from rtlsdr import RtlSdr
    print("✓ pyrtlsdr import successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Open device
try:
    sdr = RtlSdr()
    print("✓ RTL-SDR device opened")

    # Get info
    print(f"  Tuner type: {sdr.get_tuner_type()}")
    print(f"  Sample rate: {sdr.sample_rate} Hz")
    print(f"  Center freq: {sdr.center_freq / 1e6} MHz")
    print(f"  Gain: {sdr.gain} dB")

    sdr.close()
    print("✓ Device closed successfully")
    print("\n✓ All tests passed! RTL-SDR is working.")

except Exception as e:
    print(f"✗ Device open failed: {e}")
    print("\nTroubleshooting:")
    print("  1. Is RTL-SDR plugged in?")
    print("  2. Is Zadig WinUSB driver installed?")
    print("  3. Are all DLL files in place?")
    print("  4. Is another program using the device?")
    sys.exit(1)
```

Ausführen:
```powershell
python test_rtlsdr.py
```

---

Bei weiteren Problemen, überprüfen Sie die Ausgabe und folgen Sie den Troubleshooting-Schritten oben!
