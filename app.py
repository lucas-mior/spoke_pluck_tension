import numpy as np
import sounddevice as sd
import pyqtgraph
from pyqtgraph.Qt import QtCore, QtWidgets
from scipy.signal import butter, sosfilt, sosfreqz
from queue import Queue
import spokes

sample_rate = 44100
blocksize = 4096
alpha = 0.8

frequency_min = 50  #spokes.frequency(500)
frequency_max = 1500  #spokes.frequency(2000)
print(f"{frequency_min=:.1f} {frequency_max=:.1f}")

order = 5
bandpass = butter(order,
                  [frequency_min, frequency_max],
                  btype='bandpass',
                  fs=sample_rate,
                  output='sos')

frequencies = np.fft.rfftfreq(blocksize, d=1 / sample_rate)
data_queue = Queue()
spectrum_smoothed = np.zeros(len(frequencies))

qt_application = QtWidgets.QApplication([])
main_window = QtWidgets.QWidget()
main_layout = QtWidgets.QVBoxLayout()
main_window.setLayout(main_layout)

frequency_label = QtWidgets.QLabel("Frequency: -- Hz")
frequency_label.setStyleSheet("""
font-size: 22pt; color: cyan; background-color: black;
""")
main_layout.addWidget(frequency_label)

tension_label = QtWidgets.QLabel("Tension: -- N  (-- kgf)")
tension_label.setStyleSheet("""
font-size: 22pt; color: orange; background-color: black;
""")
main_layout.addWidget(tension_label)

window = pyqtgraph.GraphicsLayoutWidget()
main_layout.addWidget(window)
plot = window.addPlot(title="Frequency Spectrum (dB)")
curve = plot.plot(pen='y')
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
plot.addItem(peak_text)

plot.setLabel('left', 'Magnitude (dB)')
plot.setLabel('bottom', 'Frequency (Hz)')
plot.setXRange(0, 2000)
plot.setYRange(-100, 0)

last_valid_frequency = None
last_valid_tension = None
last_valid_time = QtCore.QTime.currentTime()
last_update_time = QtCore.QTime.currentTime()

hold_duration = 1.0         # how long to keep displaying old value
min_update_interval = 300   # milliseconds
min_freq_change = 5.0       # Hz


def detect_fundamental_autocorr(signal, fs):
    signal = signal - np.mean(signal)
    corr = np.correlate(signal, signal, mode='full')
    corr = corr[len(corr) // 2:]

    min_lag = int(fs / frequency_max)
    max_lag = int(fs / frequency_min)
    corr[:min_lag] = 0

    peak_idx = np.argmax(corr[min_lag:max_lag]) + min_lag
    if peak_idx == 0:
        return 0.0
    return fs / peak_idx


def update_plot():
    global last_valid_frequency, last_valid_tension, last_valid_time, last_update_time, spectrum_smoothed

    if data_queue.empty():
        return
    while data_queue.qsize() > 1:
        data_queue.get()
    data = data_queue.get()

    data = sosfilt(bandpass, data)
    windowed = data*np.hanning(len(data))
    spectrum = np.abs(np.fft.rfft(windowed)) / len(windowed)
    spectrum[spectrum == 0] = 1e-12
    spectrum_smoothed = (1 - alpha)*spectrum_smoothed + alpha*spectrum
    spectrum_db = 20*np.log10(spectrum_smoothed)

    curve.setData(frequencies, spectrum_db)

    now = QtCore.QTime.currentTime()
    fundamental = detect_fundamental_autocorr(data, sample_rate)

    update_allowed = last_update_time.msecsTo(now) > min_update_interval
    freq_diff_ok = (last_valid_frequency is None or abs(fundamental - last_valid_frequency) > min_freq_change)

    if frequency_min < fundamental < frequency_max and update_allowed and freq_diff_ok:
        tension = spokes.tension(fundamental)
        last_valid_frequency = fundamental
        last_valid_tension = tension
        last_valid_time = now
        last_update_time = now

    elapsed = last_valid_time.msecsTo(now) / 1000
    if elapsed > hold_duration:
        last_valid_frequency = None
        last_valid_tension = None

    if last_valid_frequency is not None:
        kgf = last_valid_tension / 9.80665
        idx = np.argmin(np.abs(frequencies - last_valid_frequency))
        y_val = spectrum_db[idx] + 5
        peak_text.setPos(last_valid_frequency, y_val)
        peak_text.setText(f"{last_valid_frequency:.1f} Hz")
        frequency_label.setText(f"Frequency: {last_valid_frequency:.1f} Hz")
        tension_label.setText(f"Tension: {last_valid_tension:.1f} N  ({kgf:.1f} kgf)")
    else:
        frequency_label.setText("Frequency: -- Hz")
        tension_label.setText("Tension: -- N  (-- kgf)")
        peak_text.setText("")

    return


def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    data_queue.put(indata[:, 0])
    return


timer = QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(33)

with sd.InputStream(callback=audio_callback,
                    channels=1,
                    samplerate=sample_rate,
                    blocksize=blocksize):
    main_window.setWindowTitle("Spoke Tension Analyzer")
    main_window.resize(800, 600)
    main_window.show()
    qt_application.exec()
