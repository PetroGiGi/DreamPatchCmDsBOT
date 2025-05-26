# main.py

import os
import discord
from dotenv import load_dotenv
import database
import game_logic # ¡Importa nuestro nuevo módulo de lógica del juego!
import market_logic
import datetime # Para manejar fechas
import commands
import re

# Carga las variables de entorno del archivo .env
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True

bot = discord.Client(intents=intents)

setup_state = {} # Para manejar el estado de setup

@bot.event
async def on_ready():
    print(f'{bot.user} se ha conectado a Discord!')
    print(f'ID del bot: {bot.user.id}')
    print('-----------------------------------------')
    database.init_db()
    print("Base de datos verificada/inicializada.")
    print('-----------------------------------------')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    user_id = message.author.id
    username = message.author.name

    # --- Manejo del estado para confirmaciones (fichar, simular partido IA) ---
    # Esto debe ir ANTES de la lógica de !iniciar_carrera para que los "si/no" sean procesados.
    
    # Lógica de confirmación de simulación de partido IA
    if user_id in setup_state and setup_state[user_id]['step'] == 'confirm_simular_partido_ia':
        if message.content.lower() == 'si':
            partido_details_to_sim = setup_state[user_id]
            
            resultado_sim, error_sim = game_logic.simular_partido(
                partido_details_to_sim['equipo_local_id'],
                partido_details_to_sim['equipo_visitante_id']
            )

            if error_sim:
                await message.channel.send(f"Error al simular el partido: {error_sim}")
                del setup_state[user_id]
                return

            database.update_partido_resultado(
                partido_details_to_sim['partido_id'],
                resultado_sim['goles_e1'],
                resultado_sim['goles_e2']
            )
            game_logic.update_clasificacion(
                partido_details_to_sim['liga_id'],
                partido_details_to_sim['temporada'],
                resultado_sim,
                zona_nombre=partido_details_to_sim.get('zona') # ¡Pasando la zona!
            )
            
            equipo_local_sim_nombre = database.get_equipo_by_id(partido_details_to_sim['equipo_local_id'])['nombre']
            equipo_visitante_sim_nombre = database.get_equipo_by_id(partido_details_to_sim['equipo_visitante_id'])['nombre']
            await message.channel.send(
                f"¡Partido simulado por IA! Resultado: **{equipo_local_sim_nombre} {resultado_sim['goles_e1']} - {resultado_sim['goles_e2']} {equipo_visitante_sim_nombre}**."
            )
            
            mensajes_avance = game_logic.avanzar_dia(user_id)
            for msg in mensajes_avance:
                # Discord tiene un límite de 2000 caracteres por mensaje.
                if len(msg) > 1900:
                    chunks = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.channel.send(msg)
            
            del setup_state[user_id]
            return
        elif message.content.lower() == 'no':
            await message.channel.send("Simulación cancelada. Ingresa el resultado de tu partido con `!resultado goles_local-goles_visitante` antes de avanzar.")
            del setup_state[user_id]
            return
        else:
            await message.channel.send("Respuesta no válida. Por favor, responde `si` para simular por IA y avanzar, o `no` para cancelar.")
            return

    # Lógica de confirmación de fichaje
    if user_id in setup_state and setup_state[user_id]['step'] == 'confirm_fichar':
        if message.content.lower() == 'si':
            offer_details = setup_state[user_id]
            
            success, msg = market_logic.intentar_fichar_jugador_ia(
                user_id,
                offer_details['jugador_id'],
                offer_details['monto_oferta']
            )
            await message.channel.send(msg)
            del setup_state[user_id]
            return
        elif message.content.lower() == 'no':
            await message.channel.send("Oferta cancelada.")
            del setup_state[user_id]
            return
        else:
            await message.channel.send("Respuesta no válida. Por favor, responde `si` para confirmar o `no` para cancelar la oferta.")
            return

    # --- Comandos generales ---
    if message.content == '!hola':
        await message.channel.send(f'¡Hola, {username}! Soy tu bot de modo carrera de Dream Patch.')
        return # Añade return aquí también para evitar procesar como comando o estado.
    
    if message.content == '!ping':
        await message.channel.send('Pong!')
        return # Añade return
    
    # --- Comando !plantilla ---
    if message.content.startswith('!plantilla'):
        args = message.content.split(maxsplit=1)
        liga_arg = None
        equipo_arg = None
        if len(args) > 1:
            full_args_str = args[1].strip()
            matches = re.findall(r'"([^"]*)"|\'([^\']*)\'|(\S+)', full_args_str)
            parsed_args = []
            for m in matches:
                if m[0]: parsed_args.append(m[0])
                elif m[1]: parsed_args.append(m[1])
                elif m[2]: parsed_args.append(m[2])
            if len(parsed_args) >= 1:
                liga_arg = parsed_args[0]
            if len(parsed_args) >= 2:
                equipo_arg = parsed_args[1]
        response_message = commands.ver_plantilla_comando(liga_nombre=liga_arg, equipo_nombre=equipo_arg)
        await message.channel.send(response_message)
        return # Añade return

    # --- Lógica de iniciar carrera ---
    if message.content.startswith('!iniciar_carrera'):
        carrera_existente = database.get_carrera_by_user(user_id)
        if carrera_existente:
            equipo_detalles = database.get_equipo_by_id(carrera_existente['equipo_id'])
            await message.channel.send(f"Ya tienes una carrera iniciada con el equipo **{equipo_detalles['nombre']}** en la **{equipo_detalles['liga_nombre']}**. Día actual: {carrera_existente['dia_actual']}.")
            return

        setup_state[user_id] = {'step': 'select_liga'}
        ligas_disponibles = database.get_all_ligas_info()
        
        if not ligas_disponibles:
            await message.channel.send("No hay ligas disponibles en la base de datos. Por favor, contacta al administrador para que las agregue.")
            del setup_state[user_id]
            return

        ligas_str = "\n".join([f"- {liga['nombre']}" for liga in ligas_disponibles])
        await message.channel.send(f"¡Vamos a iniciar tu modo carrera! Primero, ¿en qué liga quieres jugar?\nDisponibles:\n{ligas_str}\n\nEscribe el nombre exacto de la liga (ej: `Primera División`).")
        return

    # Este bloque maneja la SELECCIÓN DE LIGA
    if user_id in setup_state and setup_state[user_id]['step'] == 'select_liga':
        liga_elegida_nombre = message.content.strip()
        liga_id = database.get_liga_id(liga_elegida_nombre)

        if liga_id:
            equipos_liga = database.get_equipos_by_liga(liga_id)
            if equipos_liga:
                setup_state[user_id]['liga_id'] = liga_id
                setup_state[user_id]['step'] = 'select_equipo'
                equipos_str = "\n".join([f"- {equipo['nombre']}" for equipo in equipos_liga])
                await message.channel.send(f"¡Excelente! Has elegido **{liga_elegida_nombre}**. Ahora, ¿qué equipo quieres manejar?\nEquipos disponibles en esta liga:\n{equipos_str}\n\nEscribe el nombre exacto del equipo (ej: `River Plate`).")
            else:
                await message.channel.send(f"No se encontraron equipos para la liga '{liga_elegida_nombre}'. Por favor, elige otra liga o contacta al administrador.")
                del setup_state[user_id]
        else:
            await message.channel.send(f"La liga '{liga_elegida_nombre}' no se encontró. Por favor, escribe el nombre exacto de una de las ligas disponibles.")
        return

    # Este bloque maneja la SELECCIÓN DE EQUIPO
    if user_id in setup_state and setup_state[user_id]['step'] == 'select_equipo':
        equipo_elegido_nombre = message.content.strip()
        liga_id = setup_state[user_id]['liga_id']
        
        equipo_id = database.get_equipo_id(equipo_elegido_nombre, liga_id) 
        
        equipos_en_liga_ids = [e['id'] for e in database.get_equipos_by_liga(liga_id)]

        if equipo_id and equipo_id in equipos_en_liga_ids:
            database.add_carrera(user_id, equipo_id, liga_id)
            
            # --- ¡Generar fixture SÓLO para la liga del usuario al iniciar la carrera! ---
            # La generación de fixtures para otras ligas se hará al inicio de cada nueva temporada en game_logic.py
            await message.channel.send("Generando el fixture de tu liga, esto puede tomar un momento...")
            
            carrera_creada = database.get_carrera_by_user(user_id)
            if not carrera_creada:
                await message.channel.send("Error al obtener la carrera recién creada. Contacta al administrador.")
                del setup_state[user_id]
                return

            temporada_inicial = carrera_creada['temporada']

            # Solo generar fixture para la liga del usuario
            if game_logic.generate_fixture(liga_id, temporada_inicial): #
                equipo_details = database.get_equipo_by_id(equipo_id) #
                await message.channel.send(f"¡Felicitaciones! Has elegido a **{equipo_elegido_nombre}** para tu modo carrera en la **{equipo_details['liga_nombre']}**.\n\nEl fixture de tu liga ha sido generado. Ahora puedes usar `!mi_equipo` para ver tu plantilla, `!avanzar_dia` para empezar a jugar, y `!proximo_partido` para ver tu siguiente encuentro.")
            else:
                await message.channel.send("Hubo un error al generar el fixture de tu liga. Por favor, contacta al administrador.")
            
            del setup_state[user_id]
        else:
            await message.channel.send(f"El equipo '{equipo_elegido_nombre}' no se encontró o no pertenece a la liga seleccionada. Por favor, escribe el nombre exacto de uno de los equipos disponibles.")
        return
    

    # --- Comando: !mi_equipo ---
    if message.content == '!mi_equipo':
        print(f"DEBUG: !mi_equipo recibido de {user_id}") # <--- Añade esta línea
        carrera = database.get_carrera_by_user(user_id) #
        if not carrera: #
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar.")
            return #

        equipo_id = carrera['equipo_id'] #
        equipo_details = database.get_equipo_by_id(equipo_id) #
        jugadores = database.get_jugadores_por_equipo(equipo_id) #

        if not equipo_details: #
            await message.channel.send("Hubo un error al obtener los detalles de tu equipo. Por favor, contacta al administrador.")
            return #

        response = f"**Tu Equipo: {equipo_details['nombre']}** (Liga: {equipo_details['liga_nombre']})\n\n**Plantilla:**\n" #
        if jugadores: #
            # Organizar por posición (copiado de commands.py para consistencia)
            jugadores_por_posicion = {} #
            for jugador in jugadores: #
                posicion = jugador['posicion'].strip() # Limpiar posición
                if posicion not in jugadores_por_posicion: #
                    jugadores_por_posicion[posicion] = [] #
                jugadores_por_posicion[posicion].append(jugador) #
            
            posiciones_ordenadas = [ #
                'Portero', #
                'Defensa central', #
                'Lateral izquierdo', 'Lateral derecho', #
                'Pivote', 'Mediocentro', 'Interior derecho', 'Interior izquierdo', #
                'Mediocentro ofensivo', #
                'Extremo izquierdo', 'Extremo derecho', #
                'Delantero centro', 'Delantero' #
            ]
            impresos = set() #
            for pos_key in posiciones_ordenadas: #
                if pos_key in jugadores_por_posicion and pos_key not in impresos: #
                    response += f"\n**{pos_key}:**\n" #
                    for jugador in jugadores_por_posicion[pos_key]: #
                        response += f"- {jugador['nombre']} (OVR: {jugador['valoracion']})\n" #
                    impresos.add(pos_key) #
            
            for pos, j_list in jugadores_por_posicion.items(): #
                if pos not in impresos: #
                    response += f"\n**{pos} (Otros):**\n" #
                    for jugador in j_list: #
                        response += f"- {jugador['nombre']} (OVR: {jugador['valoracion']})\n" #

        else: #
            response += "Aún no tienes jugadores en tu plantilla." #
        
        await message.channel.send(response) #
        return # <--- Asegúrate de que este return esté presente



    # --- Lógica MEJORADA: !avanzar_dia (con confirmación) ---
    if message.content == '!avanzar_dia':
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar.")
            return

        tu_equipo_id = carrera['equipo_id']
        
        fecha_base_simulacion_global = datetime.date(2025, 3, 1)
        dia_actual_carrera = carrera['dia_actual']
        temporada_actual_carrera = carrera['temporada']
        dias_totales_simulados_actual = (dia_actual_carrera - 1) + (temporada_actual_carrera - 1) * 365
        fecha_actual_simulada_calendario = fecha_base_simulacion_global + datetime.timedelta(days=dias_totales_simulados_actual)
        fecha_str_actual_calendario = fecha_actual_simulada_calendario.strftime('%Y-%m-%d')

        partido_pendiente_hoy = database.get_partido_pendiente(user_id, tu_equipo_id, fecha_str_actual_calendario)

        if partido_pendiente_hoy:
            equipo_local_nombre_partido = database.get_equipo_by_id(partido_pendiente_hoy['equipo_local_id'])['nombre']
            equipo_visitante_nombre_partido = database.get_equipo_by_id(partido_pendiente_hoy['equipo_visitante_id'])['nombre']

            setup_state[user_id] = {
                'step': 'confirm_simular_partido_ia',
                'partido_id': partido_pendiente_hoy['id'],
                'equipo_local_id': partido_pendiente_hoy['equipo_local_id'],
                'equipo_visitante_id': partido_pendiente_hoy['equipo_visitante_id'],
                'liga_id': carrera['liga_id'],
                'temporada': carrera['temporada'],
                'zona': partido_pendiente_hoy.get('zona') # <-- Asegúrate de pasar la zona aquí
            }
            await message.channel.send(
                f"🚨 **¡ATENCIÓN {username.upper()}! ¡HOY JUEGA TU EQUIPO!** 🚨\n"
                f"Tu partido de hoy es: **{equipo_local_nombre_partido} vs {equipo_visitante_nombre_partido}**.\n"
                f"Si no ingresas el resultado con `!resultado goles_local-goles_visitante`, lo simulará la IA.\n\n"
                f"¿Quieres que simulemos este partido por IA y avancemos? Responde `si` o `no`."
            )
            return

        # Si no hay partido pendiente, simplemente avanzar el día normalmente
        mensajes_avance = game_logic.avanzar_dia(user_id)
        for msg in mensajes_avance:
            if len(msg) > 1900:
                chunks = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(msg)
        return

    if user_id in setup_state and setup_state[user_id]['step'] == 'confirm_simular_partido_ia':
        if message.content.lower() == 'si':
            partido_details_to_sim = setup_state[user_id]
            
            resultado_sim, error_sim = game_logic.simular_partido(
                partido_details_to_sim['equipo_local_id'],
                partido_details_to_sim['equipo_visitante_id']
            )

            if error_sim:
                await message.channel.send(f"Error al simular el partido: {error_sim}")
                del setup_state[user_id]
                return

            database.update_partido_resultado(
                partido_details_to_sim['partido_id'],
                resultado_sim['goles_e1'],
                resultado_sim['goles_e2']
            )
            game_logic.update_clasificacion(
                partido_details_to_sim['liga_id'],
                partido_details_to_sim['temporada'],
                resultado_sim,
                zona_nombre=partido_details_to_sim.get('zona') # ¡Pasando la zona aquí!
            )
            
            equipo_local_sim_nombre = database.get_equipo_by_id(partido_details_to_sim['equipo_local_id'])['nombre']
            equipo_visitante_sim_nombre = database.get_equipo_by_id(partido_details_to_sim['equipo_visitante_id'])['nombre']
            await message.channel.send(
                f"¡Partido simulado por IA! Resultado: **{equipo_local_sim_nombre} {resultado_sim['goles_e1']} - {resultado_sim['goles_e2']} {equipo_visitante_sim_nombre}**."
            )
            
            mensajes_avance = game_logic.avanzar_dia(user_id)
            for msg in mensajes_avance:
                if len(msg) > 1900:
                    chunks = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.channel.send(msg)
            
            del setup_state[user_id]
            return
        
    # --- Comando: !resultado (Lógica MEJORADA) ---
    if message.content.startswith('!resultado '):
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar.")
            return

        tu_equipo_id = carrera['equipo_id']
        
        fecha_base_simulacion_global = datetime.date(2025, 3, 1)
        dia_actual_carrera = carrera['dia_actual']
        temporada_actual_carrera = carrera['temporada']
        dias_totales_simulados_hasta_hoy = (dia_actual_carrera - 1) + (temporada_actual_carrera - 1) * 365
        fecha_actual_simulada_calendario = fecha_base_simulacion_global + datetime.timedelta(days=dias_totales_simulados_hasta_hoy)
        fecha_str = fecha_actual_simulada_calendario.strftime('%Y-%m-%d')

        partido_a_reportar = database.get_partido_pendiente(user_id, tu_equipo_id, fecha_str)

        if not partido_a_reportar:
            await message.channel.send(f"No hay un partido pendiente de resultado para tu equipo hoy ({fecha_str}).")
            return

        args = message.content.split(' ')[1]
        try:
            local_score, visitante_score = map(int, args.split('-'))
            if local_score < 0 or visitante_score < 0:
                 raise ValueError("Los resultados no pueden ser negativos.")
        except ValueError:
            await message.channel.send("Formato de resultado inválido. Usa `!resultado goles_locales-goles_visitantes` (ej: `!resultado 2-1`).")
            return

        if partido_a_reportar['equipo_local_id'] == tu_equipo_id:
            final_local_score = local_score
            final_visitante_score = visitante_score
        elif partido_a_reportar['equipo_visitante_id'] == tu_equipo_id:
            final_local_score = visitante_score
            final_visitante_score = local_score
        else:
            await message.channel.send("Error interno: el partido no coincide con tu equipo. Por favor, contacta al administrador.")
            return

        database.update_partido_resultado(partido_a_reportar['id'], final_local_score, final_visitante_score)
        
        resultado_simulacion = {
            'equipo1_id': partido_a_reportar['equipo_local_id'],
            'goles_e1': final_local_score,
            'equipo2_id': partido_a_reportar['equipo_visitante_id'],
            'goles_e2': final_visitante_score
        }
        game_logic.update_clasificacion(
            carrera['liga_id'],
            carrera['temporada'],
            resultado_simulacion,
            zona_nombre=partido_a_reportar.get('zona') # ¡Pasando la zona!
        )

        await message.channel.send(f"¡Resultado guardado! **{partido_a_reportar['equipo_local_nombre']} {final_local_score}-{final_visitante_score} {partido_a_reportar['equipo_visitante_nombre']}**.")
        await message.channel.send("Puedes usar `!avanzar_dia` para continuar.")
        return

    # --- NUEVO COMANDO: !proximo_partido ---
    if message.content == '!proximo_partido':
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar.")
            return

        equipo_id = carrera['equipo_id']
        proximo_partido = database.get_proximo_partido_tu_equipo(user_id, equipo_id, carrera['dia_actual']) 

        if proximo_partido:
            jornada_details = database.get_jornada_by_numero(
                carrera['liga_id'], carrera['temporada'], proximo_partido['numero_jornada']
            )
            fecha_partido_str = jornada_details['fecha_simulacion'] if jornada_details and 'fecha_simulacion' in jornada_details else "Fecha no definida"

            await message.channel.send(f"Tu próximo partido es en la Jornada {proximo_partido['numero_jornada']}:\n**{proximo_partido['equipo_local_nombre']} vs {proximo_partido['equipo_visitante_nombre']}** (Fecha: {fecha_partido_str})")
        else:
            await message.channel.send("No hay partidos de tu equipo programados en el futuro cercano. ¡La temporada podría haber terminado o se está generando el fixture!")
        return # Añade return

    # --- NUEVO COMANDO: !calendario (muestra tu fixture) ---
    if message.content == '!calendario':
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar.")
            return

        partidos_carrera = database.get_all_partidos_carrera(user_id)
        if not partidos_carrera:
            await message.channel.send("Aún no hay partidos en tu calendario. El fixture podría no haberse generado aún.")
            return

        response_parts = ["**Calendario de Partidos (Tu Carrera):**\n"]
        current_jornada = 0
        for p in partidos_carrera:
            jornada_info = database.get_jornada_by_numero(carrera['liga_id'], carrera['temporada'], p['numero_jornada'])
            fecha_jornada = jornada_info['fecha_simulacion'] if jornada_info else "Fecha N/A"

            if p['numero_jornada'] != current_jornada:
                current_jornada = p['numero_jornada']
                response_parts.append(f"\n--- Jornada {current_jornada} ({fecha_jornada}) ---")
            
            resultado = f"{p['resultado_local']}-{p['resultado_visitante']}" if p['jugado'] == 1 else "PENDIENTE" 
            response_parts.append(f"{p['equipo_local_nombre']} vs {p['equipo_visitante_nombre']} - Resultado: {resultado}")
        
        final_response = "\n".join(response_parts)
        if len(final_response) > 1900:
            await message.channel.send("Tu calendario es muy extenso. Aquí está la primera parte:\n")
            await message.channel.send(final_response[:1900] + "...")
        else:
            await message.channel.send(final_response)
        return # Añade return

    # --- COMANDO: !tabla (MODIFICADO para otras ligas y zonas) ---
    if message.content.startswith('!tabla'):
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar.")
            return

        args = message.content.split(maxsplit=1)
        liga_a_mostrar_nombre = None
        zona_a_mostrar_nombre = None

        if len(args) > 1:
            arg_content = args[1].strip()
            matches = re.findall(r'"([^"]*)"|\'([^\']*)\'|(\S+)', arg_content)
            parsed_args = []
            for m in matches:
                if m[0]: parsed_args.append(m[0])
                elif m[1]: parsed_args.append(m[1])
                elif m[2]: parsed_args.append(m[2])
            
            if len(parsed_args) >= 1:
                liga_a_mostrar_nombre = parsed_args[0]
            if len(parsed_args) >= 2:
                zona_a_mostrar_nombre = parsed_args[1]
        


        if not liga_a_mostrar_nombre:
            liga_id_mostrar = carrera['liga_id']
            liga_details_mostrar = database.get_liga_by_id(liga_id_mostrar)
            if not liga_details_mostrar:
                await message.channel.send("No se pudo encontrar la liga de tu carrera. Contacta al administrador.")
                return
            liga_a_mostrar_nombre = liga_details_mostrar['nombre']
        else:
            liga_id_mostrar = database.get_liga_id(liga_a_mostrar_nombre)
            if not liga_id_mostrar:
                await message.channel.send(f"La liga '{liga_a_mostrar_nombre}' no fue encontrada. Asegúrate de escribirla exactamente como está registrada (ej. \"Brasileirão Serie A\").")
                return
            liga_details_mostrar = database.get_liga_by_id(liga_id_mostrar)

        # Determinar si la liga es la Primera Nacional para mostrar zonas
        es_primera_nacional = (liga_details_mostrar['nombre'] == "Primera Nacional") # <-- ¡Asegúrate que este nombre sea exacto!
        
        response = []

        # ANCHOS DE COLUMNA AJUSTADOS
        ANCHO_EQUIPO = 22 # Antes 17. Probado con 22 para un mejor ajuste.
        ENCABEZADO_TABLA = f"POS EQUIPO{' ' * (ANCHO_EQUIPO - 6)} PJ PG PE PP GF GC DG PTS"


        if es_primera_nacional and not zona_a_mostrar_nombre:
            # Si es Primera Nacional y no se especifica zona, mostrar todas las zonas
            all_clasificaciones = database.get_clasificacion_liga(liga_id_mostrar, carrera['temporada'])
            # Obtener las zonas únicas de las clasificaciones
            zonas_encontradas = sorted(list(set([c['zona'] for c in all_clasificaciones if c['zona'] is not None])))
            
            if not zonas_encontradas:
                response.append(f"Aún no hay partidos jugados en la {liga_details_mostrar['nombre']} para generar la tabla de posiciones en la Temporada {carrera['temporada']}.")
                response.append("No se encontraron zonas o no hay datos de zona en la clasificación. ¿Ya se generó el fixture?")
                await message.channel.send("\n".join(response))
                return

            response.append(f"**Tabla de Posiciones - {liga_details_mostrar['nombre']} (Temporada {carrera['temporada']})**\n")
            response.append("Puedes usar `!tabla \"Primera Nacional\" \"Zona A\"` para ver una zona específica.")

            for zona_name in zonas_encontradas:
                tabla_posiciones_zona = database.get_clasificacion_liga(liga_id_mostrar, carrera['temporada'], zona_name)
                if tabla_posiciones_zona:
                    response.append(f"\n--- {zona_name} ---")
                    response.append(f"```ansi\n{ENCABEZADO_TABLA}")
                    for i, equipo_stats in enumerate(tabla_posiciones_zona):
                        pos = str(i + 1).ljust(3)
                        nombre_equipo_display = equipo_stats['equipo_nombre'][:ANCHO_EQUIPO].ljust(ANCHO_EQUIPO)
                        
                        pj = str(equipo_stats['pj']).ljust(3)
                        pg = str(equipo_stats['pg']).ljust(3)
                        pe = str(equipo_stats['pe']).ljust(3)
                        pp = str(equipo_stats['pp']).ljust(3)
                        gf = str(equipo_stats['gf']).ljust(3)
                        gc = str(equipo_stats['gc']).ljust(3)
                        dg = str(equipo_stats['dg']).ljust(4)
                        pts = str(equipo_stats['pts']).ljust(3)

                        tu_equipo_nombre = database.get_equipo_by_id(carrera['equipo_id'])['nombre'] # Re-obtener el nombre del equipo del usuario
                        if liga_id_mostrar == carrera['liga_id'] and equipo_stats['equipo_nombre'] == tu_equipo_nombre:
                            line = f" [2;36m{pos} {nombre_equipo_display} {pj}{pg}{pe}{pp}{gf}{gc}{dg}{pts} [0m"
                        else:
                            line = f"{pos} {nombre_equipo_display} {pj}{pg}{pe}{pp}{gf}{gc}{dg}{pts}"
                        response.append(line)
                    response.append("```")
                else:
                    response.append(f"\nNo hay datos de clasificación para {zona_name}.")
        else: # Ligas normales o Primera Nacional con zona específica
            tabla_posiciones = database.get_clasificacion_liga(liga_id_mostrar, carrera['temporada'], zona_a_mostrar_nombre)

            if not tabla_posiciones:
                response.append(f"Aún no hay partidos jugados en la {liga_details_mostrar['nombre']} para generar la tabla de posiciones en la Temporada {carrera['temporada']}.")
                if zona_a_mostrar_nombre:
                    response.append(f"No se encontraron datos para la zona '{zona_a_mostrar_nombre}'.")
                await message.channel.send("\n".join(response))
                return

            header_text = f"**Tabla de Posiciones - {liga_details_mostrar['nombre']} (Temporada {carrera['temporada']})"
            if zona_a_mostrar_nombre:
                header_text += f" - {zona_a_mostrar_nombre}"
            header_text += "**\n"
            response.append(header_text)
            response.append(f"```ansi\n{ENCABEZADO_TABLA}")

            tu_equipo_nombre = None
            if liga_id_mostrar == carrera['liga_id']:
                equipo_del_usuario_details = database.get_equipo_by_id(carrera['equipo_id'])
                tu_equipo_nombre = equipo_del_usuario_details['nombre']

            for i, equipo_stats in enumerate(tabla_posiciones):
                pos = str(i + 1).ljust(3)
                nombre_equipo_display = equipo_stats['equipo_nombre'][:ANCHO_EQUIPO].ljust(ANCHO_EQUIPO)
                
                pj = str(equipo_stats['pj']).ljust(3)
                pg = str(equipo_stats['pg']).ljust(3)
                pe = str(equipo_stats['pe']).ljust(3)
                pp = str(equipo_stats['pp']).ljust(3)
                gf = str(equipo_stats['gf']).ljust(3)
                gc = str(equipo_stats['gc']).ljust(3)
                dg = str(equipo_stats['dg']).ljust(4)
                pts = str(equipo_stats['pts']).ljust(3)

                if tu_equipo_nombre and equipo_stats['equipo_nombre'] == tu_equipo_nombre:
                    line = f"[2;36m{pos} {nombre_equipo_display} {pj}{pg}{pe}{pp}{gf}{gc}{dg}{pts}[0m"
                else:
                    line = f"{pos} {nombre_equipo_display} {pj}{pg}{pe}{pp}{gf}{gc}{dg}{pts}"
                
                response.append(line)
            response.append("```")
        
        final_response = "\n".join(response)
        if len(final_response) > 1900:
            await message.channel.send("La tabla es muy extensa. Aquí está la primera parte:\n")
            await message.channel.send(final_response[:1900] + "...")
        else:
            await message.channel.send(final_response)
        return

    # --- NUEVO COMANDO: !palmares (MODIFICADO para incluir títulos del usuario) ---
    if message.content.startswith('!palmares'):
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar.")
            return

        # Intentar parsear el nombre de la liga del argumento
        args = message.content.split(maxsplit=1)
        liga_a_mostrar_nombre = None # Variable para almacenar el nombre de la liga si se especifica

        if len(args) > 1:
            arg_content = args[1].strip()
            match = re.match(r'"([^"]*)"|\'([^\']*)\'|(\S+)', arg_content)
            if match:
                liga_a_mostrar_nombre = match.group(1) or match.group(2) or match.group(3)
        
        response_parts = []

        if not liga_a_mostrar_nombre:
            # Si no se especificó un nombre de liga, mostrar los títulos del equipo del usuario
            equipo_del_usuario = database.get_equipo_by_id(carrera['equipo_id'])
            if not equipo_del_usuario:
                await message.channel.send("Error: No se pudo encontrar tu equipo. Contacta al administrador.")
                return

            tus_titulos = database.get_campeonatos_equipo(equipo_del_usuario['id'])

            if not tus_titulos:
                response_parts.append(f"🏆 **Palmarés de tu equipo ({equipo_del_usuario['nombre']}):**\n")
                response_parts.append("Aún no has ganado ningún título. ¡Sigue esforzándote!")
            else:
                response_parts.append(f"🏆 **Palmarés de tu equipo ({equipo_del_usuario['nombre']}):**\n")
                for titulo in tus_titulos:
                    response_parts.append(f"- Temporada {titulo['temporada']}: Campeón de **{titulo['liga_nombre']}**")
                # Aquí podrías añadir un else para copas si las implementas más adelante
                # Por ejemplo: if not tus_copas: response_parts.append("Aún no tienes copas.")
                # else: for copa in tus_copas: response_parts.append(f"- Temporada {copa['temporada']}: {copa['nombre_copa']}")

        else:
            # Si se especificó un nombre de liga, mostrar el palmarés de esa liga (comportamiento actual)
            liga_id_mostrar = database.get_liga_id(liga_a_mostrar_nombre)
            if not liga_id_mostrar:
                await message.channel.send(f"La liga '{liga_a_mostrar_nombre}' no fue encontrada. Asegúrate de escribirla exactamente como está registrada (ej. \"Brasileirão Serie A\").")
                return
            liga_details_mostrar = database.get_liga_by_id(liga_id_mostrar) #

            palmares_liga = database.get_palmares_liga(liga_id_mostrar) #

            if not palmares_liga:
                response_parts.append(f"🏆 **Palmarés de la {liga_details_mostrar['nombre']}** 🏆\n")
                response_parts.append("Aún no hay campeones registrados para esta liga.")
            else:
                response_parts.append(f"🏆 **Palmarés de la {liga_details_mostrar['nombre']}** 🏆\n")
                for entry in palmares_liga:
                    response_parts.append(f"- Temporada {entry['temporada']}: **{entry['equipo_campeon_nombre']}**")
        
        final_response = "\n".join(response_parts)
        if len(final_response) > 1900:
            await message.channel.send("El palmarés es muy extenso. Aquí está la primera parte:\n")
            await message.channel.send(final_response[:1900] + "...")
        else:
            await message.channel.send(final_response)
        return


    # --- Comando: !fichar (MODIFICADO para incluir cartel de seguridad) ---
    if message.content.startswith('!fichar '):
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada para fichar jugadores. Usa `!iniciar_carrera`.")
            return

        if not market_logic.es_mercado_abierto(user_id):
            await message.channel.send("El mercado de pases no está abierto en este momento. Espera a que se abra para hacer ofertas.")
            return

        if user_id in setup_state and setup_state[user_id].get('step') == 'confirm_fichar':
            del setup_state[user_id]

        args_str = message.content[len('!fichar '):].strip()
        
        matches = re.findall(r'"([^"]*)"(?:\s+"([^"]*)")?\s+(\d+)', args_str)

        jugador_nombre = None
        equipo_vendedor_nombre = None
        monto_oferta_str = None

        if matches and len(matches[0]) == 3:
            jugador_nombre, equipo_vendedor_nombre, monto_oferta_str = matches[0]
        else:
            parts = args_str.split()
            if len(parts) >= 3:
                try:
                    monto_oferta = int(parts[-1])
                    jugador_nombre = " ".join(parts[:-2])
                    equipo_vendedor_nombre = parts[-2]
                except ValueError:
                    if len(parts) == 3:
                        jugador_nombre = parts[0]
                        equipo_vendedor_nombre = parts[1]
                        monto_oferta_str = parts[2]
            
        if not jugador_nombre or not equipo_vendedor_nombre or not monto_oferta_str:
            await message.channel.send("Formato incorrecto. Usa `!fichar \"Nombre Jugador\" \"Nombre Equipo Vendedor\" Monto`.\nEj: `!fichar \"Lionel Messi\" \"Inter Miami\" 100000000`")
            return

        try:
            monto_oferta = int(monto_oferta_str)
        except ValueError:
            await message.channel.send("El monto de la oferta debe ser un número entero válido.")
            return

        if monto_oferta <= 0:
            await message.channel.send("El monto de la oferta debe ser un número positivo.")
            return

        equipo_vendedor_details = database.get_equipo_by_name(equipo_vendedor_nombre)
        if not equipo_vendedor_details:
            await message.channel.send(f"Error: El equipo '{equipo_vendedor_nombre}' no fue encontrado. Asegúrate de escribirlo correctamente.")
            return

        jugador_obj_from_db = database.get_jugador_by_name_and_team(jugador_nombre, equipo_vendedor_details['id'])
        if not jugador_obj_from_db:
            await message.channel.send(f"Error: El jugador '{jugador_nombre}' no fue encontrado en el equipo '{equipo_vendedor_nombre}'.")
            return
        
        valor_mercado_estimado = market_logic.calcular_valor_mercado(jugador_obj_from_db)
        
        probabilidad_aceptacion = 0.15 
        if monto_oferta >= valor_mercado_estimado * 1.5:
            probabilidad_aceptacion = 0.95
        elif monto_oferta >= valor_mercado_estimado * 1.2:
            probabilidad_aceptacion = 0.75
        elif monto_oferta >= valor_mercado_estimado * 1.05:
            probabilidad_aceptacion = 0.5
        
        probabilidad_porcentaje = int(probabilidad_aceptacion * 100)

        setup_state[user_id] = {
            'step': 'confirm_fichar',
            'jugador_id': jugador_obj_from_db['id'],
            'jugador_nombre': jugador_obj_from_db['nombre'],
            'equipo_vendedor_nombre': equipo_vendedor_details['nombre'],
            'monto_oferta': monto_oferta,
            'probabilidad_aceptacion': probabilidad_porcentaje
        }

        confirmation_message = (
            f"Estás a punto de ofrecer **{market_logic.format_money(monto_oferta)}** "
            f"por **{jugador_obj_from_db['nombre']}** ({jugador_obj_from_db['posicion']}, OVR: {jugador_obj_from_db['valoracion']}, Valor de Mercado: {market_logic.format_money(valor_mercado_estimado)}) "
            f"del **{equipo_vendedor_details['nombre']}**.\n\n"
            f"**Probabilidad estimada de que la oferta sea aceptada: {probabilidad_porcentaje}%**\n\n"
            f"¿Confirmas esta oferta? Responde `si` para confirmar o `no` para cancelar."
        )
        await message.channel.send(confirmation_message)
        return

    if message.content == '!ofertas_recibidas':
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera activa.")
            return

        if not market_logic.es_mercado_abierto(user_id):
            await message.channel.send("El mercado de pases no está abierto en este momento.")
            return

        ofertas = database.get_ofertas_por_equipo(carrera['equipo_id']) 
        if not ofertas:
            await message.channel.send("No tienes ofertas de transferencia pendientes.")
            return

        response_msg = "**Ofertas de Transferencia Recibidas:**\n"
        for oferta in ofertas:
            response_msg += (
                f"ID: `{oferta['id']}` - "
                f"**{oferta['equipo_oferta_nombre']}** oferta **{market_logic.format_money(oferta['monto'])}** "
                f"por **{oferta['jugador_nombre']}** (OVR: {oferta['jugador_valoracion']}).\n"
            )
        response_msg += "\nUsa `!aceptar_oferta [ID]` o `!rechazar_oferta [ID]`."
        await message.channel.send(response_msg)
        return # Añade return

    # --- Comando: !aceptar_oferta ---
    if message.content.startswith('!aceptar_oferta '):
        try:
            oferta_id = int(message.content.split(' ')[1])
        except (ValueError, IndexError):
            await message.channel.send("Formato incorrecto. Usa `!aceptar_oferta [ID_Oferta]`.")
            return
        
        response_msg = market_logic.procesar_respuesta_oferta_ia_a_usuario(user_id, oferta_id, True)
        await message.channel.send(response_msg)
        return # Añade return

    # --- Comando: !rechazar_oferta ---
    if message.content.startswith('!rechazar_oferta '):
        try:
            oferta_id = int(message.content.split(' ')[1])
        except (ValueError, IndexError):
            await message.channel.send("Formato incorrecto. Usa `!rechazar_oferta [ID_Oferta]`.")
            return
        
        response_msg = market_logic.procesar_respuesta_oferta_ia_a_usuario(user_id, oferta_id, False)
        await message.channel.send(response_msg)
        return # Añade return

    # --- NUEVO COMANDO: !presupuesto ---
    if message.content == '!presupuesto':
        carrera = database.get_carrera_by_user(user_id)
        if not carrera:
            await message.channel.send("No tienes una carrera iniciada. Usa `!iniciar_carrera` para comenzar y ver tu presupuesto.")
            return

        presupuesto_actual = carrera['presupuesto']
        presupuesto_formateado = market_logic.format_money(presupuesto_actual)

        await message.channel.send(f"Tu presupuesto actual es de **{presupuesto_formateado}**.")
        return # Añade return

# Inicia el bot usando el token
bot.run(TOKEN)