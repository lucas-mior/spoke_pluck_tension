import numpy as np
import sounddevice as sd
import soundfile as sf
import pyqtgraph
from pyqtgraph.Qt import QtCore, QtWidgets
import scipy
import queue

import spokes

use_microphone = False
sample_rate = 44100
blocksize = 4096
alpha = 0.5

frequency_min = 30
frequency_max = 1500
print(f"{frequency_min=:.1f} {frequency_max=:.1f}")

order = 5
bandpass = scipy.signal.butter(order,
                               [frequency_min, frequency_max],
                               btype='bandpass',
                               fs=sample_rate,
                               output='sos')

frequencies = np.fft.rfftfreq(blocksize, d=1 / sample_rate)
data_queue = queue.Queue()
spectrum_smoothed = np.zeros(len(frequencies))
spectrum_max = 0

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
plot.setLogMode(x=True, y=False)
curve = plot.plot(pen='y')
peak_text = pyqtgraph.TextItem('', anchor=(0.5, 1.5), color='cyan')
plot.addItem(peak_text)

plot.setLabel('left', 'Magnitude (dB)')
plot.setLabel('bottom', 'Frequency (Hz)')
plot.setXRange(1, 3.3)
xticks = [
    [
     (np.log10(10), '10'),
     (np.log10(20), '20'),
     (np.log10(50), '50'),
     (np.log10(100), '100'),
     (np.log10(200), '200'),
     (np.log10(500), '500'),
     (np.log10(1000), '1000'),
     (np.log10(2000), '2000')]
]
plot.getAxis('bottom').setTicks(xticks)
plot.setYRange(-100, 0)

last_valid_frequency = None
last_valid_tension = None
last_valid_time = QtCore.QTime.currentTime()
last_update_time = QtCore.QTime.currentTime()

hold_duration = 1000
min_update_interval = 300
min_freq_change = 5.0

min_lag = int(sample_rate / frequency_max)
max_lag = int(sample_rate / frequency_min)


def detect_fundamental_autocorrelation(signal, sample_rate):
    signal = signal - np.mean(signal)

    correlation = np.correlate(signal, signal, mode='full')
    correlation = correlation[len(correlation) // 2:]
    correlation[:min_lag] = 0

    peak_idx = np.argmax(correlation[min_lag:max_lag]) + min_lag
    if peak_idx == 0:
        return 0.0

    return sample_rate / peak_idx


def update_plot():
    global last_valid_frequency, last_valid_tension
    global last_valid_time, last_update_time
    global spectrum_smoothed, spectrum_max

    if data_queue.empty():
        return
    data = data_queue.get()

    data = scipy.signal.sosfilt(bandpass, data)
    windowed = data*np.hanning(len(data))
    spectrum = np.abs(np.fft.rfft(windowed)) / len(windowed)
    spectrum[spectrum == 0] = 1e-12
    spectrum_smoothed = (1 - alpha)*spectrum_smoothed + alpha*spectrum
    spectrum_db = 20*np.log10(spectrum_smoothed)
    if max(spectrum_db) > spectrum_max:
        spectrum_max = max(spectrum_db)
    plot.setYRange(-100, spectrum_max)

    curve.setData(frequencies, spectrum_db)

    now = QtCore.QTime.currentTime()
    fundamental = detect_fundamental_autocorrelation(data, sample_rate)

    update_allowed = last_update_time.msecsTo(now) > min_update_interval
    freq_diff_ok = False
    if last_valid_frequency is None:
        freq_diff_ok = True
    elif abs(fundamental - last_valid_frequency) > min_freq_change:
        freq_diff_ok = True

    if frequency_min < fundamental < frequency_max and update_allowed and freq_diff_ok:
        tension = spokes.tension(fundamental)
        last_valid_frequency = fundamental
        last_valid_tension = tension
        last_valid_time = now
        last_update_time = now

    if last_valid_time.msecsTo(now) > hold_duration:
        last_valid_frequency = None
        last_valid_tension = None

    if last_valid_frequency is not None:
        kgf = last_valid_tension / 9.80665
        idx = np.argmin(np.abs(frequencies - last_valid_frequency))
        y_val = spectrum_db[idx] + 5
        peak_text.setPos(np.log10(last_valid_frequency), y_val)
        peak_text.setText(f"{last_valid_frequency:.0f} Hz")
        frequency_label.setText(f"Frequency: {last_valid_frequency:.0f} Hz")
        tension_label.setText(f"Tension: {last_valid_tension:.0f} N  ({kgf:.0f} kgf)")
    else:
        frequency_label.setText("Frequency: -- Hz")
        tension_label.setText("Tension: -- N  (-- kgf)")
        peak_text.setText("")

    return


frame_index = 0
if not use_microphone:
    audio_data, file_sample_rate = sf.read("output.wav", dtype='int16')
    if file_sample_rate != sample_rate:
        print(f"Sample rate mismatch: {file_sample_rate} != {sample_rate}")
        exit(1)

    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1)

    def stream_from_file():
        global frame_index
        if frame_index + blocksize >= len(audio_data):
            timer.stop()
            return
        block = audio_data[frame_index:frame_index + blocksize]
        frame_index += blocksize
        data_queue.put(block)

else:
    def audio_callback(indata, frames, time, status):
        if status:
            print(status)
        data_queue.put(indata[:, 0])
        return

    input_stream = sd.InputStream(callback=audio_callback,
                                  channels=1,
                                  samplerate=sample_rate,
                                  blocksize=blocksize)
    input_stream.start()
    stream_from_file = lambda: None  # Dummy function


timer = QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.timeout.connect(stream_from_file)
timer.start(int(1000*blocksize / sample_rate))

main_window.setWindowTitle("Spoke Tension Analyzer")
main_window.resize(800, 600)
main_window.show()
qt_application.exec()
