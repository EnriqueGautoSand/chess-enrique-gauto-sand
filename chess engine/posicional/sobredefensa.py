"""
Evaluador POSICIONAL de Sobredefensa.

Concepto (pedido por el usuario):
Si una pieza/casilla propia esta SOBREDEFENDIDA (mas defensores que atacantes),
las piezas "sobrantes" quedan LIBRES para realizar otras tareas (atacar, maniobrar),
porque la casilla seguiria defendida incluso si una de ellas se va. Esto es una
ventaja posicional, NO de material, por eso vive en la carpeta posicional.

IMPORTANTE: esto es distinto del balance de material del SEE (intercambios.py).
El SEE dice "cuanto material gano/pierdo en la secuencia de capturas"; la
sobredefensa dice "cuantas piezas tengo de mas defendiendo, que podrian hacer
otra cosa". Por eso NO se mezcla con el SEE.

Regla de conteo:
- Solo se consideran piezas propias que estan bajo PRESION real (>= 1 atacante),
  porque sobredefender algo que nadie ataca no libera nada (no hay tension).
- piezas_libres = max(0, total_defensores - total_atacantes)
- El rey cuenta como defensor a efectos de saber si la casilla aguanta, pero el
  bonus de "pieza libre" solo se da por piezas NORMALES sobrantes (el rey no se
  "libera" para atacar).
"""
import chess
from typing import Tuple

try:
    from ..constantes import VALORES_PIEZAS
except ImportError:
    from constantes import VALORES_PIEZAS

# Bonus posicional por cada pieza normal "libre" gracias a la sobredefensa.
# Valor pequeno: es un matiz posicional, no material.
BONUS_PIEZA_LIBRE = 1.5


class SobredefensaEvaluator:
    """Evalua el grado de sobredefensa de las piezas propias bajo presion."""

    def _contar_att_def(self, board: chess.Board, sq: int, color: chess.Color
                        ) -> Tuple[int, int, int]:
        """
        Cuenta atacantes y defensores de una casilla para un color dado.
        Retorna (total_att, total_def_normales, tiene_rey_defensor).
        """
        enemy_color = not color
        total_att = 0
        for s in board.attackers(enemy_color, sq):
            if board.piece_at(s):
                total_att += 1

        def_normales = 0
        tiene_rey = False
        for s in board.attackers(color, sq):
            p = board.piece_at(s)
            if not p:
                continue
            if s == sq:
                continue  # la pieza de la casilla no se defiende a si misma
            if p.piece_type == chess.KING:
                tiene_rey = True
            else:
                def_normales += 1
        return total_att, def_normales, tiene_rey

    def evaluar_sobredefensa_posicion(self, board: chess.Board, color: chess.Color
                                      ) -> Tuple[float, str]:
        """
        Bonus posicional total por sobredefensa en la posicion actual para `color`.
        Solo cuenta piezas propias atacadas (presion real) con exceso de defensores.
        """
        bonus_total = 0.0
        detalles = []
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if not p or p.color != color or p.piece_type == chess.KING:
                continue
            total_att, def_normales, tiene_rey = self._contar_att_def(board, sq, color)
            if total_att == 0:
                continue  # sin presion: no hay sobredefensa que libere piezas
            total_def = def_normales + (1 if tiene_rey else 0)
            if total_def > total_att:
                # Piezas NORMALES sobrantes (el rey no se "libera" para atacar).
                # Si el exceso se debe solo al rey, piezas_libres_normales = 0.
                exceso = total_def - total_att
                piezas_libres_normales = max(0, def_normales - total_att)
                # Si el rey es parte del exceso pero no hay normales sobrantes,
                # aun asi la posicion es solida pero no libera piezas -> sin bonus.
                if piezas_libres_normales > 0:
                    bonus = piezas_libres_normales * BONUS_PIEZA_LIBRE
                    bonus_total += bonus
                    detalles.append(
                        f"{chess.piece_name(p.piece_type)} en {chess.square_name(sq)} "
                        f"sobredefendido ({piezas_libres_normales} pieza(s) libre(s))"
                    )
        exp = ("Sobredefensa: " + "; ".join(detalles) + ".") if detalles else ""
        return bonus_total, exp

    def evaluar_sobredefensa_movimiento(self, board: chess.Board, move: chess.Move
                                        ) -> Tuple[float, str]:
        """
        Delta de sobredefensa que aporta `move`: sobredefensa(despues) - antes.
        Premia jugadas que sobredefienden (liberan piezas) y penaliza las que
        retiran un defensor necesario de una pieza bajo presion.
        """
        color = board.turn
        antes, _ = self.evaluar_sobredefensa_posicion(board, color)

        temp = board.copy(stack=False)
        temp.push(move)
        # Tras el push el turno cambio; el color que movio es `color`.
        despues, exp = self.evaluar_sobredefensa_posicion(temp, color)

        delta = despues - antes
        if abs(delta) < 0.01:
            return 0.0, ""
        if delta > 0:
            return delta, f"[Sobredefensa] {exp}"
        return delta, f"[Sobredefensa] Reduce la sobredefensa propia ({delta:+.1f}); revisa si liberas una pieza que debia seguir defendiendo."