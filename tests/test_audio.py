import numpy as np
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.SAME_encode import generate_dual_tone, SAMPLE_RATE

def test_dual_tone_amplitude():
    duration = 1.0
    tone = generate_dual_tone(1000, 1500, duration)
    assert np.max(np.abs(tone)) <= 1.0
    assert len(tone) == int(SAMPLE_RATE * duration)

