import numpy as np
import matplotlib.pyplot as plt

TENSION_MIN = 400
TENSION_MAX = 2000
TENSION_AVG = round((TENSION_MIN + TENSION_MAX)/2)

STEEL_DENSITY = 7930  # kg/m³
SPOKE_DIAMETER = 0.002  # meters
SPOKE_CROSS_SECTION = np.pi*(SPOKE_DIAMETER / 2)**2
MU_STEEL_2mm = STEEL_DENSITY*SPOKE_CROSS_SECTION
SPOKE_LENGTH = 0.18


def tension(frequency, length=SPOKE_LENGTH):
    return np.int32(np.round(4*(length**2)*(frequency**2)*MU_STEEL_2mm))


def frequency(tension, length=SPOKE_LENGTH):
    return np.int32(np.round(np.sqrt(tension / MU_STEEL_2mm) / (2*length)))


if __name__ == "__main__":
    tension_values = np.linspace(start=50, stop=2000, num=1200)
    lengths = [0.15, 0.18, 0.20, 0.22, 0.25]

    acceptable_tension_min = 900
    acceptable_tension_max = 1200

    plt.figure(figsize=(8, 5))

    for length in lengths:
        freq_values = frequency(tension_values, length)
        line, = plt.plot(tension_values, freq_values, label=f'{length:.2f} m')

        color = line.get_color()

        fmin = frequency(acceptable_tension_min, length)
        fmax = frequency(acceptable_tension_max, length)

        plt.fill_betweenx(
            [fmin, fmax],
            acceptable_tension_min,
            acceptable_tension_max,
            color=color,
            alpha=0.2
        )

    plt.xlabel('Tension (N)')
    plt.ylabel('Frequency (Hz)')
    plt.title('Frequency vs. Tension for Different Spoke Lengths')
    plt.legend(title='Spoke Length')
    plt.grid(True)
    plt.tight_layout()
    plt.show()
