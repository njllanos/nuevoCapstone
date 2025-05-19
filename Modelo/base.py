import pandas as pd
import numpy as np
import os
import csv

# ========================
# CONFIGURACIÓN
# ========================
semana = 's1'
dia = 3
dias_semana = {1: 'LUNES', 2: 'MARTES', 3: 'MIÉRCOLES', 4: 'JUEVES', 5: 'VIERNES', 6: 'SÁBADO', 7: 'DOMINGO'}
apretado = False

# Horarios de cierre por hospital de llegada
cierre_general_hospital = 23 * 60
apertura_general_hospital = 8 * 60
cierre_hospitales = {1: 17 * 60, 2: 23 * 60, 3: 23 * 60}
apertura_hospitales = {10: 8 * 60, 20: 15 * 60, 30: 8 * 60}

# ========================
# CARGA DE DATOS
# ========================
hospital_df = pd.read_excel('Capstone_Instancia/data/hospital.xlsx')
um_df = pd.read_excel('Capstone_Instancia/data/um.xlsx')
ue_df = pd.read_excel('Capstone_Instancia/data/ue.xlsx')
arcos_df = pd.read_excel('Capstone_Instancia/arcos/arcos/arcos_resumen.xlsx')
pacientes_df = pd.read_excel('Capstone_Instancia/data/pacientes.xlsx', sheet_name=semana)
enfermeros_df = pd.read_excel('Capstone_Instancia/data/enfermeros_s.xlsx', sheet_name=dias_semana[dia])

# ========================
# PARÁMETROS
# ========================
COSTO_BENCINA_POR_KM = 100
COSTO_ESPERA_POR_MIN = 5500 / 60
COSTO_INTERNO = 1000000 + 250000
COSTO_FIJO_EXTERNO = 15000
COSTOS_CATEGORIA_LaV = {
    'Baja Complejidad': 12500, 'Mediana Complejidad': 15000, 'Alta Complejidad': 20000,
    'Evaluación o Seguimiento': 7500, 'Ambulatorio Baja Complejidad': 10000, 'Ambulatorio Mediana Complejidad': 12500
}
COSTOS_CATEGORIA_SaD = {
    'Baja Complejidad': 15000, 'Mediana Complejidad': 20000, 'Alta Complejidad': 25000,
    'Evaluación o Seguimiento': 10000, 'Ambulatorio Baja Complejidad': 12500, 'Ambulatorio Mediana Complejidad': 15000
}

# ========================
# FUNCIONES
# ========================
def time_to_minutes(time_str):
    if isinstance(time_str, str) and ':' in time_str:
        try:
            h, m = map(int, time_str.strip().split(':'))
            return h * 60 + m
        except:
            return np.nan
    return np.nan

def minutos_a_hora(minutos):
    if pd.isna(minutos) or np.isinf(minutos): return "ERROR"
    horas = int(minutos // 60)
    mins = int(minutos % 60)
    return f"{horas:02d}:{mins:02d}"

def apretar_horario(paciente, apertura_hospital, cierre_hospital):
    ini, fin = paciente['inicio_minutos'], paciente['fin_minutos']
    paciente['inicio_minutos'] = max(ini, apertura_hospital + obtener_tiempo_viaje(1, paciente['ID']))
    paciente['fin_minutos'] = min(fin, cierre_hospital - obtener_tiempo_viaje(paciente['ID'], 1))

# ========================
# VIAJES
# ========================
viajes = {
    (row['id_origen'], row['id_destino']): {
        'tiempo': round(row['tiempo_min'], 1),
        'distancia': row['distancia_m'] / 1000
    } for _, row in arcos_df.iterrows()
}

def obtener_tiempo_viaje(o, d):
    o, d = (0 if x in [10, 20, 30, 1, 2, 3] else x for x in (o, d))
    return viajes.get((o, d), {'tiempo': np.inf})['tiempo']

def obtener_distancia(o, d):
    o, d = (0 if x in [10, 20, 30, 1, 2, 3] else x for x in (o, d))
    if o == d: return 0
    return viajes[(o, d)]['distancia'] if (o, d) in viajes else np.inf

def punto_mas_cercano_disponible(origen, lista_ids, t_actual, disponibilidad):
    mejor, min_t, dist = None, np.inf, np.inf
    for p in lista_ids:
        t = obtener_tiempo_viaje(origen, p)
        llegada = t_actual + t
        ini, fin = disponibilidad.get(p, (0, 1440))
        if ini <= llegada <= fin and t < min_t:
            mejor, min_t, dist = p, t, obtener_distancia(origen, p)
        
    return mejor, min_t, dist

# ========================
# PREPROCESAMIENTO
# ========================
for df, col_ini, col_fin in [(enfermeros_df, 'HORARIO ENTRADA 1', 'HORARIO SALIDA 1'),
                             (pacientes_df, 'INICIO VENTANA', 'FIN VENTANA'),
                             (um_df, 'HORARIO INICIO', 'HORARIO FIN'),
                             (ue_df, 'HORARIO INICIO', 'HORARIO FIN'),
                             (hospital_df, 'HORARIO INICIO', 'HORARIO FIN')]:
    df['inicio_minutos'] = df[col_ini].apply(time_to_minutes)
    df['fin_minutos'] = df[col_fin].apply(time_to_minutes)

pacientes_df['DURACIÓN'] = pacientes_df['DURACIÓN'].astype(float)

disponibilidad_um = {row['ID']: (row['inicio_minutos'], row['fin_minutos']) for _, row in um_df.iterrows()}
disponibilidad_ue = {row['ID']: (row['inicio_minutos'], row['fin_minutos']) for _, row in ue_df.iterrows()}
puntos_um = um_df['ID'].tolist()
puntos_ue = ue_df['ID'].tolist()

if apretado:
    for _, row in um_df.iterrows():
        row['inicio_minutos'] = max(row['inicio_minutos'], apertura_general_hospital + obtener_tiempo_viaje(1, row['ID']))
        row['fin_minutos'] = min(row['fin_minutos'], cierre_general_hospital - obtener_tiempo_viaje(row['ID'], 1))

# ========================
# SIMULACIÓN DE RUTA
# ========================
resultados, pacientes_atendidos = [], set() #defino una lista de pacientes atentidos
X, Z, I, Y, rm, re, w, PE_final, PM_final = [], [], [], [], {}, {}, {}, [], []
distancias_enfermeros = []

for _, enf in enfermeros_df.iterrows():

    k = enf['ID']
    reg = enf['REGIMEN']
    hs, hl = (10, 1) if reg == "INTERNO TURNO 1" else (20, 2) if reg == "INTERNO TURNO 2" else (30, 3)
    
    #Defino el cierre del hospital del enfermero
    cierre_hospital = cierre_hospitales[hl]
    apertura_hospital = apertura_hospitales[hs]

    t_actual = enf['inicio_minutos'] #iniciamos en su horario de partida 
    ubic = hs #iniciamos en el hospital de salida

    ruta, km, espera, ext_var = [('Hospital', hs, t_actual)], 0, 0, 0

    re[k], rm[k] = 0, 0
    examenes_no_perecibles = []


    while True:
        candidatos = pacientes_df[(pacientes_df[dias_semana[dia]] == "Si") & (~pacientes_df['ID'].isin(pacientes_atendidos))]
        if candidatos.empty: break

        mejor_p, mejor_t, info_mejor_paciente = None, np.inf, None

        for _, pac in candidatos.iterrows():
            
            t_sim, u_sim, km_sim, esp_sim = t_actual, ubic, 0, 0
            um = ue = None

            if pac['MEDICAMENTO'] == 'Medicamento Perecible':
                um, t_um, km_um = punto_mas_cercano_disponible(u_sim, puntos_um, t_sim, disponibilidad_um) #obtengo la UM más cercana, el tiempo de viaje y la ditancia hasta allá
                if not um or obtener_tiempo_viaje(um, pac['ID']) > 60: continue #Si no hay una UM disponible o si el viaje desde esa UM al paciente toma más de 60 minutos, se descarta este paciente 
                t_sim += t_um + 30 + obtener_tiempo_viaje(um, pac['ID']) #sumo el tiempo en ir a UM + 30 min de recogerlo + tiempo en ir al paciente
                km_sim += km_um + obtener_distancia(um, pac['ID']) #sumo la distancia en ir a UM + la distnacia de UM al paciente
                u_sim = pac['ID'] #ahora estoy en el paciente 

            else:
                t_sim += obtener_tiempo_viaje(u_sim, pac['ID']) #sumo solo el tiempo de viaje
                km_sim += obtener_distancia(u_sim, pac['ID']) #sumo la distancia al paciente
                u_sim = pac['ID'] #ahora estoy en el paciente

            if apretado:
                #ini_antiguo, fin_antiguo = pac['inicio_minutos'], pac['fin_minutos']
                apretar_horario(pac, apertura_general_hospital, cierre_general_hospital)
                if pac['inicio_minutos'] > pac['fin_minutos']: continue
                # si cambio hacer un print
                #if ini_antiguo != pac['inicio_minutos'] or fin_antiguo != pac['fin_minutos']:
                    #print(f"Paciente {pac['ID']} apretado de {minutos_a_hora(ini_antiguo)} a {minutos_a_hora(pac['inicio_minutos'])} y de {minutos_a_hora(fin_antiguo)} a {minutos_a_hora(pac['fin_minutos'])}")

            if t_sim < pac['inicio_minutos']: #si llegué antes de que la ventana del paciente
                esp_sim = pac['inicio_minutos'] - t_sim #sumo el tiempo de espera
                t_sim = pac['inicio_minutos'] #el tiempo actual es el inicio de la ventana del paciente

            t_ini = t_sim #guarda el tiempo de inicio efectivo de atención al paciente
            t_fin_pac = t_ini + pac['DURACIÓN'] #guarda el tiempo final efectivo de atención al paciente
            if t_fin_pac > pac['fin_minutos']: continue # si termino después de la ventana del paciente, no lo puedo atententer y sigo con el siguiente

            t_final_est = t_fin_pac #creamos un tiempo final estimado
            if pac['EXAMEN'] == 'Examen Perecible':
                ue, t_ue, km_ue = punto_mas_cercano_disponible(pac['ID'], puntos_ue, t_final_est, disponibilidad_ue)
                if not ue or t_ue > 60: continue # si no hay ninguna disponible o la distancia es mayor a 60 min, no puedo atender al paciente y voy al siguiente
                t_final_est += t_ue + 30 + obtener_tiempo_viaje(ue, hl) #el tiempo final estimado es el tiempo en ir a la UE + 30 min de dejar el exámen + el tiempo en llegar al hospital de llegada
                km_sim += km_ue #sumo la distancia a la ue
            elif pac['EXAMEN'] == 'Examen No Perecible':
                ue, t_ue, km_ue = punto_mas_cercano_disponible(pac['ID'], puntos_ue, t_final_est, disponibilidad_ue)
                if not ue: continue # si no hay ninguna disponible o la distancia es mayor a 60 min, no puedo atender al paciente y voy al siguiente
                t_final_est += t_ue + 30 + obtener_tiempo_viaje(ue, hl) #el tiempo final estimado es el tiempo en ir a la UE + 30 min de dejar el exámen + el tiempo en llegar al hospital de llegada
            else:
                if len(examenes_no_perecibles) > 0: #si ya terminé de ver a qué pacientes voy a atender, veo si tenía no perecibles
                    ue, t_ue, km_ue = punto_mas_cercano_disponible(pac['ID'], puntos_ue, t_final_est, disponibilidad_ue)
                    if not ue: continue # si no hay ninguna disponible o la distancia es mayor a 60 min, no puedo atender al paciente y voy al siguiente
                    t_final_est += t_ue + 30 + obtener_tiempo_viaje(ue, hl) #el tiempo final estimado es el tiempo en ir a la UE + 30 min de dejar el exámen + el tiempo en llegar al hospital de llegada
                else:
                    t_final_est += obtener_tiempo_viaje(pac['ID'], hl)

            if t_final_est > cierre_hospital or t_final_est > enf['fin_minutos']: continue #Si el tiempo total estimado para terminar todo (incluyendo entrega y vuelta) supera el horario de cierre del hospital, no se puede atender al paciente

            if t_ini < mejor_t:
                mejor_p = pac
                mejor_t = t_ini
                info_mejor_paciente = {'hora_ini': t_ini, 'hora_fin': t_fin_pac, 'um': um, 'ue': ue, 'km': km_sim, 'esp': esp_sim}

        if mejor_p is None: break

        #Lo voy a atender si es el mejor
        pac = mejor_p
        i = pac['ID']
        pacientes_atendidos.add(i)

        if reg == 'EXTERNO':
            ext_var += COSTOS_CATEGORIA_LaV[pac['REQUERIMIENTO']] if dia < 5 else COSTOS_CATEGORIA_SaD[pac['REQUERIMIENTO']]

        if pac['MEDICAMENTO'] == 'Medicamento Perecible':
            t_actual += obtener_tiempo_viaje(ubic, info_mejor_paciente['um']) #le sumo el tiempo de viaje a la UM más cercana
            ruta.append(('UM', info_mejor_paciente['um'], t_actual)) #agrego a la ruta la UM
            t_actual += 30 #agrego los 30 min por retirarlo
            t_actual += obtener_tiempo_viaje(info_mejor_paciente['um'], i) #sumo el tiempo en ir al paciente
            rm[k] = 1 #defino que el enfermero K si atendió al menos a 1 paciente con M
            PM_final.append((k, info_mejor_paciente['um'], i, 1)) #agrego desde qué UM hasta qué paciente fue a dejar el medicamento
        else:
            t_actual += obtener_tiempo_viaje(ubic, i) #sino simplemente agrego el tiempo en ir al paciente

        if t_actual < pac['inicio_minutos']: #si llegué antes del inicio de la ventana, el tiempo actual es el inicio de la ventana
            t_actual = pac['inicio_minutos']
        ruta.append(('Paciente', i, t_actual)) #agrego a la ruta el paciente
        t_actual += pac['DURACIÓN'] #le sumo el tiempo de servicio
        ubic = i #actualmente estoy en el paciente

        if pac['EXAMEN'] == 'Examen Perecible':
            t_actual += obtener_tiempo_viaje(ubic, info_mejor_paciente['ue']) #sumo el tiempo en ir a la UE
            ruta.append(('UE', info_mejor_paciente['ue'], t_actual)) #agrego la UE a la ruta
            t_actual += 30 #sumo al tiempo actual el tiempo de dejar el exámen
            re[k] = 1 #defino que el enfermero k si atendió a al menos 1 paciente con EP
            PE_final.append((k, i, info_mejor_paciente['ue'], 1)) #digo desde qué paciente hasta qué UE fui a dejar el exámen
            ubic = info_mejor_paciente['ue'] #actualmente estoy en la UE
        
        elif pac['EXAMEN'] == 'Examen No Perecible': #veo si tiene exámen no perecible y agrego a la lista quién es
            examenes_no_perecibles.append(i)

        km += info_mejor_paciente['km'] #agrego los kilometros recorridos en ese paciente
        espera += info_mejor_paciente['esp'] #agreggo el tiempo de espera en ese paciente

    if len(examenes_no_perecibles) > 0: #si ya terminé de ver a qué pacientes voy a atender, veo si tenía no perecibles
        ue_final, t_ue, _ = punto_mas_cercano_disponible(ubic, puntos_ue, t_actual, disponibilidad_ue) #busco la UE más cercana
        if ue_final and t_actual + obtener_tiempo_viaje(ubic, ue_final) + 30 + obtener_tiempo_viaje(ue_final, hl) <= cierre_hospital: #si alcanzo a ir a dejarlo a la UE más cercana
            t_actual += obtener_tiempo_viaje(ubic, ue_final) 
            ruta.append(('UE', ue_final, t_actual))
            t_actual += 30
            for i_p in examenes_no_perecibles: 
                PE_final.append((k, i_p, ue_final, 1)) #digo desde todos los pacientes con no perecible hasta la UE que lo fui a entregar
            re[k] = 1 #defino que el enfermero k si atendió a al menos 1 paciente con EP
            km += obtener_distancia(ubic, ue_final) # agrego la distancia recorrida
            ubic = ue_final #actuamente estoy en la UE
        
        # if  t_actual + obtener_tiempo_viaje(ubic, hl) <= cierre_hospital: #si alcanzo a ir a dejarlo al hospital
        #     for i_p in examenes_no_perecibles: 
        #         PE_final.append((k, i_p, hl, 1)) #digo desde todos los pacientes con no perecible los fui a dejar al hospital
        #     re[k] = 1 #defino que el enfermero k si atendió a al menos 1 paciente con EP

    t_actual += obtener_tiempo_viaje(ubic, hl)
    #Si tiempo actual es infinito, t_actual es el tiempo de inicio del enfermero
    if np.isinf(t_actual):
        t_actual = enf['inicio_minutos']
        no_atiende = True
    else:
        no_atiende = False
    ruta.append(('Hospital', hl, t_actual))
    km += obtener_distancia(ubic, hl)
    resultados.append((k, ruta))
    # w[k] es la espera + el tiempo que extra que le quedo en el hospital si es interno
    w[k] = round(espera + (enf["fin_minutos"] - t_actual), 2) if not no_atiende and (reg == "INTERNO TURNO 1" or reg == "INTERNO TURNO 2") else round(enf["fin_minutos"] - t_actual, 2)
    if reg == "EXTERNO":
        w[k] = 0
    # activar Y si enfermero k atiende a alguien
    Y.append((k, 1)) if not no_atiende else Y.append((k, 0))

    for idx in range(len(ruta) - 1):
        ni, nj = ruta[idx][1], ruta[idx + 1][1]
        X.append((k, ni, nj, 1))

    for tipo, nodo, tiempo in ruta:
        Z.append((k, nodo, 1))
        I.append((nodo, k, round(tiempo, 2)))

    distancias_enfermeros.append((k, km))

# ========================
# GUARDAR ARCHIVOS
# ========================
def save_csv(name, header, data):
    with open(f"resultados/{name}.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)

os.makedirs("resultados", exist_ok=True)
save_csv("X", ["Enfermero", "Desde", "Hasta", "Valor"], X)
save_csv("Z", ["Enfermero", "Nodo", "Valor"], Z)
save_csv("I", ["Nodo", "Enfermero", "InicioAtencion"], I)
save_csv("Y", ["Enfermero", "Externo"], Y)
save_csv("RM", ["Enfermero", "RM"], [(k, v) for k, v in rm.items()])
save_csv("RE", ["Enfermero", "RE"], [(k, v) for k, v in re.items()])
save_csv("W", ["Enfermero", "Espera"], [(k, v) for k, v in w.items()])
save_csv("PE", ["Enfermero", "Desde", "Hasta", "Valor"], PE_final)
save_csv("PM", ["Enfermero", "Desde", "Hasta", "Valor"], PM_final)


pacientes_no_atendidos = pacientes_df[(pacientes_df[dias_semana[dia]] == "Si") & (~pacientes_df['ID'].isin(pacientes_atendidos))]
if not pacientes_no_atendidos.empty:
    print(F"Pacientes no atendidos: {', '.join(pacientes_no_atendidos['ID'].astype(str))}")
else:
    print("Todos los pacientes fueron atendidos.")



import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines

# Función de color idéntica a la tuya
def color_paciente(nodo):
    fila = pacientes_df[pacientes_df['ID'] == nodo]
    if fila.empty:
        return 'gray'
    examen = fila['EXAMEN'].iat[0]
    med    = fila['MEDICAMENTO'].iat[0]
    if examen == 'Examen Perecible'   and med!='Medicamento Perecible': return '#e899dc'
    if examen == 'Examen Perecible'   and med=='Medicamento Perecible': return '#00BBC9'
    if examen == 'Examen No Perecible'and med!='Medicamento Perecible': return '#a6d854'
    if examen == 'Examen No Perecible'and med=='Medicamento Perecible': return '#fc8d62'
    if examen not in ['Examen Perecible','Examen No Perecible'] and med!='Medicamento Perecible': return '#ffd92f'
    if examen not in ['Examen Perecible','Examen No Perecible'] and med=='Medicamento Perecible': return '#8da0cb'
    return 'gray'

ue_color = '#878787'   # gris para UE
um_color = '#CACACA'   # gris clarito para UM

fig, ax = plt.subplots(figsize=(16,9))

# 1) Filtramos sólo enfermeros que atendieron al menos un paciente
enf_con_pacientes = [
    (k, ruta) for k, ruta in resultados
    if any(tipo == 'Paciente' for tipo, _, _ in ruta)
]

# 2) Los ordenamos por ID de enfermero
enf_con_pacientes = sorted(enf_con_pacientes, key=lambda x: x[0])

for idx, (k, ruta) in enumerate(enf_con_pacientes):
    # 1) Bloques (pacientes, UM, UE) y líneas verticales en hospitales
    for tipo, nodo, tiempo in ruta:
        t_h = tiempo / 60.0
        if tipo == 'Paciente':
            dur_h = pacientes_df.loc[pacientes_df['ID']==nodo, 'DURACIÓN'].iat[0] / 60.0
            col   = color_paciente(nodo)
            ax.barh(idx, dur_h, left=t_h, color=col, edgecolor='black')
            ax.text(t_h + dur_h/2, idx, f'P{nodo-1000}', ha='center', va='center', fontsize=7)

        elif tipo == 'UE':
            dur_h = 30/60.0
            ax.barh(idx, dur_h, left=t_h, color=ue_color, edgecolor='black')
            ax.text(t_h + dur_h/2, idx, f'{nodo-2000}', ha='center', va='center', fontsize=7, fontweight='bold')

        elif tipo == 'UM':
            dur_h = 30/60.0
            ax.barh(idx, dur_h, left=t_h, color=um_color, edgecolor='black')
            ax.text(t_h + dur_h/2, idx, f'{nodo-3000}', ha='center', va='center', fontsize=7, fontweight='bold')

        elif tipo == 'Hospital' and nodo in [10,20,30,1,2,3]:
            ax.plot([t_h, t_h], [idx-0.4, idx+0.4], color='black', linewidth=1, zorder=2)

    # 2) Traslados y esperas intermedias
    for j in range(len(ruta)-1):
        tipo_i, nodo_i, t_i = ruta[j]
        tipo_j, nodo_j, t_j = ruta[j+1]

        # Determinamos minutos de servicio en nodo_i
        if tipo_i == 'Paciente':
            servicio = pacientes_df.loc[pacientes_df['ID']==nodo_i, 'DURACIÓN'].iat[0]
        elif tipo_i in ['UE','UM']:
            servicio = 30
        else:
            servicio = 0

        # Tiempo de viaje
        tv = obtener_tiempo_viaje(nodo_i, nodo_j)
        salida  = (t_i + servicio) / 60.0
        llegada = (t_i + servicio + tv) / 60.0

        # traslado (continua)
        ax.hlines(y=idx, xmin=salida, xmax=llegada, colors='black', linewidth=1, zorder=1)

        # espera intermedia (punteada) si hay hueco antes de t_j
        if t_j/60.0 > llegada:
            ax.hlines(y=idx, xmin=llegada, xmax=t_j/60.0,
                      colors='black', linestyles='dotted',
                      linewidth=1, zorder=0)

    # 3) espera final hasta fin de turno (para todos)
    t_llegada = ruta[-1][2]
    t_fin     = enfermeros_df.loc[enfermeros_df['ID']==k, 'fin_minutos'].iat[0]
    if t_fin > t_llegada:
        ax.hlines(y=idx,
                  xmin=t_llegada/60.0, xmax=t_fin/60.0,
                  colors='black', linestyles='dotted',
                  linewidth=1, zorder=0)

# ────────────────────────────────────────────────────────────────────────────────
# Formateo final
# ────────────────────────────────────────────────────────────────────────────────
ax.set_xlim(8, 23)
ax.set_xticks(range(8, 24))                     # mostrar cada hora
ax.set_xlabel("Horas del día")

ax.set_yticks(range(len(enf_con_pacientes)))
ax.set_yticklabels([f'ENF. {k-5000}' for k,_ in enf_con_pacientes])
ax.invert_yaxis()                               # idx=0 (5001) arriba

ax.grid(axis='x', linestyle='--', alpha=0.5)

# Título
ax.set_title(f"Itinerarios de Enfermeros el dia {dias_semana[dia].lower()} de la semana {semana}")

# Leyenda más a la izquierda
legend_elems = [
    mpatches.Patch(color='#e899dc', label='Examen Perecible + No Medicamento'),
    mpatches.Patch(color='#00BBC9', label='Examen Perecible + Medicamento Perecible'),
    mpatches.Patch(color='#a6d854', label='Examen No Perecible + No Medicamento'),
    mpatches.Patch(color='#fc8d62', label='Examen No Perecible + Medicamento Perecible'),
    mpatches.Patch(color='#ffd92f', label='No Examen + No Medicamento'),
    mpatches.Patch(color='#8da0cb', label='No Examen + Medicamento Perecible'),
    mpatches.Patch(color=ue_color,   label='UE'),
    mpatches.Patch(color=um_color,   label='UM'),
    mlines.Line2D([], [], color='black', linestyle='-',      label='Traslado'),
    mlines.Line2D([], [], color='black', linestyle='dotted', label='Tiempo ocioso'),
]
ax.legend(handles=legend_elems, loc='upper right', bbox_to_anchor=(1.02, 1.01))

plt.tight_layout()
plt.show()
