def behavior(jugador):
    if jugador.tengo_pelota():
        aliado = jugador.encontrar_aliado()
        jugador.patear_pelota(aliado)
    else:
        arco = jugador.encontrar_arco_aliado()
        jugador.correr(arco)