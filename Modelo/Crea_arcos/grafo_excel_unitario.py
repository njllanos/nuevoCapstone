# Este script normaliza los puntos de interés a nodos de la red vial, creando un archivo geojson con los nodos y sus atributos.
# Tambien calcula la distancia y el tiempo de desplazamiento entre todos los nodos, creando un grafo.
# Su output incluye un excel con informacion de todos los arcos del grafo de interes en la carpeta "resultados" como arcos.csv.

# =======================
# 1. LIBRERÍAS
# =======================
import geopandas as gpd
import pandas as pd
import osmnx as ox
import networkx as nx
from osmnx.distance import nearest_nodes
from itertools import combinations
import os

# =======================
# 2. CARGA DE DATOS
# =======================
# Cargar los distintos archivos
hospital = pd.read_excel("data/hospital.xlsx")
hospital["Tipo"] = "Hospital"

ue = pd.read_excel("data/ue.xlsx")
ue["Tipo"] = "UE"

um = pd.read_excel("data/um.xlsx")
um["Tipo"] = "UM"

pacientes = pd.read_excel("data/pacientes.xlsx", sheet_name="s1")
pacientes["Tipo"] = "Pacientes"

# Unirlos todos en un solo DataFrame
df = pd.concat([pacientes, ue, um, hospital], ignore_index=True)

gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["Longitud"], df["Latitud"]), crs="EPSG:4326")

# =======================
# 3. DESCARGA O CARGA DEL GRAFO VIAL
# =======================

ruta_grafo = "descargas/grafo_santiago.graphml"

if os.path.exists(ruta_grafo):
    print("Cargando grafo desde archivo local...")
    graph = ox.load_graphml(ruta_grafo)
else:
    print("Descargando red vial desde OSM...")
    
    # Leer todos los pacientes (solo para la descarga del grafo)
    pacientes_all = pd.concat(
    pd.read_excel("data/pacientes.xlsx", sheet_name=None),
    ignore_index=True
    )

    min_lat = min(pacientes_all["Latitud"].min(), hospital["Latitud"].min(), ue["Latitud"].min(), um["Latitud"].min())
    max_lat = max(pacientes_all["Latitud"].max(), hospital["Latitud"].max(), ue["Latitud"].max(), um["Latitud"].max())
    min_lon = min(pacientes_all["Longitud"].min(), hospital["Longitud"].min(), ue["Longitud"].min(), um["Longitud"].min())
    max_lon = max(pacientes_all["Longitud"].max(), hospital["Longitud"].max(), ue["Longitud"].max(), um["Longitud"].max())
    holgura = 0.15

    oeste = min_lon - holgura
    este = max_lon + holgura
    sur = min_lat - holgura
    norte = max_lat + holgura

    bbox = tuple([oeste, sur, este, norte])
    print("Bbox:", bbox)
    
    graph = ox.graph_from_bbox(bbox=bbox, network_type='drive')
    graph = ox.project_graph(graph, to_crs="EPSG:32719")
    ox.save_graphml(graph, filepath=ruta_grafo)
    print("Grafo descargado y guardado localmente.")

print("Grafo cargado:", len(graph.nodes), "nodos,", len(graph.edges), "arcos")

graph = ox.add_edge_speeds(graph)
graph = ox.add_edge_travel_times(graph)

# =======================
# 4. ASIGNAR NODOS DEL GRAFO A PUNTOS (REINTENTANDO SI EL NODO NO TIENE CONEXIÓN)
# =======================
print("Asignando nodo más cercano del grafo a cada punto...")

gdf = gdf.to_crs(graph.graph['crs'])
delta = 1
max_intentos = 50
asignados = []

for idx, row in gdf.iterrows():
    punto = row.geometry
    intento = 0
    nodo = None

    while intento < max_intentos:
        x, y = punto.x + intento * delta, punto.y + intento * delta
        try:
            nodo_tmp = nearest_nodes(graph, X=[x], Y=[y])[0]
        except Exception:
            intento += 1
            continue

        if graph.degree[nodo_tmp] >= 2:
            nodo = nodo_tmp
            break

        intento += 1

    if nodo is None:
        print(f"No se pudo asignar nodo válido para índice {idx}")
        nodo = nearest_nodes(graph, X=[punto.x], Y=[punto.y])[0]

    asignados.append(nodo)

gdf["nodo_grafo"] = asignados

n_nodos_unicos = gdf["nodo_grafo"].nunique()
print(f"Nodos únicos asignados a los puntos: {n_nodos_unicos}")

gdf.to_file("resultados/puntos_con_nodos.geojson", driver="GeoJSON")

# =======================
# 4.1. FILTRAR HOSPITALES
# =======================
hospital_salida = gdf[gdf["ID"] == 0]
hospital_llegada = gdf[gdf["ID"] == 1]
# Filtrar todos excepto el hospital de llegada (ID 1)
gdf_tmp = gdf[gdf["ID"] != 1]

# =======================
# 5. FILTRAR SOLO PUNTOS CONECTADOS AL HOSPITAL DE SALIDA
# =======================
nodo_hospital = hospital_salida["nodo_grafo"].iloc[0]
alcanzables = nx.single_source_dijkstra_path_length(graph, source=nodo_hospital, weight="travel_time").keys()

# Filtramos solo los puntos conectados al hospital de salida
gdf_tmp = gdf_tmp[gdf_tmp["nodo_grafo"].isin(set(alcanzables))]
print(f"Puntos conectados al hospital (ID=0): {len(gdf_tmp)}")


# =======================
# 6. GENERAR TODAS LAS COMBINACIONES ENTRE PUNTOS CONECTADOS
# =======================
print("Calculando arcos entre puntos conectados...")

gdf_unico = gdf_tmp.drop_duplicates(subset="ID", keep="first")

if gdf_unico.empty:
    print("No hay puntos únicos para generar combinaciones.")
    exit()

gdf_dict = gdf_unico.set_index("ID").to_dict("index")
nodos = list(gdf_unico["ID"])

print(f"Nodos únicos conectados: {len(nodos)}")
print(f"Combinaciones posibles: {len(nodos)*(len(nodos)-1)//2}")

combinaciones = list(combinations(nodos, 2))
arcos_usados = []
fallidos = 0

for o, d in combinaciones:
    try:
        # --- ORIGEN -> DESTINO ---
        nodo_origen = gdf_dict[o]["nodo_grafo"]
        nodo_destino = gdf_dict[d]["nodo_grafo"]

        tiempo_od = nx.shortest_path_length(graph, source=nodo_origen, target=nodo_destino, weight="travel_time")
        ruta_od = nx.shortest_path(graph, source=nodo_origen, target=nodo_destino, weight="travel_time")
        distancia_od = sum(
            graph[u][v][0].get("length", 0)
            for u, v in zip(ruta_od[:-1], ruta_od[1:])
        )

        arcos_usados.append({
            "origen": nodo_origen,
            "id_origen": o,
            "tipo_origen": gdf_dict[o]["Tipo"],
            "lon_origen": gdf_dict[o]["Longitud"],
            "lat_origen": gdf_dict[o]["Latitud"],

            "destino": nodo_destino,
            "id_destino": d,
            "tipo_destino": gdf_dict[d]["Tipo"],
            "lon_destino": gdf_dict[d]["Longitud"],
            "lat_destino": gdf_dict[d]["Latitud"],

            "tiempo_min": tiempo_od / 60,  # Convertir a minutos
            "distancia_m": distancia_od,
            "ruta_nodos": ruta_od
        })

        # --- DESTINO -> ORIGEN (camino inverso) ---
        tiempo_do = nx.shortest_path_length(graph, source=nodo_destino, target=nodo_origen, weight="travel_time")
        ruta_do = nx.shortest_path(graph, source=nodo_destino, target=nodo_origen, weight="travel_time")
        distancia_do = sum(
            graph[u][v][0].get("length", 0)
            for u, v in zip(ruta_do[:-1], ruta_do[1:])
        )

        arcos_usados.append({
            "origen": nodo_destino,
            "id_origen": d,
            "tipo_origen": gdf_dict[d]["Tipo"],
            "lon_origen": gdf_dict[d]["Longitud"],
            "lat_origen": gdf_dict[d]["Latitud"],

            "destino": nodo_origen,
            "id_destino": o,
            "tipo_destino": gdf_dict[o]["Tipo"],
            "lon_destino": gdf_dict[o]["Longitud"],
            "lat_destino": gdf_dict[o]["Latitud"],

            "tiempo_min": tiempo_do / 60,  # Convertir a minutos
            "distancia_m": distancia_do,
            "ruta_nodos": ruta_do
        })

    except nx.NetworkXNoPath:
        fallidos += 1


# =======================
# 7. EXPORTAR RESULTADOS (DUPLICANDO HOSPITAL DE SALIDA Y LLEGADA)
# =======================
df_arcos = pd.DataFrame(arcos_usados)

df_hospital0 = df_arcos[df_arcos["id_origen"] == 0].copy()
df_hospital0["id_origen"] = 1
df_hospital0["tipo_origen"] = "Hospital"

df_hospital0b = df_arcos[df_arcos["id_destino"] == 0].copy()
df_hospital0b["id_destino"] = 1
df_hospital0b["tipo_destino"] = "Hospital"

# Concatenar duplicados al dataframe original
df_arcos = pd.concat([df_arcos, df_hospital0, df_hospital0b], ignore_index=True)

# Guardar arcos utilizados en un archivo
df_arcos.to_excel("resultados/arcos.xlsx", index=False)

# Guardar el resumen en otro archivo
df_resumen = df_arcos[["id_origen","id_destino", "tiempo_min", "distancia_m"]]
df_resumen.to_excel("resultados/arcos_resumen.xlsx", index=False)

print(f"Arcos válidos registrados: {len(df_arcos)}")
print(f"Pares sin conexión descartados: {fallidos}")