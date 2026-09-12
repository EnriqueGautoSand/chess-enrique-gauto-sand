import chess
from typing import Tuple

class EstadoPeonesEvaluator:
    """
    Evaluador de la estructura de peones.
    Evalúa la creación de peones pasados, solidez de cadenas, prevención de peones aislados o doblados.
    """

    def __init__(self):
        pass

    def es_peon_pasado(self, board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
        """
        Determina si un peón en una casilla dada es un peón pasado.
        Un peón es pasado si no hay peones enemigos por delante en su columna ni en columnas adyacentes.
        """
        file_idx = chess.square_file(square)
        rank_idx = chess.square_rank(square)

        files_to_check = [f for f in range(file_idx - 1, file_idx + 2) if 0 <= f <= 7]
        enemy_color = not color

        if color == chess.WHITE:
            ranks_ahead = range(rank_idx + 1, 8)
        else:
            ranks_ahead = range(0, rank_idx)

        for f in files_to_check:
            for r in ranks_ahead:
                piece = board.piece_at(chess.square(f, r))
                if piece and piece.color == enemy_color and piece.piece_type == chess.PAWN:
                    return False
        return True

    def evaluar_estructura_peones(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalúa el movimiento desde la perspectiva de la estructura de peones.
        """
        piece = board.piece_at(move.from_square)
        if not piece or piece.piece_type != chess.PAWN:
            return 0.0, ""

        color = piece.color
        to_sq = move.to_square
        to_sq_name = chess.square_name(to_sq)

        score = 0.0
        explicaciones = []

        # 1. Peón pasado
        if self.es_peon_pasado(board, to_sq, color):
            fila = chess.square_rank(to_sq)
            avance_val = (fila - 1) if color == chess.WHITE else (6 - fila)
            score += 20.0 + (avance_val * 5.0)
            explicaciones.append(f"Avanza peón pasado peligroso en {to_sq_name} aproximándolo a la promoción")

        # 2. Defiende o forma cadena de peones
        temp_board = board.copy(stack=False)
        temp_board.push(move)

        is_defended_by_pawn = False
        attackers = temp_board.attackers(color, to_sq)
        for att_sq in attackers:
            att_piece = temp_board.piece_at(att_sq)
            if att_piece and att_piece.piece_type == chess.PAWN and att_sq != to_sq:
                is_defended_by_pawn = True
                break

        if is_defended_by_pawn and score == 0.0:
            score += 8.0
            explicaciones.append(f"Consolida la estructura de peones formando una cadena firme en {to_sq_name}")

        if score > 0:
            exp_text = ". ".join(explicaciones)
            if not exp_text.endswith("."):
                exp_text += "."
            return score, exp_text

        return 0.0, ""

    def evaluar_peones_debiles(self, board: chess.Board, color: chess.Color) -> Tuple[float, str]:
        """
        Evalúa peones débiles como debilidad estática.
        - Peón aislado: Sin peones propios en columnas adyacentes
        - Peón doblado: Dos peones propios en la misma columna
        - Peón retrasado: Detrás de peones adyacentes, no puede avanzar seguro
        """
        penalty = 0.0
        explicaciones = []

        # Mapear peones por columna
        peones_por_columna = {f: [] for f in range(8)}

        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                file = chess.square_file(sq)
                rank = chess.square_rank(sq)
                peones_por_columna[file].append(rank)

        for file, ranks in peones_por_columna.items():
            # Peones doblados
            if len(ranks) >= 2:
                penalty -= 10.0 * (len(ranks) - 1)
                explicaciones.append(f"Peones doblados en columna {chess.FILE_NAMES[file]}.")

            # Peón aislado
            columnas_adyacentes = [f for f in [file-1, file+1] if 0 <= f <= 7]
            tiene_vecino = any(len(peones_por_columna[f]) > 0 for f in columnas_adyacentes)

            if not tiene_vecino and len(ranks) > 0:
                penalty -= 8.0
                explicaciones.append(f"Peón aislado en columna {chess.FILE_NAMES[file]}.")

            # Peón retrasado
            for rank in ranks:
                es_retrasado = True
                for f in columnas_adyacentes:
                    for r in peones_por_columna[f]:
                        if color == chess.WHITE:
                            if r >= rank:
                                es_retrasado = False
                        else:
                            if r <= rank:
                                es_retrasado = False

                if es_retrasado and len(columnas_adyacentes) > 0:
                    penalty -= 5.0
                    explicaciones.append(f"Peón retrasado en {chess.FILE_NAMES[file]}{rank+1}.")

        if explicaciones:
            return penalty, " ".join(explicaciones)
        return 0.0, ""