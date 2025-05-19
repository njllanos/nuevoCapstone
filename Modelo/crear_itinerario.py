import os
import csv
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines

# ────────────────────────────────────────────────────────────────────────────────
#  Parámetros de configuración
# ────────────────────────────────────────────────────────────────────────────────
semana = 's1'
dia    = 3
dias_semana = {
    1: 'LUNES', 2: 'MARTES', 3: 'MIERCOLES',
    4: 'JUEVES', 5: 'VIERNES', 6: 'SABADO', 7: 'DOMINGO'
}
tipo_modelo = 4
modelos = {
    1: 'CASO BASE SOLO',
    2: 'MODELO',
    3: 'MODELO + CASO BASE',
    4: 'MODELO + CASO BASE + SIMETRIA'
}

# ────────────────────────────────────────────────────────────────────────────────
#  1) Carga de datos de instancia
# ────────────────────────────────────────────────────────────────────────────────
inst_dir = 'Capstone_Instancia'
pacientes_df  = pd.read_excel(
    os.path.join(inst_dir, 'pacientes_small.xlsx'),
    sheet_name=semana
)
enfermeros_df = pd.read_excel(
    os.path.join(inst_dir, 'enfermeros_small.xlsx'),
    sheet_name=dias_semana[dia]
)
hospital_df = pd.read_excel(
    os.path.join(inst_dir, 'datos_espaciales_temporales.xlsx'),
    sheet_name='hospital'
)
UE_df = pd.read_excel(
    os.path.join(inst_dir, 'datos_espaciales_temporales.xlsx'),
    sheet_name='ue'
)
UM_df = pd.read_excel(
    os.path.join(inst_dir, 'datos_espaciales_temporales.xlsx'),
    sheet_name='um'
)

# matriz de arcos para tiempos de viaje
matriz_df = pd.read_excel(
    os.path.join(inst_dir, 'arcos', 'arcos', semana, 'arcos_resumen.xlsx')
)

# ────────────────────────────────────────────────────────────────────────────────
#  2) Construcción del diccionario de viajes
# ────────────────────────────────────────────────────────────────────────────────
viajes = {}
for _, row in matriz_df.iterrows():
    o = int(row['id_origen'])
    d = int(row['id_destino'])
    t = float(row['tiempo_min'])
    viajes[(o, d)] = t

def obtener_tiempo_viaje(node_i, node_j):
    return viajes.get((node_i, node_j), 0.0)

# ────────────────────────────────────────────────────────────────────────────────
#  3) Preprocesamiento de pacientes y enfermeros
# ────────────────────────────────────────────────────────────────────────────────
def to_decimal(t):
    s = t.strftime("%H:%M:%S") if hasattr(t, "strftime") else str(t)
    hh, mm, *_ = s.split(":")
    return int(hh) + int(mm)/60

# Pacientes
pacientes_df["INICIO_DEC"] = pacientes_df["INICIO VENTANA"].apply(to_decimal)
pacientes_df["FIN_DEC"]    = pacientes_df["FIN VENTANA"].apply(to_decimal)
P = {}
for _, r in pacientes_df.iterrows():
    if r[dias_semana[dia]] == 'Si':
        P[r.ID] = {
            'inicio'     : r.INICIO_DEC,
            'fin'        : r.FIN_DEC,
            'duracion'   : r.DURACIÓN,
            'examen'     : r.EXAMEN,
            'medicamento': r.MEDICAMENTO
        }
P_ids = [pid + 1000 for pid in P.keys()]

# Enfermeros
K = {}
for _, r in enfermeros_df.iterrows():
    K[r.ID] = {
        'regimen'  : r.REGIMEN,
        'inicio_v' : to_decimal(r['HORARIO ENTRADA 1']),
        'fin_v'    : to_decimal(r['HORARIO SALIDA 1'])
    }
K_ids = [kid + 5000 for kid in K.keys()]

# Nodos hospitalarios
O_ids = [10,20,30]  # hospital de salida
S_ids = [1,2,3]     # hospital de llegada
HOSPITAL_ids = set(O_ids + S_ids)

# UE y UM (sólo para detección de tipo)
UE_ids = [row.ID + 2000 for _, row in UE_df.iterrows()]
UM_ids = [row.ID - 24 + 3000 for _, row in UM_df.iterrows()]

# ────────────────────────────────────────────────────────────────────────────────
#  4) Lectura de resultados de variables (CSV)
# ────────────────────────────────────────────────────────────────────────────────
res_dir = os.path.join('Resultados_Finales', dias_semana[dia], modelos[tipo_modelo])
X_df  = pd.read_csv(os.path.join(res_dir, 'X.csv'))
Z_df  = pd.read_csv(os.path.join(res_dir, 'Z.csv'))
I_df  = pd.read_csv(os.path.join(res_dir, 'I.csv'))   # Nodo,Enfermero,InicioAtencion
Y_df  = pd.read_csv(os.path.join(res_dir, 'Y.csv'))
RM_df = pd.read_csv(os.path.join(res_dir, 'RM.csv'))
RE_df = pd.read_csv(os.path.join(res_dir, 'RE.csv'))
W_df  = pd.read_csv(os.path.join(res_dir, 'W.csv'))

# ────────────────────────────────────────────────────────────────────────────────
#  5) Reconstrucción de 'resultados'
# ────────────────────────────────────────────────────────────────────────────────
resultados = []
for k, grp in I_df.groupby('Enfermero'):
    dfk = grp.sort_values('InicioAtencion')
    ruta = []
    for _, row in dfk.iterrows():
        nodo = int(row.Nodo)
        t0   = float(row.InicioAtencion)
        if   nodo in P_ids:   tipo = 'Paciente'
        elif nodo in UE_ids:  tipo = 'UE'
        elif nodo in UM_ids:  tipo = 'UM'
        elif nodo in HOSPITAL_ids: tipo = 'Hospital'
        else:                   tipo = 'Desconocido'
        ruta.append((tipo, nodo, t0))
    resultados.append((k, ruta))




# ────────────────────────────────────────────────────────────────────────────────
#  6) Función de color para pacientes
# ────────────────────────────────────────────────────────────────────────────────
def color_paciente(nodo):
    pid = nodo - 1000
    f   = pacientes_df[pacientes_df.ID == pid]
    e,m = f.EXAMEN.iat[0], f.MEDICAMENTO.iat[0]
    if   e=='Examen Perecible'   and m!='Medicamento Perecible': return '#e899dc'
    elif e=='Examen Perecible'   and m=='Medicamento Perecible': return '#00BBC9'
    elif e=='Examen No Perecible'and m!='Medicamento Perecible': return '#a6d854'
    elif e=='Examen No Perecible'and m=='Medicamento Perecible': return '#fc8d62'
    elif m!='Medicamento Perecible':                           return '#ffd92f'
    else:                                                      return '#8da0cb'

ue_color = '#878787'
um_color = '#CACACA'

# ────────────────────────────────────────────────────────────────────────────────
#  7) Dibujo del itinerario
# ────────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(16,9))

# filtramos solo enfermeros con al menos una atención
enf_con_pac = [(k,r) for k,r in resultados if any(t=='Paciente' for t,_,_ in r)]
enf_con_pac.sort(key=lambda x: x[0])

for idx, (k, ruta) in enumerate(enf_con_pac):
    # 7.1) bloques (Paciente, UE, UM, Hospital)
    for tipo, nodo, t0 in ruta:
        th = t0 / 60.0
        if tipo == 'Paciente':
            dh = pacientes_df.loc[pacientes_df.ID == (nodo-1000), 'DURACIÓN'].iat[0] / 60.0
            c  = color_paciente(nodo)
            ax.barh(idx, dh, left=th, color=c, edgecolor='black')
            ax.text(th+dh/2, idx, f'P{nodo-1000}', ha='center', va='center', fontsize=7)

        elif tipo == 'UE':
            ax.barh(idx, 0.5, left=th, color=ue_color, edgecolor='black')
            ax.text(th+0.25, idx, str(nodo-2000), ha='center', va='center', fontsize=7, fontweight='bold')

        elif tipo == 'UM':
            ax.barh(idx, 0.5, left=th, color=um_color, edgecolor='black')
            ax.text(th+0.25, idx, str(nodo-3000), ha='center', va='center', fontsize=7, fontweight='bold')

        else:
            ax.plot([th,th], [idx-0.4,idx+0.4], color='black', linewidth=1, zorder=2)

    # 7.2) líneas de traslado (continua) y espera intermedia (punteada)
    for j in range(len(ruta)-1):
        tipo_i, i_n, t_i = ruta[j]
        _,      j_n, t_j = ruta[j+1]

        # tiempo de servicio en nodo i
        if tipo_i == 'Paciente':
            serv = pacientes_df.loc[pacientes_df.ID == (i_n-1000), 'DURACIÓN'].iat[0]
        elif tipo_i in ['UE','UM']:
            serv = 30
        else:
            serv = 0

        # tiempo de viaje desde i_n hasta j_n (minutos)
        tv_min = obtener_tiempo_viaje(i_n, j_n)
        tv_h   = tv_min / 60.0

        # instante de salida y llegada (horas)
        salida  = (t_i + serv) / 60.0
        llegada = salida + tv_h

        # traslado
        ax.hlines(idx, xmin=salida, xmax=llegada,
                  colors='black', linewidth=1, zorder=1)

        # espera antes de la siguiente atención
        inicio_prox = t_j / 60.0
        if inicio_prox > llegada:
            ax.hlines(idx, xmin=llegada, xmax=inicio_prox,
                      colors='black', linestyles='dotted',
                      linewidth=1, zorder=0)

    # 7.3) espera final hasta fin de turno
    t_lleg = ruta[-1][2] / 60.0
    t_fin  = K[k-5000]['fin_v']
    if t_fin > t_lleg:
        ax.hlines(idx, xmin=t_lleg, xmax=t_fin,
                  colors='black', linestyles='dotted',
                  linewidth=1, zorder=0)

# ────────────────────────────────────────────────────────────────────────────────
#  8) Formato final y leyenda
# ────────────────────────────────────────────────────────────────────────────────
ax.set_xlim(8, 23)
ax.set_xticks(range(8, 24))
ax.set_xlabel("Horas del día")

ax.set_yticks(range(len(enf_con_pac)))
ax.set_yticklabels([f'ENF. {k-5000}' for k,_ in enf_con_pac])
ax.invert_yaxis()
ax.grid(axis='x', linestyle='--', alpha=0.5)

ax.set_title(f"Itinerario enfermeros día {dias_semana[dia]} {semana}")

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
ax.legend(handles=legend_elems,
          loc='upper right',
          bbox_to_anchor=(1.02, 1.01))

plt.tight_layout()
plt.show()
