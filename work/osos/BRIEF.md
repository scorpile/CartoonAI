# Proyecto «Los tres osos» (`projects/tres-osos/`)

Encargo del usuario: tres osos —uno grande, una osa mediana y un oso pequeño— llegan a su casa, entran y encuentran a una niña de rizos de oro dormida en una de las camas; entonces se ponen baberos y sacan tenedores. Comedia negra suave, sin violencia mostrada: el chiste es el remate.

Motor: `celstudio/v2` (el mismo de `projects/taller-v3`, ver `docs/ESTUDIO_V3.md` y `docs/FORMATO_V2.md`). Solo video, sin audio ni diálogo. 1920×1080, 24 fps, unos 40–50 s. El listón de calidad es el piloto `projects/taller-v3/renders/taller-v16.mp4`: personajes que no parezcan muñecos por piezas, actuación con anticipación, solape y vida en las poses mantenidas.

## Estilo

Igual que el piloto del taller: cartoon de TV para niños, colores planos cel, contorno marrón oscuro grueso y expresivo, paleta cálida. Personajes cabezones (cabeza ≈ 40 % de la altura), siluetas claras y distintas por tamaño.

## Reparto (ids de biblioteca)

| id | quién | diseño |
|---|---|---|
| `papa_oso` | oso grande | marrón oscuro, corpulento, barriga clara, chaleco verde con botones, orejas redondas. ≈ 1,35× la altura de `osito`. |
| `mama_osa` | osa mediana | marrón canela, delantal blanco con flores sobre vestido rosa, lazo rojo entre las orejas. ≈ 1,15× `osito`. |
| `osito` | oso pequeño | marrón miel, peto azul con un tirante, gorra roja, ojos grandes. Escala de referencia. |
| `ricitos` | niña | rizos dorados abundantes (rizos con muelle), camisón azul claro, mejillas rosadas. Pasa casi toda la película dormida en la cama pequeña, visible de cintura para arriba sobre la manta. |

Los osos son bípedos con la misma estructura de rig que Luma y Pip: cabeza (frente, tres cuartos, perfil), torso, caderas, brazos y piernas por código con los colores medidos, pies (equivalentes a la bota: pata de oso con planta), manos de zarpa (cerrada, abierta, señalando, y **agarre** para sostener un tenedor; palma y dorso). Orejas como apéndices con muelle. Hocico y nariz pueden ir en el arte de la cabeza; ojos, cejas y boca los dibuja el motor (cara paramétrica), así que el arte de cabeza va sin ojos ni boca.

## Escenarios (ids)

- `bosque`: claro del bosque de día (luz cálida de media tarde), sendero de tierra que cruza de izquierda a derecha, cabaña de troncos de los osos a la derecha con puerta redonda de madera **abierta** (el interior oscuro se ve por la puerta), ventana con macetas, chimenea con humo. Capas multiplano como `projects/taller-v3/sets/valley.json`: cielo, nubes, lejano, medio, principal (suelo y cabaña), primer plano (marco del marco de la puerta y plantas para que los osos puedan «entrar» por detrás).
- `dormitorio`: interior de la cabaña, pared de troncos, ventana con luz, alfombra. Tres camas en fila de mayor a menor (izquierda a derecha): grande con colcha verde, mediana con colcha rosa, pequeña con colcha azul. La cama pequeña necesita su manta como capa de primer plano separada para tapar a `ricitos` de cintura para abajo.

## Utilería (ids)

- `babero`: babero blanco con borde rojo de cuadros (tres tamaños o uno que escala); se ata al cuello: una pose «en la mano» y una «puesto».
- `tenedor`: tenedor de madera/metal cartoon grande; también la mano de agarre con tenedor como dibujo de mano.

## Escaleta (planos aproximados)

1. **s01 bosque, general** (≈6 s): los tres osos caminan de perfil por el sendero hacia la cabaña, en fila (papá delante, mamá, osito al final dando saltitos para seguir el paso).
2. **s02 bosque, medio en la puerta** (≈5 s): llegan a la puerta, papá huele el aire, mamá le da un codazo, entran uno a uno por la puerta (desaparecen tras el marco).
3. **s03 dormitorio, general** (≈6 s): entran desde la izquierda; ven las camas; osito se detiene y señala la cama pequeña.
4. **s04 dormitorio, primer plano de Ricitos** (≈4 s): duerme, respira, se acomoda, un rizo cae sobre la cara.
5. **s05 dormitorio, medio de los tres** (≈6 s): se miran entre sí (sorpresa, pausa), después una sonrisa lenta compartida.
6. **s06 dormitorio, medio** (≈8 s): uno tras otro sacan un babero y se lo atan al cuello (papá, mamá, osito con retraso y torpeza).
7. **s07 dormitorio, medio** (≈6 s): sacan tenedores y los levantan a la vez, se relamen.
8. **s08 dormitorio, primer plano de Ricitos** (≈4 s): sigue dormida; al final abre un ojo. Fundido a negro.

## Reglas

- Arte por recurso con Codex (`image_gen`), nunca por fotograma. Binario: `%LOCALAPPDATA%\OpenAI\Codex\bin\<hash>\codex.exe` (listar `bin\` y usar la carpeta con `codex.exe`); uso: `codex.exe exec --skip-git-repo-check -s workspace-write -C c:\Proyectos\CartoonAI -i <ref.png> -o <salida.txt> - < prompt.md`.
- Imágenes en `projects/tres-osos/assets/<id>/`, `assets/sets/<id>/`, `assets/props/<id>/`; scripts de preparación en `work/osos/`; arte crudo y prompts en `work/osos/art/`.
- No modificar `celstudio/` ni `projects/taller-v3/`. Si el motor no permite algo, anotarlo como faltante.
- Render determinista; nada de LLM en el render.
