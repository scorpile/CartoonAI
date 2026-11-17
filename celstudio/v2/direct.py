"""Authoring helpers: turn acting verbs into explicit channel keyframes (plain data for the engine).

Nothing here runs at render time. A build script uses these to write film.json.
"""
import functools
import inspect
import math
from .anim import Track, EASES
from .puppet import DEFAULTS


def jsonable(value):
    if isinstance(value, (Take, Prop)):
        return value.ref
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


def recorded(method):
    """Mark a method as a screenplay verb. Top-level calls (not those made by other verbs) are logged on the shot."""
    signature = inspect.signature(method)

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        film = self.shot.film
        if film.depth == 0:
            action = {'on': self.ref, 'do': method.__name__}
            for name, value in list(signature.bind(self, *args, **kwargs).arguments.items())[1:]:
                kind = signature.parameters[name].kind
                if kind is inspect.Parameter.VAR_KEYWORD:
                    action.update(jsonable(value))
                elif kind is not inspect.Parameter.VAR_POSITIONAL or value:
                    action[name] = jsonable(value)
            self.shot.script['actions'].append(action)
        film.depth += 1
        try:
            return method(self, *args, **kwargs)
        finally:
            film.depth -= 1
    wrapper.verb = True
    return wrapper


def call_verb(target, verb, args):
    """Replay one recorded action: arguments by name, `*args` verbs take a list under their parameter name."""
    method = getattr(target, verb)
    args = dict(args)
    params = list(inspect.signature(method).parameters.values())
    var = next((p for p in params if p.kind is inspect.Parameter.VAR_POSITIONAL), None)
    if var is None:
        return method(**args)
    lead = []
    for p in params[:params.index(var)]:
        if p.name not in args:
            break
        lead.append(args.pop(p.name))
    return method(*lead, *args.pop(var.name, []), **args)

EXPRESSIONS = {
    'neutral': dict(smile=.6, mouth_open=0, mouth_w=1, mouth_round=0, brow_y=0, brow_rot=0, eye_open=1, squint=0, lid=0, pupil=1),
    'soft': dict(smile=.85, mouth_open=0, mouth_w=1.05, mouth_round=0, brow_y=.15, brow_rot=3, eye_open=1, squint=.18, lid=.1, pupil=1.04),
    'happy': dict(smile=1, mouth_open=.55, mouth_w=1.1, mouth_round=0, brow_y=.45, brow_rot=0, eye_open=1.04, squint=.2, lid=0, pupil=1.05),
    'joy': dict(smile=1, mouth_open=.85, mouth_w=1.2, mouth_round=0, brow_y=.6, brow_rot=4, eye_open=1, squint=1, lid=.42, pupil=1),
    'surprise': dict(smile=0, mouth_open=.62, mouth_w=.42, mouth_round=1, brow_y=1.15, brow_rot=4, eye_open=1.2, squint=0, lid=0, pupil=.74),
    'awe': dict(smile=.45, mouth_open=.38, mouth_w=.62, mouth_round=.7, brow_y=.85, brow_rot=6, eye_open=1.14, squint=0, lid=0, pupil=1.12),
    'curious': dict(smile=.25, mouth_open=0, mouth_w=.72, mouth_round=0, brow_y=.6, brow_rot=7, eye_open=1.08, squint=0, lid=0, pupil=1),
    'worried': dict(smile=-.45, mouth_open=0, mouth_w=.7, mouth_round=0, brow_y=.35, brow_rot=16, eye_open=1.06, squint=0, lid=0, pupil=.9),
    'oops': dict(smile=-.25, mouth_open=.3, mouth_w=.8, mouth_round=.3, brow_y=.5, brow_rot=14, eye_open=1.12, squint=0, lid=0, pupil=.82),
    'smug': dict(smile=.8, mouth_open=0, mouth_w=.95, mouth_round=0, brow_y=-.15, brow_rot=-4, eye_open=1, squint=.1, lid=.42, pupil=1),
    'focus': dict(smile=.1, mouth_open=0, mouth_w=.6, mouth_round=0, brow_y=-.25, brow_rot=-10, eye_open=.96, squint=.12, lid=.12, pupil=.95),
    'still': dict(smile=.05, mouth_open=0, mouth_w=.5, mouth_round=0, brow_y=.7, brow_rot=5, eye_open=1.16, squint=0, lid=0, pupil=.8),
}

# Seconds of delay per channel family: eyes lead, extremities drag.
LAGS = (('look_', -.07), ('brow', -.03), ('lid', -.03), ('eye_', -.03), ('head_', .045), ('face_', .02),
        ('shoulder_', .05), ('arm_', .07), ('hand_', .12))


def lag_of(channel):
    for prefix, value in LAGS:
        if channel.startswith(prefix):
            return value
    return 0.0


class Take:
    """Keyframe writer for one actor in one shot."""

    def __init__(self, shot, actor_id, character, rig, **start):
        self.shot, self.rig = shot, rig
        self.spec = {'id': actor_id, 'character': character, 'channels': {}, 'blinks': [], 'auto_blink': True}
        self.defaults = dict(DEFAULTS)
        reach = (rig['arm']['upper']+rig['arm']['fore'])*.97
        self.defaults.update(arm_l_x=-5.0, arm_l_y=reach, arm_r_x=5.0, arm_r_y=reach,
                             foot_l_x=-rig['hip_half'], foot_r_x=rig['hip_half'])
        self.defaults.update(rig.get('defaults', {}))
        for name, value in start.items():
            self.key(0, name, value)

    @property
    def ref(self):
        return self.spec['id']

    # -- primitives --
    def value(self, channel, t):
        keys = self.spec['channels'].get(channel)
        return Track(keys).at(t) if keys else self.defaults[channel]

    @recorded
    def key(self, t, channel, value, ease='smooth'):
        if channel not in self.defaults:
            raise KeyError(channel)
        if t < -1e-6 or t > self.shot.duration+1e-6:
            return self          # outside the shot: lets a move start before or continue past a cut
        t = round(max(0.0, t), 4)
        keys = self.spec['channels'].setdefault(channel, [])
        keys[:] = [k for k in keys if abs(k[0]-t) > 1e-4]
        keys.append([t, value, ease])
        keys.sort(key=lambda k: k[0])
        return self

    @recorded
    def set(self, t, **values):
        for name, value in values.items():
            self.key(t, name, value, 'step')
        return self

    @recorded
    def to(self, t, dur=.4, ease='inout', overlap=1.0, **values):
        """Hold the current value until t (+family lag), then arrive at the target after `dur`.
        A hand that changes direction travels on an arc around its shoulder, never in a straight line through the body."""
        for side in 'lr':
            kx, ky = f'arm_{side}_x', f'arm_{side}_y'
            if (kx in values or ky in values) and self._arm_arc(side, t, dur, ease, overlap, values.get(kx), values.get(ky)):
                values = {name: target for name, target in values.items() if name not in (kx, ky)}
        for name, target in values.items():
            start = t+lag_of(name)*overlap
            if isinstance(target, str):
                self.key(max(0.0, start), name, target, 'step')
                continue
            current = self.value(name, max(0.0, start))
            self.key(max(0.0, start), name, current, 'linear')
            self.key(max(0.0, start)+dur if start < 0 else start+dur, name, target, ease)
        return self

    def _arm_arc(self, side, t, dur, ease, overlap, x1, y1):
        """Dense keys along a polar path (angle and reach around the shoulder). False when a straight move is fine."""
        kx, ky = f'arm_{side}_x', f'arm_{side}_y'
        start = t+lag_of(kx)*overlap
        if start < 0 or dur <= 0 or ease not in EASES:
            return False
        x0, y0 = self.value(kx, start), self.value(ky, start)
        x1, y1 = x0 if x1 is None else x1, y0 if y1 is None else y1
        r0, r1 = math.hypot(x0, y0), math.hypot(x1, y1)
        a0, a1 = math.atan2(y0, x0), math.atan2(y1, x1)
        da = (a1-a0+math.pi) % (2*math.pi)-math.pi
        if r0 < 10 or r1 < 10 or abs(da) < math.radians(22):
            return False
        if abs(da) > math.radians(172):                 # straight across: swing through the front, not behind the back
            da = -abs(da) if a0 > 0 else abs(da)
        frames = max(2, round(dur*self.shot.film.fps))
        self.key(start, kx, x0, 'linear')
        self.key(start, ky, y0, 'linear')
        for i in range(1, frames+1):
            e = EASES[ease](i/frames)
            a, r = a0+da*e, r0+(r1-r0)*e
            if i == frames:
                self.key(start+dur, kx, x1, 'linear')
                self.key(start+dur, ky, y1, 'linear')
            else:
                self.key(start+dur*i/frames, kx, r*math.cos(a), 'linear')
                self.key(start+dur*i/frames, ky, r*math.sin(a), 'linear')
        return True

    @recorded
    def pulse(self, t, up=.15, hold=.1, down=.3, ease='out', back='inout', **values):
        """Go to values and return to whatever was there before."""
        before = {name: self.value(name, t) for name in values}
        self.to(t, up, ease, **values)
        self.to(t+up+hold, down, back, **before)
        return self

    @recorded
    def face(self, t, name, dur=.22, ease='soft', **extra):
        values = dict(EXPRESSIONS[name])
        values.update(extra)
        return self.to(t, dur, ease, overlap=.6, **values)

    @recorded
    def look(self, t, x, y=0.0, dur=.1, head=.0):
        self.to(t, dur, 'out', overlap=0, look_x=x, look_y=y)
        if head:
            self.to(t+.05, dur*2.6, 'soft', overlap=0, face_x=x*head, face_y=y*head*.8)
        return self

    @recorded
    def blink(self, *times):
        self.spec['blinks'].extend(times)
        return self

    @recorded
    def auto_blink(self, enabled=True):
        self.spec['auto_blink'] = enabled
        return self

    def face_point(self, x, facing, t=0.0):
        """World point of the face for an actor standing at x."""
        scale = self.value('scale', t)
        return x+facing*10*scale, self.value('y', t)-232*scale

    @recorded
    def look_at(self, t, target, x, facing, dur=.1, head=.45):
        fx, fy = self.face_point(x, facing, t)
        dx, dy = (target[0]-fx)*facing, target[1]-fy
        return self.look(t, max(-1, min(1, dx/230)), max(-1, min(1, dy/170)), dur, head)

    @recorded
    def track(self, prop, t0, t1, x, facing, step=.14, head=.5):
        """Eyes (and a little head) follow a flying prop (id in the shot)."""
        prop = self.shot.props[prop] if isinstance(prop, str) else prop
        fx, fy = self.face_point(x, facing, t0)
        t = t0
        while t <= t1+1e-6:
            lx = max(-1, min(1, (prop.value('x', t)-fx)*facing/230))
            ly = max(-1, min(1, (prop.value('y', t)-fy)/170))
            self.key(t, 'look_x', lx, 'smooth')
            self.key(t, 'look_y', ly, 'smooth')
            self.key(t+.06, 'face_x', lx*head, 'smooth')
            self.key(t+.06, 'face_y', ly*head*.8, 'smooth')
            self.key(t+.1, 'head_rot', ly*7*head+lx*2, 'smooth')
            t += step
        return self

    @recorded
    def turn_around(self, t, facing, arms=True):
        """Turn through a real front view: yaw toward camera, open into the frontal drawing, mirror there (the frontal
        pose is symmetric, so nothing swaps sides on screen), and close into the new three-quarter view."""
        yaw = self.value('face_x', t)
        if arms:        # the mirror only goes unseen on a symmetric pose: both arms come down to rest first
            self.to(t-.3, .2, 'inout', overlap=0, **self.rest_arm('l'), **self.rest_arm('r'))
        self.to(t-.16, .12, 'in', overlap=0, face_x=-.75, body_yaw=-.8)
        self.to(t-.08, .08, 'linear', overlap=0, turn=0.0)
        self.to(t-.06, .06, 'out', overlap=0, face_x=0.0, body_yaw=0.0)
        self.set(t+.02, facing=facing)
        self.to(t+.04, .08, 'linear', overlap=0, turn=1.0)
        self.set(t+.08, face_x=-.75, body_yaw=-.8)
        self.to(t+.08, .26, 'back', overlap=0, face_x=yaw, body_yaw=0.0)
        self.pulse(t-.1, .1, .06, .22, head_dy=2.5, hip_dy=3)
        return self

    # -- body verbs --
    def rest_arm(self, side):
        return {f'arm_{side}_x': self.defaults[f'arm_{side}_x'], f'arm_{side}_y': self.defaults[f'arm_{side}_y'],
                f'hand_{side}_rot': 0.0}

    @recorded
    def gasp(self, t, amount=1.0):
        """Sharp inhale: dip, then pop up and back, settle."""
        a = amount
        self.to(t, .09, 'out', hip_dy=3*a, torso_sy=.955, torso_sx=1.03, head_dy=2*a)
        self.to(t+.09, .14, 'back', hip_dy=-2*a, torso_sy=1.06, torso_sx=.975, head_dy=-5*a, lean=-5*a,
                shoulder_l_dy=-6*a, shoulder_r_dy=-6*a, head_rot=-4*a)
        self.to(t+.42, .6, 'inout', hip_dy=0, torso_sy=1, torso_sx=1, head_dy=0, lean=-1.5*a,
                shoulder_l_dy=0, shoulder_r_dy=0, head_rot=-1.5*a)
        return self

    @recorded
    def hop(self, t, height=22, air=.34, squash=1.0):
        """Anticipate, jump, land with squash and settle. Returns landing time."""
        s = squash
        self.to(t, .14, 'out', overlap=.5, hip_dy=9*s, torso_sy=.93, torso_sx=1.05, head_dy=3)
        self.to(t, .14, 'out', overlap=0, sy=1-.07*s, sx=1+.06*s)
        self.to(t+.14, .07, 'in', overlap=0, hip_dy=-3, torso_sy=1.08, torso_sx=.95, head_dy=-3)
        self.to(t+.14, .07, 'in', overlap=0, sy=1+.08*s, sx=1-.06*s)
        take_off = t+.19
        self.key(take_off, 'lift', 0, 'linear')
        self.key(take_off+air/2, 'lift', height, 'out')
        self.key(take_off+air, 'lift', 0, 'in')
        for side in 'lr':
            self.to(take_off, air*.4, 'out', overlap=0, **{f'foot_{side}_rot': 22})
            self.to(take_off+air*.6, air*.4, 'in', overlap=0, **{f'foot_{side}_rot': 0})
        land = take_off+air
        self.to(take_off+air*.45, air*.3, 'inout', overlap=0, sy=1.0, sx=1.0)
        self.to(land-.03, .08, 'out', overlap=0, sy=1-.1*s, sx=1+.09*s)
        self.to(land+.07, .24, 'back', overlap=0, sy=1.0, sx=1.0)
        self.to(land, .07, 'out', overlap=.4, hip_dy=11*s, torso_sy=.9, torso_sx=1.07, head_dy=5)
        self.to(land+.07, .2, 'back', overlap=.6, hip_dy=-1.5, torso_sy=1.03, torso_sx=.985, head_dy=-2)
        self.to(land+.27, .3, 'inout', hip_dy=0, torso_sy=1, torso_sx=1, head_dy=0)
        return land

    @recorded
    def nod(self, t, count=2, depth=9, period=.34):
        for i in range(count):
            self.to(t+i*period, period*.45, 'out', overlap=0, head_rot=depth, head_dy=2.5)
            self.to(t+i*period+period*.45, period*.55, 'soft', overlap=0, head_rot=-1.5 if i == count-1 else -3, head_dy=0)
        self.to(t+count*period, .25, 'inout', overlap=0, head_rot=0)
        return self

    @recorded
    def laugh(self, t, dur=1.4, beats=5, strength=1.0):
        """Shoulder/torso bounce while laughing."""
        step = dur/beats
        for i in range(beats):
            k = strength*(1-.45*i/beats)
            self.to(t+i*step, step*.42, 'out', overlap=.5, torso_sy=1-.045*k, hip_dy=3*k, head_dy=3*k,
                    shoulder_l_dy=-5*k, shoulder_r_dy=-5*k, head_rot=-7*k+(3 if i % 2 else 0))
            self.to(t+i*step+step*.42, step*.58, 'soft', overlap=.5, torso_sy=1+.03*k, hip_dy=-1*k, head_dy=-2*k,
                    shoulder_l_dy=1.5*k, shoulder_r_dy=1.5*k, head_rot=-3*k)
        self.to(t+dur, .35, 'inout', torso_sy=1, hip_dy=0, head_dy=0, shoulder_l_dy=0, shoulder_r_dy=0, head_rot=0)
        return self

    @recorded
    def wave(self, t, side='l', cycles=3, period=.36, out=-78, up=-50):
        """Raise the arm with anticipation, wave from the wrist/forearm, bring it down. Returns end time."""
        a = f'arm_{side}'
        h = f'hand_{side}'
        sign = -1 if side == 'l' else 1
        rest = self.rest_arm(side)
        self.to(t, .12, 'out', overlap=0, **{a+'_x': rest[a+'_x']+sign*-6, a+'_y': rest[a+'_y']-3, 'lean': self.value('lean', t)+2})
        self.set(t+.16, **{h: 'open'})
        self.to(t+.12, .26, 'back', overlap=0, **{a+'_x': sign*abs(out), a+'_y': up, a+'_bend': sign*-.9, h+'_rot': sign*20,
                                                  'lean': self.value('lean', t)-2.5})
        start = t+.4
        for i in range(cycles):
            self.to(start+i*period, period/2, 'sine', overlap=0, **{a+'_x': sign*abs(out)+sign*-20, a+'_y': up+8, h+'_rot': sign*-34})
            self.to(start+i*period+period/2, period/2, 'sine', overlap=0, **{a+'_x': sign*abs(out)+sign*14, a+'_y': up-4, h+'_rot': sign*34})
        end = start+cycles*period
        self.to(end, .16, 'out', overlap=0, **{a+'_y': up-6})
        self.to(end+.14, .38, 'inout', overlap=0, **{a+'_x': rest[a+'_x'], a+'_y': rest[a+'_y'], h+'_rot': 0,
                                                     a+'_bend': 1.0 if side == 'l' else -1.0, 'lean': self.value('lean', t)})
        self.set(end+.4, **{h: 'closed'})
        return end+.55

    @recorded
    def walk(self, t0, t1, x0, x1, scale=1.0, step=46, duty=.6, lift=15, swing=17, ease=.22, phase=0.0, bob=2.6, lean=4.0,
             strike=16, push=34, drop=5.0, view='3q'):
        """Foot-planted walk along x. Phase is tied to distance so stance feet do not slide.
        Each step lands on the heel, rolls flat, peels off over the toes and swings through with a bent knee.
        `view`: '3q' (default) walks in three-quarter view; 'profile' turns the body side-on (turn 2, needs the character's
        profile art) with a short eased transition at both ends and returns to three-quarter at the end."""
        fps = self.shot.film.fps
        direction = 1 if x1 >= x0 else -1
        cycle = step/duty*scale
        distance = abs(x1-x0)
        total = t1-t0
        ramp = min(ease, total/2)
        cruise = distance/(total-ramp)
        rest_l, rest_r = self.defaults['foot_l_x'], self.defaults['foot_r_x']
        arm_l, arm_r = self.defaults['arm_l_x'], self.defaults['arm_r_x']
        arm_y = self.defaults['arm_l_y']
        frames = max(2, round(total*fps))
        self.set(t0, facing=direction, turn=1)
        if view == 'profile':
            trans = min(.3, total/4)
            if t0+trans <= 0:
                self.key(0, 'turn', 2.0, 'step')            # the walk began before the shot: already side-on
            else:
                self.key(t0+trans, 'turn', 2.0, 'smooth')
            self.key(t1-trans, 'turn', 2.0, 'smooth')
            self.key(t1, 'turn', 1.0, 'smooth')
        for i in range(frames+1):
            u = i/frames*total
            if u < ramp:
                travelled, weight = cruise*u*u/(2*ramp), u/ramp
            elif u > total-ramp:
                r = total-u
                travelled, weight = distance-cruise*r*r/(2*ramp), r/ramp
            else:
                travelled, weight = cruise*(u-ramp/2), 1.0
            weight = weight*weight*(3-2*weight)
            t = t0+u
            cycles = travelled/cycle+phase
            self.key(t, 'x', x0+direction*travelled, 'linear')
            for side, offset, rest in (('l', 0.0, rest_l), ('r', .5, rest_r)):
                p = (cycles+offset) % 1
                if p < duty:
                    q = p/duty
                    fx, fy = step*(.5-q), 0.0
                    if q < .16:
                        fr = -strike*(1-q/.16)**1.5             # heel first, then the sole slaps down
                    elif q > .6:
                        fr = push*((q-.6)/.4)**1.7              # heel peels off, weight rolls over the toes
                    else:
                        fr = 0.0
                else:
                    k = (p-duty)/(1-duty)
                    # Hermite swing whose ends keep the ground speed, so the toe leaves and the heel arrives without skating.
                    m = -step*(1-duty)/duty
                    k2, k3 = k*k, k*k*k
                    fx = (2*k3-3*k2+1)*(-step/2)+(k3-2*k2+k)*m+(-2*k3+3*k2)*(step/2)+(k3-k2)*m
                    fy = -lift*math.sin(math.pi*k)**1.3
                    if k < .45:
                        e = k/.45
                        fr = push*(1-e*e*(3-2*e))
                    else:
                        e = (k-.45)/.55
                        fr = -strike*e*e*(3-2*e)
                self.key(t, f'foot_{side}_x', rest+(fx-rest*.55)*weight, 'linear')
                self.key(t, f'foot_{side}_y', fy*weight, 'linear')
                self.key(t, f'foot_{side}_roll', fr*weight, 'linear')
            wave = math.cos(2*math.pi*cycles)
            self.key(t, 'hip_dy', (drop+bob*math.cos(4*math.pi*cycles-.5))*weight, 'linear')   # lowest just after each contact
            self.key(t, 'lean', lean*weight, 'linear')
            self.key(t, 'body_yaw', -.12*wave*weight, 'linear')     # shoulders counter the stride
            self.key(t, 'bend', 2.2*math.cos(4*math.pi*cycles+1.2)*weight, 'linear')
            self.key(t, 'head_rot', (-lean*.7+1.6*math.sin(4*math.pi*cycles-.9))*weight, 'linear')
            self.key(t, 'head_dy', 1.2*math.cos(4*math.pi*cycles-.6)*weight, 'linear')
            self.key(t, 'arm_l_x', arm_l+(-swing*wave)*weight, 'linear')
            self.key(t, 'arm_r_x', arm_r+(swing*wave)*weight, 'linear')
            self.key(t, 'arm_l_y', arm_y-(3+3*abs(wave))*weight, 'linear')
            self.key(t, 'arm_r_y', arm_y-(3+3*abs(wave))*weight, 'linear')
            self.key(t, 'hand_l_rot', -10*math.cos(2*math.pi*cycles-.6)*weight, 'linear')
            self.key(t, 'hand_r_rot', 10*math.cos(2*math.pi*cycles-.6)*weight, 'linear')
        return t1

    # -- acting helpers (added for the acting pass) --
    @recorded
    def drift(self, t0, t1, period=1.2, **amps):
        """Keep a held pose alive: each channel sways around its current value by +-amp (own phase), eased in and out
        so it leaves and returns to the held value exactly. Write it right after the move that created the hold."""
        base = {name: self.value(name, t0) for name in amps}
        frames = max(2, round((t1-t0)*self.shot.film.fps/2))
        for i in range(frames+1):
            u = i/frames
            t = t0+u*(t1-t0)
            env = math.sin(math.pi*u)
            for k, (name, amp) in enumerate(amps.items()):
                self.key(t, name, base[name]+amp*env*math.sin(2*math.pi*(t-t0)/period+k*1.9), 'linear')
        return self

    @recorded
    def react(self, t, x=.8, y=0.0, head=.5, lean=0.0, dip=0.0, dur=.1):
        """Listener beat: the eyes lead (t), the head follows (+.05), the body leans last (+.14) and comes back."""
        self.look(t, x, y, dur, head)
        if lean or dip:
            self.pulse(t+.14, .18, .25, .4, lean=self.value('lean', t+.14)+lean, hip_dy=self.value('hip_dy', t+.14)+dip)
        return self

    @recorded
    def overshoot(self, t, dur=.2, over=.15, settle=.25, **values):
        """Arrive at numeric channel values past the target by `over` (fraction of the move), then settle on them."""
        before = {name: self.value(name, t) for name, v in values.items() if not isinstance(v, str)}
        peak = {name: (v+(v-before[name])*over if name in before else v) for name, v in values.items()}
        self.to(t, dur, 'out', **peak)
        self.to(t+dur, settle, 'inout', **values)
        return self

    @recorded
    def wave_off(self, t, side='r', cycles=4, period=.36, out=86, up=-40, decay=.12, tilt=3.0):
        """Farewell wave: pull-back anticipation, raise with overshoot and settle, cycles that taper off, a hang where the
        hand sags slowly, then a clean drop that overshoots the rest pose. Returns end time."""
        a, h = f'arm_{side}', f'hand_{side}'
        sign = -1 if side == 'l' else 1
        rest = self.rest_arm(side)
        lean0, head0 = self.value('lean', t), self.value('head_rot', t)
        self.to(t, .14, 'out', overlap=0, **{a+'_x': rest[a+'_x']-sign*6, a+'_y': rest[a+'_y']-3, 'lean': lean0+2.5})
        self.set(t+.16, **{h: 'open'})
        self.to(t+.12, .22, 'out', overlap=0, **{a+'_x': sign*(out+8), a+'_y': up-8, a+'_bend': sign*-.9, h+'_rot': sign*24,
                                                  'lean': lean0-3, 'head_rot': head0+tilt})
        self.to(t+.34, .2, 'inout', overlap=0, **{a+'_x': sign*out, a+'_y': up})
        start = t+.5
        for i in range(cycles):
            k = 1-decay*i
            self.to(start+i*period, period/2, 'sine', overlap=0, **{a+'_x': sign*out-sign*20*k, a+'_y': up+8*k, h+'_rot': sign*-34*k})
            self.to(start+i*period+period/2, period/2, 'sine', overlap=0, **{a+'_x': sign*out+sign*14*k, a+'_y': up-4*k, h+'_rot': sign*34*k})
        end = start+cycles*period
        self.to(end, .3, 'out', overlap=0, **{a+'_x': sign*out, a+'_y': up+6, h+'_rot': sign*8})
        self.to(end+.4, .34, 'in', overlap=0, **{a+'_x': rest[a+'_x'], a+'_y': rest[a+'_y'], h+'_rot': 0, a+'_bend': 1.0 if side == 'l' else -1.0,
                                                  'lean': lean0, 'head_rot': head0})
        self.set(end+.7, **{h: 'closed'})
        return end+.8


class Prop:
    def __init__(self, shot, spec):
        self.shot, self.spec = shot, spec
        self.spec.setdefault('channels', {})

    @recorded
    def key(self, t, channel, value, ease='smooth'):
        if t < -1e-6 or t > self.shot.duration+1e-6:
            return self
        t = round(max(0.0, t), 4)
        keys = self.spec['channels'].setdefault(channel, [])
        keys[:] = [k for k in keys if abs(k[0]-t) > 1e-4]
        keys.append([t, value, ease])
        keys.sort(key=lambda k: k[0])
        return self

    @property
    def ref(self):
        return self.spec['id']

    @recorded
    def perch(self, t0, t1, period=1.5):
        """Slow wing breathing while resting."""
        t = t0
        while t < t1:
            rest = self.spec.get('perch_rest')          # library entry with a landing pose: rest on it, open the wings a little
            beats = (((0, rest), (period*.5, 1), (period*.62, rest)) if rest is not None
                     else ((0, 0), (period*.5, 1), (period*.58, 2), (period*.86, 1), (period*.93, 0)))
            for offset, frame in beats:
                self.key(t+offset, 'frame', frame, 'step')
            t += period
        return self

    def value(self, channel, t, default=0.0):
        keys = self.spec['channels'].get(channel)
        return Track(keys).at(t) if keys else default

    @recorded
    def to(self, t, dur, ease='inout', **values):
        for name, target in values.items():
            self.key(t, name, self.value(name, t, target), 'linear')
            self.key(t+dur, name, target, ease)
        return self

    @recorded
    def path(self, t0, t1, points, flutter=5.0, seed=0.0, facing=True):
        """Fly through world points with a Catmull-Rom path plus fluttery bobbing; dense linear keys."""
        fps = self.shot.film.fps
        frames = max(2, round((t1-t0)*fps))
        pts = [points[0]]+list(points)+[points[-1]]
        segments = len(points)-1
        last_x = None
        for i in range(frames+1):
            u = i/frames
            e = u*u*(3-2*u)
            f = min(segments-1e-6, e*segments)
            j = int(f)
            w = f-j
            p0, p1, p2, p3 = pts[j], pts[j+1], pts[j+2], pts[j+3]
            pos = []
            for a in (0, 1):
                pos.append(.5*((2*p1[a])+(-p0[a]+p2[a])*w+(2*p0[a]-5*p1[a]+4*p2[a]-p3[a])*w*w+(-p0[a]+3*p1[a]-3*p2[a]+p3[a])*w**3))
            t = t0+u*(t1-t0)
            envelope = math.sin(math.pi*u)**.5
            x = pos[0]+flutter*.7*math.sin(t*7.3+seed)*envelope
            y = pos[1]+flutter*math.sin(t*11.1+seed*1.7)*envelope+flutter*.5*math.sin(t*4.2+seed)
            self.key(t, 'x', x, 'linear')
            self.key(t, 'y', y, 'linear')
            if facing and last_x is not None and abs(x-last_x) > .05:
                self.key(t, 'facing', 1 if x > last_x else -1, 'step')
            last_x = x
        return self

    @recorded
    def flap(self, t0, t1, rate=9.0, frames=(0, 1, 2, 1)):
        """Flipbook wing cycle."""
        frames = self.spec.get('flap_frames') or frames        # library entry may set its own cycle
        count = max(1, round((t1-t0)*rate*len(frames)))
        for i in range(count+1):
            self.key(t0+i/(rate*len(frames)), 'frame', frames[i % len(frames)], 'step')
        return self


class Shot:
    def __init__(self, film, shot_id, duration, set_name, description='', raw_duration=None):
        raw_duration = duration if raw_duration is None else raw_duration
        self.film, self.duration = film, duration
        self.spec = {'id': shot_id, 'duration': duration, 'set': set_name, 'description': description,
                     'camera': {}, 'actors': [], 'props': [], 'overlays': []}
        self.script = {'id': shot_id, 'duration': raw_duration, 'set': set_name, 'description': description,
                       'actors': [], 'props': [], 'actions': []}
        self.props = {}

    ref = 'shot'

    @property
    def shot(self):
        return self

    def actor(self, actor_id, character=None, **start):
        character = character or actor_id
        film = self.film
        film.depth += 1
        try:
            take = Take(self, actor_id, character, film.rigs[character], **start)
        finally:
            film.depth -= 1
        self.spec['actors'].append(take.spec)
        self.script['actors'].append({'id': actor_id, 'character': character, 'start': jsonable(start)})
        return take

    def prop(self, prop, id=None, **overrides):
        """Place a prop from the film's library; `overrides` are merged over the library spec."""
        spec = dict(self.film.props[prop], **overrides)
        if id:
            spec['id'] = id
        item = Prop(self, spec)
        if item.ref in self.props:
            raise ValueError(f'prop duplicado: {item.ref}')
        self.props[item.ref] = item
        self.spec['props'].append(item.spec)
        if self.film.depth == 0:
            self.script['props'].append({'id': item.ref, 'prop': prop, 'spec': jsonable(overrides)})
        return item

    @recorded
    def cam(self, t, x=None, y=None, zoom=None, ease='inout', **extra):
        for name, value in (('x', x), ('y', y), ('zoom', zoom), *extra.items()):
            if value is not None:
                keys = self.spec['camera'].setdefault(name, [])
                keys.append([round(t, 4), value, ease])
                keys.sort(key=lambda k: k[0])
        return self

    @recorded
    def overlay(self, **item):
        self.spec['overlays'].append(item)
        return self

    @recorded
    def fade_in(self, dur=.6, color='#000000'):
        return self.overlay(kind='fade', keys=[[0, 1], [dur, 0, 'inout']], color=color)

    @recorded
    def fade_out(self, dur=.8, color='#000000'):
        return self.overlay(kind='fade', keys=[[self.duration-dur, 0], [self.duration, 1, 'inout']], color=color)


    @recorded
    def dof(self, value):
        """Depth of field: a number or keys [[t, value, ease?], ...]."""
        self.spec['dof'] = value
        return self

    @recorded
    def puff_burst(self, t, x, y, direction=-1, count=3, spread=30, size=1.0):
        """Dust puffs (library prop 'puff') thrown sideways from a point."""
        phased = bool((self.film.props.get('puff') or {}).get('phases'))
        for i in range(count):
            item = self.prop('puff', id=f'puff{t:.2f}-{i}')
            if phased:
                self._puff_phases(item, t+.05*i, x, y, direction, count, spread, size, i)
                continue
            angle = (-.5+i/(count-1))*1.1 if count > 1 else 0
            dx, dy = direction*spread*(1.1+.5*math.cos(angle)), spread*.9*math.sin(angle)-10
            item.key(0, 'opacity', 0, 'step')
            item.key(0, 'frame', i % 3, 'step')
            item.key(t, 'opacity', 0, 'step')
            item.key(t+.06, 'opacity', .95, 'linear')
            item.key(t, 'x', x)
            item.key(t, 'y', y)
            item.key(t, 'scale', .14*size)
            item.key(t+.5, 'x', x+dx, 'out')
            item.key(t+.5, 'y', y+dy, 'out')
            item.key(t+.22, 'scale', (.9+.2*i)*size, 'out')
            item.key(t+.6, 'scale', (1.1+.2*i)*size, 'linear')
            item.key(t+.22, 'opacity', .9, 'linear')
            item.key(t+.6, 'opacity', 0, 'linear')
            item.key(t, 'rot', -20+20*i)
            item.key(t+.6, 'rot', 15*i, 'out')
        return self


    def _puff_phases(self, item, t, x, y, direction, count, spread, size, i):
        """Phased dust (prop library entry with `phases`: cells = burst, expanding, full, dissipating): the drawing
        changes over the puff's life instead of one sticker fading."""
        angle = (-.5+i/(count-1))*1.1 if count > 1 else 0
        dx, dy = direction*spread*(1.1+.5*math.cos(angle)), spread*.9*math.sin(angle)-10
        k = size*(1+.12*i)
        item.key(0, 'opacity', 0, 'step')
        item.key(t, 'opacity', 1, 'step')
        item.key(t+.46, 'opacity', 1, 'linear')
        item.key(t+.72, 'opacity', 0, 'linear')
        for dt, frame in ((0, 0), (.09, 1), (.2, 2), (.42, 3)):
            item.key(t+dt, 'frame', frame, 'step')
        item.key(t, 'x', x)
        item.key(t, 'y', y)
        item.key(t+.72, 'x', x+dx, 'out')
        item.key(t+.72, 'y', y+dy-6, 'out')
        item.key(t, 'scale', .75*k)
        item.key(t+.22, 'scale', 1.0*k, 'out')
        item.key(t+.72, 'scale', 1.2*k, 'linear')
        item.key(t, 'rot', -6+6*i)
        item.key(t+.72, 'rot', 6*i-4, 'out')


class Film:
    """Authoring session. Besides building `spec` (film.json), it records every top-level call so `export()`
    can write the equivalent declarative script, which replays to the identical spec."""

    def __init__(self, film_id, title, rigs, fps=24, width=1920, height=1080, props=None):
        self.id, self.title, self.fps, self.width, self.height, self.rigs = film_id, title, fps, width, height, rigs
        self.props = props or {}          # prop library: name -> spec
        self.depth = 0                    # >0 while a verb runs, so its internal calls are not recorded
        self.shots = []
        self.spec = {'schema_version': 2, 'id': film_id, 'title': title, 'fps': fps, 'width': width, 'height': height,
                     'world': [1280, 720], 'characters': {}, 'sets': {}, 'shots': []}

    def shot(self, shot_id, duration, set_name, description=''):
        shot = Shot(self, shot_id, round(duration*self.fps)/self.fps, set_name, description, duration)
        self.spec['shots'].append(shot.spec)
        self.shots.append(shot)
        return shot

    def export(self, **meta):
        """Declarative script. `meta`: story, style, bible, characters, sets, props, references, revision."""
        script = {'schema_version': 2, 'kind': 'script', 'id': self.id, 'title': self.title, 'revision': meta.pop('revision', 1),
                  'fps': self.fps, 'width': self.width, 'height': self.height}
        script.update({k: meta.pop(k, v) for k, v in (('story', ''), ('style', {}), ('bible', {}), ('characters', {}),
                                                      ('sets', {}), ('props', self.props), ('references', []))})
        script['shots'] = [s.script for s in self.shots]
        return jsonable(script)
