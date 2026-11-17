You are the art department for a 2D cartoon. Use your built-in image generation tool (image_gen) to make ONE image. Do NOT draw art with code (no PIL/matplotlib drawing; Pillow is only for checking). Work only inside this folder (the working directory).

References: the FIRST attached image is the model sheet of the character MAMA_OSA (cinnamon-brown mother bear, pink dress with flowered white apron, red bow): match it EXACTLY (same fur colours, same clothes colours, same proportions, same thick dark-brown outline weight, flat cel colours, no gradients, no shadows). The second attached image only shows the target drawing style (flat cel, thick dark-brown outline).

The software later assembles a puppet from these parts, so every part must be drawn ALONE, completely separated from the others by wide empty transparent space, laid out EXACTLY as described, on a TRANSPARENT background (real alpha, transparent_background). Nothing else on the image: no text, no labels, no guide lines, no ground shadows.

TASK: three BLANK HEADS in one row, left to right, all the same size and the same character (head only, no neck, no body, no clothes below the head). The software draws eyes, eyebrows, mouth and blush itself, so the face must be BLANK: absolutely NO eyes, NO eyelashes, NO eyebrows, NO mouth line or smile, NO blush, NO cheek spots. Keep the muzzle shape (lighter muzzle patch) and the nose, nothing else on the face: the fur above the muzzle is plain flat fur colour with enough empty space for big eyes later.
1. FRONT view head, looking straight at the viewer, symmetrical.
2. THREE-QUARTER view head turned to the viewer's RIGHT (like the three-quarter head on the model sheet), muzzle and nose shifted right.
3. perfect SIDE PROFILE head facing RIGHT: round skull, the snout protruding to the right with the nose at its tip, one ear visible (lighter inner ear), plain fur where the eye would be, nothing on the snout except the nose.
Keep the ears, and the head accessory if the character has one (red cap between the ears for OSITO with his ears poking out beside the cap; red bow for MAMA_OSA). Same outline weight on all three.

Save the image as `mama_osa-heads.png` in the working directory (largest size the tool allows). After saving, verify with Pillow that it is RGBA and that the four corner pixels have alpha 0, and that the parts are separated by fully transparent space; if a checkerboard or solid background was painted, regenerate (max 3 attempts). Then write one line with the final file and size.
