> English version (condensed): [docs/en/ENGINE.md](en/ENGINE.md) · Volver al [README](../README.es.md)

# Motor v2 y piloto v3 — «El taller del valle: una visita con alas»

Película: `projects/taller-v3/renders/taller-v3.mp4` — 1920 × 1080, 24 fps, 46,6 s, 1118 frames, H.264, sin audio (comprobado con ffprobe). Datos editables: `projects/taller-v3/film.json` (schema 2).

El motor vive en `celstudio/v2/` y está conectado al estudio web (`python -m celstudio serve`). El motor v1 (`project.json`, app clásica) se retiró y se archivó fuera de este repositorio.

## Qué cambia respecto al piloto v2

| Problema del v2 | Solución en el motor v2 |
|---|---|
| Piezas pegadas, codos y rodillas separados | Extremidades continuas («hose») dibujadas sobre una cadena IK de dos segmentos, con bandas de color y puño medidos del arte. No hay junta que se pueda abrir. |
| Pies que resbalan | Caminata con fase ligada a la distancia: el pie de apoyo queda fijo en el mundo. |
| Caras por intercambio de cabeza completa | Cabezas en blanco + cara paramétrica: pupilas, párpados, cejas y boca continuos, recortados por la máscara del rostro. 12 expresiones con transición. |
| Movimiento lineal y rígido | Easing por clave (overshoot, anticipación, elástico), solape automático por familia de canal (ojos adelantan, manos arrastran), squash/stretch, respiración y parpadeo automáticos. |
| Sin acción secundaria | Antena y orejas con muelles simulados y deformación de malla. |
| Fondo plano de una sola imagen | Set multiplano de 10 capas con paralaje, nubes a la deriva, vegetación que se mece, humo, motas, rayos de sol y profundidad de campo por plano. |
| Personajes sin integrar | Sombra proyectada y de contacto, luz de borde y sombra propia según la dirección del sol, tinte ambiente. |
| Imagen sin acabado | Bloom, corrección de color, viñeta, grano; fundidos y título. |
| Cinco planos casi iguales | Nueve planos con general, medios, primeros planos, corte en acción, temblor de cámara y grúa final. |

El render sigue siendo determinista y sin modelos: cada frame es función pura de `(film, plano, t)`.

## Arte

- Fondos por capas, mariposa y nubes de humo: generados con el generador de imágenes de Codex (`work/v3/codex-art-prompt.md`), uno por recurso.
- Personajes: las hojas del piloto v2, sin arte nuevo. `work/v3/prep_parts.py` recorta piezas, borra los rasgos de las cabezas con el color plano del rostro y mide pivotes y colores. `work/v3/build_rig.py` produce `characters/*.json`.
- Brazos, piernas y rasgos faciales se dibujan por código con los colores y grosores medidos de ese arte.

## Comandos

```powershell
python work/v3/build_film.py                                   # escribe film.json
python -m celstudio.v2 render projects/taller-v3/film.json --output projects/taller-v3/renders/taller-v3.mp4
python -m celstudio.v2 frame  projects/taller-v3/film.json --shot s07 --time 2.6 --output frame.png
python -m celstudio.v2 sheet  projects/taller-v3/film.json --output sheet.jpg --shot s05
python work/v3/strip.py sneeze s07 2.0 24                      # tira de movimiento en work/v3/review/
```

Dependencias nuevas: `skia-python` y `numpy`. Render completo medido en este equipo: unos 4,5 minutos con 6 procesos.

## Límites reales

- **Sin audio.** Sigue aplazado por decisión del proyecto; es la carencia más visible frente a una producción terminada.
- Revisión visual hecha sobre fotogramas clave, hojas de contacto y tiras de movimiento, no viendo el video en reproducción. Conviene verlo y anotar correcciones de ritmo.
- El rig es específico para bípedos de este diseño. El cuerpo solo tiene vista frontal; el giro es un volteo con squash. No hay vista de espalda ni de perfil.
- Manos: tres dibujos (cerrada, abierta, señalando). No hay agarre de objetos.
- Las cabezas frontales tienen menos resolución que las de tres cuartos; por eso los primeros planos se limitan a zoom ≈ 2,5.
- La dirección se escribe en Python (`celstudio/v2/direct.py`). (Nota posterior: desde el 15 de noviembre la app web edita, previsualiza y renderiza films v2; ver `docs/FORMATO_V2.md`.)
- Pruebas automáticas (`tests/test_v2.py`): curvas, IK y determinismo de frames. No acreditan calidad artística.

## Actualización del 15 de noviembre: que la figura parezca dibujada, no armada

Película: `projects/taller-v3/renders/taller-v4.mp4` (mismo guion de planos). El objetivo de esta pasada fue quitar el aspecto de «muñeco por partes» sin generar cuadros con modelos.

- **Cabeza 2.5D** (`face_x`, `face_y`): la placa del rostro se desliza dentro de la capucha o el casco mediante una deformación de la imagen, y los rasgos se mueven con paralaje y escorzo. Da un giro continuo de unos ±25° desde un solo dibujo. Los giros de cuerpo pasan por el frente en lugar de voltear en espejo.
- **Torso deformable** (`bend`, `body_yaw`, y `hem` en el diccionario de muelles): línea de acción curva, giro en el que bolsillo y pañuelo se desplazan más que la silueta, y bajo de la ropa con retraso. Cuello y hombros siguen la misma curva.
- **Uniones sin costura**: la manga nace del torso (sin contorno ni tapa en el hombro) y el puño cubre el corte de la mano. La manga de Luma es de un solo color.
- **Inercia** (`Performer.FOLLOW`): brazos, manos y cabeza siguen sus claves a través de muelles amortiguados; el torso se curva cuando la cadera acelera.
- **Dibujo «a doses»** (`style.hold`): la pose se mantiene dos frames (12 dibujos por segundo) y pasa sola a «unos» en acciones rápidas y caminatas; cámara y desplazamiento siguen a 24.
- **Contorno exterior único y vibración de línea** (`style.contour`, `style.boil`) sobre la figura completa ya compuesta.

`film.style` controla lo anterior; `{"hold": 1, "contour": 0, "boil": 0}` devuelve el aspecto previo para comparar.

Defectos conocidos de esta pasada: en giro máximo de cabeza el ojo del lado del giro roza el borde de la placa; con la mano abierta muy rotada asoma una esquina del corte bajo el puño; un brazo con el objetivo muy cerca del hombro se pliega en una masa; las caderas no se deforman con el torso.

## Actualización del 15 de noviembre (2): piernas y pies

Película: `projects/taller-v3/renders/taller-v5.mp4`. El usuario señaló los pies como el defecto más visible de `taller-v4.mp4`. La causa era del motor: la cadera quedaba tan alta que las piernas nunca doblaban la rodilla (dos tubos rectos en tijera) y la bota giraba sobre el tobillo, sin apoyar.

- **Apoyo del pie** (`foot_l_roll`, `foot_r_roll`): con valor positivo el talón se despega girando sobre la punta; con valor negativo el pie cae sobre el talón. El rig desplaza el tobillo para que el punto de apoyo no se mueva. Medidas opcionales en el personaje: `foot.toe`, `foot.heel`, `foot.depth`.
- **Ciclo de caminata** (`Take.walk`): golpe de talón, planta, despegue sobre la punta y paso con la rodilla doblada; la cadera baja tras cada contacto. La curva del pie en el aire conserva la velocidad del suelo en sus extremos, así que no patina al salir ni al llegar. Parámetros nuevos: `strike`, `push`, `drop`.
- **Profundidad**: la pierna y la bota del lado lejano van en sombra y pisan un poco más arriba.
- **Sombra de contacto por pie**, que se aclara cuando el pie se levanta.
- **Dibujo a doses**: si la raíz del personaje se desplaza, la pose pasa a «unos»; antes, en el arranque y la frenada de una caminata los pies apoyados patinaban un frame sí y otro no.

Revisado con tiras de piernas en primer plano (`work/v3/feet.py`), no en reproducción.

### Corrección: el tobillo es la boca de la bota (`taller-v6.mp4`)

En `taller-v5.mp4` la pierna seguía bajando por dentro de la bota hasta la suela y la bota giraba desde ahí, de modo que el pie parecía colocado a media pantorrilla. Ahora `work/v3/build_rig.py` mide la abertura de cada bota y:

- el pivote de la bota y `ankle_h` quedan en el centro de la abertura (unas 30 unidades sobre el suelo, antes 9);
- muslo y espinilla se acortan para terminar ahí, sin cambiar la altura del cuerpo;
- cada bota lleva `mouth` (`c`, `rx`, `ry` en píxeles del sprite): el rig dibuja primero la bota y después la pierna recortada a «por encima de la boca o dentro de la abertura», así la pierna entra en la bota y el borde delantero queda por delante. Una bota sin `mouth` se dibuja como antes.

### Brazos: codo y capa por anatomía (`taller-v7.mp4`)

Hasta `taller-v6.mp4` cada toma fijaba a mano el lado del codo (`arm_*_bend` con signo) y la capa del brazo (`arm_*_z`). Eso permitía codos doblados hacia arriba y brazos cruzando por delante de la cabeza. Ahora lo decide el rig (`Rig.pose`):

- **Codo**: cuelga hacia abajo y hacia atrás del cuerpo (hacia fuera en vista frontal); nunca se pliega hacia arriba. De `arm_*_bend` solo se usa la magnitud, es decir, cuánto flexiona.
- **Capa**: con el cuerpo girado, el brazo lejano y su mano van siempre detrás del torso y de la cabeza, y el cercano y su mano delante de ambos; de frente, los dos brazos van delante. `arm_*_z` ya no se usa con anatomía activada. (Hasta `taller-v12.mp4` el brazo cercano pasaba por debajo de la cabeza; se corrigió en `taller-v13.mp4`.)
- `"anatomy": false` en el personaje devuelve el control manual.

Consecuencia para la dirección: con cabezas tan grandes, un brazo levantado queda oculto si la mano no sale de la silueta de la cabeza. Los gestos de brazos arriba, señalar y saludar se reabrieron hacia los lados (`Take.wave` usa ahora `out=-78, up=-50`).

### Manos: lado del pulgar por anatomía (`taller-v8.mp4`)

El espejo de la mano (`hand_*_flip`) era fijo por lado, así que al cambiar la dirección del brazo el pulgar quedaba hacia abajo. Ahora `Rig._arm` lo decide según la dirección del antebrazo: pulgar arriba en un brazo extendido, hacia delante en uno que cuelga (hacia dentro en vista frontal) y hacia la cabeza en uno levantado. `hand_*_flip` solo se usa con `"anatomy": false`. El arte de manos debe tener el pulgar un cuarto de vuelta en sentido antihorario respecto a los dedos, como los tres dibujos actuales.

El gesto de «no, no» del plano 7 se abrió hacia delante: con el codo anatómico, las manos pegadas al pecho se plegaban en una masa.

Ayudas de revisión: `work/v3/hands.py` (medio cuerpo en momentos elegidos) y `work/v3/shots.py` (fotogramas completos).

### Corrección del recorte: puntos claros en el contorno (`taller-v9.mp4`)

La expansión del contorno trataba RGB sin premultiplicar como si ya estuviera ponderado por alfa. Al aumentar la cobertura, los colores casi transparentes del borde se volvían visibles como puntos blancos o de color. La iluminación y el contorno ahora leen y escriben explícitamente RGB premultiplicado. El muestreo de las mallas usa la misma convención para conservar el color en píxeles semitransparentes al deformar y reducir las piezas.

Se conservan las piezas, la animación y los parámetros de estilo. `tests/test_alpha_edges.py` reproduce el borde contaminado, comprueba que no se convierta en una mota opaca, conserva el blanco interior y verifica el color de las transparencias durante la deformación a dos escalas. Reinicia el servidor para cargar la corrección; los MP4 anteriores requieren volver a renderizarse.

## Pasada de calidad del 15 de noviembre (`taller-v9.mp4`)

Punto de partida: una revisión crítica de `taller-v8.mp4` hecha fotograma a fotograma (`work/v3/review/critique/INFORME.md`), que lo puntuó en 5,5/10. Cambios, todos deterministas:

- **Luz de borde por dentro del contorno** (`stage._actor`): pintada sobre la línea dejaba una franja de puntos dorados. Luz más cálida y ancha, sombra de contacto más firme y contorno exterior algo más fino (`sets/valley.json`, `style.contour`).
- **Vida en las poses mantenidas** (`Performer.base_values`): respiración más visible, el peso deriva de una pierna a otra con los pies plantados, brazos y cabeza se asientan y los ojos hacen pequeños saltos. Todo escala con el canal `life`.
- **Párpados curvos** y parpadeo más largo; los cambios rápidos de cara (`lid`, `squint`, `mouth_open`, mirada) pasan el dibujo a «unos».
- **Cuello** (`Rig._neck`): una pieza detrás de torso y cabeza que solo se ve donde se abriría un hueco.
- **Brazos en arco** (`Take.to`): cuando la mano cambia de dirección más de unos 22°, recorre un arco alrededor del hombro en lugar de una recta a través del cuerpo.
- **Giro por el frente** (`Take.turn_around`): abre a la vista frontal, invierte ahí (la pose frontal es simétrica) y cierra al tres cuartos contrario.
- **Caminata**: braceo amplio para que la mano lejana asome, más balanceo vertical y rodilla más marcada (`leg.smooth` 0,3).
- **Bocas redondas** que abren por igual alrededor de las comisuras; estornudo con boca redonda, cara apretada y recuperación; la mariposa despega mezclando `attach` de 1 a 0 en lugar de saltar.

Las pruebas que comparaban el piloto con la copia anterior a la migración ahora comparan `script.json` compilado con `film.json`.

### Segunda ronda (`taller-v10.mp4`)

La segunda revisión (`work/v3/review/critique2/INFORME2.md`) puntuó `taller-v9.mp4` en 6,0 y señaló regresiones. Correcciones:

- `Take.turn_around` baja los dos brazos a reposo antes de girar (`arms=True`): el espejo solo pasa desapercibido en una pose simétrica.
- El párpado a medio cerrar conserva la curva; plano se leía como desprecio.
- El brazo lejano de un cuerpo girado cuelga algo adelantado y su mano asoma por delante del vientre, para que no aparezca de golpe al moverse.
- `Take.hop` aplasta y estira la figura completa (`sx`, `sy`).
- Los brazos mantenidos en alto flotan más que los que cuelgan; menos giro de torso al caminar (`body_yaw` 0,12); el polvo crece desde un punto.
- Dirección: gestos grandes más largos, temblor en la última toma de aire del estornudo, cara aturdida después, segundo giro de Pip en el plano 9 retrasado hasta que termina el saludo.

Lo que la revisión considera imposible de resolver sin arte nuevo, por orden: poses de mano con dedos, torso de tres cuartos de espaldas con brazo lejano propio, piernas con muslo, pantorrilla y bota separados, nube de polvo por fases y mariposa con poses de ala.

### Manos nuevas (`taller-v11.mp4`)

Una hoja de manos por personaje generada con Codex (`work/v3/art/hands/`), cortada por `work/v3/prep_hands.py` en `assets/<id>/hand2_{closed,open,point}.png`: puño blando, mano abierta con pulgar y cuatro dedos, e índice extendido. Cumplen la convención del motor (pulgar un cuarto de vuelta en sentido antihorario respecto a los dedos). `HANDS_V2 = False` en `work/v3/build_rig.py` y volver a ejecutarlo recupera las manos anteriores; también quedan `characters/<id>.hands1.json`.

### Palma y dorso (`taller-v12.mp4`)

Las manos nuevas estaban dibujadas solo por la palma, de modo que un brazo colgando enseñaba la palma hacia delante. Ahora cada mano del rig puede llevar un segundo dibujo en `back` (mismos campos: `file`, `upp`, `pivot`, `dir`) y `Rig._arm` elige la cara por anatomía, a partir de qué mano es y de hacia dónde apunta el pulgar: el lado `l` del rig es la mano derecha del personaje y `r` la izquierda; un dibujo sin espejar (pulgar en sentido antihorario respecto a los dedos) es una palma izquierda o un dorso derecho. Resultado: dorso en un brazo que cuelga visto de frente; en tres cuartos, dorso en el brazo cercano y palma en el lejano; palma en una mano levantada que saluda.

Arte: `assets/<id>/hand2b_{closed,open,point}.png`, generado con Codex usando la hoja de palmas como referencia (`work/v3/art/hands/`). El dorso de `point` de Luma lleva una uña dibujada que el de Pip no tiene.

Además, la luz de borde ya no ilumina la tinta: en un borde paralelo a la dirección de la luz la banda caía sobre el propio contorno y lo partía en dos líneas (`stage._actor`).

### Vista de perfil (cabeza y torso)

Arte: una hoja por personaje generada con Codex (`work/v3/art/profile/`, prompts incluidos), cortada y medida por `work/v3/prep_profile.py` en `assets/<id>/head_profile.png`, `head_profile_face.png` y `torso_profile.png` (claves `head_profile` y `torso_profile` de `assets/<id>/rig.json`). `PROFILE_V3` en `work/v3/build_rig.py` la activa o desactiva (`characters/<id>.views1.json` es la copia sin perfil).

Motor: `turn` va de 0 a 2 (2 = perfil) si el personaje tiene arte de perfil; hasta 1 todo es idéntico a antes (comprobado píxel a píxel). Entre 1 y 2 los hombros y las caderas se juntan sobre el eje del cuerpo; desde `Rig.PROFILE_AT` = 1,5 se dibujan la cabeza y el torso de perfil (un solo ojo, boca en el borde delantero). Sin arte de perfil, `turn` > 1 equivale a 1.

Dirección: `Take.walk(..., view='profile')` camina de perfil con una transición suave al principio y al final. En `work/v3/build_film.py`, `PROFILE_WALK = False` devuelve las caminatas de Luma a tres cuartos.

## Pasada de actuación, transiciones e integración (`taller-v15.mp4`)

- **Actuación** (`work/v3/build_film.py`): el personaje que escucha reacciona (mirada, cabeza, cuerpo, en ese orden); los gestos mantenidos tienen anticipación, rebote y movimiento durante la pausa; varios cortes son sobre la acción (s02 abre en la pose de escucha de s01, s04 abre a mitad del saludo de s03, s05 en la pose de retroceso de Pip, s09 abre con la mariposa despegando desde donde la deja s08). Verbos nuevos en `direct.py`: `drift`, `react`, `overshoot` y `wave_off`.
- **Transición entre dibujos** (`Performer.transition`, `Stage._smear`): en los dos fotogramas en que cambia el dibujo de cabeza o torso (frente, tres cuartos, perfil, o espejo), la figura se estira y se desenfoca en horizontal; los dos fotogramas vecinos reciben el 40 %. Parámetros en `film.style`: `smear` 1, `smear_px` 2,5, `smear_stretch` 0,05 y `smear_mix` 0 (un valor mayor funde con el otro dibujo, pero se lee como doble imagen). Los fotogramas a más de 3 de un cambio salen idénticos a antes.
- **Integración con el fondo**: `style.edge_soft` 0,5 (suavizado de bordes), `style.ink_lift` 0,22 (la tinta tira a marrón cálido, más en planos generales) y `light.ambient.shade_mix` 0,3 (la sombra toma el color del atardecer). Coste: un 9 % más por fotograma.

## Arte nuevo y correcciones de la tercera revisión (`taller-v16.mp4`)

La tercera revisión (`work/v3/review/critique3/INFORME3.md`) puntuó `taller-v15.mp4` en 6,8. Cambios posteriores:

- **Arte** (cada pieza con su interruptor): cara de perfil con ojo oval, boca y nariz dentro de la placa (`EYE_V2` en `work/v3/prep_profile.py`); polvo del estornudo en cuatro fases (`PUFF_PHASES` en `build_film.py`); mariposa con poses abierta, media, cerrada y de aterrizaje (`BUTTERFLY_POSES`); vista de tres cuartos de espaldas para cabeza y torso (`BACK3Q_V3` en `build_rig.py`; `turn` llega a 3, `Rig.BACK_AT` = 2,5), lista pero sin usar en el piloto.
- **Párpados** (`Rig._face`): el borde del párpado es el arco superior del ojo desplazado hacia abajo y la pupila baja con él, así que un ojo entornado se lee relajado y no de desprecio. Los parpadeos tienen un solo dibujo intermedio (`Performer.values`).
- **Transiciones**: `smear_px` 6 y `smear_stretch` 0,10; los cambios que no implican perfil ni espalda reciben el 60 %.
- **Dirección**: anticipación al levantar los brazos en s06; continuidad en los cortes s06→s07 (el brazo sigue arriba y baja) y s07→s08 (la risa continúa); Pip con más vida en s05 y reacciones durante la risa de s07.
