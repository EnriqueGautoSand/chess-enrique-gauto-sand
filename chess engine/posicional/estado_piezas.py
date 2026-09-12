import chess
from typing import Tuple

class EstadoPiezasEvaluator:
    """
    Evaluador del estado y actividad de las piezas.
    Premia ubicar piezas en mejores casillas (outposts, columnas abiertas, 7ma fila, movilidad).
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

    def evaluar_mejora_pieza(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalúa si un movimiento mejora la ubicación y actividad posicional de una pieza.
        :param board: Tablero actual.
        :param move: Movimiento candidato.
        :return: (score, explicacion)
        """
        piece = board.piece_at(move.from_square)
        if not piece or piece.piece_type == chess.PAWN:
            return 0.0, ""

        color = piece.color
        piece_type = piece.piece_type
        piece_name = self.PIECE_NAMES_ES.get(piece_type, "pieza")
        from_sq = move.from_square
        to_sq = move.to_square
        to_sq_name = chess.square_name(to_sq)

        file_to = chess.square_file(to_sq)
        rank_to = chess.square_rank(to_sq)

        score = 0.0
        explicaciones = []

        # 1. TORRES en columnas abiertas o semiabiertas
        if piece_type == chess.ROOK:
            # Verificar si la columna no tiene peones (columna abierta) o sólo peones del oponente (semiabierta)
            pawns_on_file = [
                board.piece_at(chess.square(file_to, r))
                for r in range(8)
                if board.piece_at(chess.square(file_to, r)) and board.piece_at(chess.square(file_to, r)).piece_type == chess.PAWN
            ]
            own_pawns_on_file = [p for p in pawns_on_file if p.color == color]

            if len(pawns_on_file) == 0:
                score += 18.0
                explicaciones.append(f"Ubica la torre en la columna abierta {chess.FILE_NAMES[file_to]}")
            elif len(own_pawns_on_file) == 0:
                score += 10.0
                explicaciones.append(f"Ubica la torre en la columna semiabierta {chess.FILE_NAMES[file_to]}")

            # Torre en 7ma fila (2da para negras)
            fila_septima = 6 if color == chess.WHITE else 1
            if rank_to == fila_septima:
                score += 20.0
                explicaciones.append(f"Penetra con la torre en la 7ª fila ({to_sq_name}) atacando la base enemiga")

        # 2. CABALLOS en Puestos Avanzados (Outposts)
        if piece_type == chess.KNIGHT:
            # Puesto avanzado: 4ª, 5ª o 6ª fila, defendido por peón propio
            filas_outpost = {chess.WHITE: (3, 4, 5), chess.BLACK: (2, 3, 4)}
            if rank_to in filas_outpost[color]:
                temp_board = board.copy(stack=False)
                temp_board.push(move)
                is_defended_by_pawn = False
                attackers = temp_board.attackers(color, to_sq)
                for att_sq in attackers:
                    att_piece = temp_board.piece_at(att_sq)
                    if att_piece and att_piece.piece_type == chess.PAWN:
                        is_defended_by_pawn = True
                        break

                if is_defended_by_pawn:
                    score += 22.0
                    explicaciones.append(f"Establece un potente puesto avanzado de caballo en {to_sq_name}")

        # 3. ALFILES en diagonales activas
        if piece_type == chess.BISHOP:
            # Evaluar si la casilla destino otorga mayor alcance diagonal
            temp_board = board.copy(stack=False)
            temp_board.push(move)
            attacks = len(temp_board.attacks(to_sq))
            if attacks >= 7:
                score += 12.0
                explicaciones.append(f"Activa el alfil en la gran diagonal con alta movilidad ({to_sq_name})")

        # 4. Aumento general de movilidad de la pieza
        temp_board = board.copy(stack=False)
        attacks_before = len(board.attacks(from_sq))
        temp_board.push(move)
        attacks_after = len(temp_board.attacks(to_sq))

        if attacks_after > attacks_before + 3 and score == 0.0:
            score += 8.0
            explicaciones.append(f"Mejora la movilidad y alcance del {piece_name} moviéndolo a {to_sq_name}")

        if score > 0:
            exp_text = ". ".join(explicaciones)
            if not exp_text.endswith("."):
                exp_text += "."
            return score, exp_text

        return 0.0, ""
