import numpy as np
import sys

steel_density = 8000  # kg/m³
diameter = 0.002  # meters
length = 0.20  # meters
spoke_area = np.pi*(diameter / 2) ** 2
mu_steel_2mm = steel_density*spoke_area


def frequency(tension):
    return np.sqrt(tension / mu_steel_2mm)/(2*length)


def tension(frequency):
    return 4*(length**2)*(frequency**2)*mu_steel_2mm


if __name__ == '__main__':
    Tmin = 500  # Newtons
    Tmax = 2000  # Newtons

    if len(sys.argv) >= 3:
        Tmax = sys.argv[2]
    elif len(sys.argv) == 2:
        Tmin = sys.argv[1]

    Fmin = round(frequency(Tmin))
    Fmax = round(frequency(Tmax))

    Tmin2 = round(tension(Fmin))
    Tmax2 = round(tension(Fmax))

    print(f"Frequency(Tmin={Tmin} N) = Fmin={Fmin} Hz")
    print(f"Frequency(Tmax={Tmax} N) = Fmax={Fmax} Hz")
    print(f"Tension(Fmin={Fmin} Hz) = Tmin2={Tmin2} N")
    print(f"Tension(Fmax={Fmax} Hz) = Tmax2={Tmax2} N")
