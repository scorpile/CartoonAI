"""Close the hole of the bears' grip paws (hand_grip / handb_grip).

The art drew the grip as a tube seen end-on, but held items are drawn in the picture plane behind the fist, so the
hole showed the background. The hole and its ring outline are painted over with the paw's own fur colour; the item
then shows above and below the fist. Originals are kept as *_hole.png. Deterministic, idempotent.
"""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]/'projects/tres-osos/assets'


def fill(path):
    keep = path.with_name(path.stem+'_hole.png')
    if not keep.exists():
        keep.write_bytes(path.read_bytes())
    img = np.array(Image.open(keep).convert('RGBA')).astype(float)
    alpha = img[..., 3] > 128
    hole = ndi.binary_fill_holes(alpha) & ~alpha
    lab, n = ndi.label(hole)
    if not n:
        return 'no hole'
    sizes = ndi.sum(hole, lab, range(1, n+1))
    hole = lab == 1+int(np.argmax(sizes))
    lum = img[..., :3] @ [.299, .587, .114]
    dark = alpha & (lum < 90)
    # ring = dark pixels connected to the hole within a few pixels
    ring = np.zeros_like(hole)
    grow = hole.copy()
    for _ in range(24):
        grow = ndi.binary_dilation(grow)
        new = grow & dark & ~ring
        if not new.any():
            break
        ring |= new
        grow = hole | ring
    patch = ndi.binary_dilation(hole | ring, iterations=2) & (hole | alpha)
    near = ndi.binary_dilation(patch, iterations=4) & alpha & ~dark & ~patch & (lum > 70)
    fur = np.median(img[near][:, :3], axis=0)
    # Diffuse the surrounding fur into the patch (masked Jacobi): the paw's shading continues across it.
    out = img.copy()
    out[patch, :3] = fur
    out[patch, 3] = 255
    source = alpha & ~dark & ~patch
    known = source.astype(float)
    rgb = out[..., :3]*known[..., None]
    rgb[patch] = fur
    weight = known.copy()
    weight[patch] = 1.0
    k = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], float)
    for _ in range(300):
        num = np.stack([ndi.convolve(rgb[..., c]*weight, k, mode='constant') for c in range(3)], -1)
        den = ndi.convolve(weight, k, mode='constant')[..., None]
        rgb[patch] = (num[patch]/np.maximum(den[patch], 1e-6))
    out[patch, :3] = rgb[patch]
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(path)
    return f'filled {int(hole.sum())} px hole, ring {int(ring.sum())} px, fur {fur.round().tolist()}'


for cid in ('papa_oso', 'mama_osa', 'osito'):
    for name in ('hand_grip', 'handb_grip'):
        print(cid, name, fill(ROOT/cid/f'{name}.png'))
