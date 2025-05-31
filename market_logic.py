# market_logic.py
import database
import random
import datetime

# --- Funciones de Utilidad ---
def format_money(amount):
    """Formatea un número como moneda (ej. $5.000.000)."""
    return f"${amount:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- Lógica del Mercado de Pases ---

def calcular_valor_mercado(jugador_obj):
    """
    Calcula un valor de mercado aproximado para un jugador basado en su valoración y edad.
    Se puede hacer mucho más complejo (potencial, contrato, moral, etc.).
    """
    valoracion = jugador_obj['valoracion']
    edad = jugador_obj['edad'] # Asumimos que database.database.get_jugador_by_id() devuelve la edad

    base_price = 0
    if valoracion < 60:
        base_price = random.randint(50_000, 500_000) # De 0.05M - 0.5M (antes 0.1M - 1M)
    elif valoracion < 70:
        base_price = random.randint(500_000, 3_000_000) # De 0.5M - 3M (antes 1M - 5M)
    elif valoracion < 75:
        base_price = random.randint(3_000_000, 10_000_000) # De 3M - 10M (antes 5M - 15M)
    elif valoracion < 80:
        base_price = random.randint(10_000_000, 25_000_000) # De 10M - 25M (antes 15M - 35M)
    elif valoracion < 85:
        base_price = random.randint(25_000_000, 50_000_000) # De 25M - 50M (antes 35M - 70M)
    elif valoracion < 90:
        base_price = random.randint(50_000_000, 100_000_000) # De 50M - 100M (antes 70M - 120M)
    else: # 90+
        base_price = random.randint(100_000_000, 150_000_000) # De 100M - 150M (antes 120M - 200M)

    # Factor de edad: También podemos ajustar los multiplicadores de edad si es necesario.
    # Si quieres que la edad penalice más a los viejos y no infle tanto a los jóvenes, ajusta aquí.
    edad_factor = 1.0
    if edad < 22:
        edad_factor = random.uniform(1.1, 1.3) # Jóvenes: 10-30% más (antes 20-50% más)
    elif edad > 30:
        edad_factor = random.uniform(0.6, 0.8) # Mayores: 20-40% menos (antes 10-30% menos)
    elif edad > 34:
        edad_factor = random.uniform(0.3, 0.5) # Muy mayores: 50-70% menos (antes 40-60% menos)

    final_price = int(base_price * edad_factor)

    # Añadir un pequeño rango para simular fluctuaciones
    fluctuation = random.uniform(0.9, 1.1)
    final_price = int(final_price * fluctuation)
    
    # Redondear para que sea más "bonito"
    if final_price >= 1_000_000:
        final_price = round(final_price, -5) # Redondear a cientos de miles
    elif final_price >= 100_000:
        final_price = round(final_price, -4) # Redondear a decenas de miles
    else:
        final_price = round(final_price, -3) # Redondear a miles

    return max(20_000, final_price) # Mínimo 20k (antes 50k)
def activar_mercado_pases(usuario_id, duracion_dias=30):
    """Activa el mercado de pases para una carrera específica."""
    database.update_dias_mercado_abierto(usuario_id, duracion_dias) # Corregido: usar update_dias_mercado_abierto
    return f"¡El mercado de pases se ha abierto para tu carrera! Tienes **{duracion_dias} días** para fichar."

def es_mercado_abierto(usuario_id):
    """Verifica si el mercado de pases está abierto para una carrera."""
    dias = database.get_dias_mercado_abierto(usuario_id)
    print(f"DEBUG: es_mercado_abierto para user_id {usuario_id}: Días restantes = {dias}") # AÑADE ESTA LÍNEA
    return dias > 0

def intentar_fichar_jugador_ia(usuario_id, jugador_id, monto_oferta):
    """
    Intenta que el usuario fiche a un jugador de un equipo de la IA.
    Retorna (True, mensaje_exito) o (False, mensaje_error).
    """
    carrera = database.get_carrera_by_user(usuario_id) # Corregido: usar get_carrera_by_user
    if not carrera:
        return False, "No tienes una carrera activa para realizar fichajes."

    if not es_mercado_abierto(usuario_id):
        return False, "El mercado de pases no está abierto en este momento."

    jugador = database.get_jugador_by_id(jugador_id) # Corregido: usar get_jugador_by_id
    if not jugador:
        return False, "Jugador no encontrado."
    # Si el jugador está libre, no debería poder ser ofertado como si tuviera club.
    # La columna 'es_fichado' debería ser 1 si tiene un equipo.
    if jugador['equipo_id'] is None: # Si equipo_id es NULL, el jugador está libre
        return False, f"{jugador['nombre']} es un jugador libre. No puedes ofertar por él como si tuviera club."
    
    if jugador['equipo_id'] == carrera['equipo_id']:
        return False, f"¡{jugador['nombre']} ya está en tu equipo!"

    presupuesto_club = carrera['presupuesto']
    
    if monto_oferta <= 0:
        return False, "El monto de la oferta debe ser un número positivo."
    
    if presupuesto_club < monto_oferta:
        return False, f"Tu club solo tiene {format_money(presupuesto_club)} y tu oferta es de {format_money(monto_oferta)}. ¡No tienes suficiente dinero!"

    valor_mercado_estimado = calcular_valor_mercado(jugador)
    
    probabilidad_aceptacion = 0.15 # Baja probabilidad por defecto
    if monto_oferta >= valor_mercado_estimado * 1.5:
        probabilidad_aceptacion = 0.95
    elif monto_oferta >= valor_mercado_estimado * 1.2:
        probabilidad_aceptacion = 0.75
    elif monto_oferta >= valor_mercado_estimado * 1.05:
        probabilidad_aceptacion = 0.5
        
    if random.random() < probabilidad_aceptacion:
        equipo_vendedor_id = jugador['equipo_id']
        equipo_vendedor_details = database.get_equipo_by_id(equipo_vendedor_id) # Corregido: usar get_equipo_by_id
        
        database.update_carrera_presupuesto(usuario_id, presupuesto_club - monto_oferta)
        database.update_jugador_equipo(jugador_id, carrera['equipo_id']) # Corregido: quitar es_fichado

        mensaje_exito = (
            f"¡**{jugador['nombre']}** ({jugador['posicion']} OVR:{jugador['valoracion']}) ha sido fichado!\n"
            f"El **{equipo_vendedor_details['nombre']}** ha aceptado tu oferta de **{format_money(monto_oferta)}**.\n"
            f"Tu presupuesto actual es de **{format_money(presupuesto_club - monto_oferta)}**."
        )
        return True, mensaje_exito
    else:
        mensaje_rechazo = (
            f"El **{jugador['equipo_nombre']}** ha **rechazado** tu oferta de **{format_money(monto_oferta)}** "
            f"por **{jugador['nombre']}**.\n"
            f"Intenta con una oferta más alta o busca otro jugador."
        )
        return False, mensaje_rechazo

def generar_oferta_ia_a_usuario(usuario_id):
    """
    Genera una oferta de la IA por un jugador del equipo del usuario.
    Retorna (True, mensaje_oferta) si hay una oferta, o (False, None).
    """
    carrera = database.get_carrera_by_user(usuario_id) # Corregido: usar get_carrera_by_user
    if not carrera:
        return False, None
    
    equipo_usuario_id = carrera['equipo_id']
    jugadores_usuario = database.get_jugadores_por_equipo(equipo_usuario_id) # Corregido: usar get_jugadores_por_equipo

    if not jugadores_usuario:
        return False, None

    candidatos = [j for j in jugadores_usuario if j['valoracion'] < 85]
    if not candidatos:
        return False, None

    jugador_a_ofertar = random.choice(candidatos)
    jugador_details = database.get_jugador_by_id(jugador_a_ofertar['id']) # Corregido: usar get_jugador_by_id
    
    liga_usuario_id = carrera['liga_id']
    equipos_ia_en_liga = [e for e in database.get_equipos_by_liga(liga_usuario_id) if e['id'] != equipo_usuario_id]
    
    if not equipos_ia_en_liga:
        return False, None
    
    equipo_ia_oferta = random.choice(equipos_ia_en_liga)

    valor_mercado = calcular_valor_mercado(jugador_details)
    monto_oferta = int(valor_mercado * random.uniform(0.7, 0.95))
    monto_oferta = max(monto_oferta, 100_000)

    oferta_id = database.add_oferta_jugador(
        jugador_details['id'],
        equipo_ia_oferta['id'],
        equipo_usuario_id,
        monto_oferta,
        'venta_ia'
    )

    if oferta_id:
        mensaje_oferta = (
            f"¡NOTICIA DE ÚLTIMA HORA!\n"
            f"El **{equipo_ia_oferta['nombre']}** ha hecho una oferta por **{jugador_details['nombre']}** "
            f"de tu club por **{format_money(monto_oferta)}**.\n"
            f"Usa `!ofertas_recibidas` para verla y `!aceptar_oferta {oferta_id}` o `!rechazar_oferta {oferta_id}` para responder."
        )
        return True, mensaje_oferta
    return False, None

def procesar_respuesta_oferta_ia_a_usuario(usuario_id, oferta_id, aceptar: bool):
    """
    Procesa la respuesta del usuario a una oferta de la IA por su jugador.
    """
    carrera = database.get_carrera_by_user(usuario_id) # Corregido: usar get_carrera_by_user
    if not carrera:
        return "Error: No tienes una carrera activa."

    oferta = database.get_oferta_by_id(oferta_id) # Corregido: usar get_oferta_by_id
    if not oferta or oferta['equipo_destino_id'] != carrera['equipo_id'] or oferta['estado'] != 'pendiente' or oferta['tipo'] != 'venta_ia': # Corregido: usar 'tipo'
        return "Oferta inválida o no pendiente para tu club."
    
    jugador = database.get_jugador_by_id(oferta['jugador_id']) # Corregido: usar get_jugador_by_id
    
    if not jugador or jugador['equipo_id'] != carrera['equipo_id']:
        return f"Error: El jugador {oferta['jugador_nombre']} ya no está en tu equipo o no existe."

    if aceptar:
        database.update_jugador_equipo(jugador['id'], oferta['equipo_oferta_id']) # Corregido: quitar es_fichado
        database.update_carrera_presupuesto(usuario_id, carrera['presupuesto'] + oferta['monto'])
        database.update_oferta_estado(oferta_id, 'aceptada')
        return (f"¡Has **aceptado** la oferta!\n"
                f"**{jugador['nombre']}** ha sido vendido a **{oferta['equipo_oferta_nombre']}** por **{format_money(oferta['monto'])}**.\n"
                f"Tu presupuesto actual es de **{format_money(carrera['presupuesto'] + oferta['monto'])}**.")
    else:
        database.update_oferta_estado(oferta_id, 'rechazada')
        return (f"Has **rechazado** la oferta de **{format_money(oferta['monto'])}** de **{oferta['equipo_oferta_nombre']}** "
                f"por **{jugador['nombre']}**.")


def simular_transferencias_ia_entre_ellos(liga_id):
    """
    Simula transferencias entre equipos de la IA dentro de una liga.
    Esta es la parte más compleja y se ejecutará con baja probabilidad cada día de mercado.
    Retorna una lista de mensajes de noticias de transferencias.
    """
    noticias = []
    # Probabilidad de que haya transferencias IA-IA un día dado
    print(f"DEBUG IA-IA: Intentando simular transferencias en liga {liga_id}.") # NUEVO
    if random.random() > 0.15:
        print(f"DEBUG IA-IA: Salida temprana, probabilidad no cumplida.") # NUEVO
        return noticias

    equipos_en_liga = database.get_equipos_by_liga(liga_id)
    if not equipos_en_liga:
        print(f"DEBUG IA-IA: No hay equipos en liga {liga_id} para simular.") # NUEVO
        return noticias

    print(f"DEBUG IA-IA: Encontrados {len(equipos_en_liga)} equipos en liga {liga_id}.") # NUEVO

    random.shuffle(equipos_en_liga) # Mezclar para no favorecer a nadie

    for i, (equipo_comprador) in enumerate(equipos_en_liga): # Iterar directamente sobre los equipos
        print(f"DEBUG IA-IA: Equipo comprador: {equipo_comprador['nombre']} (ID: {equipo_comprador['id']})") # NUEVO
        if random.random() > 0.3:
            print(f"DEBUG IA-IA: {equipo_comprador['nombre']} decidió no intentar fichar.") # NUEVO
            continue

        jugador_target = None
        equipo_vendedor = None # Inicializar
        for j_attempt in range(5):
            # Asegúrate de que equipo_vendedor sea diferente a equipo_comprador
            temp_equipos_vendedores = [e for e in equipos_en_liga if e['id'] != equipo_comprador['id']]
            if not temp_equipos_vendedores:
                print(f"DEBUG IA-IA: No hay equipos vendedores disponibles para {equipo_comprador['nombre']}.")
                break # No hay otros equipos para comprar
            equipo_vendedor = random.choice(temp_equipos_vendedores)
            print(f"DEBUG IA-IA: {equipo_comprador['nombre']} considera comprar de {equipo_vendedor['nombre']}.") # NUEVO

            jugadores_vendedor = database.get_jugadores_por_equipo(equipo_vendedor['id'])
            if not jugadores_vendedor:
                print(f"DEBUG IA-IA: {equipo_vendedor['nombre']} no tiene jugadores.") # NUEVO
                continue

            jugador_target = random.choice(jugadores_vendedor)
            jugador_target_details = database.get_jugador_by_id(jugador_target['id'])
            print(f"DEBUG IA-IA: Jugador target: {jugador_target_details['nombre']} (OVR: {jugador_target_details['valoracion']})") # NUEVO

            if jugador_target_details['equipo_id'] is None:
                print(f"DEBUG IA-IA: Jugador {jugador_target_details['nombre']} está libre, saltando.") # NUEVO
                jugador_target = None # Marcar como no válido
                continue

            if jugador_target_details['valoracion'] > (equipo_vendedor['nivel_general'] + 5) and random.random() > 0.7:
                print(f"DEBUG IA-IA: {equipo_vendedor['nombre']} no quiere vender a {jugador_target_details['nombre']} (demasiado bueno).") # NUEVO
                jugador_target = None
                continue

            print(f"DEBUG IA-IA: Encontrado jugador válido: {jugador_target_details['nombre']} del {equipo_vendedor['nombre']}.") # NUEVO
            break # Encontramos un jugador

        if not jugador_target:
            print(f"DEBUG IA-IA: No se encontró un jugador adecuado para {equipo_comprador['nombre']} después de 5 intentos.") # NUEVO
            continue

        valor_mercado = calcular_valor_mercado(jugador_target_details)
        oferta_monto = int(valor_mercado * random.uniform(0.8, 1.3))
        print(f"DEBUG IA-IA: Oferta de {equipo_comprador['nombre']} por {jugador_target_details['nombre']}: {format_money(oferta_monto)} (VM: {format_money(valor_mercado)})") # NUEVO

        prob_aceptacion_vendedor = 0.0
        if oferta_monto >= valor_mercado * 1.2: prob_aceptacion_vendedor = 0.9
        elif oferta_monto >= valor_mercado * 1.0: prob_aceptacion_vendedor = 0.6
        elif oferta_monto >= valor_mercado * 0.9: prob_aceptacion_vendedor = 0.3
        else: prob_aceptacion_vendedor = 0.1

        actual_random_roll = random.random() # Captura el valor aleatorio para el debug
        print(f"DEBUG IA-IA: Probabilidad de aceptación por {equipo_vendedor['nombre']}: {prob_aceptacion_vendedor*100:.2f}%. Roll: {actual_random_roll:.4f}") # NUEVO

        if actual_random_roll < prob_aceptacion_vendedor:
            print(f"DEBUG IA-IA: ¡Oferta aceptada! {jugador_target_details['nombre']} se mueve de {equipo_vendedor['nombre']} a {equipo_comprador['nombre']}.") # NUEVO
            transferencia_exitosa = database.update_jugador_equipo(jugador_target_details['id'], equipo_comprador['id'])
            if transferencia_exitosa:
                noticias.append(f"**¡BOMBAZO EN EL MERCADO!** El **{equipo_comprador['nombre']}** ha fichado a **{jugador_target_details['nombre']}** ({jugador_target_details['posicion']} OVR:{jugador_target_details['valoracion']}) del **{equipo_vendedor['nombre']}** por **{format_money(oferta_monto)}**.")
            else:
                print(f"DEBUG: Falló la actualización DB para transferencia IA: {jugador_target_details['nombre']} a {equipo_comprador['nombre']}")
        else:
            print(f"DEBUG IA-IA: Oferta rechazada por {equipo_vendedor['nombre']}.") # NUEVO


    # Ojo: Aquí es donde podríamos filtrar el equipo del usuario si no queremos que participe en IA-IA
    # Pero si el usuario es el único equipo activo, esto es para la liga en general.
    # Si quieres que el equipo del usuario nunca sea parte de una transferencia IA-IA (ni como comprador ni vendedor),
    # puedes añadir una lógica aquí.
    # Por ahora, tu diseño ya excluye al usuario de 'equipo_ia_oferta' en generar_oferta_ia_a_usuario.

    for i in range(len(equipos_en_liga)):
        equipo_comprador = equipos_en_liga[i]
        
        # *** Importante: Asegúrate de que el equipo del usuario no sea un "comprador" o "vendedor" aquí
        # si esta función se llama para la liga del usuario.
        # La forma más fácil es obtener la carrera del usuario y saltar su equipo.
        carrera_del_usuario = None
        # Si tu bot solo soporta una carrera a la vez, puedes hacer esto:
        # carrera_del_usuario = database.get_carrera_by_user(<ID_DEL_USUARIO_ACTIVO_SI_LO_PUEDES_OBTENER>)
        # Si no, asumimos que este módulo solo afecta a equipos IA.

        # Oportunidad de que un equipo IA intente fichar
        if random.random() > 0.1: # 70% de chance de que un equipo IA intente fichar
            continue

        # Identificar una necesidad del equipo comprador (simplificado por ahora)
        jugador_target = None
        for j_attempt in range(5): # Intentar 5 veces encontrar un jugador
            equipo_vendedor = random.choice([e for e in equipos_en_liga if e['id'] != equipo_comprador['id']])
            
            # Asegurarse de que el equipo vendedor no sea el equipo del usuario si estamos en su liga
            # (aunque la probabilidad es baja si hay muchos equipos IA)
            # Ejemplo: if carrera_del_usuario and equipo_vendedor['id'] == carrera_del_usuario['equipo_id']: continue

            jugadores_vendedor = database.get_jugadores_por_equipo(equipo_vendedor['id'])
            
            if not jugadores_vendedor:
                continue
            
            # Elegir un jugador al azar de su plantilla (podría ser el de menor OVR para venta, o de cierta posición)
            jugador_target = random.choice(jugadores_vendedor)
            jugador_target_details = database.get_jugador_by_id(jugador_target['id'])
            
            # Una vez más, es_fichado=0 significa libre, pero si tiene equipo_id, debería ser 1.
            # La columna es_fichado en DB es DEFAULT 1 cuando se añade a un equipo, 0 para libres.
            # Esto puede ser un punto de confusión. Si el jugador tiene equipo_id, siempre asume que 'está fichado'.
            if jugador_target_details['equipo_id'] is None: # Si no tiene equipo, está libre. Esta transferencia no es IA-IA.
                jugador_target = None
                continue
            
            # No queremos que se vendan sus mejores jugadores fácilmente
            if jugador_target_details['valoracion'] > (equipo_vendedor['nivel_general'] + 5) and random.random() > 0.7:
                jugador_target = None # Equipo no lo venderá fácilmente si es muy bueno y no tiene necesidad
                continue

            break # Encontramos un jugador

        if not jugador_target:
            continue

        # Calcular oferta de la IA
        valor_mercado = calcular_valor_mercado(jugador_target_details)
        oferta_monto = int(valor_mercado * random.uniform(0.8, 1.3)) # IA puede ofrecer desde 80% a 130%

        # Lógica de aceptación del equipo vendedor (IA)
        prob_aceptacion_vendedor = 0.0
        if oferta_monto >= valor_mercado * 1.2:
            prob_aceptacion_vendedor = 0.9 # Muy buena oferta
        elif oferta_monto >= valor_mercado * 1.0:
            prob_aceptacion_vendedor = 0.6 # Oferta a valor de mercado
        elif oferta_monto >= valor_mercado * 0.9:
            prob_aceptacion_vendedor = 0.3 # Oferta aceptable
        else:
            prob_aceptacion_vendedor = 0.1 # Oferta baja

        if random.random() < prob_aceptacion_vendedor:
            # Transferencia aceptada
            # *** PUNTO CRÍTICO: Asegurarse de que update_jugador_equipo funcione. ***
            # La llamada a database.update_jugador_equipo(jugador_target_details['id'], equipo_comprador['id'])
            # DEBE mover al jugador. Si no lo hace, el "bombazo" no se concreta.
            
            # Asegúrate de que update_jugador_equipo en database.py sea funcional.
            # Aquí no le pasamos 'es_fichado' porque la función solo toma (jugador_id, nuevo_equipo_id).
            # El campo 'es_fichado' tiene un DEFAULT 1 en la tabla si ya está en un equipo.
            # Si el jugador se movió, sigue "fichado" con un equipo.
            
            transferencia_exitosa = database.update_jugador_equipo(jugador_target_details['id'], equipo_comprador['id'])
            
            if transferencia_exitosa: # Solo añadir noticia si la DB se actualizó
                noticias.append(
                    f"**¡BOMBAZO EN EL MERCADO!** El **{equipo_comprador['nombre']}** ha fichado a **{jugador_target_details['nombre']}** "
                    f"({jugador_target_details['posicion']} OVR:{jugador_target_details['valoracion']}) del **{equipo_vendedor['nombre']}** "
                    f"por **{format_money(oferta_monto)}**."
                )
            else:
                # Esto es para depuración si la transferencia falla silenciosamente
                print(f"DEBUG: Falló la actualización DB para transferencia IA: {jugador_target_details['nombre']} a {equipo_comprador['nombre']}")
        # else:
            # print(f"El {equipo_vendedor['nombre']} rechazó la oferta del {equipo_comprador['nombre']} por {jugador_target_details['nombre']}")

    return noticias
