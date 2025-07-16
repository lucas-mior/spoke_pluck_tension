import numpy as np

steel_density = 8000  # kg/m³
spoke_diameter = 0.002  # meters (only after crossing)
spoke_area = np.pi*(spoke_diameter / 2)**2
mu_inox_2mm = steel_density*spoke_area

spoke_length = 0.20  # meters

def compute_tension(frequency):
    return 4 * (spoke_length ** 2) * (frequency ** 2) * mu_inox_2mm

def compute_frequency(tension):
    return (1 / (2 * spoke_length)) * np.sqrt(tension / mu_inox_2mm)

Tmin = 980  # Newtons
Tmax = 1275  # Newtons

Fmin = round(compute_frequency(Tmin))
Fmax = round(compute_frequency(Tmax))

Tmin2 = round(compute_tension(Fmin))
Tmax2 = round(compute_tension(Fmax))

print(f"Frequency(Tmin={Tmin} N) = Fmin={Fmin} Hz")
print(f"Frequency(Tmax={Tmax} N) = Fmax={Fmax} Hz")
print(f"Tension(Fmin={Fmin} Hz) = Tmin2={Tmin2} N")
print(f"Tension(Fmax={Fmax} Hz) = Tmax2={Tmax2} N")
