# scrape_brasileirao.py

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random
import os

SCRAPED_TEAMS_FILE = 'scraped_teams.txt'

def calcular_edad(fecha_nacimiento_str):
    """
    Calcula la edad a partir de una fecha de nacimiento.
    Acepta formato 'DD.MM.YYYY (Edad)' o 'DD/MM/YYYY (Edad)' o solo 'DD.MM.YYYY' / 'DD/MM/YYYY'.
    """
    try:
        # Extraer solo la fecha si viene con el formato 'DD.MM.YYYY (Edad)' o 'DD/MM/YYYY (Edad)'
        # Modificación CRÍTICA: La expresión regular ahora acepta . o / como separador.
        # r'(\d{2}[./]\d{2}[./]\d{4})'  -> Esto busca XX.XX.XXXX o XX/XX/XXXX
        fecha_solo_numeros_match = re.search(r'(\d{2}[./]\d{2}[./]\d{4})', fecha_nacimiento_str)
        if fecha_solo_numeros_match:
            fecha_limpia = fecha_solo_numeros_match.group(0) # group(0) devuelve toda la coincidencia
        else:
            fecha_limpia = fecha_nacimiento_str # Si no hay match (ej. ya viene limpia), usa la original

        # Normalizar el separador a '.' si es '/' para el map(int, split('.'))
        fecha_limpia = fecha_limpia.replace('/', '.')

        dia, mes, ano = map(int, fecha_limpia.split('.'))
        fecha_nacimiento = datetime(ano, mes, dia)
        hoy = datetime.now() 

        edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
        return edad
    except (ValueError, AttributeError):
        return None

def limpiar_texto(text):
    """Limpia el texto, eliminando saltos de línea, tabulaciones y espacios extra."""
    if text:
        return text.replace('\n', '').replace('\t', '').strip()
    return ""


def load_scraped_teams():
    """Carga los nombres de los equipos ya scrapeados desde un archivo."""
    if os.path.exists(SCRAPED_TEAMS_FILE):
        with open(SCRAPED_TEAMS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_scraped_team(team_name):
    """Guarda el nombre de un equipo en el archivo de equipos scrapeados."""
    with open(SCRAPED_TEAMS_FILE, 'a', encoding='utf-8') as f:
        f.write(team_name + '\n')

def scrape_brasileirao():
    base_url = "https://www.transfermarkt.es"
    # Mantener en 2025 si la liga principal de Transfermarkt ya muestra datos de 2025.
    # Si sigue fallando, prueba a volver a 2024 aquí también.
    liga_url = f"{base_url}/primera-nacional/startseite/wettbewerb/ARG2/plus/?saison_id=2025" 

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    all_players_data = []
    scraped_teams_set = load_scraped_teams()

    print(f"Scrapeando equipos de: {liga_url}")
    response = requests.get(liga_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error al acceder a la página de la liga: {response.status_code}")
        print(f"Contenido de la respuesta (primeras 500 chars): {response.text[:500]}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    team_table_container = soup.find('div', class_='grid-view')
    if not team_table_container:
        print("No se encontró el contenedor principal de la tabla de equipos (div.grid-view).")
        return

    team_links_and_names = []
    for link in team_table_container.select('table.items td.hauptlink a'):
        if '/startseite/verein/' in link['href']:
            team_links_and_names.append({'url_suffix': link['href'], 'name': limpiar_texto(link.text)})

    unique_team_data = { (data['url_suffix'], data['name']) for data in team_links_and_names }

    print(f"Encontrados {len(unique_team_data)} equipos.")

    if not unique_team_data:
        print("Advertencia: No se encontraron enlaces de equipos únicos. Revisa los selectores.")
        return

    teams_to_scrape = []
    for url_suffix, team_name in unique_team_data:
        if team_name not in scraped_teams_set:
            teams_to_scrape.append((url_suffix, team_name))
        else:
            print(f"Saltando equipo '{team_name}': Ya fue scrapeado exitosamente en una ejecución anterior.")
            
    print(f"Quedan {len(teams_to_scrape)} equipos por scrapear.")

    if not teams_to_scrape:
        print("No hay equipos nuevos por scrapear. ¡Todos los clubes ya están en el registro!")
        return all_players_data


    for i, (team_suffix_url, team_name_from_list) in enumerate(teams_to_scrape):
        delay = random.uniform(2, 5)
        print(f"Esperando {delay:.2f} segundos antes de la siguiente solicitud... ({i+1}/{len(teams_to_scrape)})")
        time.sleep(delay)

        team_profile_url = f"{base_url}{team_suffix_url}"
        # No forzar aquí la saison_id, confiar en el enlace o en la redirección de TM
        # Si la URL viene con /saison_id/2024 pero el contenido es 2025, eso es cosa de TM.

        max_retries = 3
        retries = 0
        
        team_response = None
        while retries < max_retries:
            print(f"Scrapeando equipo: {team_profile_url} (Intento {retries + 1}/{max_retries})")
            try:
                team_response = requests.get(team_profile_url, headers=headers, timeout=10)
                if team_response.status_code == 200:
                    break
                elif team_response.status_code in [500, 502, 503, 504]:
                    print(f"Error {team_response.status_code}. Reintentando en {10 * (retries + 1)} segundos...")
                    time.sleep(10 * (retries + 1))
                else:
                    print(f"Error HTTP inesperado {team_response.status_code} al acceder a {team_profile_url}. No reintentar.")
                    break
            except requests.exceptions.RequestException as e:
                print(f"Excepción de conexión al acceder a {team_profile_url}: {e}. Reintentando...")
                time.sleep(10 * (retries + 1))
            retries += 1
        
        if team_response is None or team_response.status_code != 200:
            print(f"Falló al obtener la página del equipo {team_profile_url} después de {max_retries} intentos. Saltando este equipo.")
            continue

        team_soup = BeautifulSoup(team_response.content, 'html.parser')

        team_name = team_name_from_list 

        player_table = team_soup.find('div', class_='responsive-table')

        if not player_table:
            print(f"No se encontró la tabla de jugadores para {team_name} en {team_profile_url}. Saltando.")
            continue
        
        rows = player_table.find_all('tr', class_=re.compile(r'odd|even'))

        if not rows:
            print(f"No se encontraron filas de jugadores en la tabla de {team_name}.")
            continue

        for row in rows:
            player_name = "N/A"
            position = "N/A"
            age = "N/A"
            nationality = "N/A"
            fecha_nacimiento_str = None
            
            # --- EXTRACTORES DE DATOS DENTRO DE LA FILA DEL JUGADOR ---

            # 1. Nombre del jugador (td.hauptlink -> a)
            name_cell = row.find('td', class_='hauptlink')
            if name_cell:
                player_name_tag = name_cell.find('a') 
                if player_name_tag:
                    player_name = limpiar_texto(player_name_tag.text)
            
            # 2. Posición (td.posrela -> table.inline-table -> td.pos O span.spielerposition O texto directo)
            pos_cell = row.find('td', class_='posrela')
            if pos_cell:
                pos_tag = pos_cell.select_one('table.inline-table td.pos')
                if pos_tag:
                    position = limpiar_texto(pos_tag.text)
                else:
                    pos_span = pos_cell.find('span', class_='spielerposition')
                    if pos_span:
                        position = limpiar_texto(pos_span.text)
                    else:
                        position = limpiar_texto(pos_cell.get_text(strip=True))

                        if player_name != "N/A" and position.startswith(player_name):
                             position = position[len(player_name):].strip()
                             if not position: position = "N/A"

            # 3. Fecha de Nacimiento y Edad (Búsqueda universal en todas las celdas <td>)
            # Modificación CRÍTICA en el re.search: Aceptar puntos o barras como separadores.
            all_tds_in_row = row.find_all('td')
            for cell in all_tds_in_row:
                # El patrón ahora acepta . o / como separador de fecha
                fecha_match = re.search(r'(\d{2}[./]\d{2}[./]\d{4})', cell.text) 
                if fecha_match:
                    # limpiar_texto(fecha_match.group(0)) ya hará el strip.
                    # El calcular_edad se encargará de reemplazar '/' por '.' para el split.
                    fecha_nacimiento_str = fecha_match.group(0) 
                    age = calcular_edad(fecha_nacimiento_str)
                    break 

            # 4. Nacionalidad (Búsqueda universal en todas las celdas <td>)
            for cell in all_tds_in_row:
                flag_img = cell.find('img', class_='flaggenrahmen')
                if flag_img and 'title' in flag_img.attrs:
                    nationality = limpiar_texto(flag_img['title'])
                    break

            # --- FIN DE LOS EXTRACTORES ---

            # Filtro final antes de añadir a la lista
            if player_name != "N/A" and team_name != "Nombre Desconocido" and age is not None and nationality != "N/A" and position != "N/A":
                all_players_data.append(f"{player_name}, {position}, {age}, {nationality}, {team_name}")
                print(f"  Añadido: {player_name} ({position}, {age}, {nationality}) de {team_name}")
            else:
                print(f"  Saltando jugador incompleto en {team_name}: Nombre: '{player_name}', Posición: '{position}', Edad: '{age}', Nacionalidad: '{nationality}'")

        # Marcar equipo como scrapeado solo si se encontró al menos 1 jugador válido
        players_scraped_for_current_team = len([p for p in all_players_data if p.endswith(team_name)])
        if players_scraped_for_current_team > 0:
            print(f"  -> Equipo '{team_name}' scrapeado con éxito ({players_scraped_for_current_team} jugadores).")
            save_scraped_team(team_name)
        else:
            print(f"  -> Advertencia: No se encontraron jugadores válidos para el equipo '{team_name}'. No se marcará como scrapeado.")

    return all_players_data

if __name__ == "__main__":
    player_lines = scrape_brasileirao()
    
    if player_lines:
        # CAMBIO CRÍTICO AQUÍ: Cambiar 'w' (write) a 'a' (append)
        with open('bnacional_players.txt', 'a', encoding='utf-8') as f: #
            for line in player_lines:
                f.write(line + '\n')
        print(f"\nDatos del Brasileirão AGREGADOS a bnacional_players.txt con {len(player_lines)} jugadores.")
    else:
        print("No se encontraron datos de jugadores para AGREGAR.")