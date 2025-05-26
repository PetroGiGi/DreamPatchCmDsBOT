# game_logic.py

import random
import sqlite3
import datetime
import database
import market_logic # ¡Importa nuestro nuevo módulo de lógica de mercado!
from market_logic import es_mercado_abierto

# Días en los que se abre el mercado de pases (puedes ajustar estos valores)
MERCADO_PASE_FECHAS = {
    30: "invierno",  # Aproximadamente a mitad de temporada
    365: "verano"     # Al final de la temporada (día 365, antes de reiniciar a día 1)
}
DURACION_MERCADO_DIAS = 30 # Duración del mercado en días

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

    # --- Cálculo de la fecha actual simulada ---
    # Misma fecha base que en main.py y scrape_brasileirao.py
    fecha_base_simulacion_global = datetime.date(2025, 3, 1)
    dias_totales_simulados_actual = (dia_actual - 1) + (temporada - 1) * 365
    fecha_actual_simulada_calendario = fecha_base_simulacion_global + datetime.timedelta(days=dias_totales_simulados_actual)
    fecha_str_actual_calendario = fecha_actual_simulada_calendario.strftime('%Y-%m-%d')
    mensajes.append(f"**Día {dia_actual} de la Temporada {temporada} ({fecha_str_actual_calendario})**")

    # 1. Simular partidos de la IA en la liga del usuario para el día actual
    # Los partidos del usuario se manejan por separado (o vía confirmación en main.py)
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
                update_clasificacion(liga_id, temporada, resultado, zona_nombre=partido.get('zona')) # ¡Pasando la zona!
                mensajes.append(f"- {partido['equipo_local_nombre']} {resultado['goles_e1']} - {resultado['goles_e2']} {partido['equipo_visitante_nombre']}")

    # 2. Lógica del mercado de pases
    dias_mercado_restantes = database.get_dias_mercado_abierto(user_id)

    if dias_mercado_restantes > 0:
        dias_mercado_restantes -= 1
        database.update_dias_mercado_abierto(user_id, dias_mercado_restantes)
        mensajes.append(f"Mercado de pases abierto. Días restantes: {dias_mercado_restantes}.")

        # Generar ofertas de la IA al usuario (con baja probabilidad)
        if random.random() < 0.2: # 20% de probabilidad de recibir una oferta IA
            oferta_generada, msg_oferta = market_logic.generar_oferta_ia_a_usuario(user_id)
            if oferta_generada:
                mensajes.append(msg_oferta)

        # Simular transferencias IA-IA (dentro de la liga del usuario y otras ligas)
        if random.random() < 0.1: # 10% de probabilidad de transferencias IA-IA
            # Para la liga del usuario
            ia_ia_news_liga_usuario = market_logic.simular_transferencias_ia_entre_ellos(liga_id)
            if ia_ia_news_liga_usuario:
                mensajes.append("\n**Noticias de Transferencias en tu Liga:**")
                mensajes.extend(ia_ia_news_liga_usuario)

            # Para otras ligas (solo si quieres que haya actividad global)
            otras_ligas = [l for l in database.get_all_ligas_info() if l['id'] != liga_id]
            if otras_ligas and random.random() < 0.3: # Probabilidad menor para otras ligas
                random.shuffle(otras_ligas)
                for otra_liga in otras_ligas[:min(len(otras_ligas), 2)]: # Simular solo en 1 o 2 ligas IA
                    ia_ia_news_otras_ligas = market_logic.simular_transferencias_ia_entre_ellos(otra_liga['id'])
                    if ia_ia_news_otras_ligas:
                        mensajes.append(f"\n**Noticias de Transferencias en {otra_liga['nombre']}:**")
                        mensajes.extend(ia_ia_news_otras_ligas)

        if dias_mercado_restantes == 0:
            mensajes.append("¡El mercado de pases ha cerrado!")
    else:
        # Verificar si es un día de apertura de mercado
        # Para el día actual (dia_actual), verificamos si está en MERCADO_PASE_FECHAS
        # Si la lógica de MERCADO_PASE_FECHAS usa el día del año (1-365)
        if dia_actual in MERCADO_PASE_FECHAS:
            if database.get_dias_mercado_abierto(user_id) == 0:
                mensajes.append(market_logic.activar_mercado_pases(user_id, DURACION_MERCADO_DIAS))

    # 3. Avanzar el día y verificar el fin de temporada
    siguiente_dia = dia_actual + 1
    nueva_temporada_iniciada = False

    if siguiente_dia > 365: # Un año/temporada tiene 365 días (puedes ajustar esto)
        temporada_finalizada = temporada # La temporada que acaba de terminar
        siguiente_dia = 1
        temporada += 1 # La nueva temporada
        database.update_carrera_temporada(user_id, temporada)
        mensajes.append(f"\n--- ¡FIN DE LA TEMPORADA {temporada_finalizada}! ---")

        # ** 3.1. Resumen de la Liga del Usuario **
        mensajes.append(f"\n**RESUMEN DE LA {database.get_liga_by_id(liga_id)['nombre']} - TEMPORADA {temporada_finalizada}:**")

        # Campeón
        clasificacion_final_liga_usuario = database.get_clasificacion_liga(liga_id, temporada_finalizada)
        if clasificacion_final_liga_usuario:
            campeon_equipo = clasificacion_final_liga_usuario[0]
            database.add_campeon(liga_id, temporada_finalizada, campeon_equipo['equipo_id'])
            mensajes.append(f"🎉🏆 ¡El campeón es: **{campeon_equipo['equipo_nombre']}**! 🏆🎉")
        else:
            mensajes.append("No se pudo determinar el campeón de tu liga.")

        # Tabla de posiciones final de tu liga
        mensajes.append(f"\n**Tabla de Posiciones Final:**")
        # Asegúrate de que format_clasificacion_para_mensaje está definida o importada
        # (normalmente estaría en commands.py o aquí como auxiliar)
        # Por ahora, la dejaré como si estuviera en commands.py o definida localmente.
        # Si no la tienes, es un buen momento para añadirla aquí o donde la uses.
        # Por simplicidad, la defino aquí para asegurar que exista.
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
                if simular_temporada_liga_ia(liga_gen['id'], temporada_finalizada):
                    mensajes.append(f"Temporada {temporada_finalizada} de {liga_gen['nombre']} simulada con éxito.")
                else:
                    mensajes.append(f"Advertencia: No se pudo simular la temporada {temporada_finalizada} de {liga_gen['nombre']}.")

                # Campeón de la liga IA
                campeon_ia = database.get_campeon_temporada(liga_gen['id'], temporada_finalizada)
                if campeon_ia:
                    mensajes.append(f"🏆 Campeón: **{campeon_ia['equipo_campeon_nombre']}**")
                else:
                    mensajes.append("No se pudo determinar el campeón de esta liga.")

                # Tabla de posiciones final de la liga IA
                clasificacion_liga_ia = database.get_clasificacion_liga(liga_gen['id'], temporada_finalizada)
                if clasificacion_liga_ia:
                    mensajes.append(f"**Tabla de Posiciones Final de {liga_gen['nombre']}:**")
                    tabla_str_ia = format_clasificacion_para_mensaje(clasificacion_liga_ia) # Sin resaltar equipo de usuario
                    mensajes.append(tabla_str_ia)
                else:
                    mensajes.append("No hay datos de clasificación para esta liga.")

        mensajes.append(f"\n--- ¡COMIENZA LA TEMPORADA {temporada}! ---")
        # Resetear clasificaciones para la nueva temporada (para todas las ligas)
        mensajes.append("Reiniciando clasificaciones y generando nuevo fixture para la próxima temporada en todas las ligas...")
        for liga_reset in todas_las_ligas_db:
            database.reset_clasificacion_liga(liga_reset['id'], temporada)
            if not generate_fixture(liga_reset['id'], temporada): # Generar fixture para la nueva temporada
                mensajes.append(f"Advertencia: No se pudo generar el fixture para la nueva temporada de la liga '{liga_reset['nombre']}'.")
        nueva_temporada_iniciada = True
    dias_mercado_abierto_db = carrera['dias_mercado_abierto']

    database.update_carrera_dia(user_id, siguiente_dia, dias_mercado_abierto_db)

    # Mensaje final si solo se añadió el mensaje del día (y no hubo otros eventos importantes)
    if len(mensajes) == 1:
        mensajes.append("Día avanzado sin eventos adicionales.")

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
        LIGA_CON_ZONAS_DINAMICAS = "Primera Nacional" # Asegúrate que sea EXACTO

        if liga_details['nombre'] == LIGA_CON_ZONAS_DINAMICAS:
            num_zonas = 2
            nombres_zonas = [f"Zona {chr(65 + i)}" for i in range(num_zonas)]
            random.shuffle(equipos_raw)

            for i, equipo in enumerate(equipos_raw):
                zona_asignada = nombres_zonas[i % num_zonas]
                if zona_asignada not in equipos_por_zona:
                    equipos_por_zona[zona_asignada] = []
                equipos_por_zona[zona_asignada].append(equipo['id'])

                # ¡CRUCIAL! Guardar la zona asignada en la tabla de equipos
                database.update_equipo_zona(equipo['id'], zona_asignada, conn) 

        else: # Para ligas normales
            equipos_por_zona['unica'] = [equipo['id'] for equipo in equipos_raw]
            # Asegurarse de que la zona sea NULL para equipos de ligas no zonificadas
            for equipo in equipos_raw:
                database.update_equipo_zona(equipo['id'], None, conn) # Asigna NULL
        # --- Fin Lógica de Asignación de Zonas Aleatoria ---

        fixture_completo = []
        
        # Eliminar jornadas y partidos antiguos para esta liga y temporada antes de generar nuevos
        database.delete_jornadas_y_partidos_liga_temporada(liga_id, temporada, conn)

        max_jornadas_por_zona = 0
        for zona_nombre, equipo_ids_zona_temp in equipos_por_zona.items():
            num_equipos_zona_temp = len(equipo_ids_zona_temp)
            if num_equipos_zona_temp < 2: continue
            rondas_ida = num_equipos_zona_temp - 1 if num_equipos_zona_temp % 2 == 0 else num_equipos_zona_temp
            max_jornadas_por_zona = max(max_jornadas_por_zona, (rondas_ida * 2))

        for _ in range(max_jornadas_por_zona):
            fixture_completo.append([])

        for zona_nombre, equipo_ids_zona_original in equipos_por_zona.items():
            current_teams_in_rotation = list(equipo_ids_zona_original)
            num_equipos_zona = len(current_teams_in_rotation)

            if num_equipos_zona < 2: continue

            if num_equipos_zona % 2 != 0:
                current_teams_in_rotation.append(None)
                num_equipos_zona += 1
            
            rondas_ida = num_equipos_zona - 1

            for ronda_idx in range(rondas_ida):
                jornada_global_idx = ronda_idx
                if jornada_global_idx >= len(fixture_completo): fixture_completo.append([])

                for j in range(num_equipos_zona // 2):
                    equipo_local_id = current_teams_in_rotation[j]
                    equipo_visitante_id = current_teams_in_rotation[num_equipos_zona - 1 - j]

                    if equipo_local_id is not None and equipo_visitante_id is not None:
                        fixture_completo[jornada_global_idx].append({
                            'equipo_local_id': equipo_local_id,
                            'equipo_visitante_id': equipo_visitante_id,
                            'zona': zona_nombre # Asocia la zona al partido
                        })
                
                primer_equipo = current_teams_in_rotation[0]
                resto_equipos = current_teams_in_rotation[1:]
                resto_equipos.insert(0, resto_equipos.pop())
                current_teams_in_rotation = [primer_equipo] + resto_equipos

            for ronda_idx in range(rondas_ida):
                jornada_global_idx = rondas_ida + ronda_idx
                if jornada_global_idx >= len(fixture_completo): fixture_completo.append([])

                for j in range(num_equipos_zona // 2):
                    equipo_local_id = current_teams_in_rotation[num_equipos_zona - 1 - j]
                    equipo_visitante_id = current_teams_in_rotation[j]

                    if equipo_local_id is not None and equipo_visitante_id is not None:
                        fixture_completo[jornada_global_idx].append({
                            'equipo_local_id': equipo_local_id,
                            'equipo_visitante_id': equipo_visitante_id,
                            'zona': zona_nombre # Asocia la zona al partido
                        })
                
                primer_equipo = current_teams_in_rotation[0]
                resto_equipos = current_teams_in_rotation[1:]
                resto_equipos.insert(0, resto_equipos.pop())
                current_teams_in_rotation = [primer_equipo] + resto_equipos


        fecha_base_simulacion_global = datetime.date(2025, 3, 1)
        dias_entre_jornadas = 5 

        for i, jornada_partidos_global in enumerate(fixture_completo):
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
                        database.add_partido(jornada_id, partido_info['equipo_local_id'], partido_info['equipo_visitante_id'], conn, zona=partido_info['zona'])
        
        # Cuando se llama a add_partido, la zona debe pasarse:
        # database.add_partido(jornada_id, partido_info['equipo_local_id'], partido_info['equipo_visitante_id'], conn, zona=partido_info['zona'])
        conn.commit() # Un solo commit
        return True
    except sqlite3.Error as e:
        print(f"Error en generate_fixture para liga {liga_details.get('nombre', liga_id)}: {e}")
        if conn: conn.rollback()
        return False
    finally:
        database._close_conn_if_created(conn, True) # Cierra la conexión