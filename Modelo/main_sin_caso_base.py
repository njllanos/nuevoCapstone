import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import os
import csv
os.makedirs("resultados", exist_ok=True)

#CONJUNTOS

pacientes_df   = pd.read_excel("Capstone_Instancia/pacientes_small.xlsx", sheet_name="s1") #VEO QUÉ SEMANA QUIERO ATENDER
enfermeros_df  = pd.read_excel("Capstone_Instancia/enfermeros_small.xlsx", sheet_name="LUNES") #QUE COINCIDA EL DÍA DE LA SEMANA CON LOS PACIENTES
hospital_df  = pd.read_excel("Capstone_Instancia/datos_espaciales_temporales.xlsx", sheet_name="hospital")
UE_df  = pd.read_excel("Capstone_Instancia/datos_espaciales_temporales.xlsx", sheet_name="ue")
UM_df  = pd.read_excel("Capstone_Instancia/datos_espaciales_temporales.xlsx", sheet_name="um")
matriz_df = pd.read_excel("Capstone_Instancia/arcos/arcos/s1/arcos_resumen.xlsx", sheet_name="Sheet1") #VEO QUÉ SEMANA QUIERO ATENDER

#PACIENTES
def to_decimal(x):
    # si ya es un time o datetime, convierto a string "HH:MM:SS"
    s = x.strftime("%H:%M:%S") if hasattr(x, "strftime") else str(x)
    h, m, *_ = s.split(":")    # ignoramos los segundos
    return int(h) + int(m)/60

# aplico la transformación una sola vez:
pacientes_df["INICIO_DEC"] = pacientes_df["INICIO VENTANA"].apply(to_decimal)
pacientes_df["FIN_DEC"]    = pacientes_df["FIN VENTANA"].apply(to_decimal)

P = {}
for _, row in pacientes_df.iterrows():
    atender = row['LUNES'] #VEO QUÉ DÍA DE LA SEMANA QUIERO OPTIMIZAR
    if atender == 'Si':
        id = row['ID']
        inicio_decimal = row["INICIO_DEC"]
        fin_decimal    = row["FIN_DEC"]
        P[id] = {
            'inicio_ventana': inicio_decimal,
            'fin_ventana'   : fin_decimal,
            'requerimiento' : row['REQUERIMIENTO'],
            'servicio'      : row['DURACIÓN'],
            'examen'        : row['EXAMEN'],
            'medicamento'   : row['MEDICAMENTO']
        }


P_subsets = {'PM': [], 'PE': [], 'PEP': [], 'PV': []}
for id, attrs in P.items():
    e = attrs['examen']
    m = attrs['medicamento']
    if e == 'Examen No Perecible':   P_subsets['PE'].append(id + 1000)
    if e == 'Examen Perecible':      P_subsets['PEP'].append(id + 1000)
    if m == 'Medicamento Perecible': P_subsets['PM'].append(id + 1000)
    if e == 'No' and m == 'No':      P_subsets['PV'].append(id + 1000)

#ENFERMEROS
K = {}
for _, row in enfermeros_df.iterrows():
    id = row['ID']
    K[id] = {
        'regimen': row['REGIMEN'],
        'inicio_ventana': row['HORARIO ENTRADA 1'],
        'fin_ventana'   : row['HORARIO SALIDA 1']
    }

K_subsets = {'K1': [], 'K2': [], 'KEX': []}
for id, attrs in K.items():
    r = attrs['regimen']
    if   r == 'INTERNO TURNO 1': K_subsets['K1'].append(id + 5000)
    elif r == 'INTERNO TURNO 2': K_subsets['K2'].append(id + 5000)
    elif r == 'EXTERNO':          K_subsets['KEX'].append(id + 5000)


#HOSPITAL
O1 = {} #hospital de salida de enfermeros turno 1
O1[10] ={
    'inicio_ventana': 8.0,
    'fin_ventana'   : 17.0,
}

O2 = {} #hospital de salida de enfermeros turno 2
O2[20] ={
    'inicio_ventana': 15.0,
    'fin_ventana'   : 23.0,
}

O3 = {} #hospital de salida de enfermeros externos
O3[30] ={
    'inicio_ventana': 8.0,
    'fin_ventana'   : 23.0,
}


S1= {}
S1[1] = {
    'inicio_ventana': 8.0,
    'fin_ventana'   : 17.0
}

S2= {}
S2[2] = {
    'inicio_ventana': 15.0,
    'fin_ventana'   : 23.0
}

S3= {} #el de los externos
S3[3] = {
    'inicio_ventana': 8.0 ,
    'fin_ventana'   : 23.0
}


#UE
UE = {}
for _, row in UE_df.iterrows():
    id = row['ID'] 
    horario = row['Horarios']

    inicio_str = horario[:5]
    fin_str = horario[-5:] 

    h_inicio, m_inicio = map(int, inicio_str.split(":"))
    h_fin, m_fin = map(int, fin_str.split(":"))

    inicio_decimal = h_inicio + m_inicio / 60
    fin_decimal = h_fin + m_fin / 60

    UE[id] = {
        'inicio_ventana': inicio_decimal,
        'fin_ventana'   : fin_decimal,
        'servicio' : 30
    }

#UM
UM = {}
for _, row in UM_df.iterrows():
    id = row['ID'] - 24 #para que parta en 1 y no en 25
    horario = row['Horarios']

    inicio_str = horario[:5]
    fin_str = horario[-5:] 

    h_inicio, m_inicio = map(int, inicio_str.split(":"))
    h_fin, m_fin = map(int, fin_str.split(":"))

    inicio_decimal = h_inicio + m_inicio / 60
    fin_decimal = h_fin + m_fin / 60

    UM[id] = {
        'inicio_ventana': inicio_decimal,
        'fin_ventana'   : fin_decimal,
        'servicio' : 30
    }

#se crean listas con los id de cada conjunto, para usarlos como índices
P_ids = [id  + 1000 for id  in P.keys()] #van del 1 al 1000
K_ids = [id + 5000 for id in K.keys()] #van del 5000
O_ids = [10, 20, 30] #son los hospitales de salida 
S_ids = [1, 2, 3] #son los hospitales de llegada 
UE_ids = [id  + 2000 for id  in UE.keys()] #van del 2000
UM_ids = [id  + 3000 for id  in UM.keys()]  #van del 3000
N_ids = O_ids + S_ids + P_ids + UE_ids + UM_ids


#ARCOS

arcos = []
for i in N_ids:
    for j in N_ids: 
        if i == j:
            continue  # no bucles

        #No permitir arcos de salida desde los hospitales de llegada 
        if i in [1, 2, 3]:
            continue

        #No permitir arcos de entrada a los nodos de hospitales de salida 
        if j == 10 or j == 20 or j == 30: 
            continue
            
        #No permitir arcos entre hospitales de salida y llegada entre diferentes turnos
        if i == 10 and (j == 2 or j ==3): 
            continue

        if i == 20 and (j == 1 or j ==3): 
            continue

        if i == 30 and (j == 1 or j ==2): 
            continue

        #No permitir arcos entre UE (2000-2999)
        if 2000 <= i < 3000 and 2000 <= j < 3000:
            continue

        # No permitir arcos entre UM (3000-3999)
        if 3000 <= i < 4000 and 3000 <= j < 4000:
            continue

        # No permitir que UE o UM apunten a hospitales de llegada (1,2,3)
        # if 2000 <= i < 4000 and j in [1, 2, 3]:
        #     continue

        # Si pasó todos los filtros, agregamos el arco
        arcos.append((i, j))

arcos_set = set(arcos)



#Lógica
# n  > 1000 entonces ese nodo es un paciente
# si n > 2000 entonces es una UE
# si n >3000 entonces es una UM
# si n = 10 es el nodo de hospital salida turno 1
# si n = 20 es el nodo de hospital salida turno 2
# si n = 30 es el nodo de hospital salida turno externos
# si n = 1 es el nodo de hospital llegada turno 1
# si n = 2 es el nodo de hospital llegada turno 2
# si n = 3 es el nodo de hospital llegada turno externos


#PARÁMETROS

#tiempo de servicio S_i
s = {}
for n in N_ids:
    id = n
    if id > 1000 and n < 2000: # es un paciente
        s[n] = P[id - 1000]['servicio']

    if id > 2000 and i != 1 and i != 2 and i !=3 :
         s[n] = 30 #30 min en UE y UM

    if id == 10 or id == 20 or id == 30 or id == 1 or id == 2 or id == 3:
        s[n] = 0 #los hospitales de llegada y salida es instantáneo


#distancia y tiempo entre nodos i y j
d = {}
t = {}
for _, row in matriz_df.iterrows():
    i = row['id_origen']
    j = row['id_destino']
    if i in N_ids and j in N_ids and (i,j) in arcos_set:
        d[i, j] = row['distancia_m']
        t[i, j] = round(row['tiempo_min'], 1) #se redondea el tiempo


#inicio y fin de ventana del nodo i 
a = {}
b = {}
for n in N_ids:
    id = n
    if id > 1000 and id < 2000: # es un paciente
        a[n] = int(P[id - 1000]["inicio_ventana"]) * 60
        b[n] = int(P[id - 1000]["fin_ventana"]) * 60

    if id > 2000 and id < 3000: #es una UE
        a[n] = int(UE[id - 2000]["inicio_ventana"]) * 60
        b[n] = int(UE[id - 2000]["fin_ventana"]) * 60

    if id > 3000 and id < 4000: #es una UM
        a[n] = int(UM[id - 3000]["inicio_ventana"]) * 60
        b[n] = int(UM[id - 3000]["fin_ventana"]) * 60

    if id == 10: #es el hospital de salida  O1 turno 1
        a[n] = 8 * 60
        b[n] = 17 * 60
    
    if id == 20: #es el hospital de salida O2 turno 2
        a[n] = 15 * 60
        b[n] = 23 * 60
    
    if id == 30: #es el hospital de salida O3 externos 
        a[n] = 8 * 60
        b[n] = 23 * 60

    if id == 1: #es el hospital de llegada S1 turno 1
        a[n] = 8 * 60
        b[n] = 17 * 60

    if id == 2: #es el hospital de llegada S2 turno 2
        a[n] = 15 * 60
        b[n] = 23 * 60
    
    if id == 3: #es el hospital de llegada S3 turno externos
        a[n] = 8 * 60
        b[n] = 23 * 60

#Costo de distancia
CB = 100 / 1000 #por metros

#Costo de espera
CV = 5500 / 60  #para que esté en minutos

#Costo sueldo fijo internos
CI = 1250000

#Costo sueldo fijo externos
CEF = 15000

#Costo enfermeros externos para el paciente p
CEV = {
    'LUNES': {'Baja Complejidad': 12500, 'Mediana Complejidad': 15000, 'Alta Complejidad': 20000, 'Evaluación o Seguimiento': 7500, 'Ambulatorio Baja Complejidad': 10000, 'Ambulatorio Mediana Complejidad': 12500},
    'MARTES':{'Baja Complejidad': 12500, 'Mediana Complejidad': 15000, 'Alta Complejidad': 20000, 'Evaluación o Seguimiento': 7500, 'Ambulatorio Baja Complejidad': 10000, 'Ambulatorio Mediana Complejidad': 12500},
    'MIERCOLES': {'Baja Complejidad': 12500, 'Mediana Complejidad': 15000, 'Alta Complejidad': 20000, 'Evaluación o Seguimiento': 7500, 'Ambulatorio Baja Complejidad': 10000, 'Ambulatorio Mediana Complejidad': 12500},
    'JUEVES': {'Baja Complejidad': 12500, 'Mediana Complejidad': 15000, 'Alta Complejidad': 20000, 'Evaluación o Seguimiento': 7500, 'Ambulatorio Baja Complejidad': 10000, 'Ambulatorio Mediana Complejidad': 12500},
    'VIERNES': {'Baja Complejidad': 12500, 'Mediana Complejidad': 15000, 'Alta Complejidad': 20000, 'Evaluación o Seguimiento': 7500, 'Ambulatorio Baja Complejidad': 10000, 'Ambulatorio Mediana Complejidad': 12500},
    'SÁBADO': {'Baja Complejidad': 15000, 'Mediana Complejidad': 20000, 'Alta Complejidad': 25000, 'Evaluación o Seguimiento': 10000, 'Ambulatorio Baja Complejidad': 12500, 'Ambulatorio Mediana Complejidad': 15000},
    'DOMINGO':{'Baja Complejidad': 15000, 'Mediana Complejidad': 20000, 'Alta Complejidad': 25000, 'Evaluación o Seguimiento': 10000, 'Ambulatorio Baja Complejidad': 12500, 'Ambulatorio Mediana Complejidad': 15000}
}

m = gp.Model("Capstone_Routing")
m.setParam("TimeLimit", 8*60*60) #establece el tiempo máximo en segundos (8 horas)
#m.setParam("MIPGap", 0.50)  #establece un gap (80%)

#VARIABLES

#X[k,i,j] = 1 si el enfermero k se traslada del nodo i al nodo j
X = m.addVars(K_ids, arcos, vtype=GRB.BINARY, name="X")

# Z[k,i] = 1 si el enfermero k visita el nodo i
Z = m.addVars(K_ids, N_ids,vtype=GRB.BINARY, name="Z")

# Y[k] = 1 si el enfermero k atendió a al menos 1 paciente
Y = m.addVars(K_ids, vtype=GRB.BINARY, name="Y")

# RM[k] = 1 si el enfermero k atiende en su ruta algún paciente con Medicamento Perecible
RM = m.addVars(K_ids, vtype=GRB.BINARY, name="PM")

# RE[k] = 1 si el enfermero k atiende en su ruta algún paciente con Examen Perecible o no perecible
RE = m.addVars(K_ids, vtype=GRB.BINARY, name="RE")

# PE[k, i, j] = 1 si el enfermero k fue del paciente P con exámen a la UE j
PE = m.addVars(K_ids, P_subsets['PE'] + P_subsets['PEP'], UE_ids, vtype=GRB.BINARY, name="PE")

# PM[k, i, j] = 1 si el enfermero k fue a la UM i y luego al paciente j con medicamento
PM = m.addVars(K_ids, UM_ids, P_subsets['PM'], vtype=GRB.BINARY, name="PE")

#I[i, k] instante en el cual se inicia el servicio en el nodo i por el enfermero k
I = m.addVars(N_ids, K_ids, vtype=GRB.CONTINUOUS, name="I")

#W[k] tiempo de espera del enfermero k
W = m.addVars(K_ids, vtype=GRB.CONTINUOUS, name="W")

# Llamamos a update, para agregar las variables al modelo
m.update()

#RESTRICCIONES

#Cada paciente i ∈ P debe ser atendido exactamente una vez
m.addConstrs(
    (gp.quicksum(Z[k, i] for k in K_ids) == 1
     for i in P_ids),
    name="R1"
)

#Flujo de salida en i: para cada k y cada paciente i
m.addConstrs(
    (gp.quicksum(X[k, i2, j] for (i2, j) in arcos if i2 == i) == Z[k, i]
     for k in K_ids
     for i in N_ids if i not in [1, 2, 3]),
    name="R2"
)

#Flujo de entrada en j: para cada k y cada paciente j
m.addConstrs(
    (gp.quicksum(X[k, i, j2] for (i, j2) in arcos if j2 == j) == Z[k, j]
     for k in K_ids
     for j in N_ids if j not in [10, 20, 30]),
    name="R3"
)

# El equipo sale del hospital de partida {O} correspondiente
m.addConstrs(
    (gp.quicksum(X[k, 10, j] for (i, j) in arcos if i == 10) == 1
     for k in K_subsets['K1']),
    name="R4.1"
)

m.addConstrs(
    (gp.quicksum(X[k, 20, j] for (i, j) in arcos if i == 20) == 1
     for k in K_subsets['K2']),
    name="R4.2"
)

m.addConstrs(
    (gp.quicksum(X[k, 30, j] for (i, j) in arcos if i == 30) == 1
     for k in K_subsets['KEX']),
    name="R4.3"
)

# El equipo no puede salir del hospital de partida {O} que no le corresponde
m.addConstrs(
    (gp.quicksum(X[k, 10, j] for (i, j) in arcos if i == 10) == 0
     for k in K_subsets['K2'] + K_subsets['KEX']),
    name="R5.1"
)

m.addConstrs(
    (gp.quicksum(X[k, 20, j] for (i, j) in arcos if i == 20) == 0
     for k in K_subsets['K1'] + K_subsets['KEX']),
    name="R5.2"
)

m.addConstrs(
    (gp.quicksum(X[k, 30, j] for (i, j) in arcos if i == 30) == 0
     for k in K_subsets['K1'] + K_subsets['K2']),
    name="R5.3"
)


#El equipo vuelve al hospital de llegada correspondiente
m.addConstrs(
    (gp.quicksum(X[k, i, 1] for (i, j) in arcos if j == 1) == 1
     for k in K_subsets['K1']),
    name="R6.1"
)


m.addConstrs(
    (gp.quicksum(X[k, i, 2] for (i, j) in arcos if j == 2) == 1
     for k in K_subsets['K2']),
    name="R6.2"
)


m.addConstrs(
    (gp.quicksum(X[k, i, 3] for (i, j) in arcos if j == 3) == 1
     for k in K_subsets['KEX']),
    name="R6.3"
)

#El equipo vuelve al hospital de llegada correspondiente, Y NO A OTRO
m.addConstrs(
    (gp.quicksum(X[k, i, 1] for (i, j) in arcos if j == 1) == 0
     for k in K_subsets['K2'] + K_subsets['KEX']),
    name="R7.1"
)

m.addConstrs(
    (gp.quicksum(X[k, i, 2] for (i, j) in arcos if j == 2) == 0
     for k in K_subsets['K1'] + K_subsets['KEX']),
    name="R7.2"
)

m.addConstrs(
    (gp.quicksum(X[k, i, 3] for (i, j) in arcos if j == 3) == 0
     for k in K_subsets['K1'] + K_subsets['K2']),
    name="R7.3"
)


#Activación de RM y RE
M = len(P_ids)
m.addConstrs(
    ( gp.quicksum(Z[k, i] for i in P_subsets['PM']) <= RM[k] * M
      for k in K_ids ),
    name="R8.1"
)

m.addConstrs(
    ( gp.quicksum(Z[k, i] for i in P_subsets['PEP'] + P_subsets['PE']) <= RE[k] * M  #para perecibles y no perecibles
      for k in K_ids ),
    name="R9.1"
)


#Si pasa por EP/M debe pasar después/antes por un UE/UM
#RM
m.addConstrs(
    ( gp.quicksum(Z[k, i] for i in UM_ids) >= RM[k] 
      for k in K_ids ),
    name="R8.2"
)

m.addConstrs(
    (gp.quicksum(Z[k, i] for i in P_subsets['PM']) >=  gp.quicksum(Z[k, i] for i in UM_ids)
      for k in K_ids ),
    name="R8.3"
)

#RE
m.addConstrs(
    ( gp.quicksum(Z[k, i] for i in UE_ids) >= RE[k] 
      for k in K_ids ),
    name="R9.2"
)

m.addConstrs(
    (gp.quicksum(Z[k, i] for i in P_subsets['PEP'] + P_subsets['PE']) >=  gp.quicksum(Z[k, i] for i in UE_ids)
      for k in K_ids ),
    name="R9.3"
)

# Restricciones de PM

    #Activación PM
m.addConstrs(
    (gp.quicksum(PM[k, i, j] for i in UM_ids) == Z[k, j] for k in K_ids for j in P_subsets['PM']),
    name="R10.1"
)

    #Activación Z dado que iré a una UM específica
m.addConstrs(
    (PM[k, i, j] <= Z[k, i] for i in UM_ids for k in K_ids for j in P_subsets['PM']),
    name="R10.2"
)

    #Desactivar Z si no iré a ninguna UM
m.addConstrs(
    (Z[k, i] <= gp.quicksum(PM[k, i, j] for j in P_subsets['PM']) for k in K_ids for i in UM_ids),
    name="R10.3"
)

#Restricciones de PE

    #Activación PE
m.addConstrs(
    (gp.quicksum(PE[k, i, j] for j in UE_ids) == Z[k, i] for i in P_subsets['PEP'] + P_subsets['PE'] for k in K_ids),
    name="R11.1"
)

    #Activación Z dado que iré a una UE específica
m.addConstrs(
    (PE[k, i, j] <= Z[k, i] for i in P_subsets['PEP'] + P_subsets['PE'] for k in K_ids for j in UE_ids),
    name="R11.2"
)

    #Desactivar Z si no iré a ninguna UE
m.addConstrs(
    (Z[k, j] <= gp.quicksum(PE[k, i, j] for i in P_subsets['PEP'] + P_subsets['PE']) for k in K_ids for j in UE_ids),
    name="R11.3"
)

#El inicio de atención debe ser dentro de la ventana del paciente
Mgrande = 10000
m.addConstrs(
    (a[i] - Mgrande * (1 - Z[k, i]) <= I[i, k]
      for i in N_ids
      for k in K_ids),
    name="R12.1"
)

m.addConstrs(
    (I[i, k] <= b[i] + Mgrande * (1 - Z[k, i])
      for i in N_ids
      for k in K_ids),
    name="R12.2"
)

#Secuencia temporal
m.addConstrs(
    (I[j, k] >= I[i, k] + s[i] + t[(i,j)] - Mgrande * (1 - X[k, i, j])
      for (i, j) in arcos
      for k in K_ids 
      if i != j and j != 10 and j != 20 and j != 30),
    name="R13"
)

#Definir Y
Ngrande = 10000
m.addConstrs(
    (Ngrande * Y[k] >= gp.quicksum(Z[k, i] for i in N_ids if i not in [10, 20, 30, 1, 2, 3])
     for k in K_ids),
    name="R14"
)


#Definir tiempo de espera
m.addConstrs(
    (W[k] == (b[1] - a[1]) 
      - gp.quicksum(Z[k, i] * s[i] for i in N_ids)
      - gp.quicksum(X[k, i, j] * t[i, j] for (i, j) in arcos)
     for k in K_subsets['K1']),
    name="R15.1"
)

m.addConstrs(
    (W[k] == (b[2] - a[2])
      - gp.quicksum(Z[k, i] * s[i] for i in N_ids)
      - gp.quicksum(X[k, i, j] * t[i, j] for (i, j) in arcos)
     for k in K_subsets['K2']),
    name="R15.2"
)

#Diferencia de 60 minutos entre PM y UM, o entre PEP y UE
M = 10**4 

m.addConstrs(
    (I[j, k] - (I[i, k] + s[i]) <= 60 + M * (1 - PE[k, i, j])
     for k in K_ids for i in P_subsets['PEP'] for j in UE_ids),
    name="16.1"
)

m.addConstrs(
    (I[j, k] - (I[i, k] + s[i]) <= 60 + M * (1 - PM[k, i, j])
     for k in K_ids for i in UM_ids for j in P_subsets['PM']),
    name="R16.2"
)

#Que efectivamente antes/después a la UM/UE del paciente 

m.addConstrs(
    (M * (1 - PE[k, i, j]) + I[j, k] >= I[i, k]
     for k in K_ids for i in P_subsets['PEP'] + P_subsets['PE'] for j in UE_ids),
    name="17.1"
)

m.addConstrs(
    (M * (1 - PM[k, i, j]) + I[j, k] >= I[i, k]
     for k in K_ids for i in UM_ids for j in P_subsets['PM']),
    name="17.2"
)


#FUNCIÓN OBJETIVO
m.setObjective(

    # 1. Costos de distancia recorrida (solo internos)
    gp.quicksum(X[k, i, j] * d[i, j] * CB for k in K_subsets['K1'] + K_subsets['K2'] for (i, j) in arcos)

    +

    # 2. Costos de espera (solo internos)
    gp.quicksum(W[k] * CV for k in K_subsets['K1'] + K_subsets['K2'])

    +

    # 3. Costos de enfermeros externos fijo 15.000
    gp.quicksum(Y[k] * CEF for k in K_subsets['KEX'])

    +

    #4. Costo de enfermeros externos variable por requerimiento
    gp.quicksum(Z[k, i] * CEV['LUNES'][P[i - 1000]['requerimiento']] for k in K_subsets['KEX'] for i in P_ids)

, sense=GRB.MINIMIZE)

#OPTIMIZAR
m.optimize()


#VER COSTO

if m.status not in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
    print("¡Atención! El modelo no encontró solución válida.")
else:
    # 1) Costos de distancia (solo internos)
    dist_cost = sum(
        X[k, i, j].X * d[i, j] * CB
        for k in K_subsets['K1'] + K_subsets['K2']
        for (i, j) in arcos
    )

    # 2) Costos de espera (solo internos)
    wait_cost = sum(
        W[k].X * CV
        for k in K_subsets['K1'] + K_subsets['K2']
    )

    # 3) Costo fijo de enfermeros externos
    fixed_ext = sum(
        Y[k].X * CEF
        for k in K_subsets['KEX']
    )

    # 4) Costo variable de enfermeros externos
    var_ext = sum(
        Z[k, i].X * CEV['LUNES'][ P[i-1000]['requerimiento'] ]
        for k in K_subsets['KEX']
        for i in P_ids
    )

    total = dist_cost + wait_cost + fixed_ext + var_ext

    print(f"1) Costos distancia   : {dist_cost:,.2f}")
    print(f"2) Costos espera      : {wait_cost:,.2f}")
    print(f"3) Costo fijo ext.    : {fixed_ext:,.2f}")
    print(f"4) Costo var. ext.    : {var_ext:,.2f}")
    print(f"——————————————")
    print(f"ObjVal (m.ObjVal)     : {m.ObjVal:,.2f}")
    print(f"Suma de partes        : {total:,.2f}")


#GUARDAR VARIABLES

# Guardar X[k, i, j]
with open("resultados/X.csv", "w") as f:
    print("Enfermero,Desde,Hasta,Valor", file=f)
    for k in K_ids:
        for (i, j) in arcos:
            if X[k, i, j].X > 0.5:
                print(f"{k},{i},{j},{int(X[k, i, j].X)}", file=f)

# Guardar Z[k, i]
with open("resultados/Z.csv", "w") as f:
    print("Enfermero,Nodo,Valor", file=f)
    for k in K_ids:
        for i in N_ids:
            if Z[k, i].X > 0.5:
                print(f"{k},{i},{int(Z[k, i].X)}", file=f)

# Guardar I[i, k]
with open("resultados/I.csv", "w") as f:
    print("Nodo,Enfermero,InicioAtencion", file=f)
    for i in N_ids:
        for k in K_ids:
            if Z[k, i].X > 0.5:
                print(f"{i},{k},{round(I[i, k].X, 2)}", file=f)

# Guardar Y[k]
with open("resultados/Y.csv", "w") as f:
    print("Enfermero,Externo", file=f)
    for k in K_ids:
        print(f"{k},{int(Y[k].X)}", file=f)

# Guardar RM[k]
with open("resultados/RM.csv", "w") as f:
    print("Enfermero,RM", file=f)
    for k in K_ids:
        print(f"{k},{int(RM[k].X)}", file=f)

# Guardar RE[k]
with open("resultados/RE.csv", "w") as f:
    print("Enfermero,RE", file=f)
    for k in K_ids:
        print(f"{k},{int(RE[k].X)}", file=f)

# Guardar W[k]
with open("resultados/W.csv", "w") as f:
    print("Enfermero,Espera", file=f)
    for k in K_ids:
        print(f"{k},{round(W[k].X, 2)}", file=f)

#Guardar PE[k,i,j]
with open("resultados/PE.csv", "w") as f:
    print("Enfermero,Paciente,UE,Valor", file=f)
    for k in K_ids:
        for i in P_subsets['PE'] + P_subsets['PEP']:
            for j in UE_ids:
                valor = PE[k, i, j].X
                if valor > 1e-6:  # para no guardar ceros innecesarios
                    print(f"{k},{i},{j},{round(valor, 2)}", file=f)

#Guardar PM[k,i,j]
with open("resultados/PM.csv", "w") as f:
    print("Enfermero,UM,Paciente,Valor", file=f)
    for k in K_ids:
        for i in UM_ids:
            for j in P_subsets['PM']:
                valor = PM[k, i, j].X
                if valor > 1e-6:
                    print(f"{k},{i},{j},{round(valor, 2)}", file=f)