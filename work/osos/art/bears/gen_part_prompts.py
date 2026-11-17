NAMES = {'osito': 'OSITO (small honey-brown bear cub, blue overalls with one strap, red cap)',
         'mama_osa': 'MAMA_OSA (cinnamon-brown mother bear, pink dress with flowered white apron, red bow)',
         'papa_oso': 'PAPA_OSO (big dark-brown father bear, green vest with buttons, cream belly)'}
COMMON = """You are the art department for a 2D cartoon. Use your built-in image generation tool (image_gen) to make ONE image. Do NOT draw art with code (no PIL/matplotlib drawing; Pillow is only for checking). Work only inside this folder (the working directory).

References: the FIRST attached image is the model sheet of the character {who}: match it EXACTLY (same fur colours, same clothes colours, same proportions, same thick dark-brown outline weight, flat cel colours, no gradients, no shadows). The second attached image only shows the target drawing style (flat cel, thick dark-brown outline).

The software later assembles a puppet from these parts, so every part must be drawn ALONE, completely separated from the others by wide empty transparent space, laid out EXACTLY as described, on a TRANSPARENT background (real alpha, transparent_background). Nothing else on the image: no text, no labels, no guide lines, no ground shadows.
"""
HEADS = COMMON + """
TASK: three BLANK HEADS in one row, left to right, all the same size and the same character (head only, no neck, no body, no clothes below the head). The software draws eyes, eyebrows, mouth and blush itself, so the face must be BLANK: absolutely NO eyes, NO eyelashes, NO eyebrows, NO mouth line or smile, NO blush, NO cheek spots. Keep the muzzle shape (lighter muzzle patch) and the nose, nothing else on the face: the fur above the muzzle is plain flat fur colour with enough empty space for big eyes later.
1. FRONT view head, looking straight at the viewer, symmetrical.
2. THREE-QUARTER view head turned to the viewer's RIGHT (like the three-quarter head on the model sheet), muzzle and nose shifted right.
3. perfect SIDE PROFILE head facing RIGHT: round skull, the snout protruding to the right with the nose at its tip, one ear visible (lighter inner ear), plain fur where the eye would be, nothing on the snout except the nose.
Keep the ears, and the head accessory if the character has one (red cap between the ears for OSITO with his ears poking out beside the cap; red bow for MAMA_OSA). Same outline weight on all three.
"""
BODY = COMMON + """
TASK: four separate body parts in ONE row, left to right, same scale as the model sheet's body (as if cut from the model sheet; do NOT draw any head, any arms, any hands, any legs, any feet on the torso/hips parts):
1. TORSO FRONT view: the torso from the neck opening/shoulders down to the waist, WITH the character's clothing as on the model, but with NO arms at all (the shoulders are plain rounded stumps where the arms would attach, drawn in fur colour with no sleeves; the arms are added by software). The top edge at the neck is simply the top of the torso (the head covers it). Same outline.
2. TORSO SIDE PROFILE facing RIGHT: same torso seen from the side (narrower, belly/chest profile at the right), again with NO arm, shoulder stump only.
3. HIPS (pelvis/lower garment) FRONT view: only the lower garment/pelvis shape (for OSITO the blue overall shorts with rolled cuffs; for MAMA_OSA the pink flared skirt bottom with the white apron's scalloped hem in front; for PAPA_OSO the plain brown fur pelvis/rump shape like short shorts). It has NO legs: the bottoms are simply open at the leg holes / end of the garment (legs added later by software). Width about the same as the torso's width.
4. FOOT: ONE bear paw foot in SIDE view facing RIGHT, standing on a flat horizontal ground line: chunky fur paw with toe bumps and little toe lines at the right front, a flat sole, and a short ankle with an OVAL OPENING at the top (like the mouth of a short boot: a clean elliptical opening rim at the top whose inside is the plain fur colour, the leg tube enters here). Fur colour as the character's fur. No leg above the opening.
"""
HANDS = COMMON + """
TASK: eight bear PAW-HANDS (the paw of this bear, chunky fur paw with the same fur colour and outline) in TWO rows of FOUR, each paw alone with wide empty space around it, all the same scale and same paw (4 short chunky rounded fingers + a thumb, the same finger count in all).
ORIENTATION CONVENTION, identical for all eight: the fingers point to the RIGHT of the image, the THUMB is on the UPPER side, and the wrist end is on the LEFT as a perfectly flat, straight, VERTICAL cut (the wrist is simply cut off flat, no outline across the cut, no sleeve, no cuff, no arm). All wrist cuts have the same height.
TOP ROW = seen from the PALM side (a tiny lighter paw-pad hint is allowed): 1 "closed" soft relaxed loose fist; 2 "open" open paw with a clearly separate thumb up-right and four short chunky rounded fingers slightly spread; 3 "point" index finger extended to the right, the other fingers curled, thumb resting on top; 4 "grip" the paw closed around a thin vertical handle (like gripping a fork or spoon handle): a chunky fist whose curled fingers form a clear round OPEN HOLE in the middle of the fist, about one quarter of the fist's height in diameter, a fully EMPTY TRANSPARENT see-through hole (the background shows through it), outlined with the dark outline all around the hole; the thumb on top.
BOTTOM ROW = the SAME four poses seen from the BACK of the paw (dorsal side, smooth fur, no pad, no creases; knuckles may be hinted with one or two tiny arcs; tiny claws optional), same order: closed, open, point, grip (the back-side grip fist also has the same clear transparent round hole through it).
"""
for k, who in NAMES.items():
    for n, t in (('heads', HEADS), ('body', BODY), ('hands', HANDS)):
        text = t.format(who=who) + f"\nSave the image as `{k}-{n}.png` in the working directory (largest size the tool allows). After saving, verify with Pillow that it is RGBA and that the four corner pixels have alpha 0, and that the parts are separated by fully transparent space; if a checkerboard or solid background was painted, regenerate (max 3 attempts). Then write one line with the final file and size.\n"
        open(f'{k}-{n}-prompt.md', 'w', encoding='utf-8').write(text)
