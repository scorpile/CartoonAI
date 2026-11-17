You are the art department for a 2D cartoon pilot. Use your built-in image generation tool (image_gen) for every image. Do NOT draw art with code. Work only inside `projects/taller-v3/assets/` (create files there); do not modify any other file in the repo.

Reference: `projects/taller-v3/source/valley-studio.png` (attach/inspect it first). It is a single flattened background: sunset valley, mountains, pine forest, a workshop cottage on the right with tools, lamp and round green door, sandy courtyard ground, foreground foliage. Style: flat cel colors, thick dark-brown expressive outlines, warm sunset palette, storybook TV cartoon.

GOAL: a LAYERED version of this same location for multiplane parallax. Each layer is a separate 16:9 landscape image at the largest size the tool allows, same style, palette, line weight and composition as the reference, so that stacking them back-to-front recreates the reference. Layers behind must be fully painted where the layers in front will cover them (no holes), because the camera will slide layers at different speeds.

Save in `projects/taller-v3/assets/set/`:
1. `sky.png` — OPAQUE. Only the sunset sky gradient and the sun disc with its soft halo. No clouds, no mountains, no trees.
2. `clouds.png` — TRANSPARENT background. 4 separate stylized sunset clouds (peach/pink, outlined like the reference), well spaced apart, nothing else.
3. `far.png` — TRANSPARENT sky. Only the distant blue mountain range (with the two main peaks), spanning the full width and painted solid down to the bottom edge.
4. `mid.png` — TRANSPARENT above. Only the forested hills: pine trees, green rolling hills, bushes, spanning full width, painted solid down to the bottom edge. No house, no ground courtyard.
5. `main.png` — TRANSPARENT above the horizon line/roofline. The sandy courtyard ground across the full width (bottom ~40% of the frame, flat and mostly empty in the left and center so characters can stand on it) plus the workshop cottage on the right exactly as designed in the reference (tiled roof, chimney, lamp, window with flower box, round-top green door, steps, workbench, hanging wrenches, toolbox, barrel, potted plants). No foreground foliage.
6. `fg.png` — TRANSPARENT background. Only close foreground framing elements, darker and larger: big leaves bottom-left, a rock with orange flowers bottom-right, a pine branch hanging in the top-left corner. Center must be empty/transparent.

Save in `projects/taller-v3/assets/props/`:
7. `butterfly-sheet.png` — TRANSPARENT background. One small cute butterfly in the same outlined flat style (warm yellow-orange wings with cream spots, dark-brown body), drawn 3 times in a single row of 3 equal cells, same size and position in each cell, side/three-quarter view facing right: (a) wings fully open, (b) wings half closed, (c) wings closed together pointing up.
8. `puff-sheet.png` — TRANSPARENT background. 3 small stylized cartoon smoke/dust puffs (cream-white, outlined), in a row of 3 equal cells.

Requirements and checks (do them, do not skip):
- Use real alpha transparency (transparent_background). After each generation, open the saved PNG with Python/Pillow and verify mode is RGBA and that the corner pixel alpha is 0 for transparent layers (for sky.png verify it is opaque). If a checkerboard or a solid background was painted instead, regenerate.
- Look at each result; if it contains elements that belong to another layer (e.g. a house in mid.png, clouds in sky.png), regenerate with a stricter prompt (max 3 attempts per image, keep the best).
- Keep horizon heights consistent with the reference: ground starts around 72-75% of the height on the left side.
- Finally write `projects/taller-v3/assets/set/layers.json` listing each file, its pixel size, whether alpha verified, attempts used, and any known defect. Then print a short summary.
