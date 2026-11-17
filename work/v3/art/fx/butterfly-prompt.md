You are the art department for a 2D cartoon. Use your built-in image generation tool (image_gen) to make ONE image. Do NOT draw art with code (no PIL/matplotlib drawing). Work only inside this folder (the working directory); do not modify anything else.

Reference: the attached image `butterfly-ref.png` shows a small cartoon monarch-style butterfly (orange wings with darker orange rim, yellow inner veins, cream spots, brown striped body, round brown head with one eye, two clubbed antennae), flat cel colours, thick dark brown outline, simple storybook TV cartoon. Keep EXACTLY this butterfly: same design, colours, wing pattern, body, head, antennae, outline weight and size.

Output: ONE wide image on a TRANSPARENT background (real alpha, transparent_background) with exactly FOUR drawings in one row, left to right, each ALONE with generous empty space between them, all the same scale. In all of them the butterfly HEAD points to the RIGHT, the butterfly is shown from a slightly higher camera so the wings read as having volume rather than a flat decal. They are four wing poses of one flap cycle:
1. WINGS FULLY OPEN: both forewings and hindwings spread wide and flat like a butterfly seen from above-behind, the two wings on each side of the body visible, the body in the middle pointing right, wing tips foreshortened a little, pattern visible on the upper surfaces.
2. WINGS HALF OPEN: the wings raised about halfway in a V shape, foreshortened, the nearer wing overlapping the far wing, body visible.
3. WINGS CLOSED, EDGE-ON: the wings pressed together straight up above the body, seen exactly edge-on as a narrow tall slim shape (a single narrow pair of wings, almost a thin leaf), the body below pointing right.
4. LANDING / PERCHED POSE: the butterfly sitting, body tilted slightly head-up, wings folded up together seen from the side (the wings show their pale underside pattern with the same spots but slightly more muted), and 3 tiny thin dark legs visible under the body.

Flat colours only, no shadows, no text, no labels, no guide lines.

Save the image as `butterfly-poses.png` in the working directory (largest size the tool allows). After saving, open it with Python/Pillow and verify it is RGBA and that the corner pixels have alpha 0; if a checkerboard or solid background was painted, regenerate (max 3 attempts). Then write one line stating the final file and size to stdout.
