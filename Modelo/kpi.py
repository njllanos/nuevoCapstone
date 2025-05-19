import pandas as pd
import numpy as np

######################################################## CAMBIAR SEGUN EL CASO ########################################################
semana = 's1'
dia = 3
dias_semana = {1: 'LUNES', 2: 'MARTES', 3: 'MIERCOLES', 4: 'JUEVES', 5: 'VIERNES', 6: 'SABADO', 7: 'DOMINGO'}

# Cargar arcos
arcos_df = pd.read_excel(f"Capstone_Instancia/arcos/arcos/{semana}/arcos_resumen.xlsx")
viajes = {
    (row['id_origen'], row['id_destino']): row['distancia_m'] / 1000
    for _, row in arcos_df.iterrows()
}

tipo_modelo = 4
modelos = {1: 'CASO BASE SOLO', 2: 'MODELO', 3: 'MODELO + CASO BASE', 4: 'MODELO + CASO BASE + SIMETRIA'}

# Cargar archivos
X_df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/X.csv")
Z_df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/Z.csv")
I_df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/I.csv")
Y_df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/Y.csv")
RM_df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/RM.csv")
RE_df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/RE.csv")
W_df = pd.read_csv(f"Resultados_Finales/{dias_semana[dia]}/{modelos[tipo_modelo]}/W.csv")
#PE_df = pd.read_csv(f"Resultados_Finales/{dias_semana}/{modelos[tipo_modelo]}/PE.csv")
#PM_df = pd.read_csv(f"Resultados_Finales/{dias_semana}/{modelos[tipo_modelo]}/PM.csv")

# Mapas útiles
enfermeros_df = pd.read_excel('Capstone_Instancia/enfermeros_small.xlsx', sheet_name=dias_semana[dia])
pacientes_df = pd.read_excel('Capstone_Instancia/pacientes_small.xlsx', sheet_name=semana)

######################################################## FIN DE CAMBIAR SEGUN EL CASO #####################################################

# Parámetros
COSTO_BENCINA_POR_KM = 100
COSTO_ESPERA_POR_MIN = 5500 / 60
COSTO_FIJO_EXTERNO = 15000
COSTOS_CATEGORIA_LaV = {
    'Baja Complejidad': 12500, 'Mediana Complejidad': 15000, 'Alta Complejidad': 20000,
    'Evaluación o Seguimiento': 7500, 'Ambulatorio Baja Complejidad': 10000, 'Ambulatorio Mediana Complejidad': 12500
}
COSTOS_CATEGORIA_SaD = {
    'Baja Complejidad': 15000, 'Mediana Complejidad': 20000, 'Alta Complejidad': 25000,
    'Evaluación o Seguimiento': 10000, 'Ambulatorio Baja Complejidad': 12500, 'Ambulatorio Mediana Complejidad': 15000
}

hospital_ids = [0, 1, 2, 3, 10, 20, 30]

def obtener_distancia(o, d):
    o = 0 if o in hospital_ids else o
    d = 0 if d in hospital_ids else d
    if o == d: return 0
    return viajes.get((o, d), np.inf)

def minutos_a_hora(minutos):
    if pd.isna(minutos) or np.isinf(minutos): return "ERROR"
    horas = int(minutos // 60)
    mins = int(minutos % 60)
    return f"{horas:02d}:{mins:02d}"

print(f"KPIs para el día {dias_semana[dia]} de la semana {semana}")
# KPI 1: Distancia total por jornada
print("KPI 1: Distancia total por jornada que cada enfermero realiza")
distancias = {}
for _, row in X_df.iterrows():
    k, i, j = row['Enfermero'], row['Desde'], row['Hasta']
    dist = obtener_distancia(i, j)
    distancias[k] = distancias.get(k, 0) + dist

for k, d in distancias.items():
    print(f"    Enfermero {k}: {d:.2f} km")
print(f"    Distancia total global: {sum(distancias.values()):.2f} km")

# KPI 2: Porcentaje de utilización de internos por franja horaria
print("KPI 2: Porcentaje de utilización de enfermeros internos")
franjas = [(420, 900), (900, 1020), (1020, 1380)]
for inicio, fin in franjas:
    at_int, at_tot = 0, 0
    for _, row in I_df.iterrows():
        i, k, t = row['Nodo'], row['Enfermero'], row['InicioAtencion']
        if i in hospital_ids: continue
        regimen = enfermeros_df.loc[enfermeros_df['ID'] == (k - 5000), 'REGIMEN'].values[0]
        if inicio <= t < fin:
            at_tot += 1
            if "INTERNO" in regimen:
                at_int += 1
    if at_tot > 0:
        print(f"    {minutos_a_hora(inicio)}–{minutos_a_hora(fin)}: {at_int/at_tot*100:.2f}% ({at_int}/{at_tot})")
    else:
        print(f"    No hubo atenciones en la franja {minutos_a_hora(inicio)} - {minutos_a_hora(fin)}")

# KPI 3: Pacientes promedio por tipo de enfermero
print("KPI 3: Cantidad de pacientes promedio de internos y externos")
tipo_enf = {'INTERNO TURNO 1': 'Interno Turno 1', 'INTERNO TURNO 2': 'Interno Turno 2', 'EXTERNO': 'Externo'}
conteo = {tipo: 0 for tipo in tipo_enf}
total = {tipo: 0 for tipo in tipo_enf}
for k in Z_df['Enfermero'].unique():
    #debe haber atendido a un paciente
    if sum(Z_df['Enfermero'] == k) < 3: continue
    regimen = enfermeros_df.loc[enfermeros_df['ID'] == (k - 5000), 'REGIMEN'].values[0]
    if regimen in tipo_enf:
        total[regimen] += 1
        pacientes_atendidos = Z_df[Z_df['Enfermero'] == k]['Nodo'].unique()
        pacientes_atendidos = [i for i in pacientes_atendidos if i not in hospital_ids and i > 1000 and i < 2000]
        pacientes_atendidos = len(pacientes_atendidos)
        conteo[regimen] += pacientes_atendidos
for tipo, nombre in tipo_enf.items():
    if total[tipo] > 0:
        prom = conteo[tipo] / total[tipo]
        print(f"    Pacientes promedio por {nombre}: {prom:.2f} ({conteo[tipo]}/{total[tipo]})")
    else:
        print(f"    No hay enfermeros del tipo {nombre}")

costo_total = 0
detalle_costos = []
contador_internos = 0
espera_total = 0
for _, enf in enfermeros_df.iterrows():
    k = enf['ID'] + 5000
    regimen = enf['REGIMEN']
    atendio = int(Y_df.loc[Y_df['Enfermero'] == k , 'Externo'].values[0])  # en realidad: trabajó o no

    if "INTERNO" in regimen:
        contador_internos += 1
        dist = distancias.get(k, 0)
        espera = W_df.loc[W_df['Enfermero'] == k, 'Espera'].values[0]
        espera_total += espera
        cb = 0 if dist == 0 else dist * COSTO_BENCINA_POR_KM
        ce = espera * COSTO_ESPERA_POR_MIN
        costo_total += cb + ce
        detalle_costos.append((k, "INTERNO", cb, ce, 0, 0))
    elif "EXTERNO" in regimen:
        if atendio:
            cf = COSTO_FIJO_EXTERNO
            pacientes_k = Z_df[Z_df['Enfermero'] == k]["Nodo"].unique()
            pacientes_k = [i for i in pacientes_k if i not in hospital_ids and i > 1000 and i < 2000]
            cv = 0
            for i in pacientes_k:
                req = pacientes_df.loc[pacientes_df['ID'] == i-1000, 'REQUERIMIENTO'].values[0]
                cv += COSTOS_CATEGORIA_LaV.get(req, 0) if dia < 6 else COSTOS_CATEGORIA_SaD.get(req, 0)
            costo_total += cf + cv
            detalle_costos.append((k, "EXTERNO", 0, 0, cf, cv))

df_costos = pd.DataFrame(detalle_costos, columns=["Enfermero", "Tipo", "Costo Bencina", "Costo Espera", "Costo Fijo Ext.", "Costo Variable Ext."])
fila_total = {
    "Enfermero": "TOTAL",
    "Tipo": "",
    "Costo Bencina": df_costos["Costo Bencina"].sum(),
    "Costo Espera": df_costos["Costo Espera"].sum(),
    "Costo Fijo Ext.": df_costos["Costo Fijo Ext."].sum(),
    "Costo Variable Ext.": df_costos["Costo Variable Ext."].sum()
}
df_costos = pd.concat([df_costos, pd.DataFrame([fila_total])], ignore_index=True)

print("KPI 4: Tiempo de espera promedio")
print(f"    Tiempo de espera total: {espera_total} min")
print(f"    Tiempo de espera promedio: {espera_total/contador_internos} min")

print("KPI 5: Costo laboral de enfermeros externos")
print("    Costo fijo externo: ", df_costos["Costo Fijo Ext."][:-1].sum())
print("    Costo variable externo: ", df_costos["Costo Variable Ext."][:-1].sum())
print("    Costo total laboral: ", df_costos["Costo Fijo Ext."][:-1].sum() + df_costos["Costo Variable Ext."][:-1].sum())

print("KPI 6: Costo total de la jornada")
print(f"    Costo total de la jornada: {costo_total:.0f} CLP")

print("    Detalle por enfermero:")
print(df_costos.to_string(index=False))

print("\nRutas de los enfermeros:")
# Crear diccionario tipo_nodo
tipo_nodo = {}

for nodo in pacientes_df['ID']:
    tipo_nodo[nodo] = 'Paciente'
for nodo in pd.read_excel("Capstone_Instancia/datos_espaciales_temporales.xlsx", sheet_name="um")['ID']:
    tipo_nodo[nodo] = 'UM'
for nodo in pd.read_excel("Capstone_Instancia/datos_espaciales_temporales.xlsx", sheet_name="ue")['ID']:
    tipo_nodo[nodo] = 'UE'
for nodo in pd.read_excel("Capstone_Instancia/datos_espaciales_temporales.xlsx", sheet_name="hospital")['Hospital (ID)']:
    tipo_nodo[nodo] = 'Hospital'

for k in X_df['Enfermero'].unique():
    # Extraer arcos de este enfermero
    arcos_k = X_df[X_df['Enfermero'] == k][['Desde', 'Hasta']].values.tolist()
    
    if len(arcos_k) < 2:
        print(f"Ruta del enfermero {k}:\n  No se atendió a ningún paciente.")
        continue

    # Reconstruir orden de nodos visitados
    nodos_salida = [a for a, _ in arcos_k]
    nodos_llegada = [b for _, b in arcos_k]
    nodos_visitados = []

    # Encontrar nodo inicial (sale pero no llega)
    posibles_iniciales = set(nodos_salida) - set(nodos_llegada)
    if not posibles_iniciales:
        print(f"Ruta del enfermero {k}:\n  ⚠️ No se pudo determinar el inicio de la ruta.")
        continue
    actual = posibles_iniciales.pop()
    nodos_visitados.append(actual)
    
    # Reconstruir secuencia
    while True:
        siguiente = [j for i, j in arcos_k if i == actual]
        if not siguiente: break
        actual = siguiente[0]
        nodos_visitados.append(actual)

    # Armar ruta con tiempos
    print(f"Ruta del enfermero {k}:")
    for nodo in nodos_visitados:
        # Buscar tiempo en I.csv si existe
        fila_tiempo = I_df[(I_df['Nodo'] == nodo) & (I_df['Enfermero'] == k)]
        if not fila_tiempo.empty:
            t = fila_tiempo['InicioAtencion'].values[0]
        else:
            t = np.nan
        tipo = tipo_nodo.get(nodo, 'Desconocido')
        if nodo == 10 or nodo == 20 or nodo == 30 or nodo == 1 or nodo == 2 or nodo == 3:
            tipo = "Hospital"
            print(f"  {tipo} ({nodo}) a las {minutos_a_hora(t)}")
        else:
            if nodo > 1000 and nodo < 2000:
                tipo = f"Paciente {(nodo - 1000)}"
                print(f"  {tipo} ({nodo}) a las {minutos_a_hora(t)}")
            elif nodo > 2000 and nodo < 3000:
                tipo = f"UE {(nodo - 2000)}"
                print(f"  {tipo} ({nodo}) a las {minutos_a_hora(t)}")
            elif nodo > 3000 and nodo < 4000:
                tipo = f"UM {(nodo - 3000)}"
                print(f"  {tipo} ({nodo}) a las {minutos_a_hora(t)}")
print(costo_total)