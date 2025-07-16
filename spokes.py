import numpy as np
import sounddevice as sd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from scipy.signal import butter, sosfilt
from queue import Queue

sample_rate = 44100
blocksize = 4096
cutoff_freq = 1500

freqs = np.fft.rfftfreq(blocksize, d=1 / sample_rate)
sos = butter(5, cutoff_freq, btype='low', fs=sample_rate, output='sos')
q = Queue()

app = QtWidgets.QApplication([])

main_window = QtWidgets.QWidget()
main_layout = QtWidgets.QVBoxLayout()
main_window.setLayout(main_layout)

freq_label = QtWidgets.QLabel("Frequency: -- Hz")
freq_label.setStyleSheet("font-size: 24pt; color: cyan; background-color: black;")
main_layout.addWidget(freq_label)

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

def detect_fundamental_autocorr(signal, fs):
    signal = signal - np.mean(signal)
    corr = np.correlate(signal, signal, mode='full')
    corr = corr[len(corr)//2:]

    min_lag = int(fs / 1400)  # max frequency ~1400 Hz
    max_lag = int(fs / 70)    # min frequency ~70 Hz
    corr[:min_lag] = 0

    peak_idx = np.argmax(corr[min_lag:max_lag]) + min_lag
    if peak_idx == 0:
        return 0.0
    return fs / peak_idx

def update_plot():
    if q.empty():
        return
    data = q.get()

    filtered = sosfilt(sos, data)
    windowed = filtered * np.hanning(len(filtered))
    spectrum = np.abs(np.fft.rfft(windowed)) / len(windowed)
    spectrum[spectrum == 0] = 1e-12
    spectrum_db = 20 * np.log10(spectrum)

    curve.setData(freqs, spectrum_db)

    fundamental = detect_fundamental_autocorr(filtered, sample_rate)
    if 70 < fundamental < 1400:
        peak_text.setPos(fundamental, -10)
        peak_text.setText(f"{fundamental:.1f} Hz")
        freq_label.setText(f"Frequency: {fundamental:.1f} Hz")
    else:
        freq_label.setText("Frequency: -- Hz")

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
    main_window.setWindowTitle("Guitar Frequency Analyzer")
    main_window.resize(800, 600)
    main_window.show()
    app.exec()
