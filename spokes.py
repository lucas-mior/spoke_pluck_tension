import numpy as np
import matplotlib.pyplot as plt

steel_density = 8000  # kg/m³
diameter = 0.002  # meters
spoke_area = np.pi * (diameter / 2) ** 2
mu_steel_2mm = steel_density * spoke_area
length0=0.20


def tension(frequency, length=length0):
    return int(round(4*(length**2)*(frequency**2)*mu_steel_2mm))


def frequency(tension, length=length0):
    return int(round(np.sqrt(tension / mu_steel_2mm) / (2 * length)))


if __name__ == "__main__":
    tension_values = np.linspace(50, 3000, 500)
    lengths = [0.15, 0.18, 0.20, 0.22, 0.25]

    acceptable_tension_min = 900
    acceptable_tension_max = 1200

    plt.figure(figsize=(8, 5))

    for length in lengths:
        freq_values = frequency(tension_values, length)
        line, = plt.plot(tension_values, freq_values, label=f'{length:.2f} m')

        # Same color as line
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
