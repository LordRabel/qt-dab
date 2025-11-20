#!/usr/bin/env python3
"""
RTL-SDR Test Script
Diagnose tool to check RTL-SDR installation and device
"""

import sys
import os


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_python_version():
    """Test 1: Python version"""
    print("\n[1/6] Checking Python version...")
    print(f"  Python: {sys.version}")
    print(f"  Executable: {sys.executable}")

    major, minor = sys.version_info[:2]
    if major >= 3 and minor >= 7:
        print("  ✓ Python version OK (>= 3.7)")
        return True
    else:
        print("  ✗ Python version too old (need >= 3.7)")
        return False


def test_pyrtlsdr_package():
    """Test 2: pyrtlsdr package installation"""
    print("\n[2/6] Checking pyrtlsdr package...")

    try:
        import rtlsdr
        print(f"  ✓ pyrtlsdr package found")
        print(f"  Location: {rtlsdr.__file__}")
        try:
            import pkg_resources
            version = pkg_resources.get_distribution("pyrtlsdr").version
            print(f"  Version: {version}")
        except:
            pass
        return True
    except ImportError as e:
        print(f"  ✗ pyrtlsdr not found: {e}")
        print("  Install with: pip install pyrtlsdr")
        return False


def test_rtlsdr_import():
    """Test 3: RtlSdr class import"""
    print("\n[3/6] Importing RtlSdr class...")

    try:
        from rtlsdr import RtlSdr
        print("  ✓ RtlSdr class import successful")
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        print("\n  This usually means librtlsdr is missing on Windows!")
        print("  See WINDOWS_INSTALL.md for installation instructions.")
        return False


def test_librtlsdr():
    """Test 4: librtlsdr library"""
    print("\n[4/6] Checking librtlsdr library...")

    try:
        from rtlsdr import librtlsdr
        print("  ✓ librtlsdr library loaded")
        print(f"  Library: {librtlsdr._librtlsdr}")
        return True
    except Exception as e:
        print(f"  ✗ librtlsdr library not found: {e}")

        if sys.platform == "win32":
            print("\n  Windows: librtlsdr.dll missing!")
            print("  Solutions:")
            print("    1. Download from: https://ftp.osmocom.org/binaries/windows/rtl-sdr/")
            print("    2. Extract all .dll files")
            print("    3. Copy to Python directory:")
            print(f"       {os.path.dirname(sys.executable)}")
        else:
            print("\n  Linux/Mac: Install librtlsdr")
            print("    Ubuntu: sudo apt-get install librtlsdr-dev")
            print("    Mac: brew install librtlsdr")

        return False


def test_device_open():
    """Test 5: Open RTL-SDR device"""
    print("\n[5/6] Opening RTL-SDR device...")

    try:
        from rtlsdr import RtlSdr
        sdr = RtlSdr()
        print("  ✓ RTL-SDR device opened successfully!")
        return sdr
    except Exception as e:
        print(f"  ✗ Failed to open device: {e}")
        print("\n  Troubleshooting:")
        print("    • Is RTL-SDR dongle connected?")
        print("    • Is WinUSB driver installed? (Use Zadig on Windows)")
        print("    • Try different USB port")
        print("    • Close other SDR programs (SDR#, HDSDR, etc.)")
        print("    • On Linux: Check USB permissions")
        return None


def test_device_info(sdr):
    """Test 6: Get device information"""
    print("\n[6/6] Getting device information...")

    try:
        print(f"  Tuner type: {sdr.get_tuner_type()}")
        print(f"  Sample rate: {sdr.sample_rate / 1e6:.3f} MHz")
        print(f"  Center freq: {sdr.center_freq / 1e6:.3f} MHz")
        print(f"  Gain: {sdr.gain} dB")

        # Try to read samples
        print("\n  Testing sample reading...")
        samples = sdr.read_samples(1024)
        print(f"  ✓ Read {len(samples)} samples")
        print(f"  Sample range: {abs(samples).min():.3f} to {abs(samples).max():.3f}")

        sdr.close()
        print("\n  ✓ Device closed successfully")
        return True

    except Exception as e:
        print(f"  ✗ Error reading device info: {e}")
        try:
            sdr.close()
        except:
            pass
        return False


def print_summary(results):
    """Print test summary"""
    print_header("TEST SUMMARY")

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  ✓✓✓ All tests PASSED! RTL-SDR is working! ✓✓✓")
        print("\n  You can now run:")
        print("    python dab_constellation_viewer.py --freq 220352000")
    else:
        print("\n  ✗✗✗ Some tests FAILED ✗✗✗")
        print("\n  See error messages above and:")
        print("    • README.md for general installation")
        print("    • WINDOWS_INSTALL.md for Windows-specific help")


def main():
    """Main test routine"""
    print_header("RTL-SDR DIAGNOSTIC TEST")
    print("  This script will test your RTL-SDR installation")

    results = {}

    # Run tests
    results["Python Version"] = test_python_version()

    if not results["Python Version"]:
        print("\n  Cannot continue with old Python version!")
        sys.exit(1)

    results["pyrtlsdr Package"] = test_pyrtlsdr_package()

    if not results["pyrtlsdr Package"]:
        print("\n  Install pyrtlsdr first: pip install pyrtlsdr")
        print_summary(results)
        sys.exit(1)

    results["RtlSdr Import"] = test_rtlsdr_import()
    results["librtlsdr Library"] = test_librtlsdr()

    if not results["RtlSdr Import"] or not results["librtlsdr Library"]:
        print("\n  Fix library issues before testing device!")
        print_summary(results)
        sys.exit(1)

    sdr = test_device_open()
    results["Device Open"] = sdr is not None

    if sdr:
        results["Device Info & Samples"] = test_device_info(sdr)
    else:
        results["Device Info & Samples"] = False

    # Summary
    print_summary(results)

    # Exit code
    if all(results.values()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
