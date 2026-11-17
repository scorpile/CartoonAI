"""Biped puppet rig: IK hose limbs, sprite body parts, parametric face, spring appendages.

Local space: origin on the ground between the feet, x right, y down, world units.
Side `l` is the near/lead side (screen-left when facing=+1); `r` is the far side.
Rendering is deterministic; nothing here calls a model.
"""
import math
from pathlib import Path
import numpy as np
import skia
from .anim import Track, hash01, noise1
from .gfx import Tex, LINEAR

SAMPLING = LINEAR


def rgba(text, alpha=1.0):
    text = text.lstrip('#')
    return skia.Color(int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), round(255*max(0, min(1, alpha))))


def fill(color, alpha=1.0):
    return skia.Paint(AntiAlias=True, Color=rgba(color, alpha), Style=skia.Paint.kFill_Style)


def stroke(color, width, alpha=1.0):
    return skia.Paint(AntiAlias=True, Color=rgba(color, alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=width,
                      StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, u):
    return a+(b-a)*u


def mix(a, b, u):
    a, b = a.lstrip('#'), b.lstrip('#')
    return '#%02x%02x%02x' % tuple(round(lerp(int(a[i:i+2], 16), int(b[i:i+2], 16), u)) for i in (0, 2, 4))


def rot(x, y, radians):
    c, s = math.cos(radians), math.sin(radians)
    return x*c-y*s, x*s+y*c


def ik(root, target, a, b, bend, stretch=1.18):
    """Two-segment IK. Returns (mid, end). `bend` in [-1,1] chooses side and amount."""
    dx, dy = target[0]-root[0], target[1]-root[1]
    d = math.hypot(dx, dy) or 1e-6
    reach = a+b
    if d > reach*stretch:
        dx, dy, d = dx*reach*stretch/d, dy*reach*stretch/d, reach*stretch
    if d > reach*.999:
        k = d/(reach*.999)
        a, b = a*k, b*k
    d = max(d, abs(a-b)+1e-3)
    cosine = clamp((a*a+d*d-b*b)/(2*a*d), -1, 1)
    ux, uy = rot(dx/d, dy/d, math.acos(cosine)*bend)
    return (root[0]+ux*a, root[1]+uy*a), (root[0]+dx, root[1]+dy)


def limb_curve(start, mid, end, smooth=.8, n=14):
    mx, my = (start[0]+end[0])/2, (start[1]+end[1])/2
    cx, cy = mx+(mid[0]-mx)*(1+smooth), my+(mid[1]-my)*(1+smooth)
    points = []
    for i in range(n+1):
        u = i/n
        k0, k1, k2 = (1-u)*(1-u), 2*u*(1-u), u*u
        points.append((k0*start[0]+k1*cx+k2*end[0], k0*start[1]+k1*cy+k2*end[1]))
    return points


def _frames(points):
    out = []
    last = len(points)-1
    for i, p in enumerate(points):
        a, b = points[max(0, i-1)], points[min(last, i+1)]
        tx, ty = b[0]-a[0], b[1]-a[1]
        length = math.hypot(tx, ty) or 1e-6
        out.append((tx/length, ty/length))
    return out


def hose_path(points, widths, i0=0, i1=None, caps=True, grow=1.0, cap0=None, cap1=None):
    """Closed outline polygon around a centre line with per-point widths."""
    i1 = len(points)-1 if i1 is None else i1
    cap0, cap1 = caps if cap0 is None else cap0, caps if cap1 is None else cap1
    tangents = _frames(points)
    left, right = [], []
    for i in range(i0, i1+1):
        (px, py), (tx, ty), r = points[i], tangents[i], widths[i]*.5*grow
        left.append((px-ty*r, py+tx*r))
        right.append((px+ty*r, py-tx*r))
    path = skia.Path()
    path.moveTo(*left[0])
    for p in left[1:]:
        path.lineTo(*p)
    if cap1:
        (px, py), (tx, ty), r = points[i1], tangents[i1], widths[i1]*.5
        for k in range(1, 8):
            a = math.pi*k/8
            path.lineTo(px+(-ty*math.cos(a)+tx*math.sin(a))*r, py+(tx*math.cos(a)+ty*math.sin(a))*r)
    for p in reversed(right):
        path.lineTo(*p)
    if cap0:
        (px, py), (tx, ty), r = points[i0], tangents[i0], widths[i0]*.5
        for k in range(1, 8):
            a = math.pi*k/8
            path.lineTo(px+(ty*math.cos(a)-tx*math.sin(a))*r, py+(-tx*math.cos(a)-ty*math.sin(a))*r)
    path.close()
    return path


def draw_hose(canvas, points, spec, outline_color, outline_w, merge=None, extend=0.0):
    """Tube limb. `extend`: flat sleeve end overshooting the last point (cuff over the hand).
    `merge`: dict(draw=fn(canvas) painting the torso, radius, color=hex or None): the root end has no outline
    where it overlaps the torso and the fill blends from the torso colour, so the sleeve grows out of the body."""
    n0 = len(points)-1
    if extend:
        (ax, ay), (bx, by) = points[-2], points[-1]
        length = math.hypot(bx-ax, by-ay) or 1e-6
        points = list(points)+[(bx+(bx-ax)/length*extend, by+(by-ay)/length*extend)]
    n = len(points)-1
    w = spec['w']
    widths = [lerp(w[0], w[1], i/(n0/2)) if i <= n0/2 else lerp(w[1], w[2], min(1.0, (i-n0/2)/(n0/2))) for i in range(n+1)]
    if extend:
        widths[n] = widths[n0]*1.12      # the cuff flares slightly so a turned hand's cut edge stays hidden
    path = hose_path(points, widths, cap1=not extend)
    bands = spec.get('bands', [])
    base = bands[0]['color'] if bands else '#888888'
    # Outline first, twice as thick, with the fill on top: only the outer half shows, so folds at tight bends leave no stray lines.
    line = stroke(outline_color, outline_w*2)
    if not merge:
        canvas.drawPath(path, line)
    else:
        canvas.saveLayer(path.getBounds().makeOutset(outline_w*2, outline_w*2), None)
        canvas.drawPath(path, line)
        rx, ry = points[0]
        radius = merge['radius']
        area = skia.Rect.MakeLTRB(rx-radius, ry-radius, rx+radius, ry+radius)
        canvas.saveLayer(area, skia.Paint(BlendMode=skia.BlendMode.kDstOut))
        merge['draw'](canvas)
        fade = skia.GradientShader.MakeRadial(skia.Point(rx, ry), radius, [0xFF000000, 0xFF000000, 0x00000000], [0, .45, 1])
        canvas.drawRect(area, skia.Paint(BlendMode=skia.BlendMode.kDstIn, Shader=fade))
        canvas.restore()
        canvas.restore()
    canvas.drawPath(path, fill(base))
    canvas.save()
    canvas.clipPath(path, skia.ClipOp.kIntersect, True)
    tangents = _frames(points)
    if merge and merge.get('color'):
        k = max(1, round(.15*n0))
        grad = skia.GradientShader.MakeLinear([skia.Point(*points[0]), skia.Point(*points[k])], [rgba(merge['color']), rgba(base)], [0, 1])
        canvas.drawPath(path, skia.Paint(AntiAlias=True, Shader=grad))
    cuff = spec.get('cuff')
    for band in bands[1:]+([cuff] if cuff else []):
        i0, i1 = max(0, round(band['from']*n0)), min(n0, round(band['to']*n0))
        if extend and band is cuff:
            i1 = n
        if i1 > i0:
            canvas.drawPath(hose_path(points, widths, i0, i1, caps=band['to'] >= 1 and not extend, grow=1.5), fill(band['color']))
    if spec.get('shade'):
        shade = spec['shade']
        side = shade.get('side', 1)
        line = skia.Path()
        for i, ((px, py), (tx, ty)) in enumerate(zip(points, tangents)):
            off = widths[i]*.5*side*(1-shade.get('width', .32))
            (line.moveTo if i == 0 else line.lineTo)(px-ty*off, py+tx*off)
        canvas.drawPath(line, stroke(shade['color'], max(widths)*shade.get('width', .32), shade.get('alpha', 1)))
    if spec.get('highlight'):
        hl = spec['highlight']
        i0, i1 = round(hl.get('from', .12)*n0), round(hl.get('to', .45)*n0)
        line = skia.Path()
        for i in range(i0, i1+1):
            (px, py), (tx, ty) = points[i], tangents[i]
            off = widths[i]*hl.get('offset', -.22)
            (line.moveTo if i == i0 else line.lineTo)(px-ty*off, py+tx*off)
        canvas.drawPath(line, stroke(hl['color'], hl.get('w', 2.2), hl.get('alpha', .9)))
    for band in ([cuff] if cuff else [])+[b for b in bands[1:] if b.get('seam')]:
        for edge in (band['from'], band['to']):
            i = round(edge*n0)
            if 0 < i < n0:
                (px, py), (tx, ty), r = points[i], tangents[i], widths[i]*.6
                canvas.drawLine(px-ty*r, py+tx*r, px+ty*r, py-tx*r, stroke(outline_color, outline_w*.8))
    canvas.restore()


def smooth(a, b, x):
    u = np.clip((x-a)/(b-a), 0.0, 1.0)
    return u*u*(3-2*u)


def head_plate(view, fx, fy, x, y):
    """Displacement (sprite px) of the face plate for yaw fx / pitch fy (-1..1) at sprite points x, y.
    Full slide inside the plate, smooth falloff to zero beyond it so the outer silhouette stays put."""
    x0, y0, x1, y1 = view['face']['bbox']
    r = np.hypot((x-(x0+x1)/2)/((x1-x0)/2), (y-(y0+y1)/2)/((y1-y0)/2))
    w = 1-smooth(.85, 1.5, r)
    return fx*.108*(x1-x0)*w, fy*.07*(y1-y0)*w


def head_appendage(view, fx, bx, by, tx, ty, along, across, spread):
    """Weight of an appendage at a point and its yaw shift (ears/antenna sit behind the pivot: opposite to yaw)."""
    weight = np.clip(along*1.15, 0, 1)
    weight = weight*weight*(3-2*weight)*np.exp(-(across/spread)**2)
    x0, _, x1, _ = view['face']['bbox']
    return weight, -fx*.03*(x1-x0)*weight


DEFAULTS = dict(
    x=0.0, y=0.0, scale=1.0, facing=1.0, turn=1.0, opacity=1.0, sx=1.0, sy=1.0, life=1.0, rot=0.0, lift=0.0, shadow=1.0,
    hip_dx=0.0, hip_dy=0.0, lean=0.0, torso_sx=1.0, torso_sy=1.0, bend=0.0, body_yaw=0.0,
    head_rot=0.0, head_dx=0.0, head_dy=0.0, head_sx=1.0, head_sy=1.0,
    face_x=0.0, face_y=0.0, look_x=0.0, look_y=0.0, lid=0.0, squint=0.0, eye_open=1.0, pupil=1.0,
    brow_y=0.0, brow_rot=0.0, smile=.6, mouth_open=0.0, mouth_w=1.0, mouth_round=0.0, mouth_y=0.0, blush=1.0,
    arm_l_bend=1.0, arm_r_bend=-1.0, hand_l_rot=0.0, hand_r_rot=0.0, hand_l='closed', hand_r='closed',
    arm_l_z=1.0, arm_r_z=0.0, hand_l_flip=1.0, hand_r_flip=-1.0, shoulder_l_dy=0.0, shoulder_r_dy=0.0,
    foot_l_y=0.0, foot_r_y=0.0, foot_l_rot=0.0, foot_r_rot=0.0, foot_l_roll=0.0, foot_r_roll=0.0, boot_l='side', boot_r='side', knee=-9.0,
    lid_l=0.0, lid_r=0.0,           # per-eye lid offset added to `lid` (lid 1 + lid_r -1 = one eye open)
    item_l='', item_r='',           # rig `items` held in that hand ('' = empty)
    wear='',                        # rig `wear` garment drawn over the torso ('' = none)
    order=0.0,                      # drawing order among actors and ordered front layers (read by the stage, keys only)
)


class Rig:
    def __init__(self, data, root):
        self.d, self.root = data, Path(root)
        self._images = {}
        self.colors = data['colors']
        arm, leg = data['arm'], data['leg']
        self.defaults = dict(DEFAULTS)
        reach = (arm['upper']+arm['fore'])*.97
        self.defaults.update(arm_l_x=-5.0, arm_l_y=reach, arm_r_x=5.0, arm_r_y=reach,
                             foot_l_x=-data['hip_half'], foot_r_x=data['hip_half'])
        self.defaults.update(data.get('defaults', {}))
        # Profile art (head view 'profile' + torso 'profile') extends `turn` to 0..2 (2 = profile). Without it, turn tops out at 1.
        self.profile = bool(data['head'].get('profile') and data['torso'].get('profile'))
        # Back art (head view 'back3q' + torso 'back3q') extends `turn` to 0..3 (3 = three-quarter back, no face).
        self.back = bool(self.profile and data['head'].get('back3q') and data['torso'].get('back3q'))

    def image(self, filename):
        if filename not in self._images:
            self._images[filename] = Tex.open(self.root/filename)
        return self._images[filename]

    PROFILE_AT = 1.5        # turn at which head and torso switch to the profile drawings
    BACK_AT = 2.5           # turn at which they switch to the three-quarter back drawings (3 = fully from behind)

    def turn_max(self):
        return 3.0 if self.back else (2.0 if self.profile else 1.0)

    def view_key(self, v):
        """Which head drawing ('front', '3q', 'profile', 'back3q') `turn` selects; the torso swaps for 'profile' and 'back3q'."""
        turn_raw = clamp(v['turn'], 0.0, self.turn_max())
        if self.back and turn_raw >= self.BACK_AT:
            return 'back3q'
        if self.profile and turn_raw >= self.PROFILE_AT:
            return 'profile'
        return '3q' if min(turn_raw, 1.0) >= .5 else 'front'

    # ---- pose ----
    def pose(self, v, wobble=None):
        d = self.d
        turn_raw = clamp(v['turn'], 0.0, self.turn_max())
        turn = min(turn_raw, 1.0)                       # the front/three-quarter blend; everything below 1 is unchanged
        blend = min(1.0, max(0.0, turn_raw-1.0))        # 0..1 from three-quarter to profile layout
        is_back = self.back and turn_raw >= self.BACK_AT
        is_profile = self.profile and turn_raw >= self.PROFILE_AT and not is_back
        back_blend = clamp(turn_raw-2.0, 0.0, 1.0)      # 0..1 from profile to back layout
        pelvis = (v['hip_dx'], -d['hip_height']+v['hip_dy'])
        lean = math.radians(v['lean'])
        tpart = d['torso']['back3q'] if is_back else d['torso']['profile'] if is_profile else d['torso']

        xf = self._torso_xf(v, wobble, pelvis, tpart)

        def torso_point(dx, dy):
            x, y = xf(dx, dy)
            return float(x), float(y)
        sx, sy = d['torso']['shoulder']
        p = {'pelvis': pelvis, 'lean': v['lean'], 'turn': turn, 'profile': blend, 'is_profile': is_profile or is_back, 'is_back': is_back, 'torso_part': tpart}
        shoulder_lx, shoulder_rx = -sx*(1-.20*turn), sx*(1-.46*turn)
        neck_x, neck_y, base_y = d['torso']['neck'][0]+4*turn, d['torso']['neck'][1], d['torso']['neck'][1]+12
        if blend > 0:
            # Towards profile both shoulders gather over the body's axis (the near one a little back, the far one a little ahead).
            prof = d['torso']['profile']
            shoulder_lx, shoulder_rx = lerp(shoulder_lx, prof['shoulder'][0]-3, blend), lerp(shoulder_rx, prof['shoulder'][0]+3, blend)
            neck_x, neck_y = lerp(neck_x, prof['neck'][0], blend), lerp(neck_y, prof['neck'][1], blend)
            base_y = neck_y+12
        if back_blend > 0:
            # Towards the back view the shoulders open again (the far one now on the other side of the spine).
            back = d['torso']['back3q']
            shoulder_lx, shoulder_rx = lerp(shoulder_lx, -sx*.78, back_blend), lerp(shoulder_rx, sx*.58, back_blend)
            neck_x, neck_y = lerp(neck_x, back['neck'][0], back_blend), lerp(neck_y, back['neck'][1], back_blend)
            base_y = neck_y+12
        p['shoulder_l'] = torso_point(shoulder_lx, sy+v['shoulder_l_dy'])
        p['shoulder_r'] = torso_point(shoulder_rx, sy+v['shoulder_r_dy'])
        neck = torso_point(neck_x, neck_y)
        head_angle = v['lean']+v['head_rot']
        hx, hy = rot(v['head_dx'], v['head_dy'], lean)
        p['neck'] = (neck[0]+hx, neck[1]+hy)
        p['neck_base'] = torso_point(neck_x, base_y)
        p['head_angle'] = head_angle
        view = d['head']['back3q'] if is_back else d['head']['profile'] if is_profile else d['head']['3q' if turn >= .5 else 'front']
        p['view'] = view
        arm = d['arm']
        anatomy = d.get('anatomy', True)
        for side in 'lr':
            shoulder = p['shoulder_'+side]
            tx, ty = rot(v[f'arm_{side}_x'], v[f'arm_{side}_y'], lean*.6)
            bend, layer = v[f'arm_{side}_bend'], v[f'arm_{side}_z']
            if anatomy and side == 'r' and ty > 0:
                # The far arm of a turned body hangs slightly ahead, so its hand shows past the belly instead of
                # hiding behind the torso and popping out when it moves.
                tx += 13*turn*clamp(ty/(arm['upper']+arm['fore']))
            if anatomy:
                # The elbow side is not a free choice: it hangs down and away from where the body faces (outwards in a
                # front view) and never folds upward. The keyed bend only says how much the arm flexes.
                length = math.hypot(tx, ty) or 1e-6
                ex = lerp(-.5 if side == 'l' else .5, -.45 if side == 'l' else -.3, turn)
                bend = min(1.0, abs(bend))*clamp((-ty*ex+tx*.9)/length*5, -1, 1)
                # Depth follows the body too: on a turned body the far arm and its hand stay behind torso and head, and
                # the near arm and its hand pass in front of both. Facing the camera, both arms are in front.
                layer = 0.0 if (turn >= .5 and side == 'r') else 2.0
            p['arm_z_'+side] = layer
            mid, end = ik(shoulder, (shoulder[0]+tx, shoulder[1]+ty), arm['upper'], arm['fore'], bend)
            p['elbow_'+side], p['hand_'+side] = mid, end
            p['arm_'+side] = limb_curve(shoulder, mid, end, arm.get('smooth', .75))
        leg, foot = d['leg'], d.get('foot', {})
        knee = turn if v['knee'] < -5 else v['knee']
        half = d['hip_half']*(1-.28*turn)
        if blend > 0:
            half = d['hip_half']*lerp(.72, .3, blend)    # the legs close up as the body turns side-on
        p['hip_squeeze'] = lerp(1-.07*turn, .8, blend)
        for side, sign, bend in (('l', -1, lerp(1, -1, knee)), ('r', 1, -1)):
            hip = (pelvis[0]+sign*half, pelvis[1]+d['hip_joint_dy'])
            # The sole rolls on the ground: roll > 0 peels the heel off around the toes, roll < 0 lands on the heel.
            point = -1 if (side == 'l' and turn < .5) else 1
            roll = v[f'foot_{side}_roll']
            ax, ay = 0.0, -d['ankle_h']
            if roll:
                px = (foot.get('toe', 24.0) if roll > 0 else -foot.get('heel', 12.0))*point
                ax, ay = rot(ax-px, ay, math.radians(roll*point))
                ax += px
            # The far foot of a turned body stands a little deeper into the scene.
            depth = foot.get('depth', 3.5)*turn if side == 'r' else 0.0
            ankle = (v[f'foot_{side}_x']+ax, v[f'foot_{side}_y']+ay-depth)
            p['foot_rot_'+side] = v[f'foot_{side}_rot']+roll
            p['sole_'+side] = (v[f'foot_{side}_x']+6*point, -depth, max(0.0, -(v[f'foot_{side}_y']+ay+d['ankle_h'])))
            mid, end = ik(hip, ankle, leg['thigh'], leg['shin'], bend*.999 if abs(bend) > .05 else .05)
            p['knee_'+side], p['ankle_'+side] = mid, end
            p['leg_'+side] = limb_curve(hip, mid, end, leg.get('smooth', .55))
        # anchors in local space
        upp, pivot = view['upp'], view['pivot']
        head_r = math.radians(head_angle)

        def head_point(px, py):
            x, y = rot((px-pivot[0])*upp*v['head_sx'], (py-pivot[1])*upp*v['head_sy'], head_r)
            return p['neck'][0]+x, p['neck'][1]+y
        p['head_point'] = head_point
        box = view['face']['bbox']
        fx, fy = clamp(v['face_x'], -1, 1), clamp(v['face_y'], -1, 1)
        if view.get('back'):
            fx = fy = 0.0                               # nothing to slide: a back view has no face plate
        cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
        dx, dy = head_plate(view, fx, fy, cx, cy)
        p['face'] = head_point(cx+float(dx), cy+float(dy))
        tdx, tdy = head_plate(view, fx, fy, cx, view.get('top', 0))
        p['head_top'] = head_point(cx+float(tdx), view.get('top', 0)+float(tdy))
        for item in view.get('appendages', []):
            angle = (wobble or {}).get(item['name'], 0.0)
            bx, by = item['base']
            ox, oy = rot(item['tip'][0]-bx, item['tip'][1]-by, angle)
            shift = head_appendage(view, fx, bx, by, item['tip'][0], item['tip'][1], 1.0, 0.0, 1.0)[1]
            p['tip_'+item['name']] = head_point(bx+ox+float(shift), by+oy)
        return p

    # ---- torso deformation ----
    def _torso_rows(self, t=None):
        """Silhouette extents of the torso sprite per height: (s, half width, centre) in local units."""
        t = t or self.d['torso']
        if not hasattr(self, '_rows'):
            self._rows = {}
        if t['file'] not in self._rows:
            a = self.image(t['file']).levels[0].toarray()[..., 3] > 100
            ys = np.where(a.any(axis=1))[0]
            left = a.argmax(axis=1)[ys].astype(float)
            right = (a.shape[1]-1-a[:, ::-1].argmax(axis=1))[ys].astype(float)
            kernel = np.ones(11)/11
            pad = lambda x: np.convolve(np.pad(x, 5, mode='edge'), kernel, mode='valid')
            left, right = pad(left), pad(right)
            upp, (px, py) = t['upp'], t['pivot']
            s = -(ys-py)*upp
            order = np.argsort(s)
            self._rows[t['file']] = (s[order], ((right-left)/2*upp)[order], (((left+right)/2-px)*upp)[order])
        return self._rows[t['file']]

    def _torso_xf(self, v, wobble, pelvis, part=None):
        """Map torso-local points (dx right, dy down from the pelvis pivot, sprite units) to local space:
        body_yaw (2.5D turn) -> torso_sx/sy -> bend (C curve about the pelvis) -> hem lag -> lean."""
        d = part or self.d['torso']
        yaw, bend = clamp(v['body_yaw'], -1, 1), math.radians(v['bend'])
        hem = (wobble or {}).get('hem', 0.0)
        sx, sy = v['torso_sx'], v['torso_sy']
        lean = math.radians(v['lean'])
        cl, sl = math.cos(lean), math.sin(lean)
        squeeze = 1.0 if d is not self.d['torso'] else 1-.07*clamp(v['turn'])      # the profile drawing is not squeezed
        hn = abs(d['neck'][1])*sy
        rows = self._torso_rows(d) if (abs(yaw) > 1e-6 or abs(hem) > 1e-6) else None

        def f(u, w, sprite=False):
            u, w = np.asarray(u, float), np.asarray(w, float)
            if abs(yaw) > 1e-6:
                rs, rhw, rc = rows
                hw, cu = np.interp(-w, rs, rhw), np.interp(-w, rs, rc)
                t = np.clip((u-cu)/hw, -1, 1)
                u = (u-cu)*(1-.06*abs(yaw))+cu+yaw*hw*(.05+.30*(1-t*t))
            x, y = u*(squeeze if sprite else 1.0)*sx, w*sy
            if abs(bend) > 1e-6:
                th = bend*(-y)/hn
                x, y = hn/bend*(1-np.cos(th))+x*np.cos(th), -hn/bend*np.sin(th)+x*np.sin(th)
            if abs(hem) > 1e-6:
                rs = rows[0]
                x = x+hem*(1-smooth(rs[0]*sy, (rs[0]+.45*(rs[-1]-rs[0]))*sy, -y))
            return pelvis[0]+x*cl-y*sl, pelvis[1]+x*sl+y*cl
        return f

    def _torso(self, canvas, p, v, wobble):
        part = p['torso_part']
        hem = (wobble or {}).get('hem', 0.0)
        if abs(v['bend']) < 1e-4 and abs(v['body_yaw']) < 1e-4 and abs(hem) < 1e-4:
            px, py = p['pelvis']
            args = (part, px, py, v['lean'], v['torso_sx']*(1.0 if p['is_profile'] else 1-.07*p['turn']), v['torso_sy'])
            self._torso_draw = lambda c: self.sprite(c, *args)
            self._torso_draw(canvas)
            return
        image = self.image(part['file'])
        upp, (ppx, ppy) = part['upp'], part['pivot']
        xf = self._torso_xf(v, wobble, p['pelvis'], part)

        def forward(sx, sy):
            x, y = xf((sx-ppx)*upp, (sy-ppy)*upp, True)
            return x/upp, y/upp
        x0, y0, x1, y1 = self._alpha_box(image)
        gx, gy = np.meshgrid(np.linspace(x0, x1, 25), np.linspace(y0, y1, 25))
        wx, wy = forward(gx, gy)
        box = (math.floor(wx.min())-2, math.floor(wy.min())-2, math.ceil(wx.max())+2, math.ceil(wy.max())+2)
        cache = {}

        def draw(c):
            c.save()
            c.scale(upp, upp)
            if 'img' not in cache:
                cache['img'] = self._warp(c, [(image, None)], forward, box)
            self._blit(c, *cache['img'])
            c.restore()
        self._torso_draw = draw
        draw(canvas)

    # ---- drawing ----
    def sprite(self, canvas, part, x, y, angle=0.0, sx=1.0, sy=1.0, paint=None):
        image = self.image(part['file'])
        canvas.save()
        canvas.translate(x, y)
        canvas.rotate(angle)
        canvas.scale(sx*part['upp'], sy*part['upp'])
        canvas.translate(-part['pivot'][0], -part['pivot'][1])
        image.draw(canvas, paint=paint)
        canvas.restore()

    def _arm(self, canvas, p, v, side):
        d = self.d
        points = p['arm_'+side]
        (ax, ay), (bx, by) = points[-3], points[-1]
        direction = math.degrees(math.atan2(by-ay, bx-ax))
        hand = d['hands'][v['hand_'+side]]
        flip = -1 if v[f'hand_{side}_flip'] < 0 else 1
        if d.get('anatomy', True):
            # The thumb side is not a free choice either: thumbs point up on a reaching arm, forward (inwards in a
            # front view) on a hanging one and towards the head on a raised one. Hand art has the thumb a quarter
            # turn anticlockwise from the fingers.
            length = math.hypot(bx-ax, by-ay) or 1e-6
            ux, uy = (bx-ax)/length, (by-ay)/length
            if uy < 0:
                toward = 1 if bx < p['neck'][0] else -1
            else:
                toward = 1 if (p['turn'] >= .5 or side == 'l') else -1
            flip = 1 if uy*toward+1.2*ux >= 0 else -1
            # Which face of the hand shows follows from the same anatomy. Rig side 'l' is the body's right hand and
            # 'r' its left; an unmirrored drawing (thumb anticlockwise of the fingers) is a left palm or a right back.
            if hand.get('back') and (flip > 0) != (side == 'r'):
                hand = hand['back']
        canvas.save()
        canvas.translate(bx, by)
        canvas.rotate(direction+v[f'hand_{side}_rot'])
        canvas.scale(1, flip)
        canvas.rotate(-hand['dir'])
        canvas.scale(hand['upp'], hand['upp'])
        canvas.translate(-hand['pivot'][0], -hand['pivot'][1])
        item = d.get('items', {}).get(v.get('item_'+side) or '')
        if item and not item.get('front'):
            self._item(canvas, hand, item)
        self.image(hand['file']).draw(canvas)
        if item and item.get('front'):
            self._item(canvas, hand, item)
        canvas.restore()
        merge = None
        if p['arm_z_'+side] >= .5 and getattr(self, '_torso_draw', None) and p['torso_part'].get('merge', True):
            merge = dict(draw=self._torso_draw, radius=d['arm']['w'][0]*1.05, color=self._torso_color(p['torso_part']))
        draw_hose(canvas, points, d['arm'], self.colors['outline'], d['outline'], merge, d['arm'].get('cuff_extend', 6.5))

    def _item(self, canvas, hand, item):
        """An object held in the hand, drawn in hand-sprite pixels. It sits on the hand's `grip` point (default: pivot)
        and its `dir` (the angle of the item's main axis in its own sprite, e.g. -90 for a fork with tines up) is laid
        along the thumb side of the fist, a quarter turn anticlockwise from the fingers. `rot` adds a fixed tilt."""
        gx, gy = hand.get('grip', hand['pivot'])
        canvas.save()
        canvas.translate(gx, gy)
        canvas.rotate(hand['dir']-90-item.get('dir', -90.0)+item.get('rot', 0.0))
        k = item['upp']/hand['upp']
        canvas.scale(k, k)
        canvas.translate(-item['pivot'][0], -item['pivot'][1])
        self.image(item['file']).draw(canvas)
        canvas.restore()

    def _wear(self, canvas, p, v, wobble):
        """A garment (`wear` channel -> rig `wear[name][front|profile|back3q]`) laid on the torso through the same
        deformation, so it bends and turns with it. `at` places the sprite pivot relative to the torso's neck point."""
        spec = self.d.get('wear', {}).get(v.get('wear') or '')
        if not spec:
            return
        part = spec.get('back3q' if p['is_back'] else 'profile' if p['is_profile'] else 'front')
        if not part:
            return
        tpart = p['torso_part']
        xf = self._torso_xf(v, wobble, p['pelvis'], tpart)
        image = self.image(part['file'])
        upp, (ppx, ppy) = part['upp'], part['pivot']
        ax, ay = tpart['neck'][0]+part.get('at', [0, 0])[0], tpart['neck'][1]+part.get('at', [0, 0])[1]

        def forward(sx, sy):
            x, y = xf(ax+(sx-ppx)*upp, ay+(sy-ppy)*upp, True)
            return x/upp, y/upp
        x0, y0, x1, y1 = self._alpha_box(image)
        gx, gy = np.meshgrid(np.linspace(x0, x1, 17), np.linspace(y0, y1, 17))
        wx, wy = forward(gx, gy)
        box = (math.floor(wx.min())-2, math.floor(wy.min())-2, math.ceil(wx.max())+2, math.ceil(wy.max())+2)
        canvas.save()
        canvas.scale(upp, upp)
        self._blit(canvas, *self._warp(canvas, [(image, None)], forward, box))
        canvas.restore()

    def _torso_color(self, t):
        """Torso fill colour next to the shoulder when it visibly differs from the sleeve's first band."""
        if not hasattr(self, '_tcolor'):
            self._tcolor = {}
        if t['file'] not in self._tcolor:
            image = self.image(t['file']).levels[0].toarray()
            upp, (px, py) = t['upp'], t['pivot']
            sx, sy = t['shoulder']
            cx, cy = int(px+sx/upp), int(py+(sy+4)/upp)
            block = image[cy-3:cy+4, cx-3:cx+4, 2::-1].reshape(-1, 3).astype(float)   # BGRA -> RGB
            block = block[block.sum(axis=1) > 240]
            rgb = np.median(block, axis=0) if len(block) else np.zeros(3)
            band = self.d['arm']['bands'][0]['color'].lstrip('#')
            target = np.array([int(band[i:i+2], 16) for i in (0, 2, 4)], float)
            self._tcolor[t['file']] = None if (not len(block) or np.abs(rgb-target).max() < 5) else '#%02x%02x%02x' % tuple(int(c) for c in rgb)
        return self._tcolor[t['file']]

    def _leg(self, canvas, p, v, side):
        d = self.d
        spec, paint = d['leg'], None
        far = round(p['turn']*8)/8 if side == 'r' else 0.0       # the leg on the far side of a turned body sits in shade
        if far > 0:
            cache = self.__dict__.setdefault('_far_leg', {})
            if far not in cache:
                shade = self.colors.get('leg_shade') or self.colors['outline']
                cache[far] = dict(spec, bands=[dict(b, color=mix(b['color'], shade, far)) for b in spec.get('bands', [])])
            spec = cache[far]
            paint = skia.Paint(ColorFilter=skia.ColorFilters.Blend(rgba(self.colors['outline'], .4*far), skia.BlendMode.kSrcATop))
        boot = d['boots'][v['boot_'+side]]
        flip = -1 if (side == 'l' and p['turn'] < .5) else 1
        x, y = p['ankle_'+side]
        angle = p['foot_rot_'+side]*flip
        mouth = boot.get('mouth')
        if not mouth:                                   # legacy boots: the sprite simply covers the end of the leg
            draw_hose(canvas, p['leg_'+side], spec, self.colors['outline'], d['outline'])
            self.sprite(canvas, boot, x, y, angle, flip, 1, paint)
            return
        # The leg goes into the boot: it shows above the mouth and inside the opening, and the front rim stays over it.
        self.sprite(canvas, boot, x, y, angle, flip, 1, paint)
        (cx, cy), rx, ry = mouth['c'], mouth['rx'], mouth['ry']
        clip = skia.Path()
        clip.addRect(skia.Rect.MakeLTRB(cx-4000, cy-6000, cx+4000, cy))
        clip.addOval(skia.Rect.MakeLTRB(cx-rx, cy-ry, cx+rx, cy+ry))
        matrix = skia.Matrix()
        matrix.setTranslate(-boot['pivot'][0], -boot['pivot'][1])
        matrix.postScale(flip*boot['upp'], boot['upp'])
        matrix.postRotate(angle)
        matrix.postTranslate(x, y)
        clip.transform(matrix)
        canvas.save()
        canvas.clipPath(clip, skia.ClipOp.kIntersect, True)
        draw_hose(canvas, p['leg_'+side], spec, self.colors['outline'], d['outline'])
        canvas.restore()

    def draw(self, canvas, p, v, wobble=None):
        d = self.d
        turn = p['turn']
        if p['arm_z_r'] < .5:
            self._arm(canvas, p, v, 'r')
        if p['arm_z_l'] < .5:
            self._arm(canvas, p, v, 'l')
        self._leg(canvas, p, v, 'r')
        self._leg(canvas, p, v, 'l')
        px, py = p['pelvis']
        self.sprite(canvas, d['hips'], px, py, v['lean']*.25, p['hip_squeeze'], 1)
        self._neck(canvas, p)
        self._torso(canvas, p, v, wobble)
        self._wear(canvas, p, v, wobble)
        if 0.5 <= p['arm_z_r'] < 1.5:
            self._arm(canvas, p, v, 'r')
        if 0.5 <= p['arm_z_l'] < 1.5:
            self._arm(canvas, p, v, 'l')
        self._head(canvas, p, v, wobble or {})
        if p['arm_z_r'] >= 1.5:
            self._arm(canvas, p, v, 'r')
        if p['arm_z_l'] >= 1.5:
            self._arm(canvas, p, v, 'l')

    def _neck(self, canvas, p):
        """Drawn behind torso and head, so it only shows where a gap would open between them."""
        d = self.d
        spec = d.get('neck', {})
        width = spec.get('w', d['arm']['w'][0]*1.05)
        color = spec.get('color') or self.colors.get('neck') or d['arm']['bands'][0]['color']
        angle = math.radians(p['head_angle'])
        (ax, ay), (nx, ny) = p['neck_base'], p['neck']
        bx, by = nx+math.sin(angle)*10, ny-math.cos(angle)*10
        line = skia.Path()
        line.moveTo(ax, ay)
        line.quadTo(nx, ny, bx, by)
        ink = stroke(self.colors['outline'], width+2*d['outline'])
        ink.setStrokeCap(skia.Paint.kRound_Cap)
        body = stroke(color, width)
        body.setStrokeCap(skia.Paint.kRound_Cap)
        canvas.drawPath(line, ink)
        canvas.drawPath(line, body)

    def _head(self, canvas, p, v, wobble):
        view = p['view']
        image = self.image(view['file'])
        canvas.save()
        canvas.translate(*p['neck'])
        canvas.rotate(p['head_angle'])
        canvas.scale(view['upp']*v['head_sx'], view['upp']*v['head_sy'])
        canvas.translate(-view['pivot'][0], -view['pivot'][1])
        active = [(item, wobble.get(item['name'], 0.0)) for item in view.get('appendages', [])]
        fx, fy = clamp(v['face_x'], -1, 1), clamp(v['face_y'], -1, 1)
        if view.get('back'):
            fx = fy = 0.0
        vertices = None
        if abs(fx) > 1e-4 or abs(fy) > 1e-4 or any(abs(angle) > 1e-4 for _, angle in active):
            forward = self._head_forward(view, active, fx, fy)
            x0, y0, x1, y1 = self._alpha_box(image)
            gx, gy = np.meshgrid(np.linspace(x0, x1, 25), np.linspace(y0, y1, 25))
            wx, wy = forward(gx, gy)
            vertices = (self._head_forward(view, [], fx, fy), (math.floor(wx.min())-2, math.floor(wy.min())-2, math.ceil(wx.max())+2, math.ceil(wy.max())+2))
            self._blit(canvas, *self._warp(canvas, [(image, None)], forward, vertices[1]))
        else:
            image.draw(canvas)
        if not view.get('back'):
            self._face(canvas, view, v, vertices)       # a back view draws no face features
        canvas.restore()

    # ---- mesh warp (CPU): backward sampling through a smooth forward map ----
    def _alpha_box(self, tex):
        key = ('box', id(tex))
        if key not in self._images:
            alpha = tex.levels[0].toarray()[..., 3]
            ys, xs = np.where(alpha > 6)
            self._images[key] = (float(xs.min()), float(ys.min()), float(xs.max()+1), float(ys.max()+1))
        return self._images[key]

    def _pixels(self, tex, level):
        """Premultiplied float32 pixels of a mip level with a 1px transparent border (cached)."""
        key = ('px', id(tex), level)
        if key not in self._images:
            arr = np.atleast_3d(tex.levels[level].toarray(
                alphaType=skia.kPremul_AlphaType)).astype(np.float32)
            self._images[key] = np.pad(arr, ((1, 1), (1, 1), (0, 0)))
        return self._images[key]

    def _warp(self, canvas, textures, forward, bounds, n=20):
        """Draw `textures` (list of (Tex, paint or None)) warped by the smooth forward map forward(x, y) -> (x, y)
        (sprite px, numpy arrays). The inverse is solved on a coarse grid, upsampled, and each texture is sampled
        bilinearly in numpy at (at most) native resolution: far cheaper on CPU than skia.Vertices with a shader."""
        m = canvas.getTotalMatrix()
        k = math.sqrt(abs(m.getScaleX()*m.getScaleY()-m.getSkewX()*m.getSkewY()))
        f = clamp(k, .2, 1.0)
        x0, y0, x1, y1 = bounds
        w, h = max(2, math.ceil((x1-x0)*f)), max(2, math.ceil((y1-y0)*f))
        qx, qy = np.meshgrid(np.linspace(x0, x1, n+1), np.linspace(y0, y1, n+1))
        sx, sy = qx.copy(), qy.copy()
        for _ in range(6):
            fx_, fy_ = forward(sx, sy)
            sx, sy = sx-(fx_-qx), sy-(fy_-qy)
        def interp(count):
            """Linear interpolation matrix from the (n+1) coarse nodes to `count` pixel centres."""
            c = (np.arange(count)+.5)/count*n
            i = np.clip(c.astype(int), 0, n-1)
            matrix = np.zeros((count, n+1), np.float32)
            matrix[np.arange(count), i] = 1-(c-i)
            matrix[np.arange(count), i+1] = c-i
            return matrix
        wy_, wx_ = interp(h), interp(w)
        fine_x = (wy_ @ sx.astype(np.float32)) @ wx_.T
        fine_y = (wy_ @ sy.astype(np.float32)) @ wx_.T
        images = []
        for tex, paint in textures:
            level = min(len(tex.levels)-1, int(math.log2(1/f))) if f < 1 else 0
            arr = self._pixels(tex, level)
            lw, lh = tex.levels[level].width(), tex.levels[level].height()
            u = np.clip(fine_x*np.float32(lw/tex.w)+np.float32(.5), 0, lw+1-1e-3)
            v = np.clip(fine_y*np.float32(lh/tex.h)+np.float32(.5), 0, lh+1-1e-3)
            iu, iv = u.astype(np.int32), v.astype(np.int32)
            fu, fv = (u-iu)[..., None], (v-iv)[..., None]
            flat = arr.reshape(-1, arr.shape[2])
            i00 = iv*arr.shape[1]+iu
            stride = arr.shape[1]
            out = np.take(flat, i00, axis=0)
            out *= (1-fu)*(1-fv)
            out += np.take(flat, i00+1, axis=0)*(fu*(1-fv))
            out += np.take(flat, i00+stride, axis=0)*((1-fu)*fv)
            out += np.take(flat, i00+stride+1, axis=0)*(fu*fv)
            if out.shape[2] == 4:
                np.minimum(out[..., :3], out[..., 3:4], out=out[..., :3])
            out += .5
            pixels = np.clip(out, 0, 255, out=out).astype(np.uint8)
            img = skia.Image.fromarray(pixels if pixels.shape[2] > 1 else pixels[..., 0],
                                       colorType=tex.levels[level].colorType(), alphaType=tex.levels[level].alphaType())
            images.append((img, paint))
        return images, skia.Rect.MakeLTRB(x0, y0, x1, y1)

    @staticmethod
    def _blit(canvas, images, rect):
        for img, paint in images:
            canvas.drawImageRect(img, skia.Rect.MakeWH(img.width(), img.height()), rect, LINEAR, paint)

    def _head_forward(self, view, active, fx, fy):
        """Head warp: face plate slide (yaw/pitch) + appendage spring bend + appendage yaw shift."""
        def forward(gx, gy):
            dx, dy = head_plate(view, fx, fy, gx, gy)
            px, py = gx, gy
            for item, angle in active:
                bx, by = item['base']
                ax, ay = item['tip'][0]-bx, item['tip'][1]-by
                length2 = ax*ax+ay*ay
                along = ((gx-bx)*ax+(gy-by)*ay)/length2
                across = ((gx-bx)*-ay+(gy-by)*ax)/length2
                weight, shift = head_appendage(view, fx, bx, by, 0, 0, along, across, item.get('spread', .9))
                theta = angle*weight
                rx, ry = px-bx, py-by
                px = bx+rx*np.cos(theta)-ry*np.sin(theta)+shift
                py = by+rx*np.sin(theta)+ry*np.cos(theta)
            return px+dx, py+dy
        return forward

    def mask(self, filename):
        """Face mask as a real alpha image (the PNG is grayscale and opaque), Alpha8 with a small mip chain."""
        key = 'mask:'+filename
        if key not in self._images:
            gray = skia.Image.open(str(self.root/filename)).toarray()
            level = (gray if gray.ndim == 2 else gray[..., 0]).astype(np.float32)
            tex, levels = Tex.__new__(Tex), []
            tex.h, tex.w = level.shape
            for _ in range(4):
                levels.append(skia.Image.fromarray(np.ascontiguousarray(level.astype(np.uint8)), colorType=skia.kAlpha_8_ColorType))
                h, w = level.shape[0]//2*2, level.shape[1]//2*2
                level = level[:h, :w].reshape(h//2, 2, w//2, 2).mean(axis=(1, 3))
            tex.levels = levels
            self._images[key] = tex
        return self._images[key]

    def _face(self, canvas, view, v, vertices=None):
        f, col = view['face'], self.colors
        line = f['line']
        box = f['bbox']
        canvas.saveLayer(skia.Rect.MakeLTRB(box[0]-4, box[1]-4, box[2]+4, box[3]+4), None)
        fw, fh = box[2]-box[0], box[3]-box[1]
        yaw, pitch = clamp(v['face_x'], -1, 1), clamp(v['face_y'], -1, 1)
        fcx = (box[0]+box[2])/2

        def shift(c, depth):
            """Depth parallax: features slide by the plate displacement times their depth factor."""
            dx, dy = head_plate(view, yaw, pitch, c[0], c[1])
            return float(dx)*depth, float(dy)*depth

        def narrow(cx, near=.28, far=.10):
            """Foreshortening: the side the head turns toward narrows, the other widens."""
            t = yaw*(1 if cx >= fcx else -1)
            return 1-(near if t > 0 else far)*t
        if v['blush'] > .01:
            for side in [s for s in 'lr' if 'blush_'+s in f]:
                b = f['blush_'+side]
                ox, oy = shift(b['c'], .75)
                k = 1+(narrow(b['c'][0])-1)*.6
                canvas.drawOval(skia.Rect.MakeLTRB(b['c'][0]+ox-b['rx']*k, b['c'][1]+oy-b['ry'], b['c'][0]+ox+b['rx']*k, b['c'][1]+oy+b['ry']),
                                fill(col['blush'], .85*clamp(v['blush'], 0, 1.4)/1.0 if v['blush'] <= 1 else .95))
        pupil = f['pupil']
        for side in [s for s in 'lr' if 'eye_'+s in f]:
            e = f['eye_'+side]
            cx, cy = e['c']
            ox, oy = shift(e['c'], .95)
            canvas.save()
            canvas.translate(cx+ox, cy+oy)
            canvas.scale(narrow(cx), 1-.07*abs(pitch))
            canvas.translate(-cx, -cy)
            rx, ry = e['rx'], e['ry']*v['eye_open']
            lid, squint = clamp(v['lid']+v.get('lid_'+side, 0.0)), clamp(v['squint'])
            if lid+squint*.55 >= .88:
                y0, hw = cy+ry*.12, rx*.95
                bulge = ry*.5*(1-2*squint)
                arc = skia.Path()
                arc.moveTo(cx-hw, y0-bulge*.45)
                arc.quadTo(cx, y0+bulge, cx+hw, y0-bulge*.45)
                canvas.drawPath(arc, stroke(col['outline'], line))
            else:
                eye = skia.Path()
                eye.addOval(skia.Rect.MakeLTRB(cx-rx, cy-ry, cx+rx, cy+ry))
                top = cy-ry
                if lid > .01 or squint > .01:
                    # Upper lid: the eye's own top arch slid down, so a half-closed eye stays a rounded, relaxed lens (a flat
                    # bar reads as contempt). The arch only flattens as the lid nears the closed curve.
                    top, bottom = cy-ry+2*ry*lid, cy+ry-2*ry*squint*.55
                    top_side = top+ry*lerp(.8, .36, lid)
                    bottom_side = bottom+ry*.35*squint
                    window = skia.Path()
                    window.moveTo(cx-rx-9, top_side)
                    window.quadTo(cx, 2*top-top_side, cx+rx+9, top_side)
                    window.lineTo(cx+rx+9, bottom_side)
                    window.quadTo(cx, 2*bottom-bottom_side, cx-rx-9, bottom_side)
                    window.close()
                    eye = skia.Op(eye, window, skia.PathOp.kIntersect_PathOp)
                canvas.drawPath(eye, fill(col['eye_white']))
                canvas.save()
                canvas.clipPath(eye, skia.ClipOp.kIntersect, True)
                prx, pry = pupil['rx']*v['pupil'], pupil['ry']*v['pupil']
                ux = cx+clamp(v['look_x'], -1, 1)*max(0, rx-prx*.82)
                uy = cy+clamp(v['look_y'], -1, 1)*max(0, e['ry']-pry*.82)
                if lid > .01:
                    # the pupil rides down with the lid and stays visible until the eye is nearly shut (no hidden-pupil bar)
                    uy = min(max(uy, top+pry*.5), cy+ry-pry*.3)
                canvas.drawOval(skia.Rect.MakeLTRB(ux-prx, uy-pry, ux+prx, uy+pry), fill(col['pupil']))
                hx, hy = pupil['highlight_offset']
                canvas.drawCircle(ux+hx*v['pupil'], uy+hy*v['pupil'], pupil['highlight_r']*v['pupil'], fill(col['eye_white']))
                canvas.restore()
                canvas.drawPath(eye, stroke(col['outline'], line))
            canvas.restore()
            b = f['brow_'+side]
            ox, oy = shift(b['c'], .9)
            canvas.save()
            canvas.translate(b['c'][0]+ox, b['c'][1]+oy-v['brow_y']*e['ry']*.6)
            canvas.scale(1+(narrow(b['c'][0])-1)*.8, 1)
            canvas.rotate(v['brow_rot']*(-1 if side == 'l' else 1))
            brow = skia.Path()
            brow.moveTo(-b['w']/2, b['w']*.07)
            brow.quadTo(0, -b['w']*.30, b['w']/2, b['w']*.07)
            canvas.drawPath(brow, stroke(col['outline'], b.get('thickness', line*.8)))
            canvas.restore()
        if f.get('nose') and col.get('nose'):
            ox, oy = shift(f['nose']['c'], 1.2)
            nr = f['nose']['r']
            canvas.drawOval(skia.Rect.MakeLTRB(f['nose']['c'][0]+ox-nr*(1-.14*abs(yaw)), f['nose']['c'][1]+oy-nr, f['nose']['c'][0]+ox+nr*(1-.14*abs(yaw)), f['nose']['c'][1]+oy+nr), fill(col['nose']))
        m = f['mouth']
        ox, oy = shift(m['c'], 1.05)
        mx, my = m['c'][0]+ox, m['c'][1]+oy+v['mouth_y']
        w, s, o = m['w']*v['mouth_w']*(1-.16*abs(yaw)), v['smile'], clamp(v['mouth_open'])
        mouth = skia.Path()
        corner = -s*w*.09
        if o < .06:
            mouth.moveTo(mx-w/2, my+corner)
            mouth.quadTo(mx, my+s*w*.42, mx+w/2, my+corner)
            canvas.drawPath(mouth, stroke(col['outline'], m.get('thickness', line)))
        else:
            # A round mouth opens evenly around its corners (an O); a flat one hangs below them (a D).
            top = my+corner+s*w*.12-v['mouth_round']*o*w*.55
            bottom = my+corner+o*w*(1.05-.5*v['mouth_round'])+max(s, 0)*w*.22
            mouth.moveTo(mx-w/2, my+corner)
            mouth.quadTo(mx, top, mx+w/2, my+corner)
            mouth.quadTo(mx, bottom, mx-w/2, my+corner)
            mouth.close()
            canvas.drawPath(mouth, fill(col['mouth_inside']))
            canvas.save()
            canvas.clipPath(mouth, skia.ClipOp.kIntersect, True)
            depth = (bottom-my-corner)*.5
            canvas.drawOval(skia.Rect.MakeLTRB(mx-w*.30, my+corner+depth*.55, mx+w*.30, my+corner+depth*1.5), fill(col['tongue']))
            canvas.restore()
            canvas.drawPath(mouth, stroke(col['outline'], m.get('thickness', line)))
        if view.get('mask'):
            mask = self.mask(view['mask'])
            if vertices is None:
                mask.draw(canvas, 0, 0, skia.Paint(BlendMode=skia.BlendMode.kDstIn))
            else:
                box = view['face']['bbox']
                margin = .2*(box[2]-box[0])+6
                region = (box[0]-margin, box[1]-margin, box[2]+margin, box[3]+margin)
                self._blit(canvas, *self._warp(canvas, [(mask, skia.Paint(BlendMode=skia.BlendMode.kDstIn))], vertices[0], region))
        canvas.restore()


class Performer:
    """One actor in one shot: channel tracks + idle life + blinks + spring appendages."""

    def __init__(self, rig, spec, duration, seed=0):
        self.rig, self.spec, self.duration = rig, spec, duration
        self.seed = seed
        self.tracks = {name: Track(keys) for name, keys in spec.get('channels', {}).items()}
        unknown = set(self.tracks)-set(rig.defaults)
        if unknown:
            raise ValueError(f'Canales desconocidos: {sorted(unknown)}')
        self.blinks = sorted(spec.get('blinks', []))
        if spec.get('auto_blink', True):
            t = 0.6+2.4*hash01(seed, 'b0')
            index = 0
            while t < duration:
                if all(abs(t-b) > .5 for b in self.blinks):
                    self.blinks.append(t)
                    if hash01(seed, 'double', index) < .18:
                        self.blinks.append(t+.26)
                index += 1
                t += 2.3+2.6*hash01(seed, 'b', index)
            self.blinks.sort()
        self._springs = None

    def raw(self, t):
        v = dict(self.rig.defaults)
        for name, track in self.tracks.items():
            v[name] = track.at(t)
        return v

    def base_values(self, t):
        """Keyed channels plus idle life and blinks, before follow-through dynamics."""
        v = self.raw(t)
        life = v['life']
        if life > 0:
            a = 2*math.pi*(t/3.1+hash01(self.seed, 'breath'))
            breath = math.sin(a)
            v['torso_sy'] *= 1+.017*life*breath
            v['torso_sx'] *= 1-.007*life*breath
            v['head_dy'] -= 1.3*life*breath
            v['shoulder_l_dy'] -= 1.2*life*breath
            v['shoulder_r_dy'] -= 1.2*life*breath
            # A moving hold: weight drifts from one leg to the other over planted feet, arms and head settle after it.
            drift = lambda name, period: noise1(t/period+hash01(self.seed, name)*50, hash01(self.seed, name, 1)*997)
            shift = drift('weight', 2.6)
            v['hip_dx'] += 2.4*life*shift
            v['lean'] += life*(.5*math.sin(2*math.pi*(t/5.1+hash01(self.seed, 'sway')))-.9*shift)
            v['body_yaw'] += .05*life*drift('yaw', 3.4)
            v['head_rot'] += life*(.8*math.sin(2*math.pi*(t/4.3+hash01(self.seed, 'nod')))+1.3*drift('head', 2.1))
            v['face_x'] += .05*life*drift('face', 2.9)
            for side, sign in (('l', -1), ('r', 1)):
                # a raised arm is held by muscle, so it floats more than one that hangs
                held = 1+1.6*clamp(1-v[f'arm_{side}_y']/60)
                v[f'arm_{side}_x'] += life*(1.8*held*drift('arm'+side, 2.3)-.9*shift)
                v[f'arm_{side}_y'] += life*held*(1.5*drift('army'+side, 2.7)-.9*breath)
                v[f'hand_{side}_rot'] += 3.5*life*drift('hand'+side, 1.9)
            # Eyes never rest for long: small saccades every second or two.
            beat = math.floor(t/1.45+hash01(self.seed, 'dart'))
            if hash01(self.seed, 'dart', beat) > .45:
                v['look_x'] += .09*life*(hash01(self.seed, 'dartx', beat)*2-1)
                v['look_y'] += .06*life*(hash01(self.seed, 'darty', beat)*2-1)
        for start in self.blinks:
            u = t-start
            if 0 <= u < .26:
                closed = u/.06 if u < .06 else 1 if u < .125 else 1-(u-.125)/.135
                closed = 1.0 if closed > .8 else .5 if closed > .3 else 0.0     # one in-between drawing each way, never a slab
                v['lid'] = max(v['lid'], closed)
        return v

    # Channels that follow their keys through a damped spring: (frequency Hz, damping ratio).
    FOLLOW = {'arm_l_x': (3.3, .58), 'arm_l_y': (3.3, .58), 'arm_r_x': (3.1, .58), 'arm_r_y': (3.1, .58),
              'hand_l_rot': (2.8, .45), 'hand_r_rot': (2.7, .45), 'head_rot': (3.4, .6), 'head_dy': (3.6, .6)}

    def values(self, t):
        v = self.base_values(t)
        if not self.spec.get('dynamics', True):
            return v
        if self._springs is None:
            self._simulate()
        for name, series in self._springs[3].items():
            if name == 'bend':
                v['bend'] += self._series(series, t)
            else:
                v[name] = self._series(series, t)
        return v

    def _series(self, series, t):
        step, pre = self._springs[0], self._springs[1]
        index = max(0.0, (t+pre)/step)
        i = min(len(series)-1, int(index))
        j = min(len(series)-1, i+1)
        u = index-i
        return float(series[i]*(1-u)+series[j]*u)

    def _simulate(self):
        """One forward pass at 120 Hz: follow-through on limbs/head, torso bend, cloth hem, appendage springs."""
        step, pre = 1/120, 1.0
        count = int((self.duration+pre)/step)+3
        dynamic = self.spec.get('dynamics', True)
        items = {}
        for view in self.rig.d['head'].values():
            for item in view.get('appendages', []):
                items[item['name']] = item
        follow = {name: np.zeros(count) for name in self.FOLLOW} if dynamic else {}
        state = {}
        bend = np.zeros(count)
        xs, ys, angles, roots = np.zeros(count), np.zeros(count), np.zeros(count), np.zeros(count)
        lean_lag = lean_vel = 0.0
        for i in range(count):
            t = max(0.0, i*step-pre)
            v = self.base_values(t)
            if dynamic:
                for name, (freq, damp) in self.FOLLOW.items():
                    target = v[name]
                    if i == 0:
                        state[name] = [target, 0.0]
                    value, velocity = state[name]
                    omega = 2*math.pi*freq
                    velocity += (omega*omega*(target-value)-2*damp*omega*velocity)*step
                    value += velocity*step
                    state[name] = [value, velocity]
                    follow[name][i] = value
                    v[name] = value
                if i == 0:
                    lean_lag = v['lean']
                omega = 2*math.pi*2.4
                lean_vel += (omega*omega*(v['lean']-lean_lag)-2*.55*omega*lean_vel)*step
                lean_lag += lean_vel*step
                bend[i] = max(-16.0, min(16.0, -(v['lean']-lean_lag)*.9))   # the chest lags the hips
                v['bend'] += bend[i]
            p = self.rig.pose(v)
            xs[i] = v['x']+v['facing']*v['scale']*p['head_top'][0]
            ys[i] = v['y']-v['lift']+v['scale']*p['head_top'][1]
            roots[i] = v['x']*v['facing']/max(v['scale'], 1e-6)
            angles[i] = math.radians(p['head_angle'])*v['facing']
        ax = np.gradient(np.gradient(xs, step), step)
        ay = np.gradient(np.gradient(ys, step), step)
        aa = np.gradient(np.gradient(angles, step), step)
        out = {}
        for name, item in items.items():
            omega = 2*math.pi*item.get('freq', 3.0)
            damp, gain = item.get('damp', .22), item.get('gain', 1.0)
            theta = velocity = 0.0
            series = np.zeros(count)
            for i in range(count):
                force = -gain*(ax[i]*.0045+ay[i]*.0018*item.get('vertical', 1.0)+aa[i]*.16)
                force = max(-900.0, min(900.0, force))
                velocity += (-omega*omega*theta-2*damp*omega*velocity+force)*step
                theta += velocity*step
                theta = max(-.75, min(.75, theta))
                series[i] = theta
            out[name] = series
        # Cloth hem: lags the root's horizontal acceleration (local units of sideways offset at the hem).
        accel = np.gradient(np.gradient(roots, step), step)
        hem = np.zeros(count)
        offset = velocity = 0.0
        omega = 2*math.pi*2.1
        for i in range(count):
            force = max(-2500.0, min(2500.0, -accel[i]*.55))
            velocity += (-omega*omega*offset-2*.32*omega*velocity+force)*step
            offset = max(-9.0, min(9.0, offset+velocity*step))
            hem[i] = offset
        out['hem'] = hem
        if dynamic:
            follow['bend'] = bend
        self._springs = (step, pre, out, follow)

    def wobble(self, t, facing=1.0):
        if self._springs is None:
            self._simulate()
        step, pre, out = self._springs[0], self._springs[1], self._springs[2]
        index = (t+pre)/step
        i = int(index)
        u = index-i
        result = {}
        for name, series in out.items():
            i0 = min(len(series)-1, max(0, i))
            i1 = min(len(series)-1, i0+1)
            result[name] = float(series[i0]*(1-u)+series[i1]*u)*facing
        return result

    # Channels that always follow the true time; the pose itself may be held "on twos".
    ROOT = ('x', 'y', 'lift', 'scale', 'facing', 'opacity', 'rot', 'shadow')
    FAST = (('foot_l_x', 2.0), ('foot_r_x', 2.0), ('foot_l_y', 2.0), ('foot_r_y', 2.0), ('arm_l_x', 9.0), ('arm_l_y', 9.0),
            ('arm_r_x', 9.0), ('arm_r_y', 9.0), ('lean', 4.0), ('head_rot', 5.0), ('hip_dy', 3.0), ('lift', 2.5), ('sx', .05),
            ('lid', .1), ('squint', .12), ('mouth_open', .1), ('look_x', .1), ('look_y', .1), ('brow_y', .15), ('face_x', .08))

    def drawing(self, t, fps, hold=2):
        """Values and wobble for the drawing shown at t: held for `hold` frames unless the action is fast."""
        if hold <= 1:
            return self.values(t), self.wobble(t, 1.0)
        frame = int(math.floor(t*fps+1e-6))
        held = (frame//hold)*hold/fps
        now, nxt, true = self.values(held), self.values(held+hold/fps), self.values(t)
        moving = abs(nxt['x']-now['x']) > .2*hold       # a held drawing over a moving root would make planted feet skate
        if moving or any(abs(nxt[name]-now[name]) > limit*hold for name, limit in self.FAST) or now['facing'] != true['facing']:
            return true, self.wobble(t, 1.0)         # fast action: animate on ones
        for name in self.ROOT:
            now[name] = true[name]
        return now, self.wobble(held, 1.0)

    def _drawing_sig(self, frame, fps, hold):
        """(drawing signature, turn, facing) of the drawing shown on integer `frame` (cached: pure function of the frame)."""
        cache = self.__dict__.setdefault('_sig_cache', {})
        key = (frame, fps, hold)
        if key not in cache:
            v, _ = self.drawing(frame/fps, fps, hold)
            view = self.rig.view_key(v)
            # A mirror flip of the (symmetric) front drawing changes nothing on screen, so it is not a switch.
            cache[key] = ((view, v['facing'] >= 0 if view != 'front' else None),
                          clamp(v['turn'], 0.0, self.rig.turn_max()), v['facing'])
        return cache[key]

    # Turn change per frame (in `turn` units) that counts as a full-speed turn; slower turns get a softer in-between.
    SMEAR_FULL = .25

    def transition(self, t, fps, hold=2):
        """Drawing-switch in-between for the frame at `t`, or None when no switch is within two frames.

        A switch is a change of head view (front/3q/profile) or of mirror side between frames j and j+1.
        Frames j and j+1 get `ghost` (the other drawing, to be dissolved in at weight `mix`) plus a smear; frames
        j-1 and j+2 get a weaker smear only. `power` (0..1) grows with how fast the turn is happening."""
        f = int(math.floor(t*fps+1e-6))
        sigs = {j: self._drawing_sig(j, fps, hold) for j in range(f-2, f+3)}
        for j, role in ((f, 'last'), (f-1, 'first'), (f+1, 'before'), (f-2, 'after')):
            a, b = sigs[j], sigs[j+1]
            if a[0] == b[0]:
                continue
            speed = abs(b[1]-a[1])+(1.0 if (a[2] >= 0) != (b[2] >= 0) else 0.0)
            power = clamp(speed/self.SMEAR_FULL, .35, 1.0)
            # Profile/back drawings differ most from their neighbours (silhouette and torso both swap): full strength there only.
            power *= 1.0 if ({a[0][0], b[0][0]} & {'profile', 'back3q'}) else .6
            if role in ('before', 'after'):
                return {'role': role, 'power': power*.4, 'mix': 0.0, 'ghost': None}
            other = j+1 if role == 'last' else j
            values, wobble = self.drawing(other/fps, fps, hold)
            return {'role': role, 'power': power, 'mix': .2*power+.06, 'ghost': (values, wobble)}
        return None

    def anchor(self, name, t):
        """World position of a named rig point (hand_l, tip_antenna, face, head_top...)."""
        v = self.values(t)
        p = self.rig.pose(v, self.wobble(t, v['facing']))
        lx, ly = p[name]
        ax, ay = rot(lx*v['sx'], ly*v['sy'], math.radians(v['rot']))
        return v['x']+v['facing']*v['scale']*ax, v['y']+v['scale']*ay
