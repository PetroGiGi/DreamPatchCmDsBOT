# commands.py
import database

def ver_plantilla_comando(liga_nombre: str = None, equipo_nombre: str = None) -> str:
    """
    Comando para ver el equipo y los jugadores de un club específico en una liga.
    Permite especificar la liga y el club.
    Retorna una cadena de texto formateada para mostrar al usuario.
    """
    mensaje = [] # Usamos una lista para construir el mensaje y luego unirlos
    
    # Caso 1: No se especifica nada -> Listar ligas
    if not liga_nombre and not equipo_nombre:
        ligas = database.get_ligas_info()
        if not ligas:
            return "No hay ligas cargadas en la base de datos."
        
        mensaje.append("Para ver la plantilla de un equipo, especifica la liga y el nombre del equipo.")
        mensaje.append("Ejemplo: `!plantilla \"Primera División\" \"River Plate\"`")
        mensaje.append("\n**Ligas disponibles:**")
        for liga in ligas:
            mensaje.append(f"- {liga['nombre']} ({liga['num_equipos']} equipos)")
        return "\n".join(mensaje)

    # Caso 2: Se especifica liga, pero no equipo -> Listar equipos de esa liga
    if liga_nombre and not equipo_nombre:
        liga_id = database.get_liga_id(liga_nombre)
        if not liga_id:
            return f"Error: La liga '{liga_nombre}' no fue encontrada. Asegúrate de escribirla exactamente como está registrada (ej. \"Primera División\")."
        
        equipos = database.get_equipos_by_liga(liga_id)
        if not equipos:
            return f"No se encontraron equipos en la liga '{liga_nombre}'."
        
        mensaje.append(f"**Equipos en la liga '{liga_nombre}':**")
        for equipo in equipos:
            mensaje.append(f"- {equipo['nombre']}")
        mensaje.append("\nPara ver los jugadores, especifica también el nombre del equipo.")
        mensaje.append(f"Ejemplo: `!plantilla \"{liga_nombre}\" \"Nombre del Equipo\"`")
        return "\n".join(mensaje)

# Caso 3: Se especifica liga y equipo -> Mostrar plantilla
    if liga_nombre and equipo_nombre:
        liga_id = database.get_liga_id(liga_nombre)
        if not liga_id:
            return f"Error: La liga '{liga_nombre}' no fue encontrada. Asegúrate de escribirla exactamente como está registrada."
        
        # Obtener el ID del equipo por su nombre y AHORA TAMBIÉN POR LIGA_ID
        # Corregido: Pasar liga_id a get_equipo_id
        equipo_id = database.get_equipo_id(equipo_nombre, liga_id) #
        
        if not equipo_id:
            return f"Error: El equipo '{equipo_nombre}' no fue encontrado en la liga '{liga_nombre}'." #
        
        # Opcional pero recomendado: Verificar que el equipo pertenezca a la liga especificada
        # Esto previene que se muestren jugadores de un equipo con el mismo nombre en otra liga,
        # aunque con nombres de equipos únicos en la DB no sería estrictamente necesario.
        # Aquí también deberíamos usar get_equipo_by_id en lugar de get_equipo_details
        equipo_details = database.get_equipo_by_id(equipo_id) #
        if equipo_details and equipo_details['liga_nombre'].lower() != liga_nombre.lower():
            return f"Error: El equipo '{equipo_nombre}' pertenece a la liga '{equipo_details['liga_nombre']}', no a '{liga_nombre}'. Asegúrate de especificar la liga correcta."


        jugadores = database.get_jugadores_por_equipo(equipo_id)
        
        # Elimina o comenta tus líneas de DEBUG aquí, ya confirmamos que funciona
        # print(f"DEBUG: Jugadores obtenidos para {equipo_nombre} (ID: {equipo_id}):")
        # for j in jugadores:
        #     print(f"  - {j}")
        # print(f"DEBUG: Total de jugadores: {len(jugadores)}")
        
        mensaje.append(f"**Plantilla de '{equipo_nombre}' ({liga_nombre}):**")
        if not jugadores:
            mensaje.append("Este equipo no tiene jugadores registrados.")
        else:
            # Organizar por posición
            jugadores_por_posicion = {}
            for jugador in jugadores:
                # Normaliza la posición para asegurar la coincidencia
                # Convierte a minúsculas y quita espacios extra para una mejor comparación
                posicion = jugador['posicion'].strip() # Quita espacios al inicio/final
                
                # AÑADE ESTA LÍNEA DE DEBUG TEMPORALMENTE PARA VER LAS POSICIONES REALES
                # print(f"DEBUG: Procesando jugador {jugador['nombre']}, Posición: '{posicion}'")
                
                if posicion not in jugadores_por_posicion:
                    jugadores_por_posicion[posicion] = []
                jugadores_por_posicion[posicion].append(jugador)
            
            # Ordenar posiciones para una salida consistente y agradable a la vista
            # ASEGÚRATE DE QUE ESTAS POSICIONES COINCIDAN EXACTAMENTE CON LO QUE HAY EN TU DB
            # ES CRÍTICO. Si en tu DB tienes "Delantero centro" y aquí "Delantero", no coincidirán.
            posiciones_ordenadas = [
                'Portero', # Antes 'POR', 'Portero' - ahora solo 'Portero' si es lo que viene de la DB
                'Defensa central', # Antes 'DEF', 'Defensa central'
                'Lateral izquierdo',
                'Lateral derecho',
                'Pivote',
                'Mediocentro',
                'Interior derecho',
                'Interior izquierdo',
                'Mediocentro ofensivo',
                'Extremo izquierdo',
                'Extremo derecho',
                'Delantero centro', # Si tu DB tiene "Delantero centro", usa "Delantero centro" aquí
                'Delantero' # Si también tienes "Delantero" genérico
            ]
            
            # Crea un conjunto para seguir qué posiciones ya hemos impreso
            impresos = set()

            for pos_key in posiciones_ordenadas:
                if pos_key in jugadores_por_posicion and pos_key not in impresos:
                    mensaje.append(f"\n**{pos_key}:**")
                    for jugador in jugadores_por_posicion[pos_key]:
                        mensaje.append(f"- {jugador['nombre']} (OVR: {jugador['valoracion']})")
                    impresos.add(pos_key)
            
            # Si hay posiciones no consideradas en el orden, añadirlas al final
            for pos, j_list in jugadores_por_posicion.items():
                if pos not in impresos:
                    mensaje.append(f"\n**{pos} (Otros):**")
                    for jugador in j_list:
                        mensaje.append(f"- {jugador['nombre']} (OVR: {jugador['valoracion']})")

        return "\n".join(mensaje)
    
    return "Comando inválido. Usa `!plantilla \"Nombre Liga\" \"Nombre Equipo\"`."