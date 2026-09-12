"""
Evaluador de ataques a la descubierta.

Un ataque a la descubierta ocurre cuando al mover una pieza,
se descubre una linea de ataque de otra pieza propia.
"""

import chess
from typing import Tuple, Dict

try:
    from .constantes import VALORES_PIEZAS, PIECE_NAMES_ES
    from .base_evaluator import BaseEvaluator
except ImportError:
    from constantes import VALORES_PIEZAS, PIECE_NAMES_ES
    from base_evaluator import BaseEvaluator


class DescubiertaEvaluator(BaseEvaluator):
    """
    Evaluador de ataques a la descubierta.
    
    Logica:
    1. Antes del movimiento: calcular ataques de piezas deslizantes propias
    2. Despues del movimiento: recalcular ataques
    3. Si aparecen nuevos ataques sobre piezas enemigas valiosas = DESCUBIERTA
    """
    
    def evaluar_descubierta_movimiento(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalua si un movimiento crea un ataque a la descubierta.
        """
        piece = board.piece_at(move.from_square)
        if not piece:
            return 0.0, ""
        
        our_color = piece.color
        enemy_color = not our_color
        
        # Pre-filtro Bitboard: La pieza que se mueve debe estar sobre la línea de visión de alguna pieza propia deslizante
        sliders = board.occupied_co[our_color] & (board.bishops | board.rooks | board.queens)
        if chess.BB_SQUARES[move.from_square] & sliders:
            sliders ^= chess.BB_SQUARES[move.from_square]
            
        if not sliders:
            return 0.0, ""
            
        # Si ninguna pieza deslizante propia puede alcanzar rayos sobre from_square, no hay descubierta
        from_bb = chess.BB_SQUARES[move.from_square]
        posible_descubierta = False
        for s_sq in chess.scan_reversed(sliders):
            s_piece = board.piece_at(s_sq)
            if not s_piece:
                continue
            if s_piece.piece_type == chess.BISHOP and (chess.BB_DIAG_MASKS[s_sq] & from_bb):
                posible_descubierta = True
                break
            elif s_piece.piece_type == chess.ROOK and ((chess.BB_RANK_MASKS[s_sq] | chess.BB_FILE_MASKS[s_sq]) & from_bb):
                posible_descubierta = True
                break
            elif s_piece.piece_type == chess.QUEEN and ((chess.BB_DIAG_MASKS[s_sq] | chess.BB_RANK_MASKS[s_sq] | chess.BB_FILE_MASKS[s_sq]) & from_bb):
                posible_descubierta = True
                break

        if not posible_descubierta:
            return 0.0, ""

        ataques_antes = self._obtener_ataques_a_piezas_valiosas(board, our_color, enemy_color)
        
        board.push(move)
        ataques_despues = self._obtener_ataques_a_piezas_valiosas(board, our_color, enemy_color)
        is_chk = board.is_check()
        
        nuevos_ataques = []
        for sq, info in ataques_despues.items():
            atacantes_previos = ataques_antes.get(sq, {}).get("atacantes_set", set())
            nuevos_atacantes = info["atacantes_set"] - atacantes_previos - {move.to_square}
            if nuevos_atacantes:
                nuevos_ataques.append((sq, info))
        
        if nuevos_ataques:
            mejor = max(nuevos_ataques, key=lambda x: x[1]["valor"])
            sq_objetivo = mejor[0]
            pieza_objetivo = board.piece_at(sq_objetivo)
            board.pop()
            
            if pieza_objetivo:
                p_name = PIECE_NAMES_ES.get(pieza_objetivo.piece_type, "pieza")
                sq_name = chess.square_name(sq_objetivo)
                moving_name = PIECE_NAMES_ES.get(piece.piece_type, "pieza")
                
                score = 35.0 + (mejor[1]["valor"] * 5.0)
                
                if is_chk:
                    score += 25.0
                    return score, f"Jaque a la descubierta: mueve {moving_name} y descubre ataque sobre {p_name} en {sq_name}."
                
                return score, f"Ataque a la descubierta: al mover {moving_name}, descubre ataque sobre {p_name} en {sq_name}."
        else:
            board.pop()
        
        return 0.0, ""
    
    def _obtener_ataques_a_piezas_valiosas(self, board: chess.Board, 
                                            our_color: chess.Color, 
                                            enemy_color: chess.Color) -> Dict[int, Dict]:
        """
        Obtiene todas las casillas con piezas enemigas valiosas atacadas por nosotros.
        """
        ataques = {}
        
        # Filtro de bitboard para piezas valiosas del oponente (excluyendo peones y rey)
        enemy_valuable = board.occupied_co[enemy_color] & ~board.pawns & ~board.kings
        for sq in chess.scan_reversed(enemy_valuable):
            pt = board.piece_type_at(sq)
            val = VALORES_PIEZAS.get(pt, 1.0)
            
            attackers = board.attackers(our_color, sq)
            if attackers:
                ataques[sq] = {
                    "valor": val,
                    "atacantes": len(attackers),
                    "atacantes_set": set(attackers)
                }
        
        return ataques
    
    def evaluar(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """Implementacion de la interfaz base."""
        return self.evaluar_descubierta_movimiento(board, move)