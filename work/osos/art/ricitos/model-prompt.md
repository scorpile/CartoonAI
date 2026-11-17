You are the art department for a 2D cartoon. Use your built-in image generation tool (image_gen) to make ONE image. Do NOT draw art with code (no PIL/matplotlib drawing). Work only inside this folder (the working directory); do not modify anything else.

Reference: the attached image is the part sheet of an existing character of the same film (a small cartoon kid, "Luma"). Match its STYLE exactly: flat cel colours, thick dark-brown outline (about #311605), simple storybook TV cartoon for small children, big head (head about 40% of the body height), no gradients, no soft shading.

Draw a MODEL SHEET of a NEW character: "Ricitos" (Goldilocks), a little girl of about 5-6 years, on a TRANSPARENT background (real alpha, transparent_background), generous empty space between drawings, no text, no labels, no guide lines, no shadows on the ground.

Her design:
- Skin: light peach (#fcd69b-ish, same family as the reference kid), rosy pink cheeks (round blush spots).
- Hair: ABUNDANT golden-blonde curls (#f6c33a base, a slightly darker flat gold #dba01f for a few curl shadows), a big voluminous halo of chunky spiral ringlets around the face and falling on both sides down to the shoulders, with a few curls bouncing at the top and a couple of ringlets on the forehead. Each ringlet is a fat spiral, clearly separated from the others, thick dark-brown outline.
- Clothes: a light-blue (#a9d3f0) long nightgown with a round neckline, a white lace-frilled collar, short puffed sleeves with a white frill cuff, and a small pink bow at the neck.
- Face: simple and friendly with big eyes, small nose, small smile.

Show exactly 3 drawings in one row, all the same scale:
1. Left: the full figure, standing, seen from the FRONT, arms relaxed at her sides.
2. Middle: the HEAD ONLY, FRONT view, eyes CLOSED (sleeping, peaceful curved lash lines), tiny smile.
3. Right: the HEAD ONLY, THREE-QUARTER view (looking toward the right of the image), eyes closed, tiny smile.

Save the image as `model-sheet.png` in the working directory (largest size the tool allows). After saving, open it with Python/Pillow and verify it is RGBA and that the corner pixels have alpha 0; if a checkerboard or solid background was painted, regenerate (max 3 attempts). Then write one line stating the final file and size to stdout.
