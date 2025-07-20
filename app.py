#!/usr/bin/python

import time
import atexit
import os
import subprocess
import select
import collections
import numpy as np
import scipy
import pyqtgraph
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtCore import Qt

import spokes

pyqtgraph.setConfigOptions(antialias=True)

USE_LOG_FREQUENCY = False

Cfile_name = "./audio_to_fifo"
Cfile = open(f"{Cfile_name}.c")
for line in Cfile:
    if not line.startswith("#define"):
        continue
    parts = line.split()
    print("parts:", parts)
    match parts[1]:
        case "SAMPLE_RATE":
            SAMPLE_RATE = int(parts[2])
        case "FRAMES_PER_BUFFER":
            FRAMES_PER_BUFFER = int(parts[2])

ALPHA_SPECTRUM = 0.5

frequency_min = spokes.frequency(spokes.TENSION_MIN)
frequency_max = spokes.frequency(spokes.TENSION_MAX)

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
min_slider.setMinimum(spokes.TENSION_MIN)
min_slider.setMaximum(spokes.TENSION_AVG)
min_slider.setValue(spokes.TENSION_MIN)

min_slider_layout = QtWidgets.QHBoxLayout()
min_slider_layout.addWidget(min_label)
min_slider_layout.addWidget(min_slider)

max_label = QtWidgets.QLabel()
max_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
max_slider.setMinimum(spokes.TENSION_AVG)
max_slider.setMaximum(spokes.TENSION_MAX)
max_slider.setValue(spokes.TENSION_MAX)

max_slider_layout = QtWidgets.QHBoxLayout()
max_slider_layout.addWidget(max_label)
max_slider_layout.addWidget(max_slider)

slider_layout.addLayout(min_slider_layout)
slider_layout.addLayout(max_slider_layout)

main_layout.addLayout(slider_layout)

frequencies = np.fft.rfftfreq(FRAMES_PER_BUFFER, d=1 / SAMPLE_RATE)
spectrum_smooth = np.zeros(len(frequencies))

layout_plots = pyqtgraph.GraphicsLayoutWidget()
plot_spectrum = layout_plots.addPlot(title="Frequency Spectrum")
plot_spectrum.setLabel('left', 'Magnitude (dB)')
plot_spectrum.setLabel('bottom', 'Frequency (Hz)')
plot_spectrum_curve = plot_spectrum.plot(pen=pyqtgraph.mkPen('y', width=3))
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
plot_spectrum.addItem(peak_text)
plot_spectrum.setYRange(-50, 0)
main_layout.addWidget(layout_plots)

peak_texts = []
correlation_texts = []

nextra_frequencies = 5
for i in range(nextra_frequencies):
    text_item = pyqtgraph.TextItem('',anchor=(0.5, 2.5), color='green')
    correlation_texts.append(text_item)
    plot_spectrum.addItem(correlation_texts[i])

    text_item = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='red')
    peak_texts.append(text_item)
    plot_spectrum.addItem(peak_texts[i])

def on_data_available():
    global last_fundamental, last_tension
    global last_time, last_update
    global spectrum_smooth
    global last_fundamentals

    try:
        signal = fifo_file.read(FRAMES_PER_BUFFER*2)
        if not signal:
            return
    except BlockingIOError:
        return

    signal = np.frombuffer(signal, dtype=np.int16)
    signal = np.array(signal, dtype=np.float64)
    signal = signal / np.iinfo(np.int16).max
    signal = signal*np.hanning(len(signal))
    signal = signal - np.mean(signal)

    spectrum = np.abs(np.fft.rfft(signal)) / len(signal)
    spectrum[spectrum == 0] = 1e-12
    spectrum_smooth = (1 - ALPHA_SPECTRUM)*spectrum_smooth + ALPHA_SPECTRUM*spectrum
    spectrum_db = spectrum_smooth

    plot_spectrum.setYRange(0.0, 0.1)
    plot_spectrum_curve.setData(frequencies, spectrum_db)

    correlation = np.correlate(signal, signal, mode='full')
    correlation = correlation[(len(correlation) // 2):]
    correlation[:min_lag] = 0

    correlation /= np.max(correlation)
    correlation = correlation[min_lag:max_lag]

    peaks, _ = scipy.signal.find_peaks(correlation)
    if len(peaks) == 0:
        return
    top_peaks = peaks[np.argsort(-correlation[peaks])[:nextra_frequencies]]
    fundamentals = []
    for p in top_peaks:
        if p <= 0 or p >= len(correlation) - 1:
            lag = p + min_lag
        else:
            y0, y1, y2 = correlation[p - 1], correlation[p], correlation[p + 1]
            d = 0.5*(y0 - y2) / (y0 - 2*y1 + y2)
            lag = (p + d) + min_lag
        freq = SAMPLE_RATE / lag
        fundamentals.append((freq))

    peaks_fft, _ = scipy.signal.find_peaks(spectrum_smooth)
    peaks_fft = peaks_fft[np.argsort(-spectrum_smooth[peaks_fft])][:nextra_frequencies]
    fundamentals_fft = [(frequencies[idx]) for idx in peaks_fft]

    for i, idx in enumerate(peaks_fft):
        amplitude = spectrum_smooth[idx]
        frequency = (frequencies[idx])
        if amplitude > 0.01:
            xloc = frequency
            if USE_LOG_FREQUENCY:
                xloc = np.log10(xloc)
            peak_texts[i].setPos(xloc, amplitude)
            peak_texts[i].setText(f"{frequency:.1f}Hz")
        else:
            peak_texts[i].setText("")

    for i in range(nextra_frequencies):
        if i < len(fundamentals):
            frequency = fundamentals[i]
            idx = np.argmin(np.abs(frequencies - frequency))
            amplitude = spectrum_smooth[idx]
            xloc = frequency
            if USE_LOG_FREQUENCY:
                xloc = np.log10(xloc)
            correlation_texts[i].setPos(xloc, amplitude)
            correlation_texts[i].setText(f"{frequency:.1f}Hz")
        else:
            correlation_texts[i].setText("")

    now = int(time.time()*1000)
    update_allowed = (now - last_update) > min_update_interval
    freq_diff_ok = (
        last_fundamental is None
        or abs(fundamentals[0] - last_fundamental) > min_freq_change
    )

    fft_match = any(abs(fundamentals[0] - f) < 5 for f in fundamentals_fft)

    if update_allowed and freq_diff_ok and fft_match:
        if frequency_min < fundamentals[0] < frequency_max:
            last_fundamentals.append(fundamentals[0])
            median_freq = np.median(last_fundamentals)
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
        peak_text.setText(f"{last_fundamental:.1f}Hz = {last_tension}N")

        kgf = round(last_tension / 9.80665)
        indicator_text = f"{last_fundamental:.1f}Hz -> {last_tension}N = {kgf}kgf"
        top_indicator.setText(indicator_text)
    else:
        top_indicator.setText("Frequency: -- Hz")
        peak_text.setText("")

    return

def on_slider_changed():
    global frequency_min, frequency_max
    global min_lag, max_lag
    global plot_spectrum

    frequency_min = spokes.frequency(min_slider.value())
    frequency_max = spokes.frequency(max_slider.value())
    f0 = frequency_min
    f1 = frequency_max*2
    min_lag = round(SAMPLE_RATE / f1)
    max_lag = round(SAMPLE_RATE / f0)

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

hold_duration = 2000
min_update_interval = 600
min_freq_change = 5.0
last_fundamentals = collections.deque(maxlen=6)

fifo_path = "/tmp/audio_fifo"
if not os.path.exists(fifo_path):
    os.mkfifo(fifo_path)

make_result = subprocess.run(["make"])
if make_result.returncode != 0:
    print("Build failed. Exiting.")
    exit(1)

fifo_proc = subprocess.Popen([f"{Cfile_name}"])
fifo_fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
fifo_file = os.fdopen(fifo_fd, 'rb')

atexit.register(fifo_file.close)
atexit.register(fifo_proc.terminate)

main_window.setWindowTitle("Spoke Tension Analyzer")
main_window.resize(1000, 600)
main_window.show()

poller = select.poll()
poller.register(fifo_fd, select.POLLIN)

while main_window.isVisible():
    events = poller.poll(1000)
    if events:
        on_data_available()
    QtWidgets.QApplication.processEvents()
