import pandas as pd
import networkx as nx
import osmnx as ox
import ast
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
from matplotlib.lines import Line2D
import numpy as np

#  Parametros de configuracion
semana = 's1'
dia    = 1
dias_semana = {
    1: 'LUNES', 2: 'MARTES', 3: 'MIERCOLES',
    4: 'JUEVES', 5: 'VIERNES', 6: 'SABADO', 7: 'DOMINGO'
}
tipo_modelo = 1
modelos = {
    1: 'CASO BASE SOLO',
    2: 'MODELO',
    3: 'MODELO + CASO BASE',
    4: 'MODELO + CASO BASE + SIMETRIA'
}

PATH_GRAFO = "grafo_santiago.graphml"
semana = 's1'  # Cambia esto según la semana que uses
PATH_ARCOS = f'Capstone_Instancia/arcos/arcos/{semana}/arcos.xlsx'  # Ruta al archivo de arcos


# 1. Cargar el grafo
print("🌐 Cargando grafo desde archivo .graphml...")
G = ox.load_graphml(PATH_GRAFO)

# 2. Cargar arcos con coordenadas y tiempos
arcos = pd.read_excel(PATH_ARCOS)
arcos['ruta_nodos'] = arcos['ruta_nodos'].apply(ast.literal_eval)

# Crea carpeta de salida para imágenes
Path("visualizaciones").mkdir(parents=True, exist_ok=True)

def plot_rutas_por_enfermero():
    df_x = variables.get("X")
    if df_x is None:
        print("❌ Variable X no cargada.")
        return

    arcos_validos = df_x[df_x["Valor"] > 0]

    for enf_id, sub_df in arcos_validos.groupby("Enfermero"):
        # si hay menos de 2 arcos, no se genera la imagen
        if len(sub_df) < 2:
            print(f"❌ No se generó imagen para enfermero {enf_id}")
            continue
        fig, ax = ox.plot_graph(
            G,
            node_size=0,
            edge_color="#cccccc",
            edge_linewidth=0.5,
            bgcolor="white",
            show=False,
            close=False
        )

        for _, fila in sub_df.iterrows():
            # Normalizar nodos equivalentes a 0
            desde = fila["Desde"] if fila["Desde"] not in [1, 2, 3, 10, 20, 30] else 0
            hasta = fila["Hasta"] if fila["Hasta"] not in [1, 2, 3, 10, 20, 30] else 0
            tramo = arcos[(arcos["id_origen"] == desde) & (arcos["id_destino"] == hasta)]
            if tramo.empty:
                continue
            nodos_ruta = tramo.iloc[0]["ruta_nodos"]
            ox.plot_graph_route(
                G,
                nodos_ruta,
                route_color="red",
                route_linewidth=2,   # más fino que el valor por defecto (~4)
                ax=ax,
                show=False,
                close=False,
                orig_dest_node_size=0  # oculta los puntos de inicio y fin
            )
        plt.title(f"Ruta Enfermero {enf_id}")
        plt.savefig(f"visualizaciones/por_enfermero/ruta_enfermero_{enf_id}.png", dpi=300)
        plt.close()
        print(f"✅ Imagen generada para enfermero {enf_id}")

def plot_rutas_todos_enfermeros():
    # 3. Cargar variables de decisión
    variables = {}
    print(f"Cargando variables de decisión para el día {dias_semana[dia]} y modelo {modelos[tipo_modelo]}...")
    for var in ['X', 'Y', 'Z', 'W', 'RM', 'RE', 'PM', 'PE', 'I']:
        try:
            df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/{var}.csv")
            variables[var] = df
        except FileNotFoundError:
            print(f"{var}.csv no encontrado, se omite.")
    df_x = variables.get("X")
    if df_x is None:
        print("❌ Variable X no cargada.")
        return

    arcos_validos = df_x[df_x["Valor"] > 0]

    fig, ax = ox.plot_graph(
        G,
        node_size=0,
        edge_color="#cccccc",
        edge_linewidth=0.5,
        bgcolor="white",
        show=False,
        close=False
    )

    enfermeros = sorted(arcos_validos['Enfermero'].unique())
    enfermeros_que_atienden = []
    for enf_id in enfermeros:
        if len(arcos_validos[arcos_validos["Enfermero"] == enf_id]) > 1:
            enfermeros_que_atienden.append(enf_id)

    colormap = plt.colormaps['tab20']
    colores = {enf: mcolors.rgb2hex(colormap(i / len(enfermeros_que_atienden))) for i, enf in enumerate(enfermeros_que_atienden)}


    for _, fila in arcos_validos.iterrows():
        # es de un enfermero con menos de 2 arcos, se omite
        if fila["Enfermero"] not in enfermeros_que_atienden:
            continue
        # Normalizar nodos equivalentes a 0
        desde = fila["Desde"] if fila["Desde"] not in [1, 2, 3, 10, 20, 30] else 0
        hasta = fila["Hasta"] if fila["Hasta"] not in [1, 2, 3, 10, 20, 30] else 0
        tramo = arcos[(arcos["id_origen"] == desde) & (arcos["id_destino"] == hasta)]
        if tramo.empty:
            continue
        nodos_ruta = tramo.iloc[0]["ruta_nodos"]
        color = colores[fila["Enfermero"]]
        ox.plot_graph_route(
            G,
            nodos_ruta,
            route_color=color,
            route_linewidth=2,   # más fino que el valor por defecto (~4)
            ax=ax,
            show=False,
            close=False,
            orig_dest_node_size=0  # oculta los puntos de inicio y fin
        )

    legend_labels = [f"{enf}: {colores[enf]}" for enf in colores]
    leyenda = [Line2D([0], [0], color=colores[e], lw=2, label=f"Enf. {e}") for e in colores]
    ax.legend(handles=leyenda, loc='lower left', fontsize='small', frameon=True)
    plt.title("Rutas por enfermero (colores distintos)")
    plt.savefig(f"visualizaciones/rutas_{semana}_{dias_semana[dia]}_{modelos[tipo_modelo]}.png", dpi=300)
    plt.close()
    print("✅ Imagen general generada con rutas de todos los enfermeros")


# 5. Visualización general
if __name__ == "__main__":
    print("🔍 Generando visualización general...")
    for i in [1, 3, 7]:
        for j in [1, 2, 3, 4]:
            if i == 3 and j == 2:
                print("❌ No se generó imagen para el día 3 con el modelo 2")
            else:
                dia = i
                tipo_modelo = j
                plot_rutas_todos_enfermeros()
        print(f"\nGenerando visualización para el día {dias_semana[dia]}...")

