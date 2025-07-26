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
from pyqtgraph import AxisItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import spokes

pyqtgraph.setConfigOptions(antialias=True)

USE_LOG_FREQUENCY = False
ALPHA_SPECTRUM = 0.5

Cfile_name = "./audio_to_fifo"
Cfile = open(f"{Cfile_name}.c")
for line in Cfile:
    if not line.startswith("#define"):
        continue
    parts = line.split()
    match parts[1]:
        case "SAMPLE_RATE":
            SAMPLE_RATE = int(parts[2])
        case "FRAMES_PER_BUFFER":
            FRAMES_PER_BUFFER = int(parts[2])

qt_application = QtWidgets.QApplication([])
main_window = QtWidgets.QWidget()
main_layout = QtWidgets.QVBoxLayout()
main_window.setLayout(main_layout)

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

top_indicator = QtWidgets.QLabel("Frequency: -- Hz")
top_indicator.setStyleSheet("""
    font-size: 22pt;
    color: cyan;
    background-color: black;
""")
main_layout.addWidget(top_indicator)

layout_plots = pyqtgraph.GraphicsLayoutWidget()
plot_spectrum = layout_plots.addPlot(title="Frequency Spectrum")
plot_spectrum.setLabel('left', 'Magnitude')
plot_spectrum.setLabel('bottom', 'Frequency (Hz)')
plot_spectrum_curve = plot_spectrum.plot(
    pen=pyqtgraph.mkPen('y', width=3, join=Qt.PenJoinStyle.RoundJoin)
)
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
peak_text.setFont(QFont('LiberationSans', 18))
plot_spectrum.addItem(peak_text)
plot_spectrum.setYRange(0, 0.1)
main_layout.addWidget(layout_plots)

peak_texts = []
correlation_texts = []

nfrequencies_corr = 3
for i in range(nfrequencies_corr):
    text_item = pyqtgraph.TextItem('',anchor=(0.5, 2.5), color='green')
    text_item.setFont(QFont('LiberationSans', 18))
    correlation_texts.append(text_item)
    plot_spectrum.addItem(correlation_texts[i])

nfrequencies_fft = 5
for i in range(nfrequencies_fft):
    text_item = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='red')
    text_item.setFont(QFont('LiberationSans', 18))
    peak_texts.append(text_item)
    plot_spectrum.addItem(peak_texts[i])

tension_axis = pyqtgraph.AxisItem(orientation='bottom')
plot_spectrum.layout.addItem(tension_axis, 4, 1)
tension_axis.linkToView(plot_spectrum.getViewBox())
tension_axis.setZValue(-1000)

def tickStrings_tension(values, scale, spacing):
    return [f"{round(spokes.tension(v))}N" for v in values]

tension_axis.tickStrings = tickStrings_tension

def update_tension_axis():
    r = plot_spectrum.getViewBox().viewRange()[0]
    tension_axis.setRange(r)

plot_spectrum.getViewBox().sigXRangeChanged.connect(update_tension_axis)

def on_data_available():
    f = on_data_available
    if not hasattr(f, "spectrum_smooth"):
        f.frequencies = np.fft.rfftfreq(FRAMES_PER_BUFFER, d=1 / SAMPLE_RATE)
        f.spectrum_smooth = np.zeros(len(f.frequencies))
        f.last_fundamental = None
        f.last_tension = None
        f.last_time = time.time()*1000
        f.last_update = time.time()*1000
        f.last_fundamentals = collections.deque(maxlen=6)

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
    f.spectrum_smooth = (1 - ALPHA_SPECTRUM)*f.spectrum_smooth + ALPHA_SPECTRUM*spectrum
    spectrum_db = f.spectrum_smooth

    peaks_fft, _ = scipy.signal.find_peaks(f.spectrum_smooth)
    peaks_fft = peaks_fft[np.argsort(-f.spectrum_smooth[peaks_fft])][:nfrequencies_fft]
    fundamentals_fft = np.array([round(f.frequencies[idx]) for idx in peaks_fft])
    fundamentals_fft = fundamentals_fft[fundamentals_fft > frequency_min]
    fundamentals_fft = fundamentals_fft[fundamentals_fft < frequency_max]

    plot_spectrum_curve.setData(f.frequencies, spectrum_db)

    correlation = np.correlate(signal, signal, mode='full')
    correlation = correlation[(len(correlation) // 2):]
    correlation[:min_lag] = 0

    correlation /= np.max(correlation)
    correlation = correlation[min_lag:max_lag]

    peaks, _ = scipy.signal.find_peaks(correlation)
    fundamentals = []
    if len(peaks) > 0:
        top_peaks = peaks[np.argsort(-correlation[peaks])[:nfrequencies_corr]]
        for p in top_peaks:
            if p <= 0 or p >= len(correlation) - 1:
                lag = p + min_lag
            else:
                y0, y1, y2 = correlation[p - 1], correlation[p], correlation[p + 1]
                d = 0.5*(y0 - y2) / (y0 - 2*y1 + y2)
                lag = (p + d) + min_lag
            fundamentals.append(round(SAMPLE_RATE / lag))

    for i in range(nfrequencies_corr):
        if i < len(fundamentals):
            frequency = fundamentals[i]
            idx = np.argmin(np.abs(f.frequencies - frequency))
            amplitude = f.spectrum_smooth[idx]
            xloc = frequency
            if USE_LOG_FREQUENCY:
                xloc = np.log10(xloc)
            correlation_texts[i].setPos(xloc, amplitude)
            correlation_texts[i].setText(f"{frequency}Hz")
        else:
            correlation_texts[i].setText("")

    for i in range(nfrequencies_fft):
        if i < len(peaks_fft):
            idx = peaks_fft[i]
            amplitude = f.spectrum_smooth[idx]
            frequency = round(f.frequencies[idx])
            if True or amplitude > 0.005:
                xloc = frequency
                if USE_LOG_FREQUENCY:
                    xloc = np.log10(xloc)
                peak_texts[i].setPos(xloc, amplitude)
                peak_texts[i].setText(f"{frequency}Hz")
            else:
                peak_texts[i].setText("")
        else:
            peak_texts[i].setText("")

    if len(fundamentals) == 0:
        return
    now = int(time.time()*1000)
    update_allowed = (now - f.last_update) > min_update_interval
    freq_diff_ok = (
        f.last_fundamental is None
        or abs(fundamentals[0] - f.last_fundamental) > min_freq_change
    )

    fft_match = any(abs(fundamentals[0] - f) < 5 for f in fundamentals_fft)

    if update_allowed and freq_diff_ok and fft_match:
        if frequency_min < fundamentals[0] < frequency_max:
            f.last_fundamentals.append(fundamentals[0])
            median_freq = np.median(f.last_fundamentals)
            tension = spokes.tension(median_freq)
            f.last_fundamental = round(median_freq)
            f.last_tension = tension
            f.last_time = now
            f.last_update = now

    if (now - f.last_time) > hold_duration:
        f.last_fundamental = None
        f.last_tension = None
        f.last_fundamentals.clear()

    if f.last_fundamental is not None:
        idx = np.argmin(np.abs(f.frequencies - f.last_fundamental))

        xloc = f.last_fundamental
        if USE_LOG_FREQUENCY:
            xloc = np.log10(xloc)
        peak_text.setPos(xloc, spectrum_db[idx])
        peak_text.setText(f"{f.last_fundamental}Hz = {f.last_tension}N")

        kgf = round(f.last_tension / 9.80665)
        indicator_text = f"{f.last_fundamental}Hz -> {f.last_tension}N = {kgf}kgf"
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

hold_duration = 2000
min_update_interval = 600
min_freq_change = 5.0

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
