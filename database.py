# database.py

import sqlite3
import datetime

DATABASE_NAME = 'carrera_dream_patch.db'

def connect_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Inicializa la base de datos, creando todas las tablas necesarias si no existen.
    """
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ligas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            pais TEXT,
            num_equipos INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            liga_id INTEGER,
            nivel_general INTEGER DEFAULT 70,
            zona TEXT, -- ¡REINTRODUCIDA ESTA COLUMNA!
            FOREIGN KEY (liga_id) REFERENCES ligas(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jugadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            posicion TEXT,
            valoracion INTEGER,
            fecha_nacimiento TEXT, --YYYY-MM-DD
            edad INTEGER,
            nacionalidad TEXT,
            equipo_id INTEGER,
            es_fichado INTEGER DEFAULT 0, -- 0 = libre/no asignado, 1 = fichado por un equipo
            FOREIGN KEY (equipo_id) REFERENCES equipos(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carreras (
            usuario_id INTEGER PRIMARY KEY,
            equipo_id INTEGER NOT NULL,
            liga_id INTEGER NOT NULL,
            presupuesto INTEGER DEFAULT 10000000,
            dia_actual INTEGER DEFAULT 1,
            temporada INTEGER DEFAULT 1,
            dias_mercado_abierto INTEGER DEFAULT 0, -- 0 = cerrado, >0 = días restantes
            FOREIGN KEY (equipo_id) REFERENCES equipos(id),
            FOREIGN KEY (liga_id) REFERENCES ligas(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ofertas_jugador (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER NOT NULL,
            equipo_oferta_id INTEGER NOT NULL, -- Equipo que hace la oferta (comprador)
            equipo_destino_id INTEGER NOT NULL, -- Equipo que recibe la oferta (vendedor), o equipo_del_jugador si es libre
            monto INTEGER NOT NULL,
            tipo TEXT NOT NULL, -- 'compra_usuario', 'venta_usuario', 'compra_ia', 'venta_ia' (IA al usuario, no entre IAs)
            fecha_creacion TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente', -- 'pendiente', 'aceptada', 'rechazada', 'retirada'
            FOREIGN KEY (jugador_id) REFERENCES jugadores(id),
            FOREIGN KEY (equipo_oferta_id) REFERENCES equipos(id),
            FOREIGN KEY (equipo_destino_id) REFERENCES equipos(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clasificaciones (
            liga_id INTEGER NOT NULL,
            equipo_id INTEGER NOT NULL,
            temporada INTEGER NOT NULL,
            zona TEXT, -- ¡NUEVA COLUMNA AÑADIDA AQUÍ! (Permite clasificaciones por zona)
            pos INTEGER DEFAULT 0,
            pj INTEGER DEFAULT 0,
            pg INTEGER DEFAULT 0,
            pe INTEGER DEFAULT 0,
            pp INTEGER DEFAULT 0,
            gf INTEGER DEFAULT 0,
            gc INTEGER DEFAULT 0,
            dg INTEGER DEFAULT 0,
            pts INTEGER DEFAULT 0,
            PRIMARY KEY (liga_id, equipo_id, temporada),
            FOREIGN KEY (liga_id) REFERENCES ligas(id),
            FOREIGN KEY (equipo_id) REFERENCES equipos(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jornadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liga_id INTEGER NOT NULL,
            temporada INTEGER NOT NULL,
            numero_jornada INTEGER NOT NULL,
            fecha_simulacion TEXT, --YYYY-MM-DD (para saber cuándo se simuló)
            UNIQUE(liga_id, temporada, numero_jornada),
            FOREIGN KEY (liga_id) REFERENCES ligas(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jornada_id INTEGER NOT NULL,
            equipo_local_id INTEGER NOT NULL,
            equipo_visitante_id INTEGER NOT NULL,
            resultado_local INTEGER DEFAULT NULL,
            resultado_visitante INTEGER DEFAULT NULL,
            simulado INTEGER DEFAULT 0,
            zona TEXT, -- ¡NUEVA COLUMNA AÑADIDA AQUÍ para partidos!
            FOREIGN KEY (jornada_id) REFERENCES jornadas(id),
            FOREIGN KEY (equipo_local_id) REFERENCES equipos(id),
            FOREIGN KEY (equipo_visitante_id) REFERENCES equipos(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS palmares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liga_id INTEGER NOT NULL,
            temporada INTEGER NOT NULL,
            equipo_campeon_id INTEGER NOT NULL,
            UNIQUE(liga_id, temporada),
            FOREIGN KEY (liga_id) REFERENCES ligas(id),
            FOREIGN KEY (equipo_campeon_id) REFERENCES equipos(id)
        )
    ''')

    conn.commit()
    conn.close()

def _get_conn(conn):
    """Auxiliary function to get or create a connection and track if it was created."""
    if conn is None:
        return connect_db(), True # (connection, was_created_here)
    return conn, False

def _close_conn_if_created(conn, was_created_here):
    """Auxiliary function to close connection only if it was created here."""
    if was_created_here:
        conn.close()

# Funciones de palmares
def add_campeon(liga_id, temporada, equipo_campeon_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO palmares (liga_id, temporada, equipo_campeon_id) VALUES (?, ?, ?)",
                       (liga_id, temporada, equipo_campeon_id))
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir campeón al palmarés: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_palmares_liga(liga_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT p.temporada, e.nombre AS equipo_campeon_nombre
        FROM palmares p
        JOIN equipos e ON p.equipo_campeon_id = e.id
        WHERE p.liga_id = ?
        ORDER BY p.temporada ASC
    """, (liga_id,))
    palmares = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(row) for row in palmares]

def get_campeon_temporada(liga_id, temporada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT e.nombre AS equipo_campeon_nombre
        FROM palmares p
        JOIN equipos e ON p.equipo_campeon_id = e.id
        WHERE p.liga_id = ? AND p.temporada = ?
    """, (liga_id, temporada))
    campeon = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(campeon) if campeon else None

def get_campeonatos_equipo(equipo_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT p.temporada, l.nombre AS liga_nombre
        FROM palmares p
        JOIN ligas l ON p.liga_id = l.id
        WHERE p.equipo_campeon_id = ?
        ORDER BY p.temporada ASC, l.nombre ASC
    """, (equipo_id,))
    campeonatos = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(row) for row in campeonatos]

# Funciones de ligas
def add_liga(nombre, pais, num_equipos, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO ligas (nombre, pais, num_equipos) VALUES (?, ?, ?)",
                       (nombre, pais, num_equipos))
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir liga: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_all_ligas_info(conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT id, nombre, pais FROM ligas")
    ligas = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(liga) for liga in ligas]

def get_liga_id(nombre_liga, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT id FROM ligas WHERE nombre = ?", (nombre_liga,))
    liga_id = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return liga_id['id'] if liga_id else None

def get_liga_by_name(nombre_liga, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT * FROM ligas WHERE nombre = ?", (nombre_liga,))
    liga = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(liga) if liga else None

def get_liga_by_id(id_liga, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT * FROM ligas WHERE id = ?", (id_liga,))
    liga = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(liga) if liga else None

# Funciones de equipos
def add_equipo(nombre, liga_id, nivel_general=70, zona=None, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        # Actualiza la inserción para incluir 'zona'
        cursor.execute("INSERT OR IGNORE INTO equipos (nombre, liga_id, nivel_general, zona) VALUES (?, ?, ?, ?)",
                       (nombre, liga_id, nivel_general, zona))
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir equipo: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def update_equipo_zona(equipo_id, zona, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE equipos SET zona = ? WHERE id = ?", (zona, equipo_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar zona del equipo {equipo_id}: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_equipo_by_name(nombre_equipo, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT * FROM equipos WHERE nombre = ?", (nombre_equipo,))
    equipo = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(equipo) if equipo else None

def get_equipo_id(nombre_equipo, liga_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT id FROM equipos WHERE nombre = ? AND liga_id = ?", (nombre_equipo, liga_id))
    equipo = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return equipo['id'] if equipo else None

def get_equipos_de_liga(liga_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    # Asegúrate de seleccionar la columna 'zona' si la usas
    cursor.execute("SELECT id, nombre, liga_id, nivel_general, zona FROM equipos WHERE liga_id = ?", (liga_id,))
    equipos = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(e) for e in equipos]

def get_equipo_by_id(equipo_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT
            e.id,
            e.nombre,
            e.liga_id,
            e.nivel_general,
            e.zona, -- ¡SELECCIONADA DE NUEVO!
            l.nombre AS liga_nombre,
            l.pais AS liga_pais
        FROM equipos e
        JOIN ligas l ON e.liga_id = l.id
        WHERE e.id = ?
    """, (equipo_id,))
    equipo = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(equipo) if equipo else None

def get_equipos_by_liga(liga_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    # Asegúrate de seleccionar la columna 'zona' si la usas
    cursor.execute("SELECT id, nombre, liga_id, nivel_general, zona FROM equipos WHERE liga_id = ?", (liga_id,))
    equipos = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(e) for e in equipos]


# Funciones de jugadores
def add_jugador(nombre, posicion, valoracion, fecha_nacimiento, edad, nacionalidad, equipo_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute(
            "INSERT INTO jugadores (nombre, posicion, valoracion, fecha_nacimiento, edad, nacionalidad, equipo_id, es_fichado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (nombre, posicion, valoracion, fecha_nacimiento, edad, nacionalidad, equipo_id, 1)
        )
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir jugador {nombre}: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_jugador_by_name_and_team(nombre, equipo_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT * FROM jugadores WHERE nombre = ? AND equipo_id = ?", (nombre, equipo_id))
    jugador = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(jugador) if jugador else None

def get_jugadores_por_equipo(equipo_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT * FROM jugadores WHERE equipo_id = ?", (equipo_id,))
    jugadores = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(jugador) for jugador in jugadores]

def get_jugador_by_id(jugador_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT j.*, e.nombre as equipo_nombre, e.nivel_general as equipo_nivel FROM jugadores j JOIN equipos e ON j.equipo_id = e.id WHERE j.id = ?", (jugador_id,))
    jugador = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(jugador) if jugador else None

def get_top_jugadores_liga(liga_id, limit=10, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT
            j.nombre,
            j.valoracion,
            j.posicion,
            e.nombre AS equipo_nombre
        FROM jugadores j
        JOIN equipos e ON j.equipo_id = e.id
        WHERE e.liga_id = ?
        ORDER BY j.valoracion DESC
        LIMIT ?
    """, (liga_id, limit))
    jugadores = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(jugador) for jugador in jugadores]

def update_jugador_equipo(jugador_id, nuevo_equipo_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE jugadores SET equipo_id = ? WHERE id = ?", (nuevo_equipo_id, jugador_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar equipo del jugador {jugador_id} a equipo {nuevo_equipo_id}: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def search_jugadores(query=None, posicion=None, equipo_excluir_id=None, limit=20, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    sql = """
        SELECT j.*, e.nombre AS equipo_nombre, e.nivel_general AS equipo_nivel, l.nombre AS liga_nombre
        FROM jugadores j
        JOIN equipos e ON j.equipo_id = e.id
        JOIN ligas l ON e.liga_id = l.id
        WHERE 1=1
    """
    params = []

    if query:
        sql += " AND j.nombre LIKE ?"
        params.append(f"%{query}%")
    if posicion:
        sql += " AND j.posicion = ?"
        params.append(posicion)
    if equipo_excluir_id:
        sql += " AND j.equipo_id != ?"
        params.append(equipo_excluir_id)

    sql += " ORDER BY j.valoracion DESC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, tuple(params))
    jugadores = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(j) for j in jugadores]

# Funciones de carreras
def add_carrera(usuario_id, equipo_id, liga_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO carreras (usuario_id, equipo_id, liga_id) VALUES (?, ?, ?)",
                       (usuario_id, equipo_id, liga_id))
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir carrera: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_carrera_by_user(user_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT * FROM carreras WHERE usuario_id = ?", (user_id,))
    carrera = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(carrera) if carrera else None

def update_carrera_dia(usuario_id, dia_actual, dias_mercado_abierto, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE carreras SET dia_actual = ?, dias_mercado_abierto = ? WHERE usuario_id = ?",
                       (dia_actual, dias_mercado_abierto, usuario_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar día de carrera: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def update_carrera_temporada(usuario_id, temporada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE carreras SET temporada = ? WHERE usuario_id = ?",
                       (temporada, usuario_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar temporada de carrera: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def update_carrera_presupuesto(usuario_id, nuevo_presupuesto, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE carreras SET presupuesto = ? WHERE usuario_id = ?", (nuevo_presupuesto, usuario_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar presupuesto de carrera: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

# Funciones de ofertas de jugador
def add_oferta_jugador(jugador_id, equipo_oferta_id, equipo_destino_id, monto, tipo, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        fecha_creacion = datetime.date.today().strftime('%Y-%m-%d')
        cursor.execute(
            "INSERT INTO ofertas_jugador (jugador_id, equipo_oferta_id, equipo_destino_id, monto, tipo, fecha_creacion, estado) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (jugador_id, equipo_oferta_id, equipo_destino_id, monto, tipo, fecha_creacion, 'pendiente')
        )
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir oferta: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_ofertas_por_equipo(equipo_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT
            of.*,
            j.nombre AS jugador_nombre, j.posicion AS jugador_posicion, j.valoracion AS jugador_valoracion,
            eo.nombre AS equipo_oferta_nombre,
            ed.nombre AS equipo_destino_nombre
        FROM ofertas_jugador of
        JOIN jugadores j ON of.jugador_id = j.id
        JOIN equipos eo ON of.equipo_oferta_id = eo.id
        JOIN equipos ed ON of.equipo_destino_id = ed.id
        WHERE of.equipo_destino_id = ? AND of.estado = 'pendiente'
    """, (equipo_id,))
    ofertas = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(o) for o in ofertas]

def get_oferta_by_id(oferta_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT
            of.*,
            j.nombre AS jugador_nombre, j.posicion AS jugador_posicion, j.valoracion AS jugador_valoracion, j.equipo_id AS jugador_equipo_actual_id,
            eo.nombre AS equipo_oferta_nombre,
            ed.nombre AS equipo_destino_nombre
        FROM ofertas_jugador of
        JOIN jugadores j ON of.jugador_id = j.id
        JOIN equipos eo ON of.equipo_oferta_id = eo.id
        JOIN equipos ed ON of.equipo_destino_id = ed.id
        WHERE of.id = ?
    """, (oferta_id,))
    oferta = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(oferta) if oferta else None

def update_oferta_estado(oferta_id, estado, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE ofertas_jugador SET estado = ? WHERE id = ?", (estado, oferta_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar estado de oferta: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

# Funciones de Clasificaciones
def update_clasificacion(liga_id, equipo_id, temporada, pj, pg, pe, pp, gf, gc, dg, pts, zona_nombre=None, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        # Se asegura de que la columna 'zona' se use si está presente
        if zona_nombre:
            cursor.execute('''
                INSERT INTO clasificaciones (liga_id, equipo_id, temporada, zona, pj, pg, pe, pp, gf, gc, dg, pts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(liga_id, equipo_id, temporada) DO UPDATE SET
                    zona = excluded.zona,
                    pj = excluded.pj,
                    pg = excluded.pg,
                    pe = excluded.pe,
                    pp = excluded.pp,
                    gf = excluded.gf,
                    gc = excluded.gc,
                    dg = excluded.dg,
                    pts = excluded.pts
            ''', (liga_id, equipo_id, temporada, zona_nombre, pj, pg, pe, pp, gf, gc, dg, pts))
        else: # Si no se pasa zona, inserta NULL para la zona
            cursor.execute('''
                INSERT INTO clasificaciones (liga_id, equipo_id, temporada, zona, pj, pg, pe, pp, gf, gc, dg, pts)
                VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(liga_id, equipo_id, temporada) DO UPDATE SET
                    zona = excluded.zona, -- Actualiza zona a NULL
                    pj = excluded.pj,
                    pg = excluded.pg,
                    pe = excluded.pe,
                    pp = excluded.pp,
                    gf = excluded.gf,
                    gc = excluded.gc,
                    dg = excluded.dg,
                    pts = excluded.pts
            ''', (liga_id, equipo_id, temporada, pj, pg, pe, pp, gf, gc, dg, pts))
        
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar clasificación: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_clasificacion_liga(liga_id, temporada, zona_nombre=None, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()

    sql = '''
        SELECT c.*, e.nombre AS equipo_nombre
        FROM clasificaciones c
        JOIN equipos e ON c.equipo_id = e.id
        WHERE c.liga_id = ? AND c.temporada = ?
    '''
    params = [liga_id, temporada]

    if zona_nombre:
        sql += ' AND c.zona = ?'
        params.append(zona_nombre)
    
    sql += ' ORDER BY c.pts DESC, c.dg DESC, c.gf DESC, e.nombre ASC'

    cursor.execute(sql, tuple(params))
    clasificacion = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(c) for c in clasificacion]

def get_equipo_clasificacion_stats(liga_id, equipo_id, temporada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute('''
        SELECT * FROM clasificaciones
        WHERE liga_id = ? AND equipo_id = ? AND temporada = ?
    ''', (liga_id, equipo_id, temporada))
    stats = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(stats) if stats else None

def reset_clasificacion_liga(liga_id, temporada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        equipos = get_equipos_by_liga(liga_id, conn_actual)
        if not equipos:
            return False

        for equipo in equipos:
            # Reinsertar o actualizar a 0, con zona en NULL
            cursor.execute('''
                INSERT INTO clasificaciones (liga_id, equipo_id, temporada, zona, pj, pg, pe, pp, gf, gc, dg, pts)
                VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 0, 0)
                ON CONFLICT(liga_id, equipo_id, temporada) DO UPDATE SET
                    zona = NULL, -- Reinicia la zona a NULL
                    pj = 0, pg = 0, pe = 0, pp = 0, gf = 0, gc = 0, dg = 0, pts = 0
            ''', (liga_id, equipo['id'], temporada))
        
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al reiniciar clasificación para liga {liga_id}, temporada {temporada}: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

# Funciones para Jornadas y Partidos
def add_jornada(liga_id, temporada, numero_jornada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO jornadas (liga_id, temporada, numero_jornada)
            VALUES (?, ?, ?)
        ''', (liga_id, temporada, numero_jornada))
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir jornada: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def update_jornada_fecha(jornada_id, fecha_simulacion_str, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE jornadas SET fecha_simulacion = ? WHERE id = ?", (fecha_simulacion_str, jornada_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar fecha de jornada {jornada_id}: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_jornada_by_numero(liga_id, temporada, numero_jornada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute('''
        SELECT * FROM jornadas
        WHERE liga_id = ? AND temporada = ? AND numero_jornada = ?
    ''', (liga_id, temporada, numero_jornada))
    jornada = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(jornada) if jornada else None

def add_partido(jornada_id, equipo_local_id, equipo_visitante_id, conn=None, zona=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO partidos (jornada_id, equipo_local_id, equipo_visitante_id, simulado, zona)
            VALUES (?, ?, ?, 0, ?)
        ''', (jornada_id, equipo_local_id, equipo_visitante_id, zona))
        if close_conn: conn_actual.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error al añadir partido: {e}")
        return None
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def update_partido_resultado(partido_id, resultado_local, resultado_visitante, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute('''
            UPDATE partidos
            SET resultado_local = ?, resultado_visitante = ?, simulado = 1
            WHERE id = ?
        ''', (resultado_local, resultado_visitante, partido_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar resultado de partido: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_partidos_por_jornada(jornada_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute('''
        SELECT
            p.*,
            el.nombre AS equipo_local_nombre, el.nivel_general AS equipo_local_ovr,
            ev.nombre AS equipo_visitante_nombre, ev.nivel_general AS equipo_visitante_ovr
        FROM partidos p
        JOIN equipos el ON p.equipo_local_id = el.id
        JOIN equipos ev ON p.equipo_visitante_id = ev.id
        WHERE p.jornada_id = ?
        ORDER BY p.id
    ''', (jornada_id,))
    partidos = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(p) for p in partidos]

def get_jornadas_por_liga_y_temporada(liga_id, temporada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute('''
        SELECT * FROM jornadas
        WHERE liga_id = ? AND temporada = ?
        ORDER BY numero_jornada ASC
    ''', (liga_id, temporada))
    jornadas = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(j) for j in jornadas]

def get_all_partidos_carrera(user_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("""
        SELECT
            p.id,
            p.jornada_id,
            j.numero_jornada,
            el.nombre AS equipo_local_nombre,
            ev.nombre AS equipo_visitante_nombre,
            p.resultado_local,
            p.resultado_visitante,
            j.fecha_simulacion AS fecha_partido,
            p.simulado AS jugado,
            p.zona, -- Seleccionar la zona
            c.equipo_id AS id_equipo_usuario
        FROM partidos p
        JOIN jornadas j ON p.jornada_id = j.id
        JOIN equipos el ON p.equipo_local_id = el.id
        JOIN equipos ev ON p.equipo_visitante_id = ev.id
        JOIN carreras c ON (c.equipo_id = p.equipo_local_id OR c.equipo_id = p.equipo_visitante_id)
        WHERE c.usuario_id = ?
        ORDER BY j.numero_jornada ASC, p.id ASC
    """, (user_id,))
    partidos = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(p) for p in partidos]

def get_all_partidos_simulados_en_temporada(liga_id, temporada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute('''
        SELECT
            p.*,
            el.nombre AS equipo_local_nombre, el.nivel_general AS equipo_local_ovr,
            ev.nombre AS equipo_visitante_nombre, ev.nivel_general AS equipo_visitante_ovr,
            j.numero_jornada
        FROM partidos p
        JOIN jornadas j ON p.jornada_id = j.id
        JOIN equipos el ON p.equipo_local_id = el.id
        JOIN equipos ev ON p.equipo_visitante_id = ev.id
        WHERE j.liga_id = ? AND j.temporada = ? AND p.simulado = 1
        ORDER BY j.numero_jornada, p.id
    ''', (liga_id, temporada))
    partidos = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(p) for p in partidos]

def get_proximo_partido_tu_equipo(user_id, tu_equipo_id, dia_actual, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()

    carrera = get_carrera_by_user(user_id, conn_actual)
    if not carrera:
        _close_conn_if_created(conn_actual, close_conn)
        return None

    liga_id = carrera['liga_id']
    temporada = carrera['temporada']

    cursor.execute("""
        SELECT
            p.*,
            el.nombre AS equipo_local_nombre, el.nivel_general AS equipo_local_ovr,
            ev.nombre AS equipo_visitante_nombre, ev.nivel_general AS equipo_visitante_ovr,
            j.numero_jornada, j.id as jornada_db_id,
            p.zona -- Seleccionar la zona
        FROM partidos p
        JOIN equipos el ON p.equipo_local_id = el.id
        JOIN equipos ev ON p.equipo_visitante_id = ev.id
        JOIN jornadas j ON p.jornada_id = j.id
        WHERE (p.equipo_local_id = ? OR p.equipo_visitante_id = ?)
          AND p.simulado = 0
          AND j.liga_id = ?
          AND j.temporada = ?
        ORDER BY j.numero_jornada ASC
        LIMIT 1
    """, (tu_equipo_id, tu_equipo_id, liga_id, temporada))

    partido = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(partido) if partido else None

def update_dias_mercado_abierto(usuario_id, dias_restantes, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("UPDATE carreras SET dias_mercado_abierto = ? WHERE usuario_id = ?",
                       (dias_restantes, usuario_id))
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al actualizar días de mercado abierto: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)

def get_dias_mercado_abierto(usuario_id, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    cursor.execute("SELECT dias_mercado_abierto FROM carreras WHERE usuario_id = ?", (usuario_id,))
    result = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return result['dias_mercado_abierto'] if result else 0

def get_partido_pendiente(user_id, tu_equipo_id, fecha_str, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()

    carrera = get_carrera_by_user(user_id, conn_actual)
    if not carrera:
        _close_conn_if_created(conn_actual, close_conn)
        return None

    liga_id = carrera['liga_id']
    temporada = carrera['temporada']

    cursor.execute("""
        SELECT
            p.*,
            el.nombre AS equipo_local_nombre,
            ev.nombre AS equipo_visitante_nombre,
            j.numero_jornada, j.id as jornada_db_id,
            p.zona -- Seleccionar la zona
        FROM partidos p
        JOIN jornadas j ON p.jornada_id = j.id
        JOIN equipos el ON p.equipo_local_id = el.id
        JOIN equipos ev ON p.equipo_visitante_id = ev.id
        WHERE (p.equipo_local_id = ? OR p.equipo_visitante_id = ?)
          AND p.simulado = 0
          AND j.liga_id = ?
          AND j.temporada = ?
          AND j.fecha_simulacion = ?
        ORDER BY j.numero_jornada ASC
        LIMIT 1
    """, (tu_equipo_id, tu_equipo_id, liga_id, temporada, fecha_str))

    partido = cursor.fetchone()
    _close_conn_if_created(conn_actual, close_conn)
    return dict(partido) if partido else None

def get_partidos_por_dia(user_id, fecha_str, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()

    carrera = get_carrera_by_user(user_id, conn_actual)
    if not carrera:
        _close_conn_if_created(conn_actual, close_conn)
        return []

    liga_id = carrera['liga_id']
    temporada = carrera['temporada']
    equipo_usuario_id = carrera['equipo_id']

    cursor.execute("""
        SELECT
            p.id,
            p.equipo_local_id,
            p.equipo_visitante_id,
            el.nombre AS equipo_local_nombre,
            ev.nombre AS equipo_visitante_nombre,
            p.simulado,
            p.zona -- Asegúrate de seleccionar la zona
        FROM partidos p
        JOIN jornadas j ON p.jornada_id = j.id
        JOIN equipos el ON p.equipo_local_id = el.id
        JOIN equipos ev ON p.equipo_visitante_id = ev.id
        WHERE j.liga_id = ? AND j.temporada = ? AND j.fecha_simulacion = ?
          AND p.simulado = 0
          AND NOT (p.equipo_local_id = ? OR p.equipo_visitante_id = ?)
    """, (liga_id, temporada, fecha_str, equipo_usuario_id, equipo_usuario_id))

    partidos = cursor.fetchall()
    _close_conn_if_created(conn_actual, close_conn)
    return [dict(p) for p in partidos]

def delete_jornadas_y_partidos_liga_temporada(liga_id, temporada, conn=None):
    conn_actual, close_conn = _get_conn(conn)
    cursor = conn_actual.cursor()
    try:
        cursor.execute("SELECT id FROM jornadas WHERE liga_id = ? AND temporada = ?", (liga_id, temporada))
        jornada_ids_rows = cursor.fetchall()
        
        if jornada_ids_rows:
            jornada_ids_tuple = tuple([j['id'] for j in jornada_ids_rows])
            
            cursor.execute(f"DELETE FROM partidos WHERE jornada_id IN ({','.join(['?' for _ in jornada_ids_tuple])})", jornada_ids_tuple)
            cursor.execute("DELETE FROM jornadas WHERE liga_id = ? AND temporada = ?", (liga_id, temporada))
        
        if close_conn: conn_actual.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al eliminar jornadas y partidos antiguos: {e}")
        return False
    finally:
        _close_conn_if_created(conn_actual, close_conn)


if __name__ == '__main__':
    print("Inicializando base de datos para pruebas...")
    init_db()
    print("Base de datos de prueba lista. No se cargaron datos principales ni fixture completo.")

    # Prueba de adición de liga con la nueva lógica de conexión
    print("\n--- Prueba de adición de liga con manejo de conexión ---")
    test_liga_id = get_liga_id("Liga Test Nueva")
    if not test_liga_id:
        test_liga_id = add_liga("Liga Test Nueva", "Testland", 2)
        print(f"Liga Test Nueva añadida con ID: {test_liga_id}")
    else:
        print(f"Liga Test Nueva ya existe con ID: {test_liga_id}")

    # Prueba de get_liga_by_id con y sin pasar conexión
    liga_info_1 = get_liga_by_id(test_liga_id)
    print(f"Liga info (sin conn): {liga_info_1['nombre'] if liga_info_1 else 'No encontrada'}")

    conn_test = connect_db()
    liga_info_2 = get_liga_by_id(test_liga_id, conn_test)
    print(f"Liga info (con conn): {liga_info_2['nombre'] if liga_info_2 else 'No encontrada'}")
    _close_conn_if_created(conn_test, True) # Usar la nueva función de cierre
