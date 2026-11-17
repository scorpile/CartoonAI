"""Writes the Codex prompts for the tres-osos sets and props (text only)."""
from pathlib import Path
R = Path(__file__).resolve().parent/'art'
STYLE = """You are the art department for a 2D cartoon film. Use your built-in image generation tool (image_gen) for EVERY image. Do NOT draw art with code. Do not modify any repo file except the output files named below.
Style references attached: `projects/taller-v3/assets/set/main.png` and `projects/taller-v3/source/valley-studio.png`. Match their look exactly: flat cel colors, THICK dark-brown expressive outlines, storybook TV children's cartoon, warm palette, no gradients except soft sky, no photo realism, no text.
Each image: 16:9 landscape at the largest size the tool allows (about 1672x941). Use real alpha transparency where requested (transparent_background). After EACH generation open the PNG with Python/Pillow and verify the mode is RGBA and that the corner pixels have alpha 0 for transparent layers (opaque layers: alpha 255 everywhere). If a checkerboard or solid background was painted, or if the content violates the rules below, regenerate (max 3 attempts, keep the best). Look at each result. Finish with a 3-line summary: file, size, alpha check, attempts.
"""


def w(path, name, body):
    (R/path).mkdir(parents=True, exist_ok=True)
    (R/path/f'{name}.md').write_text(STYLE+body, encoding='utf-8')


B = 'sets/bosque'
LIGHT = "Light: warm golden mid-afternoon sun from the upper LEFT (shadows fall to the right)."
w(B, 'sky', LIGHT+"""
Save to `work/osos/art/sets/bosque/sky.png` - OPAQUE. Only a warm afternoon sky: soft pale blue at the top fading to creamy peach-gold near the bottom, with a faint soft sun glow in the upper left (about 20% from left, 15% from top). No clouds, no trees, no hills, no ground.""")
w(B, 'clouds', LIGHT+"""
Save to `work/osos/art/sets/bosque/clouds.png` - TRANSPARENT background. Exactly 4 separate stylized fluffy cartoon clouds (cream-white with soft peach-pink undersides, thick brown-ish outlines like the reference), well spaced apart and different sizes, all in the top 40% of the image, nothing else. Clouds must not touch each other.""")
w(B, 'far', LIGHT+"""
Save to `work/osos/art/sets/bosque/far.png` - TRANSPARENT sky. Only a distant misty range of blue-green rolling hills with a few small distant pine silhouettes, across the full width, tops of the hills between 35% and 55% of the height, painted SOLID down to the bottom edge. Softer, lower-contrast and bluer than closer layers. No sky, no cabin, no ground path.""")
w(B, 'mid', LIGHT+"""
Save to `work/osos/art/sets/bosque/mid.png` - TRANSPARENT above the trees. Only the forest wall of a woodland clearing: a dense row of tall pine and round leafy trees with trunks, bushes and green hills, across the FULL width, tree tops reaching about 12-25% from the top, and painted SOLID down to the bottom edge (no holes, no ground path, no cabin, no sky, no foreground plants). The forest should read as a clearing's edge: slightly lower and more open in the middle, dense on both sides.""")
w(B, 'main', LIGHT+"""
Save to `work/osos/art/sets/bosque/main.png` - TRANSPARENT everywhere above the ground (no sky, no trees behind). This is the playing layer of a forest clearing where three bears live.
GROUND: a flat meadow of warm green grass whose top edge (horizon line) is at about 66% of the image height across the whole width (slightly wavy), and a wide DIRT PATH (warm sandy brown with a few pebbles and grass tufts at its edges) crossing the image from the LEFT edge to the RIGHT edge, running horizontally between 82% and 96% of the image height, passing right in front of the cabin. The ground is painted solid to the bottom edge. The LEFT 48% of the image must be mostly empty (only meadow, path, tiny grass tufts and flat pebbles), because characters walk there. No trees, no foreground plants.
CABIN (right side): a cozy cartoon LOG CABIN belonging to bears, front wall facing the viewer, occupying from 47% to 99% of the image width, its base on the meadow at about 82% of the image height, roof apex at about 17% of the height (the right edge may be cropped by the image border). Horizontal brown logs with visible round log ends at the corners, a warm brown wooden-shingle roof with a bit of green moss, a stone chimney on the right part of the roof (NO smoke drawn: smoke is added later). In the front wall:
 - a very TALL round-topped (arched) wooden DOOR, its bottom at 82% of the height, door height about 42% of the image height, width about 15% of the image width, centered at 74% of the image width, standing wide OPEN inward: we see only a thick wooden arched door frame with hinges on its right side, a flat stone threshold slab at the bottom, and inside the opening a very dark brown (almost black, flat, uniform) interior, with just a small warm glow on the floor at the bottom. The door leaf is NOT visible (swung inward). Nothing sticks out in front of the doorway.
 - a window with a wooden frame, panes showing warm daylight, and a wooden flower box with red and yellow flowers under it, to the LEFT of the door, centered at 56% of the image width, at 50% of the height.
 - a little woodpile stacked against the wall at the far right and a couple of potted plants at the wall base but NOT near the doorway (keep 6% free on both sides of the door).
Keep the doorway's dark interior exactly arch shaped and clearly bounded by the thick frame.""")
w(B, 'fg', LIGHT+"""
Save to `work/osos/art/sets/bosque/fg.png` - TRANSPARENT background. Only close foreground framing elements, darker, larger and slightly dim: big broad fern/green leaves in the bottom-left corner, a flowering bush (small white and yellow flowers) in the bottom-right corner (not taller than 22% of the image height, nor wider than 20% of the width), a leafy tree branch hanging in the top-left corner and a smaller leafy branch in the top-right corner. The center must be completely empty/transparent. Each element must be one separate blob that touches only its own corner.""")

D = 'sets/dormitorio'
INT = "Light: warm daylight coming from a window on the right side of the room, cozy storybook atmosphere."
w(D, 'wall', INT+"""
Save to `work/osos/art/sets/dormitorio/wall.png` - OPAQUE full image. The back wall and floor of the bears' bedroom inside a log cabin, seen straight on. Upper part (top 0% to 77% of the height): wall of horizontal brown logs with warm tone; a wooden-framed window with a sunny sky and a green tree seen through it, with simple cream curtains tied back, at x 56%-72% and y 14%-47% (daylight glows around it); a small wooden shelf with jars at x 14%-26%, y 22%; a small framed picture at x 38%-46%, y 20%. At 77% of the height a thick dark wooden baseboard line, below it the floor: warm wooden planks running horizontally in perspective to the bottom edge, with a big oval braided rug (red, cream and brown rings) lying on the floor spanning x 14%-86% and y 84%-97%. IMPORTANT: leave the lower wall between x 8% and 94% and from y 40% to 77% COMPLETELY EMPTY plain log wall (beds will be added in front later), and leave the floor between the baseboard and the rug bare. No furniture, no beds, no characters.""")
w(D, 'beds', INT+"""
Save to `work/osos/art/sets/dormitorio/beds.png` - TRANSPARENT background everywhere except the objects. Three wooden beds in a row, left to right BIG, MEDIUM, SMALL, all drawn from the same viewpoint straight on from the foot of the bed (headboard at the back, a fluffy pillow below the top of the headboard, a thick quilt with a folded-over top edge covering the front part of the bed and hanging over the sides, stubby wooden legs), bases standing on one common floor line at 82% of the image height. Rustic log-style frames.
 - BIG bed: x 12%-35% of the width, headboard top at 30% of the height, GREEN patchwork quilt, big pillow.
 - MEDIUM bed: x 37%-57%, headboard top at 38%, PINK quilt, medium pillow.
 - SMALL bed: x 58%-74%, headboard top at 47%, BLUE quilt, small pillow clearly visible and EMPTY (a plain, wide, clearly visible white pillow at y 59%-67%, at the top of the bed just under the headboard), the quilt's folded top edge is a clean, nearly horizontal line at about y 68%, so a child lying in the bed could show above it.
 - At the far right x 78%-93%: a small wooden toy chest with a little bear toy on it, base on the same floor line.
No wall, no floor, no rug, no cast shadow on the floor, no characters, no window.""")
w(D, 'door', INT+"""
Save to `work/osos/art/sets/dormitorio/door.png` - TRANSPARENT background except for one strip. A tall DOOR FRAME on the LEFT edge of the image only: occupying x 0%-12% of the width and the full height (y 0%-100%): from the left edge, a flat very dark warm brown doorway interior (x 0%-4.5%, solid, uniform) and then a thick wooden door jamb post of brown planks with dark outlines (x 4.5%-11%), plus a short lintel nub at the very top. The rest of the image (x > 12%) must be fully transparent.""")

P = 'props'
w(P, 'babero', """Save to `work/osos/art/props/babero-sheet.png` - TRANSPARENT background. A plain, flat, white bib with a RED GINGHAM (checked) border. One horizontal row with 4 separate drawings, well spaced, same size, each with generous empty margins (nothing touches another drawing), thick dark-brown outlines, flat cel color:
 1. bib HELD FLAT by its strings: front view of a rounded bib (white with red gingham border and a small stitched edge), its two ties/strings forming a loop that meets at a small knot at the top center, the bib hanging below the knot.
 2. bib WORN seen from the FRONT: the same bib on a chest, neck strap/ties visible as a band across the top center, hanging down from the top edge, symmetrical.
 3. bib WORN seen from the SIDE (profile facing right): a thin curved bib shape hanging down with the neck strap on top, the gingham border visible along its edge.
 4. bib in three-quarter view (turned a bit to the right), worn, top neck strap at the top.
Only the bib, no body, no hands, no shadows.""")
w(P, 'tenedor', """Save to `work/osos/art/props/tenedor-sheet.png` - TRANSPARENT background. One horizontal row with 2 separate drawings of a BIG cartoon dinner fork (silver-grey metal tines with a white highlight, wooden light-brown handle with a darker band, thick dark-brown outlines, flat cel color, chunky proportions, 4 tines): 1. UPRIGHT vertical, tines pointing up. 2. TILTED about 35 degrees to the right (tines up and to the right), same size. Well spaced, nothing touching, generous margins. No hands, no shadows.""")
