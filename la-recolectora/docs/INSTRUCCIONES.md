# LA RECOLECTORA: instrucciones de juego

## La idea
Tu serpiente es una **lista enlazada**: cada segmento ocupa memoria, y solo caben **40 nodos**. Al rebotar, la serpiente se parte y su mitad delantera queda tirada como **basura**: ya no la usas, pero sigue ocupando memoria. Para recuperar ese espacio tienes que atrapar la **pelota recolectora** y limpiar.

## Controles
| Tecla | Acción |
|---|---|
| Flechas | Mover |
| P | Pausa (P otra vez para seguir) |
| Q | Salir |
| R | Reiniciar tras perder |

## Qué hay en el campo
| Dibujo | Qué es | Efecto |
|---|---|---|
| Rombo | Dato | +10 puntos y creces 1 nodo |
| Marco hueco | Pared de rebote | Te inviertes y sueltas tu mitad delantera como basura |
| Bola pequeña | Pelota recolectora | Rebota en paredes, basura y en tu cuerpo. Atrápala con la cabeza para cargarte (+5) |
| Cuadro con punto | Basura | Te mata, salvo que estés cargada |
| Bloque negro | Pared sólida | Te mata |

Los pulsos de luz que recorren el borde son decorativos: muestran el "bus de datos".

## Cómo se limpia
Cargada (el marcador dice `Recolector:LISTO` y la cabeza abre la boca), toca cualquier basura: se libera en cadena todo el grupo conectado.
**Puntos = bloques × bloques.** Limpiar 3 da 9; limpiar 10 da 100.

## Cómo se pierde
- Chocar con una pared sólida, con tu cuerpo o con basura sin estar cargada.
- Comer un dato con la memoria llena (`Memoria:40/40`).

## Consejos
- Usa tu cuerpo como paleta para dirigir la pelota hacia tu cabeza.
- Con 3 segmentos o menos, rebotar no suelta basura.
- Deja que la basura se junte antes de limpiarla, pero vigila la memoria.
- El turno se acorta a medida que subes de puntaje.
