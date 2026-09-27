def behavior(jugador):
    if jugador.tengo_pelota():
        arco = jugador.encontrar_arco_enemigo()
        jugador.patear_pelota(arco)
    else:
        pelota = jugador.encontrar_pelota()
        jugador.correr(pelota)