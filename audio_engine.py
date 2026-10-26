"""SesKutusu local audio playback engine."""
from __future__ import annotations
import threading
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf
from broadcast import BroadcastBus

MAX_SECONDS = 600
MAX_BYTES = 150 * 1024 * 1024

@dataclass
class Clip:
    samples: np.ndarray
    rate: int
    path: str
    @property
    def duration(self): return len(self.samples) / self.rate


def load_clip(path: str, normalize=False) -> Clip:
    file = Path(path)
    if file.stat().st_size > MAX_BYTES:
        raise ValueError('File exceeds the 150 MB limit.')
    with sf.SoundFile(str(file)) as src:
        if src.frames * max(2, src.channels) > 30000000:
            raise ValueError('Decoded audio exceeds the memory limit.')
        if src.frames / src.samplerate > MAX_SECONDS:
            raise ValueError('Audio files are limited to ten minutes.')
        data = src.read(dtype='float32', always_2d=True)
        rate = src.samplerate
    if len(data) == 0: raise ValueError('The audio file is empty.')
    if data.shape[1] == 1: data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2: data = data[:, :2]
    data = np.nan_to_num(data, nan=0, posinf=1, neginf=-1)
    if normalize:
        peak = float(np.max(np.abs(data)))
        if peak > 0.0001: data *= min(4.0, 0.89 / peak)
    np.clip(data, -1, 1, out=data)
    return Clip(np.ascontiguousarray(data, dtype=np.float32), rate, str(file))


def resample(data, source_rate, target_rate):
    if source_rate == target_rate: return data
    length = max(1, round(len(data) * target_rate / source_rate))
    original = np.arange(len(data), dtype=np.float64)
    positions = np.arange(length, dtype=np.float64) * source_rate / target_rate
    return np.stack([np.interp(positions, original, data[:, c]) for c in range(data.shape[1])], axis=1).astype(np.float32)


def output_devices():
    devices = sd.query_devices()
    apis = sd.query_hostapis()
    return [{'index': i, 'name': d['name'], 'api': apis[d['hostapi']]['name'],
             'rate': int(d['default_samplerate']), 'channels': int(d['max_output_channels'])}
            for i, d in enumerate(devices) if d['max_output_channels'] > 0]


class AudioEngine:
    def __init__(self):
        self.streams = []
        self.tracks = []
        self.clip = None
        self.paused = False
        self.loop = False
        self.preview_gain = 0.65
        self.broadcast_gain = 0.65
        self.peak = 0.0
        self.warning = ''
        self.lock = threading.RLock()
        self.broadcast_track = None
        self.bus = BroadcastBus(self.render_broadcast, self.broadcast_file_active)

    def broadcast_file_active(self):
        with self.lock:
            t = self.broadcast_track
            return bool(t is not None and not self.paused and (self.loop or t["position"] < len(t["data"])))

    def render_broadcast(self, outdata, frames):
        with self.lock:
            track = self.broadcast_track
            if track is None: outdata.fill(0)
            else: self.render(track, outdata, frames)

    @property
    def position(self):
        with self.lock:
            if not self.tracks: return 0.0
            t = self.tracks[0]
            return t['position'] / t['rate']

    @property
    def playing(self):
        with self.lock:
            return bool(self.tracks) and (self.loop or any(t['position'] < len(t['data']) for t in self.tracks))

    def stop(self):
        streams, self.streams = self.streams, []
        for stream in streams:
            try: stream.abort(); stream.close()
            except Exception: pass
        with self.lock:
            self.tracks = []
            self.broadcast_track = None
            self.paused = False
            self.peak = 0

    def seek(self, seconds):
        with self.lock:
            for t in self.tracks:
                t['position'] = max(0, min(len(t['data']), round(seconds * t['rate'])))

    def render(self, track, outdata, frames):
        outdata.fill(0)
        with self.lock:
            if self.paused: return
            data = track['data']
            left = frames
            offset = 0
            gain = self.preview_gain if track['role'] == 'preview' else self.broadcast_gain
            while left:
                available = len(data) - track['position']
                if available <= 0:
                    if not self.loop: break
                    track['position'] = 0
                    available = len(data)
                count = min(left, available)
                np.multiply(data[track['position']:track['position'] + count], gain,
                            out=outdata[offset:offset + count])
                track['position'] += count
                offset += count
                left -= count
            np.clip(outdata, -1, 1, out=outdata)
            self.peak = float(np.max(np.abs(outdata))) if outdata.size else 0

    def play(self, clip, preview=None, broadcast=None, mode='preview'):
        self.stop()
        self.clip = clip
        self.warning = ''
        requested = []
        if mode in ('preview', 'both'): requested.append(('preview', preview))
        if mode in ('broadcast', 'both'):
            if broadcast is None: raise ValueError('Select a broadcast output first. For a virtual cable, select CABLE Input.')
            requested.append(('broadcast', broadcast))
        default = int(sd.default.device[1])
        if self.bus.active: requested.sort(key=lambda pair: pair[0] != "broadcast")
        seen = set()
        try:
            for role, device in requested:
                actual = default if device is None else int(device)
                if actual in seen: continue
                seen.add(actual)
                if role == 'broadcast' and self.bus.active:
                    if actual != self.bus.output_device:
                        raise ValueError('The broadcast output changed. Reconnect from the microphone mixing dialog.')
                    data = resample(clip.samples, clip.rate, self.bus.rate)
                    if self.bus.channels == 1: data = data.mean(axis=1, keepdims=True)
                    track = dict(data=data, rate=self.bus.rate, position=0, role=role)
                    with self.lock:
                        self.broadcast_track = track
                        self.tracks.append(track)
                    continue
                info = sd.query_devices(actual, 'output')
                channels = min(2, int(info['max_output_channels']))
                rate = int(info['default_samplerate'])
                data = resample(clip.samples, clip.rate, rate)
                if channels == 1: data = data.mean(axis=1, keepdims=True)
                track = dict(data=data, rate=rate, position=0, role=role)
                self.tracks.append(track)
                def callback(out, frames, timing, status, current=track):
                    if status: self.warning = str(status)
                    self.render(current, out, frames)
                stream = sd.OutputStream(device=actual, samplerate=rate, channels=channels,
                                         dtype='float32', callback=callback, latency='high')
                self.streams.append(stream)
            for stream in self.streams: stream.start()
        except Exception:
            self.stop()
            raise

    def close(self):
        self.stop()
        self.bus.stop()


