import chess
from typing import Dict, List, Tuple, Optional

class JaquesEvaluator:
    """
    Evaluador de jaques para el motor de ajedrez humano.
    Analiza jaques propios hacia el oponente (incluyendo jaques generados por la torre al enrocar)
    y jaques potenciales del oponente hacia nosotros.
    """

    PIECE_NAMES_ES = {
        chess.PAWN: "peón",
        chess.KNIGHT: "caballo",
        chess.BISHOP: "alfil",
        chess.ROOK: "torre",
        chess.QUEEN: "dama",
        chess.KING: "rey"
    }

    def __init__(self):
        pass

    def evaluar_jaque_movimiento(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalúa si un movimiento específico produce un jaque y calcula su valor y explicación.
        """
        if not board.gives_check(move):
            return 0.0, ""

        temp_board = board.copy(stack=False)
        piece = temp_board.piece_at(move.from_square)
        piece_name = self.PIECE_NAMES_ES.get(piece.piece_type, "pieza") if piece else "pieza"
        to_sq_name = chess.square_name(move.to_square)

        # Si el movimiento que da jaque es un enroque (jaque con la torre que se mueve)
        is_castling_check = board.is_castling(move)

        temp_board.push(move)

        # 1. Jaque Mate
        if temp_board.is_checkmate():
            if is_castling_check:
                return 10000.0, f"¡Jaque mate directo al enrocar con la torre!"
            return 10000.0, f"¡Jaque mate directo con {piece_name} en {to_sq_name}!"

        score = 35.0
        explicaciones = []

        if is_castling_check:
            explicaciones.append("el enroque activa la torre dando jaque al rey enemigo")
        else:
            # Verificar si la pieza que da jaque queda indefensa ante el enemigo
            is_attacked_by_enemy = temp_board.is_attacked_by(temp_board.turn, move.to_square)
            is_defended_by_us = temp_board.is_attacked_by(not temp_board.turn, move.to_square)

            if is_attacked_by_enemy and not is_defended_by_us:
                score = 0.0
                explicaciones.append(f"da jaque suicida con {piece_name} en {to_sq_name}")
            else:
                explicaciones.append(f"da jaque al rey enemigo con {piece_name} en {to_sq_name}")

        # 2. Jaque a la descubierta o doble jaque
        checkers = temp_board.checkers()
        if len(checkers) > 1:
            score += 40.0
            explicaciones.append("es un jaque doble devastador")

        explicacion_final = "Se " + " y ".join(explicaciones) + "."
        return score, explicacion_final

    def obtener_jaques_nuestros(self, board: chess.Board) -> List[Dict]:
        jaques = []
        for move in board.legal_moves:
            score, exp = self.evaluar_jaque_movimiento(board, move)
            if score > 0:
                jaques.append({
                    "move": move,
                    "score": score,
                    "explanation": exp
                })
        jaques.sort(key=lambda x: x["score"], reverse=True)
        return jaques

    def evaluar_jaques_oponente(self, board: chess.Board) -> List[Dict]:
        board_copia = board.copy(stack=False)
        board_copia.turn = not board.turn  # Simular turno del oponente

        jaques_oponente = []
        for move in board_copia.legal_moves:
            if board_copia.gives_check(move):
                piece = board_copia.piece_at(move.from_square)
                p_name = self.PIECE_NAMES_ES.get(piece.piece_type, "pieza") if piece else "pieza"
                to_sq = chess.square_name(move.to_square)
                
                jaques_oponente.append({
                    "move": move,
                    "piece_name": p_name,
                    "target_square": to_sq,
                    "explanation": f"El oponente amenazaría con jaque de {p_name} en {to_sq}"
                })
        return jaques_oponente
