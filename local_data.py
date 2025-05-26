# local_data.py

import database
import re
import random
from datetime import date

def cargar_datos_desde_txt_a_db(ruta_archivo, liga_nombre, pais_liga):
    """
    Carga los datos de equipos y jugadores desde un archivo de texto
    a la base de datos, utilizando las funciones de database.py.
    """
    database.init_db()

    equipos_cargados = set()
    jugadores_cargados = 0

    liga_id = database.get_liga_id(liga_nombre)
    if not liga_id:
        liga_id = database.add_liga(liga_nombre, pais_liga, 0)
        if not liga_id:
            print(f"Error: No se pudo agregar ni encontrar la liga '{liga_nombre}'. Abortando carga.")
            return

    print(f"\nCargando datos desde '{ruta_archivo}' a la base de datos para la liga '{liga_nombre}'...")

    # El formato del archivo para Primera Nacional podría ser: Nombre, Posicion, Edad, Nacionalidad, Nombre Equipo, Zona
    # Para otras ligas, sigue siendo: Nombre, Posicion, Edad, Nacionalidad, Nombre Equipo
    
    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue

            try:
                partes = [p.strip() for p in linea.split(',')]
                
                nombre_jugador = partes[0]
                posicion = partes[1]
                edad = int(partes[2])
                nacionalidad = partes[3]
                nombre_equipo_linea = partes[4]
                


                equipo_id = database.get_equipo_id(nombre_equipo_linea, liga_id)
                if not equipo_id:
                    # Pasar la zona al añadir equipo
                    equipo_id = database.add_equipo(nombre_equipo_linea, liga_id)
                
                if not equipo_id:
                    print(f"Advertencia: No se pudo añadir o encontrar el equipo '{nombre_equipo_linea}' para el jugador '{nombre_jugador}'. Saltando jugador.")
                    continue
                
                equipos_cargados.add(nombre_equipo_linea)

                # ... (Lógica de generación de valoración existente) ...
                if edad <= 20:
                    valoracion = random.randint(50, 67) + int(edad * 0.5)
                elif 21 <= edad <= 28:
                    valoracion = random.randint(55, 78)
                else:
                    valoracion = random.randint(58, 72)
                
                if liga_nombre == "Brasileirão Serie A":
                    valoracion = min(86, valoracion)
                elif liga_nombre == "Primera Nacional":
                    valoracion = min(71, valoracion)
                else:
                    valoracion = min(80, valoracion)
                
                valoracion = max(40, valoracion)

                current_year = date.today().year
                est_birth_year = current_year - edad
                fecha_nacimiento_str = f"{est_birth_year}-07-01" 

                jugador_existente = database.get_jugador_by_name_and_team(nombre_jugador, equipo_id)
                if not jugador_existente:
                    database.add_jugador(
                        nombre_jugador, posicion, valoracion, fecha_nacimiento_str, 
                        edad, nacionalidad, equipo_id
                    )
                    jugadores_cargados += 1

            # ... (Manejo de errores existente) ...
            except ValueError as e:
                print(f"Error al parsear datos numéricos/fecha en línea de jugador: {linea} - {e}")
            except IndexError as e:
                print(f"Error al acceder a partes de la línea de jugador (posiblemente formato incorrecto): {linea} - {e}")

    # Actualizar el número de equipos en la tabla de ligas
    conn = database.connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE ligas SET num_equipos = ? WHERE id = ?", (len(equipos_cargados), liga_id))
    conn.commit()
    conn.close()

    print(f"\nCarga de datos completada para '{liga_nombre}'.")
    print(f"  - {len(equipos_cargados)} equipos cargados/actualizados.")
    print(f"  - {jugadores_cargados} jugadores añadidos.")

# --- Ejecución principal ---
if __name__ == '__main__':
    database.init_db()

    print("\n--- Cargando Primera División Argentina (ejemplo con nuevo formato) ---")
    cargar_datos_desde_txt_a_db('equipos primera div.txt', "Primera División", "Argentina")

    print("\n--- Cargando Brasileirão Serie A ---")
    cargar_datos_desde_txt_a_db('brasileirao_players.txt', "Brasileirão Serie A", "Brasil")

    # --- NUEVO: Cargar Primera Nacional ---
    print("\n--- Cargando Primera Nacional ---")
    # NECESITARÁS CREAR 'primera_nacional_players.txt' con el formato:
    # Nombre, Posicion, Edad, Nacionalidad, Nombre Equipo
    # Ejemplo: Juan Perez, Delantero, 25, Argentina, Chacarita Juniors, Zona A
    # OJO: Si la Primera Nacional no tiene un país "Argentina" diferente en la DB,
    # asegúrate de usar el mismo país que otras ligas argentinas para consistencia.
    cargar_datos_desde_txt_a_db('bnacional_players.txt', "Primera Nacional", "Argentina") # Asumiendo Argentina


    # --- Verificación de la carga (opcional) ---
    print("\n--- Verificando datos cargados en la DB ---")
    
    # Verifica la Primera División
    primera_id = database.get_liga_id("Primera División")
    if primera_id:
        print(f"\nLiga 'Primera División' (ID: {primera_id}, Equipos: {database.get_liga_by_id(primera_id)['num_equipos']})")
        # Puedes añadir una verificación de algunos equipos/jugadores si quieres

    # Verifica el Brasileirão
    brasileirao_id = database.get_liga_id("Brasileirão Serie A")
    if brasileirao_id:
        print(f"\nLiga 'Brasileirão Serie A' (ID: {brasileirao_id}, Equipos: {database.get_liga_by_id(brasileirao_id)['num_equipos']})")
        # Puedes añadir una verificación de algunos equipos/jugadores si quieres

    print("\nVerificación de datos completada.")