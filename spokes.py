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


def newton2kgf(t):
    return t / 9.80665


if __name__ == "__main__":
    tension_values = np.linspace(start=50, stop=2000, num=1200)
    lengths = [0.15, 0.18, 0.20, 0.22, 0.25]

    acceptable_tension_min = 900
    acceptable_tension_max = 1200

    fig, ax_n = plt.subplots(figsize=(8, 5))

    for length in lengths:
        freq_values = frequency(tension_values, length)
        line, = ax_n.plot(tension_values, freq_values, label=f'{length:.2f} m')

        color = line.get_color()

        fmin = frequency(acceptable_tension_min, length)
        fmax = frequency(acceptable_tension_max, length)

        ax_n.fill_betweenx(
            [fmin, fmax],
            acceptable_tension_min,
            acceptable_tension_max,
            color=color,
            alpha=0.2
        )

    ax_n.set_xlabel('Tension (N)')
    ax_n.set_ylabel('Frequency (Hz)')
    ax_n.set_title('Frequency vs. Tension for Different Spoke Lengths')
    ax_n.grid(True)

    ax_kgf = ax_n.secondary_xaxis(
        location='bottom',
        functions=(newton2kgf, lambda kgf: kgf * 9.80665)
    )
    ax_kgf.set_xlabel("Tension (kgf)")

    ax_n.spines['bottom'].set_position(('outward', 30))

    ax_n.legend(title='Spoke Length')
    fig.tight_layout()
    plt.show()
