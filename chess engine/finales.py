"""
Evaluador de conocimiento especifico de finales.

Implementa:
1. Conducción y victoria en finales de Reyes y Peones (Rey + Peones vs Rey / Ventaja de peones)
2. Acompañamiento del Rey a peones pasados hacia la coronación (King Escort)
3. Regla del cuadrado (peón pasado vs rey rival)
4. Oposición de reyes y casillas clave (Key Squares en K+P vs K)
5. Cadenas de peones y soporte mutuo
6. Regla de Tarrasch (torres detrás de peones pasados)
"""

import chess
from typing import Tuple, List, Optional

try:
    from .constantes import VALORES_PIEZAS, PIECE_NAMES_ES
except ImportError:
    from constantes import VALORES_PIEZAS, PIECE_NAMES_ES


class FinalesEvaluator:
    """
    Evaluador de conocimiento específico de finales.
    """

    def evaluar_final(self, board: chess.Board) -> Tuple[float, str]:
        """
        Evalúa la posición desde la perspectiva de finales (para board.turn).
        """
        if not self._es_final(board):
            return 0.0, ""

        scores = []
        explicaciones = []

        score_escort, exp_escort = self._evaluar_acompanamiento_peones(board)
        if score_escort != 0:
            scores.append(score_escort)
            explicaciones.append(exp_escort)

        score_cuad, exp_cuad = self._evaluar_regla_cuadrado(board)
        if score_cuad != 0:
            scores.append(score_cuad)
            explicaciones.append(exp_cuad)

        score_key, exp_key = self._evaluar_casillas_clave(board)
        if score_key != 0:
            scores.append(score_key)
            explicaciones.append(exp_key)

        score_op, exp_op = self._evaluar_oposicion(board)
        if score_op != 0:
            scores.append(score_op)
            explicaciones.append(exp_op)

        score_torre, exp_torre = self._evaluar_torres_final(board)
        if score_torre != 0:
            scores.append(score_torre)
            explicaciones.append(exp_torre)

        if scores:
            return sum(scores), " | ".join(explicaciones)
        return 0.0, ""

    def evaluar_movimiento_final(self, board_before: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalúa un movimiento específico en el final y genera su explicación pedagógica.
        """
        if not self._es_final(board_before):
            return 0.0, ""

        color = board_before.turn
        piece = board_before.piece_at(move.from_square)
        if not piece:
            return 0.0, ""

        from_sq = move.from_square
        to_sq = move.to_square
        from_file = chess.square_file(from_sq)
        from_rank = chess.square_rank(from_sq)
        to_file = chess.square_file(to_sq)
        to_rank = chess.square_rank(to_sq)
        to_name = chess.square_name(to_sq)

        enemy = not color
        my_king = to_sq if piece.piece_type == chess.KING else board_before.king(color)
        enemy_king = board_before.king(enemy)

        # 1. Movimiento del Rey en el Final
        if piece.piece_type == chess.KING:
            # A) Acompañamiento del rey a peón pasado propio
            my_pawns = [sq for sq in chess.SQUARES if board_before.piece_at(sq) == chess.Piece(chess.PAWN, color)]
            passed_pawns = [sq for sq in my_pawns if self._es_peon_pasado(board_before, sq, color)]

            if passed_pawns:
                best_pawn = max(passed_pawns, key=lambda sq: chess.square_rank(sq) if color == chess.WHITE else (7 - chess.square_rank(sq)))
                p_file = chess.square_file(best_pawn)
                p_rank = chess.square_rank(best_pawn)
                p_name = chess.square_name(best_pawn)

                prev_dist = max(abs(from_file - p_file), abs(from_rank - p_rank))
                new_dist = max(abs(to_file - p_file), abs(to_rank - p_rank))

                rel_rank_to = to_rank if color == chess.WHITE else (7 - to_rank)
                rel_rank_p = p_rank if color == chess.WHITE else (7 - p_rank)

                if new_dist < prev_dist:
                    return 35.0, f"Acompañamiento del Rey al peón pasado en {p_name} para asegurar su coronación."
                elif rel_rank_to > rel_rank_p and abs(to_file - p_file) <= 1:
                    return 45.0, f"El Rey se sitúa por delante del peón pasado en {p_name} controlando las casillas de avance."

            # B) Oposición de Reyes
            if enemy_king is not None:
                ek_file = chess.square_file(enemy_king)
                ek_rank = chess.square_rank(enemy_king)
                dist_opp = abs(to_file - ek_file) + abs(to_rank - ek_rank)
                if dist_opp == 2 and (to_file == ek_file or to_rank == ek_rank):
                    return 30.0, "Toma de la oposición de reyes para dominar las casillas clave y abrir paso a los peones."

            # C) Centralización activa del Rey
            prev_center_dist = max(abs(2 * from_file - 7), abs(2 * from_rank - 7))
            new_center_dist = max(abs(2 * to_file - 7), abs(2 * to_rank - 7))
            if new_center_dist < prev_center_dist:
                return 25.0, f"Centralización activa del Rey en {to_name} para dominar el tablero en el final."

            # D) Caza de peones rivales
            enemy_pawns = [sq for sq in chess.SQUARES if board_before.piece_at(sq) == chess.Piece(chess.PAWN, enemy)]
            if enemy_pawns:
                min_prev = min(max(abs(from_file - chess.square_file(sq)), abs(from_rank - chess.square_rank(sq))) for sq in enemy_pawns)
                min_new = min(max(abs(to_file - chess.square_file(sq)), abs(to_rank - chess.square_rank(sq))) for sq in enemy_pawns)
                if min_new < min_prev:
                    return 25.0, f"Marcha del Rey hacia los peones rivales para neutralizarlos y capturarlos."

        # 2. Movimiento de Peón en el Final
        elif piece.piece_type == chess.PAWN:
            rel_rank_to = to_rank if color == chess.WHITE else (7 - to_rank)
            is_passed = self._es_peon_pasado(board_before, from_sq, color)

            if move.promotion:
                promo_name = PIECE_NAMES_ES.get(move.promotion, "dama")
                return 90.0, f"Coronación exitosa del peón pasado en {to_name} a {promo_name}."

            if is_passed:
                # Regla del cuadrado
                if enemy_king is not None:
                    dist_promo = 7 - rel_rank_to
                    promo_sq_file = to_file
                    promo_sq_rank = 7 if color == chess.WHITE else 0
                    dist_ek = max(abs(chess.square_file(enemy_king) - promo_sq_file),
                                  abs(chess.square_rank(enemy_king) - promo_sq_rank))
                    if dist_promo < dist_ek:
                        return 60.0, f"Regla del cuadrado: el peón pasado avanza a {to_name} de forma imparable hacia la coronación."

                return 40.0, f"Avanza peón pasado peligroso en {to_name} aproximándolo a la coronación."

            # Cadenas de peones
            temp = board_before.copy(stack=False)
            temp.push(move)
            defended = temp.is_attacked_by(color, to_sq)
            if defended:
                return 20.0, f"Consolida la estructura de peones formando una cadena protegida en {to_name}."

        return 0.0, ""

    def _es_final(self, board: chess.Board) -> bool:
        """Determina si estamos en fase de final."""
        material_mayor = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type in (chess.QUEEN, chess.ROOK, chess.KNIGHT, chess.BISHOP):
                material_mayor += 1
        return material_mayor <= 6

    def _es_peon_pasado(self, board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
        """Determina si un peón es pasado."""
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

    def _evaluar_oposicion(self, board: chess.Board) -> Tuple[float, str]:
        """Evalúa la oposición de reyes."""
        rey_blanco = board.king(chess.WHITE)
        rey_negro = board.king(chess.BLACK)

        if rey_blanco is None or rey_negro is None:
            return 0.0, ""

        file_b = chess.square_file(rey_blanco)
        rank_b = chess.square_rank(rey_blanco)
        file_n = chess.square_file(rey_negro)
        rank_n = chess.square_rank(rey_negro)

        misma_columna = (file_b == file_n)
        misma_fila = (rank_b == rank_n)
        distancia = abs(rank_b - rank_n) + abs(file_b - file_n)

        if distancia == 2 and (misma_columna or misma_fila):
            tiene_oposicion = (board.turn == chess.WHITE)
            if tiene_oposicion:
                return 25.0, "Tiene la oposición: ventaja posicional decisiva en final de peones."
            else:
                return -25.0, "El rival tiene la oposición: desventaja en final de peones."

        return 0.0, ""

    def _evaluar_regla_cuadrado(self, board: chess.Board) -> Tuple[float, str]:
        """Evalúa si un peón pasado puede coronar usando la regla del cuadrado."""
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.piece_type != chess.PAWN:
                continue

            color = piece.color
            if not self._es_peon_pasado(board, sq, color):
                continue

            rank = chess.square_rank(sq)
            file = chess.square_file(sq)

            if color == chess.WHITE:
                distancia_coronacion = 7 - rank
                rank_coronacion = 7
            else:
                distancia_coronacion = rank
                rank_coronacion = 0

            rey_enemigo = board.king(not color)
            if rey_enemigo is None:
                continue

            file_rey = chess.square_file(rey_enemigo)
            rank_rey = chess.square_rank(rey_enemigo)

            distancia_rey = max(abs(file_rey - file), abs(rank_rey - rank_coronacion))

            if distancia_coronacion < distancia_rey or (color == board.turn and distancia_coronacion <= distancia_rey):
                sq_name = chess.square_name(sq)
                bonus = 60.0 + (distancia_rey - distancia_coronacion) * 10.0
                if color == board.turn:
                    return bonus, f"Peón pasado en {sq_name} corona antes de que el rey rival lo alcance (Regla del cuadrado)."
                else:
                    return -bonus, f"Peón pasado rival en {sq_name} corona antes de que nuestro rey lo alcance."

        return 0.0, ""

    def _evaluar_casillas_clave(self, board: chess.Board) -> Tuple[float, str]:
        """Evalúa el control de casillas clave en finales de rey y peón."""
        color = board.turn
        king_sq = board.king(color)
        if king_sq is None:
            return 0.0, ""

        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)
        king_rel_rank = kr if color == chess.WHITE else (7 - kr)

        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if not p or p.piece_type != chess.PAWN or p.color != color:
                continue
            if not self._es_peon_pasado(board, sq, color):
                continue

            pf = chess.square_file(sq)
            pr = chess.square_rank(sq)
            rel_rank = pr if color == chess.WHITE else (7 - pr)

            if abs(kf - pf) <= 1:
                if rel_rank <= 4 and king_rel_rank >= rel_rank + 2:
                    return 35.0, "El Rey ocupa las casillas clave frente al peón asegurando la victoria."
                elif rel_rank >= 5 and king_rel_rank >= rel_rank + 1:
                    return 35.0, "El Rey ocupa las casillas clave de avance frente al peón pasado."

        return 0.0, ""

    def _evaluar_acompanamiento_peones(self, board: chess.Board) -> Tuple[float, str]:
        """Evalúa la proximidad del rey a los peones pasados propios."""
        color = board.turn
        king_sq = board.king(color)
        if king_sq is None:
            return 0.0, ""

        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)

        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if not p or p.piece_type != chess.PAWN or p.color != color:
                continue
            if not self._es_peon_pasado(board, sq, color):
                continue

            pf = chess.square_file(sq)
            pr = chess.square_rank(sq)
            dist = max(abs(kf - pf), abs(kr - pr))
            if dist <= 2:
                return 20.0, "Rey activo escoltando de cerca al peón pasado."

        return 0.0, ""

    def _evaluar_torres_final(self, board: chess.Board) -> Tuple[float, str]:
        """Evalúa la actividad de torres en el final (Regla de Tarrasch)."""
        score = 0.0
        explicaciones = []

        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.piece_type != chess.ROOK:
                continue

            color = piece.color
            rank = chess.square_rank(sq)
            file = chess.square_file(sq)

            peon_pasado_delante = False
            step = 1 if color == chess.WHITE else -1
            r = rank + step
            while 0 <= r <= 7:
                p_sq = chess.square(file, r)
                p = board.piece_at(p_sq)
                if p and p.color == color and p.piece_type == chess.PAWN:
                    if self._es_peon_pasado(board, p_sq, color):
                        peon_pasado_delante = True
                    break
                elif p:
                    break
                r += step

            if not peon_pasado_delante:
                continue

            if color == chess.WHITE and rank >= 5:
                score += 10.0
                explicaciones.append(f"Torre blanca activa en {chess.square_name(sq)}.")
            elif color == chess.BLACK and rank <= 2:
                score += 10.0
                explicaciones.append(f"Torre negra activa en {chess.square_name(sq)}.")

            for pawn_sq in chess.SQUARES:
                pawn = board.piece_at(pawn_sq)
                if not pawn or pawn.piece_type != chess.PAWN or pawn.color != color:
                    continue

                pawn_file = chess.square_file(pawn_sq)
                pawn_rank = chess.square_rank(pawn_sq)

                if pawn_file == file:
                    if color == chess.WHITE and rank < pawn_rank:
                        score += 15.0
                        explicaciones.append("Torre detrás de peón pasado (Tarrasch).")
                    elif color == chess.BLACK and rank > pawn_rank:
                        score += 15.0
                        explicaciones.append("Torre detrás de peón pasado (Tarrasch).")

        if explicaciones:
            return score, " ".join(explicaciones)
        return 0.0, ""