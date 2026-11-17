# LA RECOLECTORA

**Un videojuego en Jack para la computadora Hack (Nand2Tetris) donde la memoria es el campo de batalla**

> 🎬 **Video de demostración y arquitectura:** [ENLACE DE YOUTUBE AQUÍ](Todavia no esta).

![Partida en curso](<img width="1024" height="512" alt="imagen" src="https://github.com/user-attachments/assets/acc63389-d80e-45d1-82df-e61c550ba83f" />
)

Tu serpiente es una **lista enlazada** y solo caben **40 nodos** en memoria. Al rebotar se parte, y su mitad delantera queda tirada como **basura** que sigue ocupando memoria. Para liberarla tienes que atrapar la **pelota recolectora**, que rebota por el campo como en Pong, y limpiar la basura **en cadena**.

Equipo: Juan José Sierra Ocampo · Viliam Mesa Angarita · Marbin Rivera Ciro

---

## Cómo ejecutarlo

1. Abre el IDE web de Nand2Tetris y entra al **VM Emulator**.
2. Con el ícono de carpeta del panel **VM Code**, carga la carpeta **`LaRecolectora/`** (trae los `.vm` ya compilados).
3. Comprueba que el código cargado empieza con `function Ball.new` y no con el ejemplo de Fibonacci.
4. Lleva el control de velocidad **al extremo derecho (Fast)**. En la posición media el emulador ejecuta una sola instrucción cada 16 ms y el juego parece no hacer nada.
5. Pulsa **Run** y activa el teclado del emulador.

Para compilarlo tú: carga la misma carpeta en el **Jack Compiler** del IDE, compila y ejecuta.

## Controles y reglas

| Tecla | Acción |
|---|---|
| Flechas | Mover |
| P | Pausa |
| Q | Salir (muestra los nodos que quedaron vivos: 0) |
| R | Reiniciar tras perder |

| En pantalla | Qué es | Efecto |
|---|---|---|
| Rombo | Dato | +10 puntos y creces un nodo |
| Marco hueco | Pared de rebote | Te inviertes y tu mitad delantera queda como basura |
| Bola pequeña | Pelota recolectora | Rebota en todo; si la atrapas con la cabeza, quedas cargada (+5) |
| Cuadro con punto | Basura | Cargada, tócala: se libera todo el grupo. Puntos = bloques × bloques |
| Bloque negro | Pared sólida | Te mata |

Pierdes si chocas con un bloque negro, con tu cuerpo, con basura sin estar cargada, o si comes un dato con la memoria llena (40/40).

---

## Requisitos del proyecto y dónde se cumplen

| Requisito | Cómo se cumple | Dónde |
|---|---|---|
| Interactividad por teclado sin lectura bloqueante | Durante cada turno se consulta `Keyboard.keyPressed()` en tramos de 30 ms y se guarda la última flecha; el juego nunca se detiene a esperar una tecla | `Game.waitTurn`, `Game.readKey` |
| Fondo móvil / entorno dinámico | Tres pulsos de luz recorren las 90 celdas del borde (el "bus de datos"); cada turno solo redibuja 6 celdas | `World.animate` |
| Comportamiento físico modelado | Pelota con posición y velocidad en píxeles; reflexión especular eje por eje (`vx → −vx`, `vy → −vy`) contra paredes, basura, datos y el cuerpo de la serpiente | `Ball.step`, `Ball.probe` |
| Visualización de puntaje | Marcador con puntos, memoria usada, estado del recolector y último combo; se redibuja solo cuando cambia | `Hud.update` |
| Rigor de bajo nivel: memoria de video | Las celdas y la pelota se dibujan escribiendo directo en la RAM de pantalla (16384+) | `Gfx.cell`, `Gfx.ball` |
| Rigor de bajo nivel: ciclos de instrucción | Medidos: ≈ 5.500 instrucciones VM por turno (mediana); 270 por celda dibujada | `tools/medir.py` |

---

## Arquitectura

```
                    ┌──────────┐
                    │   Main   │  arranca y, al salir, libera todo
                    └────┬─────┘
                    ┌────▼─────┐
                    │   Game   │  bucle de turnos, reglas, puntaje, teclado
                    └┬───┬───┬─┘
         ┌───────────┘   │   └────────────┐
   ┌─────▼─────┐   ┌─────▼────┐     ┌─────▼────┐
   │  Snake    │   │  World   │     │   Ball   │
   │ (lista de │   │ 32×15    │     │ física   │
   │   Node)   │   │ celdas,  │     │ de       │
   └───────────┘   │ basura,  │     │ rebote   │
                   │ bus      │     └──────────┘
                   └──────────┘
   Servicios:  Gfx (memoria de video)   Hud (marcador y textos)   Rng (azar)
```

| Clase | Responsabilidad |
|---|---|
| `Main` | Inicializa, ejecuta el juego y libera toda la memoria al salir |
| `Game` | Bucle de turnos, reglas, colisiones, puntaje, teclado y pausa |
| `Snake` | La serpiente como lista enlazada: avanzar, crecer, rebotar |
| `Node` | Nodo de la lista; lleva la cuenta de nodos vivos |
| `World` | Cuadrícula de 32 × 15 celdas, basura, bus animado del borde |
| `Ball` | Pelota recolectora con física de rebote |
| `Gfx` | Sprites y dibujo directo en la memoria de video (generado por `tools/gen_gfx.py`) |
| `Hud` | Marcador y pantallas de texto, sin fugas de `String` |
| `Rng` | Generador congruencial lineal; semilla = vueltas hasta la primera tecla |

### Un turno

1. **Teclado:** se lee cada 30 ms mientras dura el turno (sin bloquear).
2. **Borrar** la pelota.
3. **Serpiente:** se mueve y se resuelve lo que hay en la celda de adelante.
4. **Física:** dos pasos de la pelota y se dibuja.
5. **Fondo:** los tres pulsos del borde avanzan una celda.

De 480 celdas solo se redibujan unas 10 por turno.

### Memoria de video

La pantalla de Hack es la RAM 16384–24575: 256 filas × 32 palabras de 16 bits, con el bit 0 como píxel izquierdo. El campo usa celdas de 16 × 16 píxeles alineadas a palabras, así que **cada fila de una celda es exactamente una palabra**:

```
palabra de la celda (x, y), fila r  =  16384 + 512 + 512·y + 32·r + x
```

- Dibujar una celda = 16 escrituras. El bucle está **desenrollado**: 270 instrucciones VM en vez de 507 (−47 %).
- La pelota (6 × 6) no está alineada y Hack no tiene desplazamiento de bits: se guardan sus 16 posiciones posibles **ya desplazadas** en tablas (`ballL`, `ballR`).
- La física garantiza que la pelota solo pisa celdas libres, así que puede escribir palabras completas sin dañar nada.

### Física de la pelota

Posición `(x, y)` y velocidad `(vx, vy)` en píxeles (±2 o ±3 por paso, dos pasos por turno). En cada paso:

1. Se prueba `x + vx` con las 4 esquinas de la pelota. Si alguna toca algo sólido: `vx = −vx`.
2. Se prueba `y + vy` (con la X ya resuelta). Si toca: `vy = −vy`. Si chocaron los dos ejes, fue una esquina.
3. Si una esquina toca la **cabeza**, la serpiente la atrapa.

Como avanza como máximo 3 píxeles por paso y las celdas miden 16, nunca atraviesa una pared.

### Memoria y recursividad

| Función recursiva | Qué hace | Caso base |
|---|---|---|
| `Node.reverse` | Invierte la serpiente al rebotar | No hay siguiente nodo |
| `World.sweep` | Limpieza en cadena (relleno por inundación) | Fuera del campo, o la celda no es basura |
| `Node.disposeAll` | Libera la serpiente completa | Es el último nodo |

- La profundidad máxima es 40 (nunca hay más de 40 nodos).
- **Avanzar no reserva memoria:** el nodo de la cola se recicla como nueva cabeza.
- **Basura = memoria sin liberar a propósito:** los nodos sueltos siguen vivos hasta que `sweep` los libera.
- **Sin fugas de texto:** en Jack cada `"texto"` crea un `String`; `Hud.say` lo imprime y lo libera.
- Al salir, `Game.dispose` y `Gfx.dispose` liberan todo, y la pantalla final muestra `Nodos vivos: 0`.

---

## Pruebas

En `tools/` hay un intérprete de Jack, un compilador de Jack a VM y un intérprete de VM, con un sistema operativo simulado **estricto**: detiene la prueba ante accesos a memoria liberada, escrituras fuera de la pantalla, liberaciones dobles o coordenadas ilegales. Sobre eso, jugadores automáticos (uno cuidadoso, uno al azar y uno que acapara datos) juegan partidas completas.

En **cada turno** se verifica la lista enlazada, la cuadrícula, el contador de nodos, que no queden `String` vivos y **la pantalla palabra por palabra** contra lo esperado.

| Ejecución | Turnos verificados | Reservas de memoria | Fugas | Pico del heap | Pico de pila (estimado) |
|---|---|---|---|---|---|
| Código Jack (23 sesiones) | 85.085 | 37.702 | 0 | 1.636 de 14.336 palabras (11 %) | 445 de 1.792 palabras (25 %) |
| Archivos `.vm` entregados (8 sesiones) | 23.927 | 10.753 | 0 | 1.636 de 14.336 palabras (11 %) | 422 de 1.792 palabras (24 %) |

En esas partidas la pelota fue atrapada 699 veces, hubo 576 limpiezas en cadena (la mayor, de 20 bloques), la memoria llegó al límite de 40 nodos y aparecieron las cuatro formas de perder. La recursión más profunda observada fue de 29 llamadas.

```
cd tools
python3 probar.py          # sobre el código Jack
python3 probar.py --vm     # sobre los .vm compilados
python3 medir.py           # instrucciones VM por turno y por celda
python3 gen_gfx.py         # regenera Gfx.jack si cambias un sprite
python3 compilar.py        # regenera los .vm
```

> Las pruebas automáticas usan herramientas propias. La prueba final es en el emulador oficial del IDE web.

## Estructura del repositorio

```
LaRecolectora/   código Jack (.jack) y compilado (.vm): esta carpeta se carga en el emulador
docs/            capturas e instrucciones de juego
tools/           generador de sprites, compilador, intérpretes, pruebas y mediciones (Python 3)
```
