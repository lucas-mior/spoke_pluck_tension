#!/usr/bin/env python3

import os
import atexit
import numpy as np
import soundfile as sf
import pyqtgraph
from pyqtgraph.Qt import QtCore, QtWidgets
import scipy
import subprocess
import select
import time
from collections import deque

import spokes

sample_rate = 44100
blocksize = 4096
overlap = 0.75
hop_size = int(blocksize*(1 - overlap))
alpha = 0.5

f0 = spokes.frequency(100)
f1 = spokes.frequency(3000)

order = 5
bandpass = scipy.signal.butter(order, [f0, f1], btype='bandpass', fs=sample_rate, output='sos')

frequencies = np.fft.rfftfreq(blocksize, d=1 / sample_rate)
spectrum_smoothed = np.zeros(len(frequencies))
spectrum_max = 0

max_lag = int(sample_rate / f0)
min_lag = int(sample_rate / f1)
last_fundamentals = deque(maxlen=3)

qt_application = QtWidgets.QApplication([])
main_window = QtWidgets.QWidget()
main_layout = QtWidgets.QVBoxLayout()
main_window.setLayout(main_layout)

frequency_label = QtWidgets.QLabel("Frequency: -- Hz")
frequency_label.setStyleSheet("font-size: 22pt; color: cyan; background-color: black;")
main_layout.addWidget(frequency_label)

tension_label = QtWidgets.QLabel("Tension: -- N  (-- kgf)")
tension_label.setStyleSheet("font-size: 22pt; color: orange; background-color: black;")
main_layout.addWidget(tension_label)

window = pyqtgraph.GraphicsLayoutWidget()
main_layout.addWidget(window)
plot = window.addPlot(title="Frequency Spectrum")
curve = plot.plot(pen='y')
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
plot.addItem(peak_text)

plot.setLabel('left', 'Magnitude (dB)')
plot.setLabel('bottom', 'Frequency (Hz)')
plot.setLogMode(x=True, y=False)

xs = np.round(np.logspace(np.log10(f0), np.log10(f1), num=10))
xticks = np.array([[(np.log10(f), str(round(f))) for f in xs]], dtype=object)
plot.setXRange(np.log10(xs[0]), np.log10(xs[-1]))
plot.getAxis('bottom').setTicks(xticks)
plot.setYRange(-50, 0)

def detect_fundamental_autocorrelation(signal, sample_rate):
    signal = signal - np.mean(signal)
    correlation = np.correlate(signal, signal, mode='full')
    correlation = correlation[len(correlation) // 2:]
    correlation[:min_lag] = 0
    peak_idx = np.argmax(correlation[min_lag:max_lag]) + min_lag
    if peak_idx == 0:
        return 0.0
    return sample_rate / peak_idx

last_valid_frequency = None
last_valid_tension = None
last_valid_time = QtCore.QTime.currentTime()
last_update_time = QtCore.QTime.currentTime()
hold_duration = 1000
min_update_interval = 300
min_freq_change = 5.0

overlap_buffer = np.zeros(blocksize, dtype=np.int16)
raw_buffer = bytearray()

def update_plot():
    global last_valid_frequency, last_valid_tension
    global last_valid_time, last_update_time
    global spectrum_smoothed, spectrum_max
    global last_fundamentals
    global overlap_buffer, raw_buffer

    hop_bytes = hop_size*2
    try:
        chunk = fifo_file.read(hop_bytes)
        if chunk:
            raw_buffer += chunk
    except BlockingIOError:
        return

    while len(raw_buffer) >= hop_bytes:
        hop = np.frombuffer(raw_buffer[:hop_bytes], dtype=np.int16)
        raw_buffer = raw_buffer[hop_bytes:]

        overlap_buffer[:-hop_size] = overlap_buffer[hop_size:]
        overlap_buffer[-hop_size:] = hop

        windowed = overlap_buffer*np.hanning(len(overlap_buffer))
        spectrum = np.abs(np.fft.rfft(windowed)) / len(overlap_buffer)
        spectrum[spectrum == 0] = 1e-12
        spectrum_smoothed = (1 - alpha)*spectrum_smoothed + alpha*spectrum

        spectrum_db = 20*np.log10(spectrum_smoothed)
        spectrum_max = max(spectrum_max, max(spectrum_db))
        plot.setYRange(-80, spectrum_max)
        curve.setData(frequencies, spectrum_db)

        now = QtCore.QTime.currentTime()
        fundamental = detect_fundamental_autocorrelation(windowed, sample_rate)

        update_allowed = last_update_time.msecsTo(now) > min_update_interval
        freq_diff_ok = (
            last_valid_frequency is None or
            abs(fundamental - last_valid_frequency) > min_freq_change
        )

        if update_allowed and freq_diff_ok:
            if f0 < fundamental < f1:
                last_fundamentals.append(fundamental)
                median_freq = np.median(last_fundamentals)
                tension = spokes.tension(median_freq)
                last_valid_frequency = median_freq
                last_valid_tension = tension
                last_valid_time = now
                last_update_time = now

        if last_valid_time.msecsTo(now) > hold_duration:
            last_valid_frequency = None
            last_valid_tension = None
            last_fundamentals.clear()

        if last_valid_frequency is not None:
            kgf = last_valid_tension / 9.80665
            idx = np.argmin(np.abs(frequencies - last_valid_frequency))
            peak_text.setPos(np.log10(last_valid_frequency), spectrum_db[idx] + 3)
            peak_text.setText(f"{last_valid_frequency:.0f} Hz")
            frequency_label.setText(f"Frequency: {last_valid_frequency:.0f} Hz")
            tension_label.setText(f"Tension: {last_valid_tension:.0f} N  ({kgf:.0f} kgf)")
        else:
            frequency_label.setText("Frequency: -- Hz")
            tension_label.setText("Tension: -- N  (-- kgf)")
            peak_text.setText("")

fifo_path = "/tmp/audio_fifo"
if not os.path.exists(fifo_path):
    os.mkfifo(fifo_path)

make_result = subprocess.run(["make"])
if make_result.returncode != 0:
    print("Build failed. Exiting.")
    exit(1)

fifo_proc = subprocess.Popen(["./audio_to_fifo"])
fifo_fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
fifo_file = os.fdopen(fifo_fd, 'rb')

atexit.register(fifo_file.close)
atexit.register(fifo_proc.terminate)

main_window.setWindowTitle("Spoke Tension Analyzer")
main_window.resize(800, 600)
main_window.show()

poller = select.poll()
poller.register(fifo_fd, select.POLLIN)

poll_timeout = 1000
idle_sleep = 0.001

while main_window.isVisible():
    events = poller.poll(poll_timeout)
    if events:
        update_plot()
    QtWidgets.QApplication.processEvents()
