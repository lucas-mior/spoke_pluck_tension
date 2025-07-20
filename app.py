#!/usr/bin/python

import os
import atexit
import queue
import numpy as np
import soundfile as sf
import pyqtgraph
from pyqtgraph.Qt import QtCore, QtWidgets
from PyQt6.QtCore import Qt
import scipy
import subprocess
import select
import time
from collections import deque

import spokes

SAMPLE_RATE = 44100
BLOCK_SIZE = 4096
ALPHA_SPECTRUM = 0.5
TENSION_MIN = 200
TENSION_MAX = 2000

frequency_min = spokes.frequency(TENSION_MIN)
frequency_max = spokes.frequency(TENSION_MAX)

qt_application = QtWidgets.QApplication([])
main_window = QtWidgets.QWidget()
main_layout = QtWidgets.QVBoxLayout()
main_window.setLayout(main_layout)

frequency_label = QtWidgets.QLabel("Frequency: -- Hz")
frequency_label.setStyleSheet("""
    font-size: 22pt;
    color: cyan;
    background-color: black;
""")
main_layout.addWidget(frequency_label)

tension_label = QtWidgets.QLabel("Tension: -- N  (-- kgf)")
tension_label.setStyleSheet("""
    font-size: 22pt;
    color: orange;
    background-color: black;
""")
main_layout.addWidget(tension_label)

frequencies = np.fft.rfftfreq(BLOCK_SIZE, d=1 / SAMPLE_RATE)
spectrum_smooth = np.zeros(len(frequencies))
spectrum_max = 0


def detect_fundamental_autocorrelation(signal, SAMPLE_RATE):
    signal = signal - np.mean(signal)
    correlation = np.correlate(signal, signal, mode='full')
    correlation = correlation[(len(correlation) // 2):]
    correlation[:min_lag] = 0

    correlation /= np.max(correlation)
    correlation = correlation[min_lag:max_lag]
    correlation_curve.setData(correlation_lags[:len(correlation)], correlation)

    peak_idx = np.argmax(correlation) + min_lag
    # energy = np.sum(signal**2)
    # if energy < 1 or peak_idx == 0:
    #     return 0.0
    return int(round(SAMPLE_RATE / peak_idx))


def on_data_available():
    global last_valid_frequency, last_valid_tension
    global last_valid_time, last_update_time
    global spectrum_smooth, spectrum_max
    global last_fundamentals

    try:
        raw = fifo_file.read(BLOCK_SIZE*2)
        if not raw:
            return
    except BlockingIOError:
        print("BlockingIO")
        return

    signal = np.array(np.frombuffer(raw, dtype=np.int16), dtype=np.float64)
    signal /= np.iinfo(np.int16).max
    signal = signal*np.hanning(len(signal))

    spectrum = np.abs(np.fft.rfft(signal)) / len(signal)
    spectrum[spectrum == 0] = 1e-12
    spectrum_smooth = (1 - ALPHA_SPECTRUM)*spectrum_smooth \
            + ALPHA_SPECTRUM*spectrum
    spectrum_db = spectrum_smooth

    plot_spectrum.setYRange(0.0, 0.1)
    curve.setData(frequencies, spectrum_db)

    now = QtCore.QTime.currentTime()
    fundamental = detect_fundamental_autocorrelation(signal, SAMPLE_RATE)
    print(f"{fundamental=}")

    update_allowed = last_update_time.msecsTo(now) > min_update_interval
    freq_diff_ok = (
        last_valid_frequency is None
        or abs(fundamental - last_valid_frequency) > min_freq_change
    )

    if update_allowed and freq_diff_ok:
        if frequency_min < fundamental < frequency_max:
            last_fundamentals.append(fundamental)
            median_freq = int(round(np.median(last_fundamentals)))
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
        idx = np.argmin(np.abs(frequencies - last_valid_frequency))

        xloc = last_valid_frequency
        if use_log_frequency:
            xloc = np.log10(xloc)
        peak_text.setPos(xloc, spectrum_db[idx])
        peak_text.setText(f"{last_valid_frequency}Hz = {last_valid_tension}N")

        frequency_label.setText(f"Frequency: {last_valid_frequency}Hz")
        kgf = int(round(last_valid_tension / 9.80665))
        tension_label.setText(f"Tension: {last_valid_tension}N  ({kgf}kgf)")
    else:
        frequency_label.setText("Frequency: -- Hz")
        tension_label.setText("Tension: -- N  (-- kgf)")
        peak_text.setText("")

    peaks = np.argpartition(spectrum_db, -nextra_frequencies)
    peaks = peaks[-nextra_frequencies:]
    peaks = peaks[np.argsort(-spectrum_db[peaks])]
    for i, idx in enumerate(peaks):
        amplitude = spectrum_db[idx]
        frequency = int(round(frequencies[idx]))
        if amplitude > 0.005 and frequency_min < frequency < frequency_max:
            tension = spokes.tension(frequency)
            xloc = frequency
            if use_log_frequency:
                xloc = np.log10(xloc)
            peak_texts[i].setPos(xloc, amplitude)
            peak_texts[i].setText(f"{frequency}Hz = {tension}N")
        else:
            peak_texts[i].setText("")

    return

def on_slider_changed():
    global frequency_min, frequency_max, f0, f1, min_lag, max_lag
    global last_valid_frequency, last_valid_tension
    global last_valid_time, last_update_time
    global spectrum_smooth, spectrum_max
    global last_fundamentals, frequencies

    frequencies = np.fft.rfftfreq(BLOCK_SIZE, d=2 / SAMPLE_RATE)
    spectrum_smooth = np.zeros(len(frequencies))
    spectrum_max = 0

    frequency_min = spokes.frequency(min_slider.value())
    frequency_max = spokes.frequency(max_slider.value())
    f0 = frequency_min/2
    f1 = frequency_max*4
    min_lag = int(SAMPLE_RATE / f1)
    max_lag = int(SAMPLE_RATE / f0)

    print(f"{frequency_min=} {frequency_max=}")

    return


slider_layout = QtWidgets.QHBoxLayout()
min_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
max_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)

min_slider.setMinimum(100)
min_slider.setMaximum(500)
max_slider.setMinimum(600)
max_slider.setMaximum(1000)

min_slider.setValue(frequency_min)
max_slider.setValue(frequency_max)

min_slider.valueChanged.connect(on_slider_changed)
max_slider.valueChanged.connect(on_slider_changed)

slider_layout.addWidget(min_slider)
slider_layout.addWidget(max_slider)
main_layout.addLayout(slider_layout)

on_slider_changed()

layout_plots = pyqtgraph.GraphicsLayoutWidget()
main_layout.addWidget(layout_plots)
plot_spectrum = layout_plots.addPlot(title="Frequency Spectrum")
curve = plot_spectrum.plot(pen='y')
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
plot_spectrum.addItem(peak_text)
nextra_frequencies = 5
peak_texts = []
for i in range(nextra_frequencies):
    peak_texts.append(pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='red'))
    plot_spectrum.addItem(peak_texts[i])

plot_spectrum.setLabel('left', 'Magnitude (dB)')
plot_spectrum.setLabel('bottom', 'Frequency (Hz)')

use_log_frequency = False
if use_log_frequency:
    plot_spectrum.setLogMode(x=True, y=False)
    xs = np.round(np.logspace(np.log10(f0), np.log10(f1), num=10))
    xticks = [[(np.log10(f), str(round(f))) for f in xs]]
    xticks = np.array(xticks, dtype=object)
    plot_spectrum.setXRange(np.log10(xs[0]), np.log10(xs[-1]))
    plot_spectrum.getAxis('bottom').setTicks(xticks)
else:
    plot_spectrum.setXRange(f0, f1)
plot_spectrum.setYRange(-50, 0)

last_valid_frequency = None
last_valid_tension = None
last_valid_time = QtCore.QTime.currentTime()
last_update_time = QtCore.QTime.currentTime()

hold_duration = 1000
min_update_interval = 300
min_freq_change = 5.0

last_fundamentals = deque(maxlen=3)
plot_correlation = layout_plots.addPlot(title="Auto Correlation")
correlation_curve = plot_correlation.plot(pen='g')
plot_correlation.setLabel('left', "Correlation")
plot_correlation.setLabel('bottom', 'Lag')
plot_correlation.setYRange(0, 1)
plot_correlation.setXRange(min_lag, max_lag)

correlation_lags = np.arange(min_lag, max_lag)


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
