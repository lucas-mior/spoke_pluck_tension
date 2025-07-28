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

ALPHA_SPECTRUM = 0.5
DEBUG = False

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
main_window.setWindowTitle("spoke_pluck_tension")
main_window.resize(1000, 600)
main_window.show()

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

layout_plots = pyqtgraph.GraphicsLayoutWidget()
plot_spectrum = layout_plots.addPlot(title="Frequency Spectrum")
plot_spectrum_curve = plot_spectrum.plot(
    pen=pyqtgraph.mkPen('y', width=3, join=Qt.PenJoinStyle.RoundJoin)
)
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
peak_text.setFont(QFont('LiberationSans', 18))
plot_spectrum.addItem(peak_text)
plot_spectrum.setYRange(0, 0.1)
plot_spectrum.showGrid(x=True, y=True)

layout_with_slider = QtWidgets.QHBoxLayout()

yscale_slider = QtWidgets.QSlider(Qt.Orientation.Vertical)
yscale_slider.setMinimum(1)
yscale_slider.setMaximum(100)
yscale_slider.setValue(50)
yscale_slider.setFixedWidth(40)
layout_with_slider.addWidget(yscale_slider)

layout_with_slider.addWidget(layout_plots)
main_layout.addLayout(layout_with_slider)

spoke_input_layout = QtWidgets.QHBoxLayout()
spoke_label = QtWidgets.QLabel("Spoke Length (cm):")
spoke_input = QtWidgets.QLineEdit()
spoke_input.setPlaceholderText(f"{round(spokes.SPOKE_LENGTH*100, 1)}")
spoke_input.returnPressed.connect(lambda: update_spoke_length(spoke_input.text()))

spoke_input_layout.addWidget(spoke_label)
spoke_input_layout.addWidget(spoke_input)
main_layout.addLayout(spoke_input_layout)

def update_spoke_length(text):
    try:
        value = float(text)
    except Exception:
        QtWidgets.QMessageBox.warning(main_window,
                                      "Invalid Input",
                                      "Enter spoke length in centimeters.")
        return

    if value <= 1 or value >= 100:
        QtWidgets.QMessageBox.warning(main_window,
                                      "Invalid Input",
                                      f"Invalid spoke length: {value}cm.")
        return

    spokes.SPOKE_LENGTH = value/100
    spoke_input.setPlaceholderText(f"{value}")
    return

def on_yscale_changed():
    global amplitude_min

    v = yscale_slider.value()
    amplitude_min = v/2e4
    plot_spectrum.setYRange(0, v / 2000)
    return


yscale_slider.valueChanged.connect(on_yscale_changed)
on_yscale_changed()

peak_texts = []
corr_texts = []

npeaks_corr = 3
for i in range(npeaks_corr):
    text_item = pyqtgraph.TextItem('',anchor=(0.5, 2.5), color='green')
    text_item.setFont(QFont('LiberationSans', 18))
    corr_texts.append(text_item)
    plot_spectrum.addItem(corr_texts[i])

npeaks_fft = 5
for i in range(npeaks_fft):
    text_item = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='red')
    text_item.setFont(QFont('LiberationSans', 18))
    peak_texts.append(text_item)
    plot_spectrum.addItem(peak_texts[i])

frequency_axis = pyqtgraph.AxisItem(orientation='bottom', maxTickLength=-5)
def tickStrings_frequency(values, scale, spacing):
    return [f"{round(v)}Hz" for v in values]
frequency_axis.tickStrings = tickStrings_frequency
plot_spectrum.setAxisItems({'bottom': frequency_axis})
frequency_axis.setGrid(100)

tension_newton_axis = pyqtgraph.AxisItem(orientation='bottom', maxTickLength=0)
def tickStrings_tension(values, scale, spacing):
    return [f"{round(spokes.tension(v))}N" for v in values]
tension_newton_axis.tickStrings = tickStrings_tension
plot_spectrum.layout.addItem(tension_newton_axis, 4, 1)
tension_newton_axis.linkToView(plot_spectrum.getViewBox())

tension_kgf_axis = pyqtgraph.AxisItem(orientation='bottom', maxTickLength=0)
def tickStrings_tension_kgf(values, scale, spacing):
    return [f"{newton2kgf(spokes.tension(v))}kgf" for v in values]
tension_kgf_axis.tickStrings = tickStrings_tension_kgf
plot_spectrum.layout.addItem(tension_kgf_axis, 5, 1)
tension_kgf_axis.linkToView(plot_spectrum.getViewBox())

def on_data_available():
    f = on_data_available
    if not hasattr(f, "spectrum_smooth"):
        f.frequencies = np.fft.rfftfreq(FRAMES_PER_BUFFER, d=1 / SAMPLE_RATE)
        f.spectrum_smooth = np.zeros(len(f.frequencies))
        f.last_fundamental = None
        f.last_tension = None
        f.last_time = time.time()*1000
        f.last_update = time.time()*1000
        f.last_fundamentals = collections.deque(maxlen=1)

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
    peaks_fft = peaks_fft[np.argsort(-f.spectrum_smooth[peaks_fft])][:npeaks_fft]
    fundamentals_fft = np.array([round(f.frequencies[idx]) for idx in peaks_fft])
    fundamentals_fft = fundamentals_fft[fundamentals_fft > frequency_min]
    fundamentals_fft = fundamentals_fft[fundamentals_fft < frequency_max]

    plot_spectrum_curve.setData(f.frequencies, spectrum_db)

    corr = np.correlate(signal, signal, mode='full')
    corr = corr[(len(corr) // 2):]
    corr[:min_lag] = 0

    if corr_max := np.max(corr) > 0:
        corr /= corr_max
    else:
        return

    corr = corr[min_lag:max_lag]

    peaks_corr, _ = scipy.signal.find_peaks(corr)
    fundamentals = []
    if len(peaks_corr) > 0:
        top_peaks = peaks_corr[np.argsort(-corr[peaks_corr])[:npeaks_corr]]
        for p in top_peaks:
            if p <= 0 or p >= len(corr) - 1:
                lag = p + min_lag
            else:
                y0, y1, y2 = corr[p - 1], corr[p], corr[p + 1]
                d = 0.5*(y0 - y2) / (y0 - 2*y1 + y2)
                lag = (p + d) + min_lag
            fundamentals.append(round(SAMPLE_RATE / lag))

    if DEBUG:
        for i in range(npeaks_corr):
            if i < len(fundamentals):
                frequency = fundamentals[i]
                idx = np.argmin(np.abs(f.frequencies - frequency))
                amplitude = f.spectrum_smooth[idx]
                if amplitude > 0.001:
                    corr_texts[i].setPos(frequency, amplitude)
                    corr_texts[i].setText(f"{frequency}Hz")
                else:
                    corr_texts[i].setText("")
            else:
                corr_texts[i].setText("")

        for i in range(npeaks_fft):
            if i < len(peaks_fft):
                idx = peaks_fft[i]
                amplitude = f.spectrum_smooth[idx]
                frequency = round(f.frequencies[idx])
                if amplitude > 0.001:
                    peak_texts[i].setPos(frequency, amplitude)
                    peak_texts[i].setText(f"{frequency}Hz")
                else:
                    peak_texts[i].setText("")
            else:
                peak_texts[i].setText("")

    if len(fundamentals) == 0:
        return

    now = int(time.time()*1000)
    update_allowed = (now - f.last_update) > min_update_interval

    matched = None
    for f_corr in fundamentals:
        for f_fft in fundamentals_fft:
            idx = np.argmin(np.abs(f.frequencies - f_fft))
            A = f.spectrum_smooth[idx]
            if abs(f_corr - f_fft) < 10 and A > amplitude_min:
                matched = f_corr
                break

    if matched and update_allowed:
        if frequency_min < matched < frequency_max:
            f.last_fundamentals.append(matched)
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
        kgf = newton2kgf(f.last_tension)
        indicator_text = f"{f.last_fundamental}Hz -> {f.last_tension}N = {kgf}kgf"

        peak_text.setPos(xloc, spectrum_db[idx])
        peak_text.setText(indicator_text)
    else:
        peak_text.setText("")

    return


def newton2kgf(TN):
    return round(TN / 9.80665)


def on_slider_changed():
    global frequency_min, frequency_max
    global min_lag, max_lag
    global plot_spectrum

    t0 = round(min_slider.value())
    t1 = round(max_slider.value())
    frequency_min = spokes.frequency(t0)
    frequency_max = spokes.frequency(t1)
    f0 = frequency_min
    f1 = frequency_max
    min_lag = round(SAMPLE_RATE / f1)
    max_lag = round(SAMPLE_RATE / f0)

    min_label.setText(f"Min Tension: {t0}N")
    max_label.setText(f"Max Tension: {t1}N")

    plot_spectrum.setLogMode(x=False, y=False)
    plot_spectrum.setXRange(f0, f1)
    tick_spacing = (frequency_max - frequency_min) / 10
    plot_spectrum.getAxis('bottom').setTickSpacing(major=tick_spacing,
                                                   minor=tick_spacing / 10)
    tension_newton_axis.setTickSpacing(major=tick_spacing,
                                       minor=tick_spacing / 10)
    tension_kgf_axis.setTickSpacing(major=tick_spacing,
                                    minor=tick_spacing / 10)

    tension_kgf_axis.setHeight(30)
    return


min_slider.valueChanged.connect(on_slider_changed)
max_slider.valueChanged.connect(on_slider_changed)

on_slider_changed()

hold_duration = 2000
min_update_interval = 600

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

poller = select.poll()
poller.register(fifo_fd, select.POLLIN)

while main_window.isVisible():
    events = poller.poll(1000)
    if events:
        on_data_available()
    QtWidgets.QApplication.processEvents()
