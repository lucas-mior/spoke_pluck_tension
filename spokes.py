import numpy as np
import sounddevice as sd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from scipy.signal import butter, sosfilt
from queue import Queue

sample_rate = 44100
blocksize = 4096

steel_density = 8000  # kg/m³
spoke_diameter = 0.002  # meters (2mm)
spoke_area = np.pi*(spoke_diameter / 2) ** 2
mu_inox_2mm = steel_density*spoke_area
spoke_length = 0.20  # meters

def compute_frequency(tension):
    return (1/(2*spoke_length))*np.sqrt(tension / mu_inox_2mm)

f_low = compute_frequency(500)   # ~250 Hz
f_high = compute_frequency(2000) # ~500 Hz
print(f"{f_low=} {f_high=}")

band = [f_low, f_high]
sos = butter(5, band, btype='bandpass', fs=sample_rate, output='sos')

freqs = np.fft.rfftfreq(blocksize, d=1 / sample_rate)
q = Queue()
app = QtWidgets.QApplication([])

main_window = QtWidgets.QWidget()
main_layout = QtWidgets.QVBoxLayout()
main_window.setLayout(main_layout)

freq_label = QtWidgets.QLabel("Frequency: -- Hz")
freq_label.setStyleSheet("font-size: 24pt; color: cyan; background-color: black;")
main_layout.addWidget(freq_label)

tension_label = QtWidgets.QLabel("Tension: -- N  (-- kgf)")
tension_label.setStyleSheet("font-size: 18pt; color: orange; background-color: black;")
main_layout.addWidget(tension_label)

win = pg.GraphicsLayoutWidget()
main_layout.addWidget(win)
plot = win.addPlot(title="Frequency Spectrum (dB)")
curve = plot.plot(pen='y')
peak_text = pg.TextItem('', anchor=(0.5, 1.5), color='cyan')
plot.addItem(peak_text)

plot.setLabel('left', 'Magnitude (dB)')
plot.setLabel('bottom', 'Frequency (Hz)')
plot.setXRange(0, 1500)
plot.setYRange(-100, 0)

def compute_tension(frequency):
    return 4*(spoke_length**2)*(frequency**2)*mu_inox_2mm

def detect_fundamental_autocorr(signal, fs):
    signal = signal - np.mean(signal)
    corr = np.correlate(signal, signal, mode='full')
    corr = corr[len(corr)//2:]

    min_lag = int(fs / f_high)
    max_lag = int(fs / f_low)
    corr[:min_lag] = 0

    peak_idx = np.argmax(corr[min_lag:max_lag]) + min_lag
    if peak_idx == 0:
        return 0.0
    return fs / peak_idx

last_valid_frequency = None
last_valid_tension = None
last_valid_time = QtCore.QTime.currentTime()
hold_duration = 1.0  # seconds

def update_plot():
    global last_valid_frequency, last_valid_tension, last_valid_time

    if q.empty():
        return
    data = q.get()

    filtered = sosfilt(sos, data)
    windowed = filtered*np.hanning(len(filtered))
    spectrum = np.abs(np.fft.rfft(windowed)) / len(windowed)
    spectrum[spectrum == 0] = 1e-12
    spectrum_db = 20*np.log10(spectrum)

    curve.setData(freqs, spectrum_db)

    fundamental = detect_fundamental_autocorr(filtered, sample_rate)
    if f_low < fundamental < f_high:
        tension = compute_tension(fundamental)
        last_valid_frequency = fundamental
        last_valid_tension = tension
        last_valid_time = QtCore.QTime.currentTime()
    else:
        elapsed = last_valid_time.msecsTo(QtCore.QTime.currentTime()) / 1000
        if elapsed > hold_duration:
            last_valid_frequency = None
            last_valid_tension = None

    if last_valid_frequency:
        kgf = last_valid_tension / 9.80665
        peak_text.setPos(last_valid_frequency, -10)
        peak_text.setText(f"{last_valid_frequency:.1f} Hz")
        freq_label.setText(f"Frequency: {last_valid_frequency:.1f} Hz")
        tension_label.setText(f"Tension: {last_valid_tension:.1f} N  ({kgf:.1f} kgf)")
    else:
        freq_label.setText("Frequency: -- Hz")
        tension_label.setText("Tension: -- N  (-- kgf)")
        peak_text.setText("")

    plot.setYRange(-100, max(-30, np.max(spectrum_db) + 10))

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    q.put(indata[:, 0].copy())

timer = QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(30)

with sd.InputStream(callback=audio_callback,
                    channels=1,
                    samplerate=sample_rate,
                    blocksize=blocksize,
                    latency=0.1):
    main_window.setWindowTitle("Spoke Tension Analyzer")
    main_window.resize(800, 600)
    main_window.show()
    app.exec()
