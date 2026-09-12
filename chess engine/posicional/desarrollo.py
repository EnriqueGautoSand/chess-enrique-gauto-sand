import chess
from typing import Tuple

class DesarrolloEvaluator:
    """
    Evaluador de desarrollo en la fase de apertura y medio juego temprano.
    Prioriza de forma ABSOLUTA la seguridad del Rey (Enroque), sacar piezas menores y dominar el centro.
    """

    PIECE_NAMES_ES = {
        chess.PAWN: "peón",
        chess.KNIGHT: "caballo",
        chess.BISHOP: "alfil",
        chess.ROOK: "torre",
        chess.QUEEN: "dama",
        chess.KING: "rey"
    }

    CASILLAS_CENTRO = {chess.D4, chess.E4, chess.D5, chess.E5}
    CASILLAS_AMPLIO_CENTRO = {
        chess.C4, chess.D4, chess.E4, chess.F4,
        chess.C5, chess.D5, chess.E5, chess.F5,
        chess.C3, chess.D3, chess.E3, chess.F3,
        chess.C6, chess.D6, chess.E6, chess.F6
    }

    def __init__(self):
        pass

    def evaluar_desarrollo_movimiento(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalúa la contribución al desarrollo y la prioridad de la seguridad del rey.
        :param board: Tablero actual.
        :param move: Movimiento candidato.
        :return: (score, explicacion)
        """
        piece = board.piece_at(move.from_square)
        if not piece:
            return 0.0, ""

        color = piece.color
        piece_type = piece.piece_type
        piece_name = self.PIECE_NAMES_ES.get(piece_type, "pieza")
        from_sq = move.from_square
        to_sq = move.to_square
        to_sq_name = chess.square_name(to_sq)

        fullmove_number = board.fullmove_number

        # 1. PRIORIDAD ABSOLUTA: ENROQUE PARA LA SEGURIDAD DEL REY
        if board.is_castling(move):
            tipo_enroque = "corto" if chess.square_file(to_sq) > chess.square_file(from_sq) else "largo"
            return 60.0, f"Prioridad de Seguridad del Rey: Enroca {tipo_enroque} para poner a salvo al Rey y conectar las torres."

        score = 0.0
        explicaciones = []

        # 2. EVALUAR DEBILITAMIENTO DEL ESCUDO DEL REY TRAS EL ENROQUE
        king_sq = board.king(color)
        if king_sq is not None:
            king_file = chess.square_file(king_sq)
            # Si el rey ya está enrocado en g1/g8 o c1/c8
            if king_file in (6, 2):
                if piece_type == chess.PAWN:
                    from_file = chess.square_file(from_sq)
                    if abs(from_file - king_file) <= 1 and fullmove_number < 25:
                        score -= 15.0
                        explicaciones.append("avanza peón del escudo del Rey debilitando su estructura protectora")

        # 3. Desarrollo de piezas menores (Caballos y Alfiles) desde primera fila
        filas_iniciales = {chess.WHITE: 0, chess.BLACK: 7}
        fila_origen = chess.square_rank(from_sq)

        if piece_type in (chess.KNIGHT, chess.BISHOP) and fila_origen == filas_iniciales[color]:
            score += 15.0
            explicaciones.append(f"Desarrolla el {piece_name} desde su casilla inicial hacia {to_sq_name}")

        # 4. Ocupación o control del centro
        if to_sq in self.CASILLAS_CENTRO:
            score += 12.0
            explicaciones.append(f"ocupa el centro en {to_sq_name}")
        elif to_sq in self.CASILLAS_AMPLIO_CENTRO and piece_type in (chess.KNIGHT, chess.BISHOP):
            score += 6.0
            explicaciones.append(f"apunta al centro extendido desde {to_sq_name}")

        # 5. Movimiento de peón central en la apertura (e2-e4, d2-d4, e7-e5, d7-d5)
        if piece_type == chess.PAWN:
            if from_sq in (chess.E2, chess.D2, chess.E7, chess.D7) and to_sq in self.CASILLAS_CENTRO:
                score += 14.0
                explicaciones.append(f"Avanza el peón central a {to_sq_name} abriendo diagonales y dominando el centro")

        # 6. Penalización por sacar la Dama demasiado temprano
        if piece_type == chess.QUEEN and fullmove_number < 6 and score < 5.0:
            score -= 10.0
            explicaciones.append("desarrolla la dama prematuramente antes de desarrollar piezas menores")

        if score > 0:
            exp_text = ". ".join(explicaciones) if explicaciones else f"Mejora el desarrollo con {piece_name} a {to_sq_name}."
            if not exp_text.endswith("."):
                exp_text += "."
            return score, exp_text

        return 0.0, ""
