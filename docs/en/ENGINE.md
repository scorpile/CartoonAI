> Spanish original (with the full change log): [docs/ESTUDIO_V3.md](../ESTUDIO_V3.md) · Format reference: [FORMAT.md](FORMAT.md) · Back to [README](../../README.md)

# Engine v2: a condensed guide

The engine lives in `celstudio/v2/` and is connected to the web studio (`python -m celstudio serve`). It draws on the CPU with Skia, and **every frame is a pure function of `(film, shot, t)`**: no model inference, no network, no hidden state. Rendering the same `film.json` twice gives identical frames.

The demo "The workshop in the valley" (`projects/taller-v3`) is 1920x1080, 24 fps, 46.6 s, silent. A full render takes about 4-5 minutes on a CPU with 6 processes.

## Pipeline

```
art (image model, once per resource)
  -> prep scripts: cut pieces, erase facial features, measure pivots and colours   (work/*/prep_*.py)
  -> rig builders: characters/<id>.json                                            (work/*/build_rig*.py)
  -> script.json  (library -> scenes -> shots -> ordered actions)                  (edited by an agent, a human or direct.py)
  -> compile      -> film.json (keyframes already computed)
  -> render       -> frames -> FFmpeg -> MP4
```

Modules: `puppet.py` (rig: limbs, face, head, torso), `anim.py` (curves, IK), `stage.py` (compositing, camera, lighting, post, render and FFmpeg encoding), `gfx.py` and `fx.py` (drawing helpers and effects), `project.py` (format, validation, series), `direct.py` (Python DSL that records actions), `api.py` (HTTP API of the studio).

## Concepts

- **Rig of pieces + code.** Heads, torsos, hands and boots are art pieces. Arms, legs and facial features are drawn by code using the colours and widths measured from the art.
- **Continuous limbs ("hose").** Arms and legs are single continuous shapes drawn over a two-segment IK chain, with colour bands and a cuff measured from the art. There is no joint that can open up.
- **Parametric faces.** Heads are drawn blank; pupils, eyelids (per eye), brows, mouth and blush are continuous and clipped by the face mask. There are 12 expressions (`neutral`, `soft`, `happy`, `joy`, `surprise`, `awe`, `curious`, `worried`, `oops`, `smug`, `focus`, `still`) with transitions, plus channels to tune them.
- **2.5D head turn** (`face_x`, `face_y`): the face plate slides inside the hood or helmet via an image deformation, and the features move with parallax and foreshortening, giving a continuous turn of about ±25° from a single drawing.
- **Views.** Head and torso can have front, three-quarter, profile and back-three-quarter drawings. `turn` goes 0 (front) → 1 (three-quarter) → 2 (profile) → 3 (back three-quarter) when the character has the art; without it, higher values fall back to the last available view. Body turns go through the front view instead of flipping as a mirror image.
- **Deformable torso** (`bend`, `body_yaw`, hem spring): curved line of action, turning where pockets and scarves shift more than the silhouette, clothing hem that lags behind.
- **Anatomy-aware arms and hands.** The elbow always hangs down and back; the far arm goes behind the torso and head and the near one in front; the hand picks palm or back and the mirroring from the arm direction. `"anatomy": false` on the character gives manual control back.
- **Feet planted.** The walk phase is tied to distance: the supporting foot stays fixed in the world. Foot roll (`foot_*_roll`), heel strike, push-off, knee bend, hip drop. Far-side leg is shaded and steps a little higher.
- **Secondary motion.** Ears, curls, antennae and hems use simulated damped springs with mesh deformation. Arms, hands and head follow their keys through springs (`Performer.FOLLOW`).
- **Easing and overlap.** Per-key easing (overshoot, anticipation, elastic), automatic overlap by channel family (eyes lead, hands drag), squash/stretch, automatic breathing and blinking, small eye saccades in held poses (all scale with the `life` channel).
- **Held items and worn garments** (`item_l` / `item_r`, `wear`), **ordered front layers** between actors (`order`, `layer_order`).
- **Multiplane sets.** Layers with parallax `depth`, drifting clouds, swaying vegetation, smoke, motes and leaves, light rays, soft lights, and per-shot depth of field.
- **Lighting and integration.** Rim light and shade by sun direction (painted inside the outline, not over the ink), ambient tint, contact shadow per foot (fades when the foot lifts), cast shadow, `ink_lift` toward warm brown in wide shots.
- **Post.** Bloom, colour grade, vignette, grain; fades and titles through `overlay`.
- **Drawing on twos** (`style.hold`): the pose holds for two frames (12 drawings per second) and switches to ones on fast actions and walks; camera and travel stay at 24. A single outer contour over the composed figure and line boil (`style.contour`, `style.boil`).
- **Smear transitions** (`style.smear*`): when the head or torso drawing changes (front, three-quarter, profile, mirror) the figure stretches and blurs horizontally for two frames, so the swap does not read as a pop.

## Style parameters (`film.style`)

| Key | Effect |
|---|---|
| `hold` | Frames per drawing: 2 = on twos, 1 = on ones |
| `contour` | Outer contour thickness over the whole composed figure (0 disables) |
| `boil`, `boil_hold` | Line jitter amount, and how many frames it holds |
| `smear`, `smear_px`, `smear_stretch`, `smear_mix` | Transition smear: on/off, blur in pixels, horizontal stretch, cross-fade with the other drawing (higher values read as a double image) |
| `edge_soft` | Edge softening so figures sit in the background |
| `ink_lift` | Pulls the ink toward warm brown (more in wide shots) |
| `light.ambient.shade_mix` (in the set) | How much the shade takes the colour of the ambient light |

`{"hold": 1, "contour": 0, "boil": 0}` returns an earlier, plainer look for comparison. Sets carry their own `light` and `post` (see [FORMAT.md](FORMAT.md)).

## Commands

```bash
python work/v3/build_film.py                                   # writes script.json and compiles film.json
python -m celstudio.v2 render projects/taller-v3/film.json --output out.mp4
python -m celstudio.v2 frame  projects/taller-v3/film.json --shot s07 --time 2.6 --output frame.png
python -m celstudio.v2 sheet  projects/taller-v3/film.json --output sheet.jpg --shot s05
python work/v3/strip.py sneeze s07 2.0 24                      # motion strip into work/v3/review/
```

`render` also accepts `--shot` (repeatable), `--width`, `--workers`, `--motion-blur` and `--crf`. Reviewing with contact sheets (`sheet`) and motion strips before accepting a shot is part of the workflow; helpers such as `work/v3/hands.py`, `work/v3/feet.py` and `work/v3/shots.py` crop specific parts of the body at chosen moments.

## Art conventions (what the engine expects)

- Generate art **per resource**, never per frame: model sheet, parts, hands, profile views, set layers, props. Prompts are kept in `work/v3/art` and `work/osos/art`.
- Hands: a palm drawing per pose (`closed`, `open`, `point`) and an optional back-of-hand drawing. The thumb is a quarter turn counter-clockwise from the fingers.
- Prepare hidden areas and overlap at joints; validate the assembled character and its extreme poses. A complete image is not a rig.
- Plan resolution for close-ups: frontal heads have less resolution than three-quarter ones, so close-ups are limited to about zoom 2.5.
- Adding a character from art is not done in the web app: it needs the prep and rig scripts in `work/`.

## How the pilot was improved (summary)

The workshop pilot went through repeated critical reviews, each done on keyframes, contact sheets and motion strips, with scores rising from 5.5 to 6.8 out of 10. The changes that matter for understanding the engine: continuous IK limbs instead of glued parts; a parametric face; planted-foot walking; an anatomy-aware elbow, arm layering and hand side; palm/back hands; profile and back views; drawing on twos with a single contour and smear transitions; premultiplied-alpha handling in the outline and mesh sampling (fixes light specks on edges; covered by `tests/test_alpha_edges.py`); acting passes (anticipation, reactions, cuts on action). The full dated log is in the Spanish [ESTUDIO_V3.md](../ESTUDIO_V3.md).

## Known limitations

- **No audio and no lip-sync.** The biggest gap compared with a finished production.
- Reviews were done on keyframes, contact sheets and motion strips rather than watching in real time; timing notes from watching the video are still welcome.
- Rigs are specific to bipeds of this design. Other body types need new rig work.
- Hands have three poses (closed, open, pointing) plus grips for held items where the art exists; there are no individual finger poses.
- Frontal heads have less resolution than three-quarter ones (close-up limit).
- Some art is still missing per the reviews: finger poses, a three-quarter back torso with its own far arm, legs with separate thigh, calf and boot.
- Known artefacts: at maximum head turn the eye on the turned side can touch the edge of the face plate; with a very rotated open hand a corner of the cut can show below the cuff; an arm whose target is very close to the shoulder folds into a mass; hips do not deform with the torso.
- CPU rendering only.
- Automated tests (`python -m pytest tests -q`) cover curves, IK, frame determinism, alpha edges, the project format, series and the API; they do not prove artistic quality.
