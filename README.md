# Molcy — motor de vídeo de MolDesign

*English, in short: Molcy is the video engine that ships inside [MolDesign](https://molecule-design.amezcua-dev.com). It is a set of Python scripts that run **inside
Blender** (`blender -b --python scripts/maestro.py`), use the Blender API (`bpy`) and the Molecular Nodes extension, and turn a MolDesign scene package into a short
scientific video. License: GPL-3.0-or-later.*

Molcy convierte un **paquete de escena** de MolDesign (`scene.json` + geometría PDB, producidos a partir de una corrida de docking o de un receptor) en un vídeo
corto: la proteína, el sitio de unión y, si la corrida lo conserva, la pose de Vina. Dibuja sólo lo que el paquete demuestra; si el contrato científico veta algo, el
motor lo degrada y lo deja registrado en el acta del vídeo en vez de dibujarlo en silencio.

## Requisitos

- **Blender 5.2 o posterior** (probado con 5.2.2). El motor **no** funciona en 4.2 ni en 4.5: la plantilla de arte no abre en 4.2 y en 4.5 el control de calidad del
  propio motor aborta (la geometría de Molecular Nodes 4.x tiene otra escala).
- La extensión **Molecular Nodes** (`bl_ext.blender_org.molecularnodes`; probada la 520.2.0), instalada desde Blender Extensions.
- Windows y PowerShell: el lanzador `scripts/correr_caso.ps1` orquesta Blender en varias pasadas (escena, cierre de marca, codificación y sellado).
- Python 3 con [Pillow](https://python-pillow.org/) (`-Python`): el contraste de la capa de rótulos y el sellado del MP4 corren fuera de Blender.

## Uso

MolDesign lo lanza solo, con rutas absolutas. A mano, desde PowerShell:

```powershell
$env:MOLCY_SCENES_DIR = "C:\ruta\a\los\paquetes-de-escena"      # <PDB_ID>/scene.json + geometry/
scripts\correr_caso.ps1 -Pdb 1HSG -Sufijo prueba -Carpeta C:\ruta\de\salida `
    -Formato previsualizacion -Renderizador gpu -Guion sitio_activo -Sujeto receptor_solo `
    -Root . -Blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

Formatos: `previsualizacion` (1:1, 720 px), `social_vertical` (9:16, 1080×1920) y `biblioteca` (16:9, 1080p). Renderizadores: `gpu` (EEVEE) y `cpu` (Cycles; la escena se
limita a tres segundos).

Variables de entorno que reconoce: `MOLCY_SCENES_DIR`, `MOLCY_CASES_DIR`, `MOLCY_OUTPUT_DIR`, `MOLCY_BLENDER`, `MOLCY_ART_TEMPLATE`, `MOLCY_BRAND_CACHE_DIR` y
`MOLCY_CPU_THREADS`. Ninguna ruta de una máquina concreta está escrita en el código.

La arquitectura (un maestro, módulos atómicos para guion, sujeto y formato) se describe en el código de `scripts/`: cada variable vive en su fichero y el maestro los
descubre solos.

## Pruebas

Las pruebas que no necesitan Blender:

```bash
cd scripts
python -m pytest pruebas -q
```

## Etiquetas y pausas de lectura

Una etiqueta anclada en 3D sólo se lee con la imagen quieta. Cuando un grupo de etiquetas termina de entrar, el vídeo se **congela**: el mismo PNG —escena y capa de
rótulos— se repite durante la pausa (de 2 a 3 s en Resultado según cuántas haya; 1 s por pose en Búsqueda y Ensamble). La pausa existe sólo en el montaje
(`variables/pausas.py`): el maestro escribe `montaje.json` (fotograma de salida → PNG fuente) y `codificar.py` lo sigue, así que una imagen repetida no se rinde dos
veces, y un tramo del guion que sería una imagen fija se rinde una sola vez. En el acta, `fotogramas` y `duracion_s` son los del vídeo (antes del cierre),
`fotogramas_fuente` los del `.blend` y `fotogramas_render_unicos` los PNG que hay que rendir; `pausas` es el índice en segundos.

Además, un fotograma cuyo estado es idéntico al de otro ya rendido no se vuelve a rendir (`salida/firmas.py`: la «firma» es el valor de todas las curvas horneadas en ese fotograma; con desenfoque de movimiento cuentan también sus vecinos). La escena y la capa de rótulos se comparan por separado: mientras las etiquetas entran sobre una cámara quieta la escena no cambia, y el texto de pantalla no cambia porque la cámara se mueva. `montaje.json` lleva los mapas `escena` y `capa` (fotograma → PNG ya rendido).

Las etiquetas de un mismo instante se reparten juntas con restricciones duras (`variables/disposicion.py`): ningún texto se solapa con otro ni con el texto de
pantalla, ni tapa el sujeto o una línea de interacción, y ninguna guía cruza otra. Si no caben, se achican y, como último recurso, se rotulan menos; el acta lo dice
(`etiquetas_omitidas`). La capa de rótulos lleva un halo y una placa oscura detrás de cada etiqueta (`salida/contraste.py`, con Pillow). POLAR y APOLAR llevan el
color de su línea; un hotspot del catálogo dice «HOTSPOT» y va en neutro.

## Licencia y marca

**GNU General Public License v3.0 o posterior** (`GPL-3.0-or-later`); el texto completo está en [`LICENSE`](LICENSE) y las razones en [`NOTICE.md`](NOTICE.md).
Esto no es asesoría jurídica.

El **nombre y el emblema de MolDesign** (`moldesign/assets/marca/`, que el motor usa en el cierre de los vídeos) son marca: la GPL concede derechos sobre el código y los
ficheros, no sobre la marca. Una versión modificada que se distribuya debe quitarlos o sustituirlos.

Los vídeos que el motor genera no están cubiertos por la GPL (igual que lo que se renderiza con Blender), y todo vídeo que genera MolDesign termina con el cierre de
la marca: el motor no ofrece ningún mando para quitarlo.

## Búsqueda interna de Vina

El guion `x` utiliza `traza_interna.tipo = vina_monte_carlo_bfgs_interno`: estados retenidos muestreados de una réplica, métricas reales por paso y contadores de todas las réplicas. No acepta el muestreo Metropolis independiente anterior. Sin archivos verificables se abstiene. El número de réplicas procede de la corrida y la animación no interpola movimiento físico. El cierre de MolDesign sigue siendo obligatorio.

## Ensamble conformacional

El guion `y` (sujeto `ensamble_conformacional`) cuenta una evaluación en modo ensamble: las geometrías de entrada que aportaron poses, la mejor pose de cada corrida independiente de Vina, y las poses entregadas por la piscina con sus controles físicos e interacciones polares y apolares. Lee `ensamble.json` (`schema = moldesign.ensamble/1`), un contrato aparte de `docking.json` porque un ensamble tiene K corridas de Vina detrás y ningún archivo de poses único. Cada archivo que cita se verifica contra su SHA-256 y, sin contrato verificable, la escena se abstiene.

Qué no hace: no anima rotaciones entre conformaciones (ETKDG entrega geometrías finales, no una trayectoria) ni sugiere que una conformación sea «la correcta». Las conformaciones se alinean rígidamente a la mejor pose sólo para compararlas; Vina recibió cada una sin alinear. Los controles físicos se aplicaron después del acoplamiento, y «no evaluado» se rotula como tal, nunca como aprobado. En un formato corto sólo se enseñan los primeros elementos que caben con tiempo para leerse, y el acta (`mostradas_en_el_video`) dice cuántos. El cierre de MolDesign sigue siendo obligatorio.
