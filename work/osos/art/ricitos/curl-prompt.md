You are the art department for a 2D cartoon. Use your built-in image generation tool (image_gen) to make ONE image. Do NOT draw art with code (no PIL/matplotlib drawing). Work only inside this folder (the working directory); do not modify anything else.

Reference: the attached model sheet shows the little girl Ricitos with golden spiral curls. Draw a PROP sheet: a single loose golden ringlet (one chunky spiral curl of her hair, same gold colours #f6c33a with flat darker gold #dba01f, thick dark-brown outline about #311605, same style, flat cel colours) in THREE poses, in one row, each ALONE with generous empty space between, same scale:
1. Left, "hang": the ringlet hanging straight down from a flat top attachment end (the top end is a plain flat-cut tapered root, no outline across the cut), ending in a tight spiral at the bottom. Overall tall and slim (about 1 : 3).
2. Middle, "swing": the same ringlet, root at the top left, bent in a soft S-curve falling to the right, spiral tip curling.
3. Right, "across": the same ringlet lying horizontally across, root on the LEFT, the body of the curl stretched to the right with the spiral tip at the right end, as if resting across a cheek. About 3 : 1.
All roots are flat cuts (the root is hidden under the hair later). No face, no head, no body, no text, no shadows.

Save the image as `curl-props.png` in the working directory (largest size the tool allows). Transparent background (real alpha). After saving, open it with Python/Pillow and verify it is RGBA and that the corner pixels have alpha 0; if a checkerboard or solid background was painted, regenerate (max 3 attempts). Then write one line stating the final file and size to stdout.
