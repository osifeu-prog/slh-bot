"""Small deterministic audio renderer used by the SLH Synth Telegram command.

Instrument models are lightweight synthesis presets, not sampled emulations of
physical instruments. Settings may be supplied by the UI with explicit bounds.
"""
import math
import os
import re
import struct
import subprocess
import tempfile
import wave

SR = 22050
N = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOTE_RE = re.compile(r"([A-G])([#b]?)([0-8])$")
WAVES = ("sine", "saw", "square", "tri")
INSTRUMENTS = WAVES + ("piano", "moog", "bass", "organ", "pluck")
SETTING_KEYS = ("attack", "decay", "sustain", "release", "cutoff", "resonance")
SETTING_LIMITS = {
    "attack": (0.005, 0.5),
    "decay": (0.005, 0.8),
    "sustain": (0.0, 1.0),
    "release": (0.005, 0.8),
    "cutoff": (200.0, 12000.0),
    "resonance": (0.5, 12.0),
}
PRESET_SETTINGS = {
    "sine":   (0.02, 0.10, 0.70, 0.15, 12000.0, 0.707),
    "saw":    (0.02, 0.10, 0.70, 0.15, 12000.0, 0.707),
    "square": (0.02, 0.10, 0.70, 0.15, 12000.0, 0.707),
    "tri":    (0.02, 0.10, 0.70, 0.15, 12000.0, 0.707),
    "piano":  (0.005, 0.38, 0.22, 0.32, 10000.0, 0.8),
    "moog":   (0.02, 0.18, 0.72, 0.20, 1800.0, 5.0),
    "bass":   (0.008, 0.18, 0.60, 0.14, 850.0, 2.0),
    "organ":  (0.01, 0.04, 0.90, 0.08, 10000.0, 0.8),
    "pluck":  (0.005, 0.22, 0.08, 0.12, 5200.0, 1.0),
}


def freq(note):
    match = NOTE_RE.fullmatch(str(note))
    if not match:
        raise ValueError("INVALID_NOTE")
    letter, accidental, octave = match.groups()
    midi = N[letter] + (accidental == "#") - (accidental == "b") + 12 * (int(octave) + 1)
    return 440.0 * 2 ** ((midi - 69) / 12)


def osc(waveform, phase):
    phase %= 1
    if waveform == "sine":
        return math.sin(2 * math.pi * phase)
    if waveform == "saw":
        return 2 * phase - 1
    if waveform == "square":
        return 1 if phase < 0.5 else -1
    if waveform == "tri":
        return 4 * abs(phase - 0.5) - 1
    raise ValueError("INVALID_WAVEFORM")


def normalize_settings(waveform, settings=None):
    if waveform not in INSTRUMENTS:
        raise ValueError("INVALID_INSTRUMENT")
    base = dict(zip(SETTING_KEYS, PRESET_SETTINGS[waveform]))
    if settings is None:
        return base
    if not isinstance(settings, dict):
        raise ValueError("INVALID_SYNTH_SETTINGS")
    for key in SETTING_KEYS:
        if key in settings:
            try:
                value = float(settings[key])
            except (TypeError, ValueError, OverflowError):
                raise ValueError("INVALID_SYNTH_SETTINGS") from None
            lo, hi = SETTING_LIMITS[key]
            if not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError("INVALID_SYNTH_SETTINGS")
            base[key] = value
    return base


def env(i, count, attack=0.02, decay=0.1, sustain=0.7, release=0.15):
    if count <= 0:
        return 0.0
    t = i / SR
    total = count / SR

    def level_at(position):
        if position <= 0:
            return 0.0
        if position < attack:
            return position / attack
        if position < attack + decay:
            return 1.0 - (1.0 - sustain) * (position - attack) / decay
        return sustain

    # A short note cannot contain an entire long release stage. Reserve at
    # least 65% of the note for its attack/decay/sustain before fading out.
    release_duration = min(release, total * 0.35)
    release_start = max(0.0, total - release_duration)
    if t >= release_start:
        release_level = level_at(release_start)
        remaining = max(0.0, (total - t) / max(release_duration, 1 / SR))
        return release_level * remaining
    return level_at(t)


def _lowpass(samples, cutoff, resonance):
    """Second-order low-pass biquad (RBJ cookbook form), mono."""
    cutoff = max(20.0, min(float(cutoff), SR * 0.45))
    q = max(0.5, min(float(resonance), 12.0))
    omega = 2.0 * math.pi * cutoff / SR
    cosine = math.cos(omega)
    alpha = math.sin(omega) / (2.0 * q)
    a0 = 1.0 + alpha
    b0 = ((1.0 - cosine) / 2.0) / a0
    b1 = (1.0 - cosine) / a0
    b2 = b0
    a1 = (-2.0 * cosine) / a0
    a2 = (1.0 - alpha) / a0
    z1 = z2 = 0.0
    filtered = []
    for sample in samples:
        y = b0 * sample + z1
        z1 = b1 * sample - a1 * y + z2
        z2 = b2 * sample - a2 * y
        filtered.append(y)
    return filtered


def tone(notes, waveform, duration, settings=None):
    if waveform not in INSTRUMENTS:
        raise ValueError("INVALID_INSTRUMENT")
    if not math.isfinite(float(duration)) or not (0.1 <= float(duration) <= 1.5):
        raise ValueError("INVALID_DURATION")
    if not notes or len(notes) > 8:
        raise ValueError("INVALID_CHORD_SIZE")
    frequencies = [freq(note) for note in notes]
    settings = normalize_settings(waveform, settings)
    count = int(SR * float(duration))
    attack = settings["attack"]
    decay = settings["decay"]
    sustain = settings["sustain"]
    release = settings["release"]

    result = []
    for i in range(count):
        t = i / SR
        value = 0.0
        for f in frequencies:
            phase = f * i / SR
            if waveform in WAVES:
                voice = osc(waveform, phase)
            elif waveform == "piano":
                # A decaying inharmonic-ish partial stack: piano-like, not a sample.
                voice = (
                    0.66 * math.sin(2 * math.pi * phase) * math.exp(-t * 1.55)
                    + 0.23 * math.sin(2 * math.pi * phase * 2.01) * math.exp(-t * 3.4)
                    + 0.085 * math.sin(2 * math.pi * phase * 3.99) * math.exp(-t * 5.8)
                    + 0.035 * math.sin(2 * math.pi * phase * 6.02) * math.exp(-t * 8.2)
                )
            elif waveform == "moog":
                voice = osc("saw", phase)
            elif waveform == "bass":
                voice = 0.68 * osc("saw", phase) + 0.32 * math.sin(math.pi * phase * 2.0)
            elif waveform == "organ":
                voice = (
                    0.67 * math.sin(2 * math.pi * phase)
                    + 0.22 * math.sin(2 * math.pi * phase * 2)
                    + 0.11 * math.sin(2 * math.pi * phase * 3)
                )
            else:  # pluck
                voice = (
                    0.72 * osc("tri", phase) * math.exp(-t * 5.0)
                    + 0.28 * math.sin(2 * math.pi * phase * 2) * math.exp(-t * 8.5)
                )
            value += voice
        value /= len(frequencies)
        value *= env(i, count, attack, decay, sustain, release)
        result.append(value)

    if waveform in {"moog", "bass"} or settings["cutoff"] < 11999 or settings["resonance"] > 1.25:
        result = _lowpass(result, settings["cutoff"], settings["resonance"])
    return result


def main(score, waveform="sine", duration=0.5, out="/tmp/synth.ogg", settings=None):
    if waveform not in INSTRUMENTS:
        raise ValueError("INVALID_INSTRUMENT")
    duration = float(duration)
    if not math.isfinite(duration) or not (0.1 <= duration <= 1.5):
        raise ValueError("INVALID_DURATION")
    validated_settings = normalize_settings(waveform, settings)
    steps = score.split(",")
    if not 1 <= len(steps) <= 16:
        raise ValueError("INVALID_STEP_COUNT")
    parsed = [step.split() for step in steps]
    if any(not notes or len(notes) > 8 for notes in parsed):
        raise ValueError("INVALID_CHORD_SIZE")
    if any(not NOTE_RE.fullmatch(note) for notes in parsed for note in notes):
        raise ValueError("INVALID_NOTE")

    samples = []
    for notes in parsed:
        samples.extend(tone(notes, waveform, duration, validated_settings))
    peak = max(map(abs, samples), default=0) or 1

    output_parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(output_parent, exist_ok=True)
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(wav_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SR)
            wav.writeframes(b"".join(
                struct.pack("<h", int(max(-1.0, min(1.0, sample / peak)) * 26000))
                for sample in samples
            ))
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
             "-c:a", "libopus", out],
            check=True,
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    finally:
        try:
            os.remove(wav_path)
        except FileNotFoundError:
            pass
    return out
