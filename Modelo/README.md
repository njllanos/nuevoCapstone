# Explicación de archivos
## Caso base
Este código plantea una heuristica basada en el algoritmo del Vecino Más Cercano y genera una primera solución factible. Su objetivo principal es proporcionar un punto de partida que pueda ser utilizado por los modelos de optimización exactos para acelerar la convergencia y comprar este punto inicial con las soluciones obtenidas.

## Modelo Sin Caso Base
Este archivo contiene el modelo MILP completo, pero sin utilizar la solución del caso base para partir interando. El modelo parte desde cero e intenta encontrar una solución óptima por su cuenta.

## Modelo Con Caso Base
Este modelo es idéntico al anterior, pero integra la solución del caso base como punto inicial factible, lo cual mejora los tiempos de resolución y acelera la convergecia del modelo.


## Modelo Apretado 
Este archivo implementa el modelo MILP con técnicas adicionales para mejorar la eficiencia de la resolución, tanto en calidad de solución como en tiempo computacional. Los cambios incluidos son: restricciones de simetría tipo 1, restricciones de simetría tipo 2, el acotamiento de ventanas de atención de los pacientes, UM y UE y en lugar de utilizar un valor de los parámetro Big M arbitrariamente grande, se definen de forma específica para cada combinación de índices.

