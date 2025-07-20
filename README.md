# spoke pluck tension
Measure spoke tension by the sound. Work in progress.

## Getting started
```sh
git clone https://github.com/lucas-mior/spoke_pluck_tension
cd spoke_pluck_tension
pip install -r requirements.txt
python app.py
```

## Dependencies
- python and libraries declared in `requirements.txt`
- make
- a C compiler
- rtaudio

## How are sound frequency and spoke tension related?
When you pluck a spoke, it ressonates at a frequency given by
the following:

```python
def frequency(tension, length=length0):
    return np.sqrt(tension / mu_steel) / (2 * length)
```
Where `length` is the spoke length and `mu_steel` is the longitudinal mass
density.

![Frequency x Tension](spoke_tension_frequency.png)
This graph shows the relation between tension and frequency for spokes of 2mm
diameter of multiple lengths. The highlighted areas are the typical optimal
values.

## Spokes parameters
You should set the spoke parameters in `spokes.py`. The most relevant are:
- `SPOKE_DIAMETER`: Diameter of your spokes (currently only works for straight
  spokes).
- `SPOKE_LENGTH`: Length of the spoke, from the nipple bottom until it crosses
   another spoke, if [interlaced](https://www.youtube.com/watch?v=-fX5mAOzJVU&pp=ugMICgJwdBABGAHKBRBzcG9rZXMgaW50ZXJsYWNl)),
   or until the hub flange (if not interlaced).
