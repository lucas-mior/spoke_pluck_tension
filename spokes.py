import numpy as np
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 14})

TENSION_MIN = 300
TENSION_MAX = 2000
TENSION_AVG = round((TENSION_MIN + TENSION_MAX)/2)

STEEL_DENSITY = 7930  # kg/m³
SPOKE_DIAMETER = 0.002  # meters
SPOKE_CROSS_SECTION = np.pi*(SPOKE_DIAMETER / 2)**2
MU_STEEL_2mm = STEEL_DENSITY*SPOKE_CROSS_SECTION
SPOKE_LENGTH = 0.18


def update_length(new_length):
    global SPOKE_LENGTH
    SPOKE_LENGTH = new_length
    return


def tension(frequency):
    length = SPOKE_LENGTH
    return np.int32(np.round(4*(length**2)*(frequency**2)*MU_STEEL_2mm))


def frequency(tension):
    length = SPOKE_LENGTH
    return np.int32(np.round(np.sqrt(tension / MU_STEEL_2mm) / (2*length)))


def newton2kgf(TN):
    return TN / 9.80665


def kgf2newton(Tkgf):
    return Tkgf * 9.80665


if __name__ == "__main__":
    tension_values = np.linspace(start=250, stop=2000, num=1200)
    lengths = [0.10, 0.15, 0.18, 0.20, 0.22, 0.25, 0.30]

    acceptable_tension_min = 900
    acceptable_tension_max = 1200

    fig, ax_n = plt.subplots(figsize=(8, 8))

    for i, length in enumerate(lengths):
        freq_values = frequency(tension_values, length)
        if i % 2 == 0:
            linestyle = '-'
        else:
            linestyle = '--'
        line, = ax_n.plot(tension_values, freq_values,
                          label=f'{length * 100:.0f} cm',
                          linewidth=2, linestyle=linestyle)

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

    ax_n.xaxis.set_label_position('top')
    ax_n.xaxis.tick_top()
    ax_n.set_xlabel('Tension (N)', labelpad=10)
    ax_n.set_ylabel('Frequency (Hz)')
    ax_n.grid(True)

    ax_kgf = ax_n.secondary_xaxis(
        location='bottom',
        functions=(newton2kgf, kgf2newton)
    )
    ax_kgf.set_xlabel("Tension (kgf)")

    note_names = ['C', 'C#',
                  'D', 'D#',
                  'E',
                  'F', 'F#',
                  'G', 'G#',
                  'A', 'A#',
                  'B']
    start_freq = 195.99772  # G3
    start_index = note_names.index('G')
    start_octave = 3

    freqs = []
    labels = []
    freq = start_freq
    index = start_index
    octave = start_octave
    while freq <= ax_n.get_ylim()[1]:
        name = note_names[index] + str(octave)
        freqs.append(freq)
        labels.append(name)
        freq *= 2 ** (1/12)
        index += 1
        if index == 12:
            index = 0
            octave += 1

    for i, (f, label) in enumerate(zip(freqs, labels)):
        if i % 2 == 0:
            align = 'right'
            x = -0.01
        else:
            align = 'left'
            x = 0.01
        ax_n.axhline(f, linestyle='--', color='gray', linewidth=0.5, alpha=0.3)
        ax_n.text(
            x=1.0+x, y=f, s=label,
            transform=ax_n.get_yaxis_transform(),
            va='center',
            ha=align,
            fontsize=12,
            clip_on=False
        )

    handles, labels = ax_n.get_legend_handles_labels()
    ax_n.legend(handles, labels, title='Spoke Length')
    fig.tight_layout()
    plt.show()
