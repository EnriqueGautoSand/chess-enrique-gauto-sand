import chess
from typing import Tuple, List, Dict, Any

try:
    from .intercambios.intercambios import IntercambiosEvaluator
    from .constantes import VALORES_PIEZAS
except (ImportError, ValueError):
    from intercambios.intercambios import IntercambiosEvaluator
    from constantes import VALORES_PIEZAS

class CapturasEvaluator:
    """
    Evaluador de Capturas Tácticas.
    Evalúa la ganancia real de material limpia o favorable.
    Las capturas que resultan en pérdida neta de material (ΔMaterial < 0) o cuelgan piezas de mayor valor
    son penalizadas proporcionalmente y jamás reciben bonificaciones positivas.
    """

    def __init__(self):
        self.intercambios_eval = IntercambiosEvaluator()

    def evaluar_captura_movimiento(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Calcula el puntaje de una captura evaluando la ganancia o pérdida neta de material (ΔMaterial).
        """
        if not board.is_capture(move):
            return 0.0, ""

        to_sq = move.to_square
        target = board.piece_at(to_sq)
        piece = board.piece_at(move.from_square)

        if not target or not piece:
            return 0.0, ""

        target_val = VALORES_PIEZAS.get(target.piece_type, 1.0)
        moving_val = VALORES_PIEZAS.get(piece.piece_type, 1.0)

        mat_neto, es_suicida, exp_int = self.intercambios_eval.simular_secuencia_intercambio(board, move)

        target_name = chess.piece_name(target.piece_type)
        piece_name = chess.piece_name(piece.piece_type)
        to_sq_name = chess.square_name(to_sq)

        if es_suicida or mat_neto < 0:
            score_desfavorable = mat_neto * 10.0
            return score_desfavorable, f"Entrega desfavorecida: cambia {piece_name} por {target_name} en {to_sq_name} ({mat_neto:+.1f})."

        temp_board = board.copy(stack=False)
        temp_board.push(move)

        enemy_color = temp_board.turn
        is_attacked = temp_board.is_attacked_by(enemy_color, to_sq)

        if not is_attacked:
            score = 60.0 + (target_val * 10.0) + (mat_neto * 5.0)
            return score, f"Captura {target_name} indefenso/a en {to_sq_name} con {piece_name} ganando material limpio (+{target_val:.1f})."
        else:
            score = 20.0 + (mat_neto * 10.0)
            return score, f"Captura {target_name} en {to_sq_name} realizando un intercambio favorable (+{mat_neto:.1f})."

    def evaluar_capturas_oponente(self, board: chess.Board) -> List[Dict[str, Any]]:
        """
        Evalua las capturas que el OPONENTE puede hacer sobre nuestras piezas.
        CORRECCION: Simula el turno del oponente para obtener sus movimientos legales.
        """
        amenazas = []
        enemy_color = not board.turn

        # CORRECCION: Simular turno del oponente
        board_oponente = board.copy(stack=False)
        board_oponente.turn = enemy_color

        for move in board_oponente.legal_moves:
            if board_oponente.is_capture(move):
                target = board_oponente.piece_at(move.to_square)
                piece = board_oponente.piece_at(move.from_square)
                # Verificar que la pieza capturada sea NUESTRA (del color original)
                if target and target.color == board.turn:
                    t_val = VALORES_PIEZAS.get(target.piece_type, 1.0)
                    p_val = VALORES_PIEZAS.get(piece.piece_type, 1.0) if piece else 1.0
                    amenazas.append({
                        "move": move,
                        "target_square": move.to_square,
                        "target_val": t_val,
                        "attacker_val": p_val,
                        "gain": t_val - p_val if p_val < t_val else 0.0
                    })
        amenazas.sort(key=lambda x: x["target_val"], reverse=True)
        return amenazas
