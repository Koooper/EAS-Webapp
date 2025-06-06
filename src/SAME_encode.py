import numpy as np
import wave

# define SAME params @ https://www.govinfo.gov/content/pkg/CFR-2010-title47-vol1/xml/CFR-2010-title47-vol1-sec11-31.xml
BAUD_RATE = 520.83 #bps
MARK = 2083.3 #hz
SPACE = 1562.5 #hz
SAMPLE_RATE = 44100
MARK_TIME = 0.00192
SPACE_TIME = 0.00192
ATTENTION_FREQS = [853, 960]

# SAME header elements
PREAMBLE = "ZCZC-"
EOM = "-NNNN"
eas_code = "PEP-EAN-32003+0600-1001200-KPEP"

def generate_tone(frequency, duration):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    signal = np.sin(2 * np.pi * frequency * t)
    return signal

def generate_dual_tone(frequency1, frequency2, duration):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    signal1 = np.sin(2 * np.pi * frequency1 * t)
    signal2 = np.sin(2 * np.pi * frequency2 * t)
    dual_tone = (signal1 + signal2) / 2
    return dual_tone


