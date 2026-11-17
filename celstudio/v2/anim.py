"""Keyframe tracks with easing. Deterministic, random-access in time."""
import bisect
import math


def _back_out(u, s=1.70158):
    u -= 1
    return u*u*((s+1)*u+s)+1


def _back_in(u, s=1.70158):
    return u*u*((s+1)*u-s)


def _elastic(u):
    if u <= 0 or u >= 1:
        return float(u >= 1)
    return 2**(-9*u)*math.sin((u-0.08)*2*math.pi/0.32)+1


def _bounce(u):
    n, d = 7.5625, 2.75
    if u < 1/d:
        return n*u*u
    if u < 2/d:
        u -= 1.5/d
        return n*u*u+.75
    if u < 2.5/d:
        u -= 2.25/d
        return n*u*u+.9375
    u -= 2.625/d
    return n*u*u+.984375


EASES = {
    'linear': lambda u: u,
    'smooth': lambda u: u*u*(3-2*u),
    'in': lambda u: u*u*u,
    'out': lambda u: 1-(1-u)**3,
    'inout': lambda u: 4*u*u*u if u < .5 else 1-(-2*u+2)**3/2,
    'sine': lambda u: .5-.5*math.cos(math.pi*u),
    'back': _back_out,                      # overshoot then settle
    'soft': lambda u: _back_out(u, .9),     # light overshoot
    'backin': _back_in,                     # anticipation
    'elastic': _elastic,
    'bounce': _bounce,
    'snap': lambda u: 1-2**(-9*u) if u < 1 else 1.0,
    'step': lambda u: 1.0 if u >= 1 else 0.0,
}


class Track:
    """Keys are [t, value] or [t, value, ease]; `ease` shapes the arrival at that key."""
    __slots__ = ('times', 'values', 'eases', 'discrete')

    def __init__(self, keys):
        keys = sorted(keys, key=lambda k: k[0])
        self.times = [k[0] for k in keys]
        self.values = [k[1] for k in keys]
        self.eases = [k[2] if len(k) > 2 else 'smooth' for k in keys]
        self.discrete = any(isinstance(v, str) for v in self.values)

    def at(self, t):
        times = self.times
        i = bisect.bisect_right(times, t)
        if i <= 0:
            return self.values[0]
        if i >= len(times):
            return self.values[-1]
        if self.discrete:
            return self.values[i-1]
        a, b = self.values[i-1], self.values[i]
        if a == b:
            return a
        u = (t-times[i-1])/(times[i]-times[i-1])
        return a+(b-a)*EASES[self.eases[i]](u)


def hash01(*parts):
    """Stable pseudo-random in [0,1) from integers/floats (no global state)."""
    h = 2166136261
    for p in parts:
        for byte in repr(p).encode():
            h = ((h ^ byte)*16777619) & 0xffffffff
    h ^= h >> 15
    h = (h*2246822519) & 0xffffffff
    h ^= h >> 13
    return h/4294967296


def noise1(t, seed=0):
    """Smooth value noise, roughly in [-1,1], unit frequency."""
    i = math.floor(t)
    u = t-i
    u = u*u*(3-2*u)
    a, b = hash01(seed, i)*2-1, hash01(seed, i+1)*2-1
    return a+(b-a)*u
