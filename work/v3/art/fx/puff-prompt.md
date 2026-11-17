You are the art department for a 2D cartoon. Use your built-in image generation tool (image_gen) to make ONE image. Do NOT draw art with code (no PIL/matplotlib drawing). Work only inside this folder (the working directory); do not modify anything else.

Reference: the attached image `puff-ref.png` shows three cartoon dust clouds in the film's style: flat cel colours (cream fill with a peach underside shade), thick dark brown outline, simple storybook TV cartoon.

Output: ONE wide image on a TRANSPARENT background (real alpha, transparent_background) with exactly FOUR drawings in one row, left to right, each ALONE with generous empty space between them, all at the same scale, same outline weight, same colours and same flat style as the reference. They are 4 consecutive animation phases of ONE sneeze dust cloud:
1. A tiny sharp burst: a small compact round-lobed puff (about 45% the size of the reference's left cloud) with a few short motion tick lines radiating from it.
2. Expanding: a bigger cloud made of 4-5 lobes, roughly the size of the reference's left cloud, with 2 small separate puffs thrown off to the right.
3. Fully expanded: a large billowing cloud, the biggest one (about the size of the reference's middle cloud), plump lobes, peach shade underneath, a couple of small detached puffs around it.
4. Dissipating: a few small separate soft puffs and wisps drifting apart (3-5 small cloud pieces of different sizes, the biggest about 40% the size of drawing 3), thinner, spread out; keep a thick outline and the same cream fill, no gradients or transparency.

Flat colours only, no shadows on the ground, no text, no labels, no guide lines.

Save the image as `puff-phases.png` in the working directory (largest size the tool allows). After saving, open it with Python/Pillow and verify it is RGBA and that the corner pixels have alpha 0; if a checkerboard or solid background was painted, regenerate (max 3 attempts). Then write one line stating the final file and size to stdout.
