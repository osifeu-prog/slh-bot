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


def freq(note):
    match = NOTE_RE.fullmatch(note)
    if not match:
        raise ValueError("INVALID_NOTE")
    letter, accidental, octave = match.groups()
    midi = N[letter] + (accidental == "#") - (accidental == "b") + 12 * (int(octave) + 1)
    return 440 * 2 ** ((midi - 69) / 12)


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


def env(i, count, attack=0.02, decay=0.1, sustain=0.7, release=0.15):
    t = i / SR
    total = count / SR
    if t < attack:
        return t / attack
    if t < attack + decay:
        return 1 - (1 - sustain) * (t - attack) / decay
    if t < total - release:
        return sustain
    return max(0, sustain * (total - t) / release)


def tone(notes, waveform, duration):
    count = int(SR * duration)
    frequencies = [freq(note) for note in notes]
    result = []
    for i in range(count):
        sample = sum(osc(waveform, frequency * i / SR) for frequency in frequencies)
        result.append(sample / len(frequencies) * env(i, count))
    return result


def main(score, waveform="sine", duration=0.5, out="/tmp/synth.ogg"):
    if waveform not in {"sine", "saw", "square", "tri"}:
        raise ValueError("INVALID_WAVEFORM")
    if not (0.1 <= float(duration) <= 1.5):
        raise ValueError("INVALID_DURATION")

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
        samples.extend(tone(notes, waveform, float(duration)))
    peak = max(map(abs, samples), default=0) or 1

    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(wav_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SR)
            wav.writeframes(b"".join(
                struct.pack("<h", int(sample / peak * 26000))
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
