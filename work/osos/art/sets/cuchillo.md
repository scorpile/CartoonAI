You are the prop department of a 2D cartoon. Use your built-in image generation tool (image_gen) — do NOT draw with code. Work only inside `projects/tres-osos/assets/props/cuchillo/` (create it); do not modify any other file.

Attached reference: `projects/tres-osos/assets/props/tenedor/tenedor.png`, the fork of this film (flat cel colours, thick dark-brown outline, grey metal with a soft highlight, cartoon proportions).

Make `cuchillo.png`: ONE matching cartoon table knife, the companion of that fork: same style, outline weight, metal colour and highlight, same overall length and handle width, so they read as a set. Vertical, BLADE UP, handle down, cutting edge facing right, rounded blade tip. Transparent background (transparent_background), nothing else in the image, the knife centred and filling most of the height.

Checks (do them): open the PNG with Pillow, verify mode RGBA and corner alpha 0; regenerate (max 3 attempts) if a checkerboard or solid background was painted. Then crop to the alpha bounding box plus 6 px padding and save over `cuchillo.png`. Print its pixel size and the pixel point at the centre of the handle, 25 % of the knife length up from the bottom end (that is where a fist grips it).
