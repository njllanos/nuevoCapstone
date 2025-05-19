# Este script simplemente visualiza el grafo de Santiago de Chile utilizando OSMnx y matplotlib.
# Su output es un mapa del grafo en la carpeta "resultados" como grafo_santiago.png.
# A diferencia de los otros scripts no se gruarda automaticamente

import osmnx as ox
import matplotlib.pyplot as plt

grafico = ox.load_graphml("grafo_santiago.graphml")

ox.plot_graph(
    grafico,
    node_size=0.5,
    edge_linewidth=0.3,
    bgcolor='white',
    edge_color='black',
    node_color='black'
)
