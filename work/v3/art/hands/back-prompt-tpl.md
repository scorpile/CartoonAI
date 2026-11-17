You are the art department for a 2D cartoon. Use your built-in image generation tool (image_gen) to make ONE image. Do NOT draw art with code. Work only inside this folder (the working directory); do not modify anything else.

Reference: the attached image `REFNAME` shows three cartoon hands seen from the PALM side (closed fist, open hand, pointing hand). Draw the SAME three hands (same hand, same skin colour, same dark outline colour and exactly the same outline thickness, same size, same chunky proportions, same flat wrist cut, same finger count) but seen from the BACK OF THE HAND (dorsal side) instead of the palm side.

Output: a single wide image on a TRANSPARENT background (real alpha, transparent_background), exactly 3 hands in one row, each ALONE with generous empty space between them, same scale as the reference, flat skin colour and outline identical to the reference, no shading beyond what the reference has, no shadows, no text, no arms, no sleeves.

Orientation, identical to the reference: fingers point to the RIGHT, the thumb is on the UPPER side, wrist end on the LEFT as a perfectly flat vertical cut of the same height as the reference wrist cuts (no outline across the cut). Back of the hand toward the viewer: smooth back of the hand with NO palm creases and NO palm lines; knuckles may be hinted with one or two tiny small arcs; optionally tiny simple fingernails on the finger tips that are visible.
1. Left cell, "closed": relaxed soft fist seen from the back: the smooth back of the hand and the row of rounded knuckles along the right side, the thumb lying along the top edge. The curled fingertips are NOT visible.
2. Middle cell, "open": open hand back side, thumb pointing up-right plus four short rounded fingers slightly spread, same finger count, spread and proportions as the reference open hand; no creases.
3. Right cell, "point": index finger extended to the right, the other fingers curled into a fist seen from the back (knuckles on the right side of the fist, no visible curled fingertips), thumb along the top side.

Save the image as `OUTNAME` in the working directory (largest size the tool allows). Verify with Pillow that it is RGBA and the corner pixels have alpha 0; if a checkerboard or solid background was painted, regenerate (max 3 attempts). Then write one line with the final file and size.
