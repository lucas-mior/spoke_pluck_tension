#!/usr/bin/python

import os
import atexit
import queue
import numpy as np
import soundfile as sf
import pyqtgraph
from pyqtgraph.Qt import QtCore, QtWidgets
from PyQt6.QtCore import Qt
import subprocess
import select
import time
from collections import deque
from scipy.signal import find_peaks

import spokes

USE_LOG_FREQUENCY = False
SAMPLE_RATE = 44100
BLOCK_SIZE = 4096
ALPHA_SPECTRUM = 0.5
TENSION_MIN = 100
TENSION_MAX = 2000
TENSION_AVG = int(round((TENSION_MIN + TENSION_MAX)/2))

frequency_min = spokes.frequency(TENSION_MIN)
frequency_max = spokes.frequency(TENSION_MAX)

qt_application = QtWidgets.QApplication([])
main_window = QtWidgets.QWidget()
main_layout = QtWidgets.QVBoxLayout()
main_window.setLayout(main_layout)

top_indicator = QtWidgets.QLabel("Frequency: -- Hz")
top_indicator.setStyleSheet("""
    font-size: 22pt;
    color: cyan;
    background-color: black;
""")
main_layout.addWidget(top_indicator)

slider_layout = QtWidgets.QVBoxLayout()

min_label = QtWidgets.QLabel()
min_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
min_slider.setMinimum(TENSION_MIN)
min_slider.setMaximum(TENSION_AVG)
min_slider.setValue(TENSION_MIN)

min_slider_layout = QtWidgets.QHBoxLayout()
min_slider_layout.addWidget(min_label)
min_slider_layout.addWidget(min_slider)

max_label = QtWidgets.QLabel()
max_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
max_slider.setMinimum(TENSION_AVG)
max_slider.setMaximum(TENSION_MAX)
max_slider.setValue(TENSION_MAX)

max_slider_layout = QtWidgets.QHBoxLayout()
max_slider_layout.addWidget(max_label)
max_slider_layout.addWidget(max_slider)

slider_layout.addLayout(min_slider_layout)
slider_layout.addLayout(max_slider_layout)

main_layout.addLayout(slider_layout)

frequencies = np.fft.rfftfreq(BLOCK_SIZE, d=1 / SAMPLE_RATE)
spectrum_smooth = np.zeros(len(frequencies))

layout_plots = pyqtgraph.GraphicsLayoutWidget()
plot_spectrum = layout_plots.addPlot(title="Frequency Spectrum")
plot_spectrum.setLabel('left', 'Magnitude (dB)')
plot_spectrum.setLabel('bottom', 'Frequency (Hz)')
plot_spectrum_curve = plot_spectrum.plot(pen='y')
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
plot_spectrum.addItem(peak_text)
plot_spectrum.setYRange(-50, 0)
main_layout.addWidget(layout_plots)

nextra_frequencies = 10
peak_texts = []
for i in range(nextra_frequencies):
    text_item = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='red')
    peak_texts.append(text_item)
    plot_spectrum.addItem(peak_texts[i])

correlation_texts = []
for i in range(3):
    text_item = pyqtgraph.TextItem('',anchor=(0.5, -0.5), color='green')
    correlation_texts.append(text_item)
    plot_spectrum.addItem(correlation_texts[i])

def detect_fundamental_autocorrelation(signal):
    signal = signal - np.mean(signal)
    correlation = np.correlate(signal, signal, mode='full')
    correlation = correlation[(len(correlation) // 2):]
    correlation[:min_lag] = 0

    correlation /= np.max(correlation)
    correlation = correlation[min_lag:max_lag]

    peaks, _ = find_peaks(correlation)
    top_peaks = peaks[np.argsort(-correlation[peaks])][:3]
    top_peaks = [p + min_lag for p in top_peaks]
    return [int(round(SAMPLE_RATE / lag)) for lag in top_peaks]

def on_data_available():
    global last_fundamental, last_tension
    global last_time, last_update
    global spectrum_smooth
    global last_fundamentals

    try:
        signal = fifo_file.read(BLOCK_SIZE*2)
        if not signal:
            return
    except BlockingIOError:
        print("BlockingIO")
        return

    signal = np.frombuffer(signal, dtype=np.int16)
    signal = np.array(signal, dtype=np.float64)
    signal = signal / np.iinfo(np.int16).max
    signal = signal*np.hanning(len(signal))

    spectrum = np.abs(np.fft.rfft(signal)) / len(signal)
    spectrum[spectrum == 0] = 1e-12
    spectrum_smooth = (1 - ALPHA_SPECTRUM)*spectrum_smooth + ALPHA_SPECTRUM*spectrum
    spectrum_db = spectrum_smooth

    plot_spectrum.setYRange(0.0, 0.1)
    plot_spectrum_curve.setData(frequencies, spectrum_db)

    fundamentals = detect_fundamental_autocorrelation(signal)
    if len(fundamentals) == 0:
        return

    now = int(time.time()*1000)
    update_allowed = (now - last_update) > min_update_interval
    freq_diff_ok = (
        last_fundamental is None
        or abs(fundamentals[0] - last_fundamental) > min_freq_change
    )

    if update_allowed and freq_diff_ok:
        if frequency_min < fundamentals[0] < frequency_max:
            last_fundamentals.append(fundamentals[0])
            median_freq = int(round(np.median(last_fundamentals)))
            tension = spokes.tension(median_freq)
            last_fundamental = median_freq
            last_tension = tension
            last_time = now
            last_update = now

    if (now - last_time) > hold_duration:
        last_fundamental = None
        last_tension = None
        last_fundamentals.clear()

    if last_fundamental is not None:
        idx = np.argmin(np.abs(frequencies - last_fundamental))

        xloc = last_fundamental
        if USE_LOG_FREQUENCY:
            xloc = np.log10(xloc)
        peak_text.setPos(xloc, spectrum_db[idx])
        peak_text.setText(f"{last_fundamental}Hz = {last_tension}N")

        kgf = int(round(last_tension / 9.80665))
        indicator_text = f"{last_fundamental}Hz -> {last_tension}N = {kgf}kgf"
        top_indicator.setText(indicator_text)
    else:
        top_indicator.setText("Frequency: -- Hz")
        peak_text.setText("")

    peaks, _ = find_peaks(spectrum_smooth)
    peaks = peaks[np.argsort(-spectrum_smooth[peaks])]
    peaks = peaks[:nextra_frequencies]
    for i, idx in enumerate(peaks):
        amplitude = spectrum_smooth[idx]
        frequency = int(round(frequencies[idx]))
        if amplitude > 0.01:
            tension = spokes.tension(frequency)
            xloc = frequency
            if USE_LOG_FREQUENCY:
                xloc = np.log10(xloc)
            peak_texts[i].setPos(xloc, amplitude)
            peak_texts[i].setText(f"{frequency}Hz = {tension}N")
        else:
            peak_texts[i].setText("")

    for i in range(3):
        if i < len(fundamentals):
            f = fundamentals[i]
            idx = np.argmin(np.abs(frequencies - f))
            amp = spectrum_db[idx]
            xloc = f
            if USE_LOG_FREQUENCY:
                xloc = np.log10(xloc)
            correlation_texts[i].setPos(xloc, amp)
            correlation_texts[i].setText(f"{f}Hz")
        else:
            correlation_texts[i].setText("")

    return

def on_slider_changed():
    global frequency_min, frequency_max
    global min_lag, max_lag
    global plot_spectrum

    frequency_min = spokes.frequency(min_slider.value())
    frequency_max = spokes.frequency(max_slider.value())
    f0 = frequency_min/2
    f1 = frequency_max*4
    min_lag = int(SAMPLE_RATE / f1)
    max_lag = int(SAMPLE_RATE / f0)

    min_label.setText(f"Min Tension: {min_slider.value()}N")
    max_label.setText(f"Max Tension: {max_slider.value()}N")

    if USE_LOG_FREQUENCY:
        plot_spectrum.setLogMode(x=True, y=False)
        xs = np.round(np.logspace(np.log10(f0), np.log10(f1), num=10))
        xticks = [[(np.log10(f), str(round(f))) for f in xs]]
        xticks = np.array(xticks, dtype=object)
        plot_spectrum.setXRange(np.log10(xs[0]), np.log10(xs[-1]))
        plot_spectrum.getAxis('bottom').setTicks(xticks)
    else:
        plot_spectrum.setXRange(f0, f1)
    return

min_slider.valueChanged.connect(on_slider_changed)
max_slider.valueChanged.connect(on_slider_changed)

on_slider_changed()

last_fundamental = None
last_tension = None
last_time = int(time.time()*1000)
last_update = int(time.time()*1000)

hold_duration = 1000
min_update_interval = 300
min_freq_change = 5.0
last_fundamentals = deque(maxlen=3)

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
main_window.resize(1000, 600)
main_window.show()

poller = select.poll()
poller.register(fifo_fd, select.POLLIN)

poll_timeout = 1000
idle_sleep = 0.001

while main_window.isVisible():
    events = poller.poll(poll_timeout)
    if events:
        on_data_available()
    QtWidgets.QApplication.processEvents()
