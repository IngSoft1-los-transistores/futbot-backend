def behavior(jugador):
    if jugador.tengo_pelota():
        aliado = jugador.encontrar_aliado()
        jugador.patear_pelota(aliado)
    else:
        pelota = jugador.encontrar_pelota()
        jugador.correr(pelota)