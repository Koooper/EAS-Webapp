"""
SAME protocol constants per 47 CFR 11.31
https://www.govinfo.gov/content/pkg/CFR-2010-title47-vol1/xml/CFR-2010-title47-vol1-sec11-31.xml
"""

# AFSK modulation parameters
SAMPLE_RATE = 22050  # standard broadcast quality, sufficient for SAME
BAUD_RATE = 520.83   # bits per second
BIT_DURATION = 1 / BAUD_RATE  # ~1.92ms per bit

# FSK frequencies
MARK_FREQ = 2083.3   # Hz, represents binary 1
SPACE_FREQ = 1562.5  # Hz, represents binary 0

# Attention signal (two-tone)
ATTENTION_FREQ_1 = 853   # Hz
ATTENTION_FREQ_2 = 960   # Hz
ATTENTION_DURATION_MIN = 8    # seconds
ATTENTION_DURATION_MAX = 25   # seconds
ATTENTION_DURATION_DEFAULT = 8  # seconds

# Timing
PREAMBLE_BYTES = 16      # 0xAB pattern repeated
HEADER_REPETITIONS = 3   # header sent 3 times
HEADER_GAP = 1.0         # 1 second between headers
EOM_REPETITIONS = 3      # EOM sent 3 times

# Message markers
PREAMBLE_BYTE = 0xAB     # 10101011 binary
HEADER_START = "ZCZC"
EOM_MARKER = "NNNN"

# Amplitude
TONE_AMPLITUDE = 0.8     # leave headroom
