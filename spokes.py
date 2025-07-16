import numpy as np

steel_density = 8000  # kg/m³
diameter = 0.002  # meters
length = 0.20  # meters
spoke_area = np.pi*(diameter / 2) ** 2
mu_steel_2mm = steel_density*spoke_area


def frequency(tension):
    return np.sqrt(tension / mu_steel_2mm)/(2*length)


def tension(frequency):
    return 4*(length**2)*(frequency**2)*mu_steel_2mm
