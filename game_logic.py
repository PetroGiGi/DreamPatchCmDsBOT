# game_logic.py

import random
import sqlite3
import datetime
import database
import market_logic
from market_logic import es_mercado_abierto

# Días en los que se abre el mercado de pases (puedes ajustar estos valores)
MERCADO_PASE_FECHAS = {
    60: "invierno",  # Aproximadamente a mitad de temporada
    365: "verano"     # Al final de la temporada (día 365, antes de reiniciar a día 1)
}
DURACION_MERCADO_DIAS = 40 # Duración del mercado en días

def simular_temporada_liga_ia(liga_id, temporada):
    """
    Simula una temporada completa para una liga de IA (todos los partidos de todas las jornadas).
    Retorna True si la simulación fue exitosa, False en caso contrario.
    """
    mensajes_simulacion = [] # Para posibles logs internos o debug
    
    equipos_en_liga = database.get_equipos_by_liga(liga_id)
    if not equipos_en_liga:
        # print(f"DEBUG IA: No hay equipos en la liga {liga_id} para simular temporada {temporada}.")
        return False

    # Asegurarse de que la clasificación para la nueva temporada esté reseteada a cero
    database.reset_clasificacion_liga(liga_id, temporada)
    
    # Obtener todas las jornadas programadas para esta liga y temporada
    jornadas_programadas = database.get_jornadas_por_liga_y_temporada(liga_id, temporada)
    
    if not jornadas_programadas:
        # print(f"DEBUG IA: No hay jornadas programadas para la liga {liga_id}, temporada {temporada}. Generando fixture...")
        # Si no hay fixture generado, lo generamos (esto debería haberse hecho al iniciar la liga)
        # Nota: generate_fixture necesita un user_id para obtener la temporada, pero aquí es IA.
        # Podríamos pasar un user_id dummy o modificar generate_fixture para no depender de ello.
        # Por simplicidad, asumiremos que generate_fixture ya crea el fixture para todas las ligas
        # al inicio de cada nueva carrera, o si no, se deberá llamar antes de esta simulación.
        # Asumiendo que generate_fixture ya se ejecutó para todas las ligas al crear la carrera inicial.
        # Si no, esto es un punto de posible error.
        
        # Una solución robusta aquí sería llamar a generate_fixture si no hay jornadas.
        # generate_fixture(carrera_del_usuario_id, liga_id) # Esto complica si no tenemos el user_id aquí.
        # Por ahora, asumimos que las jornadas existen.
        pass # Por ahora, no hacer nada si no hay jornadas (se salta la simulación)


    # Simular cada jornada
    for jornada in jornadas_programadas:
        partidos_jornada = database.get_partidos_por_jornada(jornada['id'])
        for partido in partidos_jornada:
            if partido['simulado'] == 0: # Solo simular si no ha sido simulado
                resultado, error = simular_partido(partido['equipo_local_id'], partido['equipo_visitante_id'])
                if error:
                    # print(f"DEBUG IA: Error simulando partido IA {partido['equipo_local_nombre']} vs {partido['equipo_visitante_nombre']}: {error}")
                    continue
                database.update_partido_resultado(partido['id'], resultado['goles_e1'], resultado['goles_e2'])
                update_clasificacion(liga_id, temporada, resultado, zona_nombre=partido.get('zona'))
    
    # print(f"DEBUG IA: Temporada {temporada} simulada para liga {database.get_liga_by_id(liga_id)['nombre']}.")
    return True

def simular_partido(equipo1_id, equipo2_id):
    """
    Simula un partido entre dos equipos y devuelve el resultado.
    Puedes refinar la lógica aquí (factores como OVR, localía, etc.).
    """
    equipo1 = database.get_equipo_by_id(equipo1_id) # Usar get_equipo_by_id
    equipo2 = database.get_equipo_by_id(equipo2_id) # Usar get_equipo_by_id

    if not equipo1 or not equipo2:
        return None, "Error: Uno o ambos equipos no existen."

    ovr1 = equipo1['nivel_general']
    ovr2 = equipo2['nivel_general']

    diferencia_ovr = ovr1 - ovr2
    prob_victoria_1_base = 0.5
    prob_victoria_1_ajustada = prob_victoria_1_base + (diferencia_ovr / 100 * 0.2)
    prob_victoria_1_ajustada = max(0.1, min(0.9, prob_victoria_1_ajustada))

    rand_val = random.random()

    goles_e1 = 0
    goles_e2 = 0

    if rand_val < prob_victoria_1_ajustada:
        goles_e1 = random.randint(1, 4)
        goles_e2 = random.randint(0, max(0, goles_e1 - 1))
    elif rand_val > (1 - prob_victoria_1_ajustada):
        goles_e2 = random.randint(1, 4)
        goles_e1 = random.randint(0, max(0, goles_e2 - 1))
    else:
        goles_e1 = random.randint(0, 3)
        goles_e2 = goles_e1

    return {'equipo1_id': equipo1_id, 'goles_e1': goles_e1,
            'equipo2_id': equipo2_id, 'goles_e2': goles_e2}, None

def simular_partido_eliminatorio(equipo1_id, equipo2_id):
    """
    Simula un partido eliminatorio que debe tener un ganador (sin empates).
    En caso de empate en goles, se decide por OVR o penales simulados.
    """
    equipo1 = database.get_equipo_by_id(equipo1_id)
    equipo2 = database.get_equipo_by_id(equipo2_id)

    if not equipo1 or not equipo2:
        return None, "Error: Uno o ambos equipos no existen para la simulación eliminatoria."

    resultado_partido, error = simular_partido(equipo1_id, equipo2_id)
    if error:
        return None, error

    goles_e1 = resultado_partido['goles_e1']
    goles_e2 = resultado_partido['goles_e2']

    # Si hay empate, aplicar lógica de desempate
    if goles_e1 == goles_e2:
        ovr1 = equipo1['nivel_general']
        ovr2 = equipo2['nivel_general']

        if ovr1 > ovr2:
            goles_e1 += 1 # Gana el de mayor OVR
        elif ovr2 > ovr1:
            goles_e2 += 1 # Gana el de mayor OVR
        else:
            # Si OVR también es igual, simular penales (simplificado)
            if random.random() < 0.5:
                goles_e1 += 1
            else:
                goles_e2 += 1
        
        # Opcional: ajustar el resultado para que no parezca un 1-0 o 0-1 "extra" si fue 0-0
        # Esto es solo cosmético para el mensaje final
        if goles_e1 == 0 and goles_e2 == 0: # Si la simulación base dio 0-0
            if random.random() < 0.5:
                goles_e1 = 1
            else:
                goles_e2 = 1
        elif goles_e1 == goles_e2: # Si la simulación base dio X-X y se desempata
            if random.random() < 0.5:
                goles_e1 += 1
            else:
                goles_e2 += 1


    return {'equipo1_id': equipo1_id, 'goles_e1': goles_e1,
            'equipo2_id': equipo2_id, 'goles_e2': goles_e2}, None


def update_clasificacion(liga_id, temporada, resultado, zona_nombre=None): # ¡Añadido zona_nombre=None aquí!
    """
    Actualiza las estadísticas de la tabla de posiciones de la liga, opcionalmente por zona.
    Se espera que 'resultado' sea un diccionario como {'equipo1_id': id, 'goles_e1': g, 'equipo2_id': id, 'goles_e2': g}
    """
    equipo_local_id = resultado['equipo1_id']
    equipo_visitante_id = resultado['equipo2_id']
    goles_local = resultado['goles_e1']
    goles_visitante = resultado['goles_e2']

    stats_local = database.get_equipo_clasificacion_stats(liga_id, equipo_local_id, temporada)
    stats_visitante = database.get_equipo_clasificacion_stats(liga_id, equipo_visitante_id, temporada)

    if not stats_local: stats_local = {'pj':0,'pg':0,'pe':0,'pp':0,'gf':0,'gc':0,'dg':0,'pts':0}
    else: stats_local = dict(stats_local)
    if not stats_visitante: stats_visitante = {'pj':0,'pg':0,'pe':0,'pp':0,'gf':0,'gc':0,'dg':0,'pts':0}
    else: stats_visitante = dict(stats_visitante)

    stats_local['pj'] += 1
    stats_local['gf'] += goles_local
    stats_local['gc'] += goles_visitante
    stats_local['dg'] = stats_local['gf'] - stats_local['gc']

    stats_visitante['pj'] += 1
    stats_visitante['gf'] += goles_visitante
    stats_visitante['gc'] += goles_local
    stats_visitante['dg'] = stats_visitante['gf'] - stats_visitante['gc']

    if goles_local > goles_visitante:
        stats_local['pg'] += 1
        stats_local['pts'] += 3
        stats_visitante['pp'] += 1
    elif goles_local < goles_visitante:
        stats_visitante['pg'] += 1
        stats_visitante['pts'] += 3
        stats_local['pp'] += 1
    else:
        stats_local['pe'] += 1
        stats_local['pts'] += 1
        stats_visitante['pe'] += 1
        stats_visitante['pts'] += 1

    database.update_clasificacion(
        liga_id, equipo_local_id, temporada,
        stats_local['pj'], stats_local['pg'], stats_local['pe'], stats_local['pp'],
        stats_local['gf'], stats_local['gc'], stats_local['dg'], stats_local['pts'],
        zona_nombre # ¡Pasando zona_nombre a database.update_clasificacion!
    )
    database.update_clasificacion(
        liga_id, equipo_visitante_id, temporada,
        stats_visitante['pj'], stats_visitante['pg'], stats_visitante['pe'], stats_visitante['pp'],
        stats_visitante['gf'], stats_visitante['gc'], stats_visitante['dg'], stats_visitante['pts'],
        zona_nombre # ¡Pasando zona_nombre a database.update_clasificacion!
    )

def avanzar_dia(user_id):
    """
    Avanza un día en la carrera del usuario, simulando eventos como partidos y mercado de pases.
    Retorna una lista de mensajes a enviar al usuario.
    """
    mensajes = []
    carrera = database.get_carrera_by_user(user_id)
    if not carrera:
        mensajes.append("Error: No se encontró tu carrera. Inicia una con `!iniciar_carrera`.")
        return mensajes

    dia_actual = carrera['dia_actual']
    temporada = carrera['temporada']
    liga_id = carrera['liga_id']
    tu_equipo_id = carrera['equipo_id']

    liga_details = database.get_liga_by_id(liga_id)
    es_primera_nacional = (liga_details['nombre'] == "Primera Nacional")
    
    # --- Cálculo de la fecha actual simulada ---
    fecha_base_simulacion_global = datetime.date(2025, 3, 1)
    dias_totales_simulados_actual = (dia_actual - 1) + (temporada - 1) * 365
    fecha_actual_simulada_calendario = fecha_base_simulacion_global + datetime.timedelta(days=dias_totales_simulados_actual)
    fecha_str_actual_calendario = fecha_actual_simulada_calendario.strftime('%Y-%m-%d')

    print(f"DEBUG GAME_LOGIC: Entrando avanzar_dia. Dia actual (leído de DB): {dia_actual}, Temporada: {temporada}, Fecha calculada: {fecha_str_actual_calendario}")
    mensajes.append(f"**Día {dia_actual} de la Temporada {temporada} ({fecha_str_actual_calendario})**")    

    # ELIMINA o COMENTA estas líneas, ya que el partido del usuario se simula en main.py
    # partido_pendiente_hoy = database.get_partido_pendiente(user_id, tu_equipo_id, fecha_str_actual_calendario)
    # if partido_pendiente_hoy:
    #     mensajes.append(f"🚨 ¡ATENCIÓN {username.upper()}! ¡HOY JUEGA TU EQUIPO! 🚨") # Este mensaje y la confirmación se moverán a main.py
    #     # La lógica de simular el partido del usuario se moverá a main.py antes de llamar a avanzar_dia
    #     pass # No hacemos nada aquí con el partido del usuario, main.py se encargará.


    # 1. Simular partidos de la IA en la liga del usuario para el día actual
    # Esta consulta get_partidos_por_dia YA EXCLUYE el partido del equipo del usuario.
    partidos_ia_hoy = database.get_partidos_por_dia(user_id, fecha_str_actual_calendario)
    
    if partidos_ia_hoy:
        mensajes.append("\n**Resultados de la Liga (Simulados por IA):**")
        for partido in partidos_ia_hoy:
            if partido['simulado'] == 0: # Solo simular si no ha sido jugado
                resultado, error = simular_partido(partido['equipo_local_id'], partido['equipo_visitante_id'])
                if error:
                    mensajes.append(f"Error simulando partido IA {partido['equipo_local_nombre']} vs {partido['equipo_visitante_nombre']}: {error}")
                    continue
                database.update_partido_resultado(partido['id'], resultado['goles_e1'], resultado['goles_e2'])
                update_clasificacion(liga_id, temporada, resultado, zona_nombre=partido.get('zona'))
                mensajes.append(f"- {partido['equipo_local_nombre']} {resultado['goles_e1']} - {resultado['goles_e2']} {partido['equipo_visitante_nombre']}")
    
    # 2. Lógica del mercado de pases
    dias_mercado_restantes = database.get_dias_mercado_abierto(user_id) #

    if dias_mercado_restantes > 0:
        dias_mercado_restantes -= 1
        print(f"DEBUG: avanzar_dia para user_id {user_id}: Dias mercado a actualizar: {dias_mercado_restantes}") # AÑADE ESTA LÍNEA
        database.update_dias_mercado_abierto(user_id, dias_mercado_restantes)
        mensajes.append(f"Mercado de pases abierto. Días restantes: {dias_mercado_restantes}.") #

        # Generar ofertas de la IA al usuario (con baja probabilidad)
        if random.random() < 0.2: # 20% de probabilidad de recibir una oferta IA
            oferta_generada, msg_oferta = market_logic.generar_oferta_ia_a_usuario(user_id) #
            if oferta_generada:
                mensajes.append(msg_oferta)

        # Simular transferencias IA-IA (dentro de la liga del usuario y otras ligas)
        if random.random() < 0.5: # 10% de probabilidad de transferencias IA-IA
            # Para la liga del usuario
            ia_ia_news_liga_usuario = market_logic.simular_transferencias_ia_entre_ellos(liga_id)
            if ia_ia_news_liga_usuario:
                mensajes.append("\n**Noticias de Transferencias en tu Liga:**")
                mensajes.extend(ia_ia_news_liga_usuario)

            # Para otras ligas (solo si quieres que haya actividad global)
            otras_ligas = [l for l in database.get_all_ligas_info() if l['id'] != liga_id]
            if otras_ligas and random.random() < 0.7: # Probabilidad menor para otras ligas
                random.shuffle(otras_ligas)
                for otra_liga in otras_ligas[:min(len(otras_ligas), 2)]: # Simular solo en 1 o 2 ligas IA
                    ia_ia_news_otras_ligas = market_logic.simular_transferencias_ia_entre_ellos(otra_liga['id'])
                    if ia_ia_news_otras_ligas:
                        mensajes.append(f"\n**Noticias de Transferencias en {otra_liga['nombre']}:**")
                        mensajes.extend(ia_ia_news_otras_ligas)
                    return


    # --- Detección y manejo de la finalización de la fase regular de Primera Nacional ---
    # Detección: game_logic.avanzar_dia debe identificar que la fase regular ha terminado (ej. tras simular la Jornada 34).
    # Solo aplica si es Primera Nacional y se ha superado la jornada 34
    if es_primera_nacional and dia_actual == 200: # Asumiendo que el día 365 es el final de la fase regular
        mensajes.append("\n⚽ ¡La fase regular de la Primera Nacional ha terminado! ⚽")
        mensajes.append("Calculando la tabla final y preparando la Final por el Primer Ascenso y el Reducido...")

        # 1. Lógica de Clasificación Final por Zona (ya se actualiza con cada partido)
        # Ahora, obtener los clasificados
        clasificacion_zona_a = database.get_clasificacion_liga(liga_id, temporada, zona_nombre="Zona A")
        clasificacion_zona_b = database.get_clasificacion_liga(liga_id, temporada, zona_nombre="Zona B")

        # Identificación precisa del 1° de cada zona, y de los equipos del 2° al 8° de cada zona
        primeros_zona_a = clasificacion_zona_a[0] if clasificacion_zona_a else None
        primeros_zona_b = clasificacion_zona_b[0] if clasificacion_zona_b else None

        if primeros_zona_a and primeros_zona_b:
            mensajes.append(f"\n🏆 **¡FINAL POR EL PRIMER ASCENSO!** 🏆")
            mensajes.append(f"Se enfrentan los campeones de cada zona:")
            mensajes.append(f"- **{primeros_zona_a['equipo_nombre']}** (1° de la Zona A) vs **{primeros_zona_b['equipo_nombre']}** (1° de la Zona B)")

            # Simulación del Partido: Crear una nueva función de simulación de partido eliminatorio
            # Usamos la nueva función simular_partido_eliminatorio
            resultado_final_ascenso, error_sim = simular_partido_eliminatorio(
                primeros_zona_a['equipo_id'],
                primeros_zona_b['equipo_id']
            )

            if not error_sim:
                ganador_final_ascenso_id = None
                perdedor_final_ascenso_id = None
                if resultado_final_ascenso['goles_e1'] > resultado_final_ascenso['goles_e2']:
                    ganador_final_ascenso_id = resultado_final_ascenso['equipo1_id']
                    perdedor_final_ascenso_id = resultado_final_ascenso['equipo2_id']
                else:
                    ganador_final_ascenso_id = resultado_final_ascenso['equipo2_id']
                    perdedor_final_ascenso_id = resultado_final_ascenso['equipo1_id']
                
                ganador_final_ascenso_nombre = database.get_equipo_by_id(ganador_final_ascenso_id)['nombre']
                perdedor_final_ascenso_nombre = database.get_equipo_by_id(perdedor_final_ascenso_id)['nombre']

                mensajes.append(f"\n¡Resultado de la Final por el Primer Ascenso!")
                mensajes.append(f"**{database.get_equipo_by_id(resultado_final_ascenso['equipo1_id'])['nombre']} {resultado_final_ascenso['goles_e1']} - {resultado_final_ascenso['goles_e2']} {database.get_equipo_by_id(resultado_final_ascenso['equipo2_id'])['nombre']}**")
                mensajes.append(f"¡FELICITACIONES! **{ganador_final_ascenso_nombre}** ha logrado el **PRIMER ASCENSO** a Primera División. 🥳")
                
                # Registrar al equipo ascendido en una nueva tabla ascensos_descensos o en palmares con un tipo_titulo adecuado.
                database.add_ascenso_descenso(ganador_final_ascenso_id, liga_id, 'Primera División', temporada, 'ascenso_directo')
                database.add_campeon(liga_id, temporada, ganador_final_ascenso_id, tipo_titulo="Campeón Primera Nacional - Ascenso Directo") # Marcar como campeón de la categoría también

               # Lógica del Reducido
                mensajes.append("\n--- ¡COMIENZA EL REDUCIDO POR EL SEGUNDO ASCENSO! ---")
                
                # Obtener equipos del 2° al 8° de cada zona
                clasificacion_zona_a = database.get_clasificacion_liga(liga_id, temporada, zona_nombre="Zona A")
                clasificacion_zona_b = database.get_clasificacion_liga(liga_id, temporada, zona_nombre="Zona B")
                
                # Filtra para obtener solo del 2do al 8vo puesto (índices 1 a 7)
                equipos_reducido_zona_a = [e for e in clasificacion_zona_a[1:8]] 
                equipos_reducido_zona_b = [e for e in clasificacion_zona_b[1:8]]
                
                print(f"DEBUG REDUCIDO: Equipos para reducido Zona A (2do-8vo): {len(equipos_reducido_zona_a)} equipos. Nombres: {[e['equipo_nombre'] for e in equipos_reducido_zona_a]}")
                print(f"DEBUG REDUCIDO: Equipos para reducido Zona B (2do-8vo): {len(equipos_reducido_zona_b)} equipos. Nombres: {[e['equipo_nombre'] for e in equipos_reducido_zona_b]}")

                # Asegurarse de que el perdedor de la final por el primer ascenso se incluya
                perdedor_final_ascenso_details_full = None
                if perdedor_final_ascenso_id:
                    perdedor_final_ascenso_details_full = database.get_equipo_clasificacion_stats(liga_id, perdedor_final_ascenso_id, temporada)
                    if perdedor_final_ascenso_details_full:
                        perdedor_final_ascenso_details_full['equipo_nombre'] = database.get_equipo_by_id(perdedor_final_ascenso_id)['nombre']
                        print(f"DEBUG REDUCIDO: Perdedor Final Ascenso: {perdedor_final_ascenso_details_full['equipo_nombre']}")
                else:
                    print("DEBUG REDUCIDO: No se encontró perdedor de la final por el primer ascenso.")

                # --- NUEVA PRIMERA RONDA DEL REDUCIDO (Octavos de Final) ---
                # Esta ronda es entre los 14 equipos (2do al 8vo de cada zona).
                # Se forman 7 partidos.

                ganadores_primera_ronda = [] # Para almacenar los 7 ganadores

                if len(equipos_reducido_zona_a) >= 7 and len(equipos_reducido_zona_b) >= 7:
                    mensajes.append("\n--- Primera Ronda del Reducido (Octavos de Final) ---")
                    
                    # Cruces específicos (A2 vs B8, B2 vs A8, etc.)
                    partidos_primera_ronda_reducido = [
                        {'e1': equipos_reducido_zona_a[0]['equipo_id'], 'e2': equipos_reducido_zona_b[6]['equipo_id']}, # A2 vs B8
                        {'e1': equipos_reducido_zona_b[0]['equipo_id'], 'e2': equipos_reducido_zona_a[6]['equipo_id']}, # B2 vs A8
                        {'e1': equipos_reducido_zona_a[1]['equipo_id'], 'e2': equipos_reducido_zona_b[5]['equipo_id']}, # A3 vs B7
                        {'e1': equipos_reducido_zona_b[1]['equipo_id'], 'e2': equipos_reducido_zona_a[5]['equipo_id']}, # B3 vs A7
                        {'e1': equipos_reducido_zona_a[2]['equipo_id'], 'e2': equipos_reducido_zona_b[4]['equipo_id']}, # A4 vs B6
                        {'e1': equipos_reducido_zona_b[2]['equipo_id'], 'e2': equipos_reducido_zona_a[4]['equipo_id']}, # B4 vs A6
                        {'e1': equipos_reducido_zona_a[3]['equipo_id'], 'e2': equipos_reducido_zona_b[3]['equipo_id']}  # A5 vs B5
                    ]
                    
                    for i, partido_info in enumerate(partidos_primera_ronda_reducido):
                        equipo_c1_nombre = database.get_equipo_by_id(partido_info['e1'])['nombre']
                        equipo_c2_nombre = database.get_equipo_by_id(partido_info['e2'])['nombre']
                        mensajes.append(f"Simulando Partido {i+1}: {equipo_c1_nombre} vs {equipo_c2_nombre}")
                        
                        resultado_ronda, error_sim = simular_partido_eliminatorio(partido_info['e1'], partido_info['e2'])
                        if not error_sim:
                            ganador_ronda_id = None
                            if resultado_ronda['goles_e1'] > resultado_ronda['goles_e2']:
                                ganador_ronda_id = resultado_ronda['equipo1_id']
                            else:
                                ganador_ronda_id = resultado_ronda['equipo2_id']
                            
                            ganador_stats = database.get_equipo_clasificacion_stats(liga_id, ganador_ronda_id, temporada)
                            if ganador_stats:
                                ganador_stats['equipo_nombre'] = database.get_equipo_by_id(ganador_ronda_id)['nombre']
                                ganadores_primera_ronda.append(ganador_stats)
                            
                            mensajes.append(f"  Resultado: {equipo_c1_nombre} {resultado_ronda['goles_e1']} - {resultado_ronda['goles_e2']} {equipo_c2_nombre}")
                            mensajes.append(f"  **{database.get_equipo_by_id(ganador_ronda_id)['nombre']}** avanza a Cuartos de Final.")
                    
                    print(f"DEBUG REDUCIDO: Ganadores Primera Ronda: {len(ganadores_primera_ronda)} equipos. Nombres: {[e['equipo_nombre'] for e in ganadores_primera_ronda]}")

                else:
                    mensajes.append(f"Advertencia: No hay suficientes equipos para formar la Primera Ronda del Reducido. (Se necesitan 7 equipos del 2° al 8° por zona). Encontrados A:{len(equipos_reducido_zona_a)}, B:{len(equipos_reducido_zona_b)}.")
                    ganadores_primera_ronda = [] # Asegurar que esté vacía si no se pudieron formar los cruces
                
                # --- Cruce de Cuartos de Final (8 equipos) ---
                # Los 7 ganadores de la primera ronda + el perdedor de la final directa.
                cuartos_participantes = list(ganadores_primera_ronda) 
                if perdedor_final_ascenso_details_full: 
                    cuartos_participantes.append(perdedor_final_ascenso_details_full) 

                print(f"DEBUG REDUCIDO: Participantes Cuartos de Final (después de añadir perdedor): {len(cuartos_participantes)} equipos. Nombres: {[e['equipo_nombre'] for e in cuartos_participantes]}")

                # Ordenar por Puntos, DG, GF para determinar "mejor" y "peor" clasificado
                cuartos_participantes_ordenados = sorted(
                    cuartos_participantes,
                    key=lambda x: (x['pts'], x['dg'], x['gf']),
                    reverse=True
                )
                
                # Asegurarse de tener 8 equipos para los cuartos
                ganadores_cuartos_reducido = [] # Para almacenar los 4 ganadores de Cuartos
                if len(cuartos_participantes_ordenados) == 8:
                    mensajes.append("\n--- Cuartos de Final del Reducido ---")
                    partidos_cuartos_reducido_fase = [] # Renombrado para evitar conflicto con la variable de la ronda anterior
                    
                    # Generar los 4 cruces de cuartos de final (1° vs 8°, 2° vs 7°, etc.)
                    for i in range(4): # 4 partidos para 8 equipos
                        e1 = cuartos_participantes_ordenados[i]
                        e2 = cuartos_participantes_ordenados[len(cuartos_participantes_ordenados) - 1 - i]
                        partidos_cuartos_reducido_fase.append({'e1': e1['equipo_id'], 'e2': e2['equipo_id']})
                    
                    for i, partido_info in enumerate(partidos_cuartos_reducido_fase):
                        equipo_c1_nombre = database.get_equipo_by_id(partido_info['e1'])['nombre']
                        equipo_c2_nombre = database.get_equipo_by_id(partido_info['e2'])['nombre']
                        mensajes.append(f"Simulando Partido {i+1}: {equipo_c1_nombre} vs {equipo_c2_nombre}")

                        resultado_cuartos_fase, error_sim = simular_partido_eliminatorio(partido_info['e1'], partido_info['e2'])
                        if not error_sim:
                            ganador_cuartos_fase_id = None
                            if resultado_cuartos_fase['goles_e1'] > resultado_cuartos_fase['goles_e2']:
                                ganador_cuartos_fase_id = resultado_cuartos_fase['equipo1_id']
                            else:
                                ganador_cuartos_fase_id = resultado_cuartos_fase['equipo2_id']
                            
                            ganador_stats_cuartos = database.get_equipo_clasificacion_stats(liga_id, ganador_cuartos_fase_id, temporada)
                            if ganador_stats_cuartos:
                                ganador_stats_cuartos['equipo_nombre'] = database.get_equipo_by_id(ganador_cuartos_fase_id)['nombre']
                                ganadores_cuartos_reducido.append(ganador_stats_cuartos) # Añadir a los ganadores de CUARTOS
                            
                            mensajes.append(f"  Resultado: {equipo_c1_nombre} {resultado_cuartos_fase['goles_e1']} - {resultado_cuartos_fase['goles_e2']} {equipo_c2_nombre}")
                            mensajes.append(f"  **{database.get_equipo_by_id(ganador_cuartos_fase_id)['nombre']}** avanza a Semifinales.")
                    
                    print(f"DEBUG REDUCIDO: Ganadores Cuartos de Final (del reducido): {len(ganadores_cuartos_reducido)} equipos. Nombres: {[e['equipo_nombre'] for e in ganadores_cuartos_reducido]}")

                else:
                    mensajes.append(f"Advertencia: El número de equipos para Cuartos de Final del Reducido no es 8 exactos ({len(cuartos_participantes_ordenados)} encontrados). No se jugarán los cuartos de final.")
                    ganadores_cuartos_reducido = [] # Asegurar que esté vacía si no se pudieron formar los cruces

                # --- Cruce de Semifinales del Reducido (4 equipos) ---
                # Los 4 ganadores de Cuartos de Final.
                semis_participantes_reducido_fase = list(ganadores_cuartos_reducido) # Renombrado
                
                print(f"DEBUG REDUCIDO: Participantes Semifinales del Reducido: {len(semis_participantes_reducido_fase)} equipos. Nombres: {[e['equipo_nombre'] for e in semis_participantes_reducido_fase]}")

                # Ordenar por Puntos, DG, GF (para semifinales)
                semis_participantes_reducido_fase_ordenados = sorted(
                    semis_participantes_reducido_fase,
                    key=lambda x: (x['pts'], x['dg'], x['gf']),
                    reverse=True
                )
                
                ganadores_semis_reducido = [] # Para almacenar los 2 ganadores de Semis
                if len(semis_participantes_reducido_fase_ordenados) == 4: # ¡Ahora se esperan 4 equipos!
                    mensajes.append("\n--- Semifinales del Reducido ---")
                    partidos_semis_reducido_fase = []
                    
                    for i in range(2): # 2 partidos para 4 equipos
                        e1 = semis_participantes_reducido_fase_ordenados[i]
                        e2 = semis_participantes_reducido_fase_ordenados[len(semis_participantes_reducido_fase_ordenados) - 1 - i]
                        partidos_semis_reducido_fase.append({'e1': e1['equipo_id'], 'e2': e2['equipo_id']})
                    
                    for i, partido_info in enumerate(partidos_semis_reducido_fase):
                        equipo_s1_nombre = database.get_equipo_by_id(partido_info['e1'])['nombre']
                        equipo_s2_nombre = database.get_equipo_by_id(partido_info['e2'])['nombre']
                        mensajes.append(f"Simulando Semifinal {i+1}: {equipo_s1_nombre} vs {equipo_s2_nombre}")

                        resultado_semis_fase, error_sim = simular_partido_eliminatorio(partido_info['e1'], partido_info['e2'])
                        if not error_sim:
                            ganador_semis_fase_id = None
                            if resultado_semis_fase['goles_e1'] > resultado_semis_fase['goles_e2']:
                                ganador_semis_fase_id = resultado_semis_fase['equipo1_id']
                            else:
                                ganador_semis_fase_id = resultado_semis_fase['equipo2_id']
                            
                            ganadores_semis_reducido.append(database.get_equipo_by_id(ganador_semis_fase_id))
                            
                            mensajes.append(f"  Resultado: {equipo_s1_nombre} {resultado_semis_fase['goles_e1']} - {resultado_semis_fase['goles_e2']} {equipo_s2_nombre}")
                            mensajes.append(f"  **{database.get_equipo_by_id(ganador_semis_fase_id)['nombre']}** avanza a la Final del Reducido.")
                    
                    print(f"DEBUG REDUCIDO: Ganadores Semifinales (del reducido): {len(ganadores_semis_reducido)} equipos. Nombres: {[e['nombre'] for e in ganadores_semis_reducido]}")

                else:
                    mensajes.append(f"Advertencia: El número de equipos para Semifinales del Reducido no es 4 exactos ({len(semis_participantes_reducido_fase_ordenados)} encontrados). No se jugarán las semifinales.")
                    ganadores_semis_reducido = []

                # --- Cruce de Final del Reducido (2 equipos) ---
                # Los 2 ganadores de Semifinales.
                if len(ganadores_semis_reducido) == 2: # ¡Ahora esta condición debería ser True!
                    finalista_1 = ganadores_semis_reducido[0]
                    finalista_2 = ganadores_semis_reducido[1]

                    mensajes.append("\n--- ¡GRAN FINAL DEL REDUCIDO! ---")
                    mensajes.append(f"Se enfrentan: **{finalista_1['nombre']}** vs **{finalista_2['nombre']}**")

                    resultado_final_reducido, error_sim = simular_partido_eliminatorio(finalista_1['id'], finalista_2['id'])
                    
                    if not error_sim:
                        ganador_reducido_id = None
                        if resultado_final_reducido['goles_e1'] > resultado_final_reducido['goles_e2']:
                            ganador_reducido_id = resultado_final_reducido['equipo1_id']
                        else:
                            ganador_reducido_id = resultado_final_reducido['equipo2_id']
                        
                        ganador_reducido_nombre = database.get_equipo_by_id(ganador_reducido_id)['nombre']

                        mensajes.append(f"\n¡Resultado de la Final del Reducido!")
                        mensajes.append(f"**{database.get_equipo_by_id(resultado_final_reducido['equipo1_id'])['nombre']} {resultado_final_reducido['goles_e1']} - {resultado_final_reducido['goles_e2']} {database.get_equipo_by_id(resultado_final_reducido['equipo2_id'])['nombre']}**")
                        mensajes.append(f"¡INCREÍBLE! **{ganador_reducido_nombre}** ha ganado el Reducido y logra el **SEGUNDO ASCENSO** a Primera División. 🥳")

                        database.add_ascenso_descenso(ganador_reducido_id, liga_id, 'Primera División', temporada, 'ascenso_reducido')
                        database.add_campeon(liga_id, temporada, ganador_reducido_id, tipo_titulo="Ganador Reducido - Ascenso")
                else:
                    mensajes.append(f"Error: No hay suficientes finalistas para jugar la Final del Reducido. Se esperaban 2 ganadores de semifinales, pero se encontraron {len(ganadores_semis_reducido)}.")

    # 3. Avanzar el día y verificar el fin de temporada
    siguiente_dia = dia_actual + 1
    nueva_temporada_iniciada = False

    if siguiente_dia > 365: # Un año/temporada tiene 365 días (puedes ajustar esto)
        temporada_finalizada = temporada
        siguiente_dia = 1
        temporada += 1
        database.update_carrera_temporada(user_id, temporada)
        mensajes.append(f"\n--- ¡FIN DE LA TEMPORADA {temporada_finalizada}! ---")


        # ** 3.1. Resumen de la Liga del Usuario **
        mensajes.append(f"\n**RESUMEN DE LA {database.get_liga_by_id(liga_id)['nombre']} - TEMPORADA {temporada_finalizada}:**")

        # Campeón de liga regular (si no es Primera Nacional, o el campeón directo de PN)
        if not es_primera_nacional:
            clasificacion_final_liga_usuario = database.get_clasificacion_liga(liga_id, temporada_finalizada)
            if clasificacion_final_liga_usuario:
                campeon_equipo = clasificacion_final_liga_usuario[0]
                # Solo añadir al palmarés si no fue ya añadido por el ascenso directo de PN
                if not database.get_campeon_temporada(liga_id, temporada_finalizada):
                    database.add_campeon(liga_id, temporada_finalizada, campeon_equipo['equipo_id'], tipo_titulo="Campeón de Liga")
                mensajes.append(f"🎉🏆 ¡El campeón es: **{campeon_equipo['equipo_nombre']}**! 🏆🎉")
            else:
                mensajes.append("No se pudo determinar el campeón de tu liga.")

        # Tabla de posiciones final de tu liga (si no es Primera Nacional, o las tablas zonales)
        if not es_primera_nacional:
            mensajes.append(f"\n**Tabla de Posiciones Final:**")
            def format_clasificacion_para_mensaje(tabla_posiciones, equipo_usuario_id=None):
                if not tabla_posiciones:
                    return "No hay datos de clasificación disponibles."

                response_parts = []
                response_parts.append("```ansi\nPOS EQUIPO            PJ PG PE PP GF GC DG PTS")

                tu_equipo_nombre = None
                if equipo_usuario_id:
                    equipo_del_usuario_details = database.get_equipo_by_id(equipo_usuario_id)
                    if equipo_del_usuario_details:
                        tu_equipo_nombre = equipo_del_usuario_details['nombre']

                for i, equipo_stats in enumerate(tabla_posiciones):
                    pos = str(i + 1).ljust(3)
                    nombre = equipo_stats['equipo_nombre'][:17].ljust(17)

                    pj = str(equipo_stats['pj']).ljust(3)
                    pg = str(equipo_stats['pg']).ljust(3)
                    pe = str(equipo_stats['pe']).ljust(3)
                    pp = str(equipo_stats['pp']).ljust(3)
                    gf = str(equipo_stats['gf']).ljust(3)
                    gc = str(equipo_stats['gc']).ljust(3)
                    dg = str(equipo_stats['dg']).ljust(4)
                    pts = str(equipo_stats['pts']).ljust(3)

                    if tu_equipo_nombre and equipo_stats['equipo_nombre'] == tu_equipo_nombre:
                        line = f" [2;36m{pos} {nombre} {pj}{pg}{pe}{pp}{gf}{gc}{dg}{pts} [0m"
                    else:
                        line = f"{pos} {nombre} {pj}{pg}{pe}{pp}{gf}{gc}{dg}{pts}"

                    response_parts.append(line)

                response_parts.append("```")
                return "\n".join(response_parts)

            tabla_str = format_clasificacion_para_mensaje(clasificacion_final_liga_usuario, tu_equipo_id)
            mensajes.append(tabla_str)
        
        # Top jugadores de tu liga (por OVR, ya que no tenemos otras estadísticas)
        top_jugadores_liga_usuario = database.get_top_jugadores_liga(liga_id, limit=5)
        if top_jugadores_liga_usuario:
            mensajes.append(f"\n**Top 5 Jugadores por OVR en {database.get_liga_by_id(liga_id)['nombre']}:**")
            for i, jugador in enumerate(top_jugadores_liga_usuario):
                mensajes.append(f"{i+1}. {jugador['nombre']} ({jugador['equipo_nombre']}) - OVR: {jugador['valoracion']}")
        else:
            mensajes.append("No se encontraron jugadores para el top de tu liga.")

        # ** 3.2. Resumen de OTRAS LIGAS (IA) **
        todas_las_ligas_db = database.get_all_ligas_info()
        for liga_gen in todas_las_ligas_db:
            if liga_gen['id'] != liga_id: # No simular la liga del usuario aquí
                mensajes.append(f"\n--- RESUMEN DE LA {liga_gen['nombre']} - TEMPORADA {temporada_finalizada}: ---")

                # Simular temporada si no se hizo previamente (ya se hace arriba, esto es un catch-all)
                # MODIFICACIÓN: Asegurarse de que simular_temporada_liga_ia se maneje.
                simulacion_ia_exitosa = simular_temporada_liga_ia(liga_gen['id'], temporada_finalizada)
                if simulacion_ia_exitosa: # Si simular_temporada_liga_ia devuelve True
                    mensajes.append(f"Temporada {temporada_finalizada} de {liga_gen['nombre']} simulada con éxito.")
                else: # Si simular_temporada_liga_ia devuelve False
                    mensajes.append(f"Advertencia: No se pudo simular la temporada {temporada_finalizada} de {liga_gen['nombre']}.")

                # Campeón de la liga IA
                campeon_ia = database.get_campeon_temporada(liga_gen['id'], temporada_finalizada)
                if campeon_ia:
                    mensajes.append(f"🏆 Campeón: **{campeon_ia['equipo_campeon_nombre']}**")
                else:
                    mensajes.append("No se pudo determinar el campeón de esta liga.")

                # Tabla de posiciones final de la liga IA
                if liga_gen['nombre'] == "Primera Nacional": #
                    all_clasificaciones_ia = database.get_clasificacion_liga(liga_gen['id'], temporada_finalizada)
                    zonas_encontradas_ia = sorted(list(set([c['zona'] for c in all_clasificaciones_ia if c['zona'] is not None])))
                    if zonas_encontradas_ia:
                        for zona_name_ia in zonas_encontradas_ia:
                            clasificacion_liga_ia_zona = database.get_clasificacion_liga(liga_gen['id'], temporada_finalizada, zona_name_ia)
                            if clasificacion_liga_ia_zona:
                                mensajes.append(f"**Tabla de Posiciones Final de {liga_gen['nombre']} - {zona_name_ia}:**")
                                tabla_str_ia = format_clasificacion_para_mensaje(clasificacion_liga_ia_zona)
                                mensajes.append(tabla_str_ia)
                            else:
                                mensajes.append(f"No hay datos de clasificación para {liga_gen['nombre']} - {zona_name_ia}.")
                    else:
                        mensajes.append(f"No hay datos de clasificación para {liga_gen['nombre']}.")
                else:
                    clasificacion_liga_ia = database.get_clasificacion_liga(liga_gen['id'], temporada_finalizada)
                    if clasificacion_liga_ia:
                        mensajes.append(f"**Tabla de Posiciones Final de {liga_gen['nombre']}:**")
                        tabla_str_ia = format_clasificacion_para_mensaje(clasificacion_liga_ia) # Sin resaltar equipo de usuario
                        mensajes.append(tabla_str_ia)
                    else:
                        mensajes.append("No hay datos de clasificación para esta liga.")

        mensajes.append(f"\n--- ¡COMIENZA LA TEMPORADA {temporada}! ---")
        mensajes.append("Reiniciando clasificaciones y generando nuevo fixture para la próxima temporada en todas las ligas...")
        for liga_reset in todas_las_ligas_db:
            database.reset_clasificacion_liga(liga_reset['id'], temporada)
            # MODIFICACIÓN: Asegurarse de que generate_fixture se maneje.
            fixture_generado = generate_fixture(liga_reset['id'], temporada)
            if not fixture_generado: # Si generate_fixture devuelve False
                mensajes.append(f"Advertencia: No se pudo generar el fixture para la nueva temporada de la liga '{liga_reset['nombre']}'.")
        nueva_temporada_iniciada = True

    # Obtener el estado MÁS RECIENTE de dias_mercado_abierto DESPUÉS de toda la lógica de mercado del día.
    dias_mercado_actualizados_para_db = database.get_dias_mercado_abierto(user_id)

    # DEBUG: Estado antes de actualizar el día en la BD
    print(f"DEBUG GAME_LOGIC: Saliendo avanzar_dia. Se actualizará BD a: Dia {siguiente_dia}, Temporada {temporada}, Dias Mercado: {dias_mercado_actualizados_para_db}")

    database.update_carrera_dia(user_id, siguiente_dia, dias_mercado_actualizados_para_db)

    # Mensaje final si solo se añadió el mensaje del día (y no hubo otros eventos importantes)
    if len(mensajes) == 1 and mensajes[0].startswith("**Día"): # El primer mensaje es siempre el del día.
        mensajes.append("Día avanzado sin eventos adicionales.") # Si solo hay ese, no hubo otros eventos.

    return mensajes


def generate_fixture(liga_id, temporada):
    """
    Genera un fixture de ida y vuelta para una liga y lo guarda en la base de datos.
    Soporta ligas con y sin zonas. Para ligas como Primera Nacional, asigna zonas aleatoriamente y las guarda.
    Algoritmo Round-Robin para generar los emparejamientos.
    Asigna una fecha_simulacion a cada jornada.
    
    liga_id: ID de la liga para la que generar el fixture.
    temporada: La temporada para la que se genera el fixture.
    """
    conn = database.connect_db() # Abre la conexión una vez para toda la operación
    
    try:
        liga_details = database.get_liga_by_id(liga_id, conn)
        if not liga_details:
            print(f"Error: La liga con ID {liga_id} no fue encontrada en la base de datos.")
            return False

        equipos_raw = database.get_equipos_by_liga(liga_id, conn)
        if not equipos_raw:
            print(f"No hay equipos en la liga {liga_details['nombre']} para generar el fixture.")
            return False

        # --- Lógica de Asignación de Zonas Aleatoria (para Primera Nacional) ---
        equipos_por_zona = {}
        LIGA_CON_ZONAS_DINAMICAS = "Primera Nacional"

        if liga_details['nombre'] == LIGA_CON_ZONAS_DINAMICAS:
            num_zonas = 2
            nombres_zonas = [f"Zona {chr(65 + i)}" for i in range(num_zonas)]
            random.shuffle(equipos_raw)

            punto_division = len(equipos_raw) // 2
            equipos_asignados_zona_a = equipos_raw[:punto_division]
            equipos_asignados_zona_b = equipos_raw[punto_division:]

            equipos_por_zona[nombres_zonas[0]] = []
            equipos_por_zona[nombres_zonas[1]] = []

            for equipo_obj in equipos_asignados_zona_a:
                database.update_equipo_zona(equipo_obj['id'], nombres_zonas[0], conn)
                equipos_por_zona[nombres_zonas[0]].append(equipo_obj['id'])
            
            for equipo_obj in equipos_asignados_zona_b:
                database.update_equipo_zona(equipo_obj['id'], nombres_zonas[1], conn)
                equipos_por_zona[nombres_zonas[1]].append(equipo_obj['id'])
        else:
            equipos_por_zona['unica'] = [equipo['id'] for equipo in equipos_raw]
            for equipo in equipos_raw:
                database.update_equipo_zona(equipo['id'], None, conn)
        # --- Fin Lógica de Asignación de Zonas Aleatoria ---
        
        fixture_completo = []
        
        # Eliminar jornadas y partidos antiguos antes de generar nuevos
        database.delete_jornadas_y_partidos_liga_temporada(liga_id, temporada, conn)

        # Determinar el número máximo de jornadas necesarias
        # Para ligas normales, es 2*(N-1) si N es par, o 2*N si N es impar.
        # Para Primera Nacional, si cada zona tiene 18 equipos, son 34 jornadas POR ZONA.
        # PERO el requisito es "34 jornadas globales para la fase regular".
        # Esto implica que si Zona A juega 17 jornadas (ida) y Zona B juega 17 jornadas (ida)
        # y luego lo mismo para la vuelta, eso NO SUMA 34 globales.

        # Re-interpretación del requisito "34 jornadas globales para la fase regular":
        # Se refiere al número total de "días de partido" o "jornadas".
        # Si tienes 2 zonas, cada una con 18 equipos, y juegan ida y vuelta (34 partidos por equipo en la zona).
        # Esto significa 34 jornadas para la Zona A y 34 jornadas para la Zona B.
        # Si cada jornada global tiene partidos de AMBAS zonas, entonces necesitarías 34 jornadas totales.
        # Es decir, la Jornada 1 global tiene partidos de Zona A y Zona B.
        # La Jornada 18 global tendría los primeros partidos de vuelta.
        # En total, se generarían 34 jornadas, y cada una contendría los partidos correspondientes de ambas zonas.

        # Primero, generar el fixture de IDA y VUELTA para CADA ZONA de forma independiente.
        # Luego, combinarlos en un fixture global por jornada.

        fixture_por_zona = {} # {'Zona A': [[jornada1_partidos], [jornada2_partidos]], 'Zona B': ...}
        max_jornadas_totales = 0 # El máximo de jornadas que tendrá la liga (34 para PN, 2*(N-1) para otras)

        for zona_nombre, equipo_ids_zona_original in equipos_por_zona.items():
            current_teams_in_rotation = list(equipo_ids_zona_original)
            num_equipos_zona = len(current_teams_in_rotation)

            if num_equipos_zona < 2:
                fixture_por_zona[zona_nombre] = []
                continue

            if num_equipos_zona % 2 != 0:
                current_teams_in_rotation.append(None)
                num_equipos_zona += 1
            
            rondas_ida = num_equipos_zona - 1
            
            temp_fixture_zona = [] # Almacenar el fixture de esta zona temporalmente
            # Generación de partidos de IDA para esta zona
            teams_for_rotation_ida = list(current_teams_in_rotation) # Copia para rotación de ida
            for ronda_idx in range(rondas_ida):
                jornada_partidos_ida = []
                for j in range(num_equipos_zona // 2):
                    equipo_local_id = teams_for_rotation_ida[j]
                    equipo_visitante_id = teams_for_rotation_ida[num_equipos_zona - 1 - j]
                    if equipo_local_id is not None and equipo_visitante_id is not None:
                        jornada_partidos_ida.append({
                            'equipo_local_id': equipo_local_id,
                            'equipo_visitante_id': equipo_visitante_id,
                            'zona': zona_nombre
                        })
                temp_fixture_zona.append(jornada_partidos_ida) # Los partidos de ida se añaden aquí
                
                # Rotar equipos para la siguiente ronda de ida
                primer_equipo = teams_for_rotation_ida[0]
                resto_equipos = teams_for_rotation_ida[1:]
                resto_equipos.insert(0, resto_equipos.pop())
                teams_for_rotation_ida = [primer_equipo] + resto_equipos
            
            # --- SECCIÓN CORREGIDA: Generación de partidos de VUELTA para esta zona ---
            # Crear una lista TEMPORAL para almacenar las jornadas de vuelta
            # antes de añadirlas a temp_fixture_zona
            jornadas_vuelta_temp = []
            
            # Iterar sobre las jornadas que ya fueron generadas en la fase de ida
            for jornada_partidos_ida in temp_fixture_zona[:rondas_ida]: # Asegurarse de iterar solo las de ida
                jornada_partidos_vuelta = []
                for partido_ida in jornada_partidos_ida:
                    # Invertir local y visitante
                    jornada_partidos_vuelta.append({
                        'equipo_local_id': partido_ida['equipo_visitante_id'],
                        'equipo_visitante_id': partido_ida['equipo_local_id'],
                        'zona': partido_ida['zona'] # Usar la zona original del partido de ida
                    })
                jornadas_vuelta_temp.append(jornada_partidos_vuelta)
            
            # Ahora, añadir TODAS las jornadas de vuelta a temp_fixture_zona
            temp_fixture_zona.extend(jornadas_vuelta_temp)
            # --- FIN SECCIÓN CORREGIDA ---

            fixture_por_zona[zona_nombre] = temp_fixture_zona
            max_jornadas_totales = max(max_jornadas_totales, len(temp_fixture_zona))

        # Ajuste para Primera Nacional: asegurar 34 jornadas globales
        if liga_details['nombre'] == LIGA_CON_ZONAS_DINAMICAS:
            # Si cada zona tiene 18 equipos, se generan 34 jornadas (17 de ida + 17 de vuelta) por zona.
            # Como la fase regular es "34 jornadas globales", asumimos que cada jornada global
            # contiene partidos de AMBAS zonas.
            final_num_jornadas_globales = 34
            # Esto implica que cada jornada global será la combinación de las jornadas de la Zona A y Zona B.
            # Si se generaron más jornadas por zona (ej. si una zona tenía menos de 18 equipos y se generaron menos rondas),
            # entonces necesitaríamos un manejo especial (rellenar con vacías o simplemente aceptar menos).
            # Por simplicidad, tomaremos 34 como el total.
            
            # Asegurarse de que `max_jornadas_totales` refleje el número de jornadas por zona si son más de 34.
            # O forzar a 34 si es Primera Nacional.
            if max_jornadas_totales > final_num_jornadas_globales:
                max_jornadas_totales = final_num_jornadas_globales
            elif max_jornadas_totales < final_num_jornadas_globales and liga_details['nombre'] == LIGA_CON_ZONAS_DINAMICAS:
                # Esto es una advertencia. Si las zonas no tienen 18 equipos, no se llegarán a 34 jornadas por zona.
                print(f"ADVERTENCIA: Para Primera Nacional, el número de equipos en una zona ({num_equipos_zona}) no permite generar 34 jornadas por zona.")
                # Podemos optar por mantener el número de jornadas generadas o forzar 34 y tener jornadas con menos partidos.
                # Por ahora, simplemente nos adaptaremos a `max_jornadas_totales` y combinaremos.

            # Combinar los fixtures de las zonas en un fixture global
            fixture_completo_global = []
            for i in range(max_jornadas_totales):
                jornada_actual_global = []
                for zona_name in nombres_zonas: # Itera sobre "Zona A", "Zona B"
                    if i < len(fixture_por_zona[zona_name]): # Asegurarse de que la jornada exista para esa zona
                        jornada_actual_global.extend(fixture_por_zona[zona_name][i])
                fixture_completo_global.append(jornada_actual_global)
            
            # Reemplazar fixture_completo con el global combinado
            fixture_completo = fixture_completo_global

        else: # Para ligas normales (sin zonas, o si no es Primera Nacional)
            # Si no hay zonas, 'unica' es la única clave y su fixture ya está completo.
            fixture_completo = fixture_por_zona['unica']
            # Asegurarse de que si se generaron más jornadas por el Round-Robin (ej. impar),
            # el max_jornadas_totales esté bien establecido.
            # Ya lo hacemos al calcular `len(temp_fixture_zona)`.

        fecha_base_simulacion_global = datetime.date(2025, 3, 1)
        dias_entre_jornadas = 5 

        for i, jornada_partidos_global in enumerate(fixture_completo):
            # Asegurarse de no exceder las 34 jornadas para Primera Nacional (si es el caso)
            if liga_details['nombre'] == LIGA_CON_ZONAS_DINAMICAS and i >= final_num_jornadas_globales:
                break
            
            numero_jornada_db = i + 1

            dia_relativo_en_temporada = (i * dias_entre_jornadas) + 1
            dias_totales_simulados_para_jornada = (dia_relativo_en_temporada - 1) + (temporada - 1) * 365
            fecha_simulacion_actual = fecha_base_simulacion_global + datetime.timedelta(days=dias_totales_simulados_para_jornada)
            fecha_simulacion_str = fecha_simulacion_actual.strftime('%Y-%m-%d')

            jornada_id = database.add_jornada(liga_id, temporada, numero_jornada_db, conn)
            
            if jornada_id:
                database.update_jornada_fecha(jornada_id, fecha_simulacion_str, conn)
            else:
                existing_jornada = database.get_jornada_by_numero(liga_id, temporada, numero_jornada_db, conn)
                if existing_jornada:
                    jornada_id = existing_jornada['id']
                    database.update_jornada_fecha(jornada_id, fecha_simulacion_str, conn)
                else:
                    print(f"Error: No se pudo añadir ni encontrar la jornada {numero_jornada_db} para la liga {liga_details['nombre']}.")
                    return False

            if jornada_id:
                for partido_info in jornada_partidos_global:
                    if partido_info['equipo_local_id'] is not None and partido_info['equipo_visitante_id'] is not None:
                        # Asegurarse de que add_partido reciba el tipo_partido si es necesario.
                        # Por defecto, add_partido tiene tipo_partido='liga', lo cual es correcto aquí.
                        database.add_partido(jornada_id, partido_info['equipo_local_id'], partido_info['equipo_visitante_id'], conn, zona=partido_info['zona'])
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error en generate_fixture para liga {liga_details.get('nombre', liga_id)}: {e}")
        if conn: conn.rollback()
        return False
    finally:
        database._close_conn_if_created(conn, True)
