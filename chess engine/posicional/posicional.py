import chess
from typing import Tuple, Dict, List
from .desarrollo import DesarrolloEvaluator
from .estado_piezas import EstadoPiezasEvaluator
from .estado_peones import EstadoPeonesEvaluator
from .sobredefensa import SobredefensaEvaluator

try:
    from ..intercambios.intercambios import IntercambiosEvaluator
except ImportError:
    from intercambios.intercambios import IntercambiosEvaluator

class PosicionalEvaluator:
    """
    Evaluador posicional principal.
    Combina el análisis de desarrollo, estado de piezas, estado de peones,
    intercambios posicionales (Alfil Bueno/Malo, Caballo Bueno/Malo, Peones Pasados Defendibles)
    y penaliza la repetición pasiva de movimientos de piezas (ej. idas y vueltas de Torre sin plan).
    """

    VALORES_PIEZAS = {
        chess.PAWN: 1.0,
        chess.KNIGHT: 3.0,
        chess.BISHOP: 3.25,
        chess.ROOK: 5.0,
        chess.QUEEN: 9.0,
        chess.KING: 200.0
    }

    def __init__(self):
        self.evaluador_desarrollo = DesarrolloEvaluator()
        self.evaluador_piezas = EstadoPiezasEvaluator()
        self.evaluador_peones = EstadoPeonesEvaluator()
        self.evaluador_intercambios = IntercambiosEvaluator()
        self.evaluador_sobredefensa = SobredefensaEvaluator()

    def es_casilla_segura(self, board: chess.Board, move: chess.Move) -> Tuple[bool, str]:
        mat_neto, es_suicida, exp = self.evaluador_intercambios.simular_secuencia_intercambio(board, move)
        if es_suicida:
            return False, exp
        return True, ""

    def evaluar_amenazas_rival_tras_movimiento(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        temp_board = board.copy(stack=False)
        temp_board.push(move)

        if temp_board.is_game_over():
            return 0.0, ""

        max_material_op = 0.0
        exp_op = ""

        for m_op in temp_board.legal_moves:
            b_op = temp_board.copy(stack=False)
            b_op.push(m_op)
            if b_op.is_checkmate():
                return 10000.0, "Permite un jaque mate del oponente en la respuesta."

            if temp_board.is_capture(m_op):
                mat_neto, es_suic, exp_sub = self.evaluador_intercambios.simular_secuencia_intercambio(temp_board, m_op)
                if mat_neto > max_material_op:
                    max_material_op = mat_neto
                    exp_op = f"Permite al rival capturar en {chess.square_name(m_op.to_square)} ganando +{mat_neto:.1f} de material."

            if temp_board.gives_check(m_op):
                for m_escape in b_op.legal_moves:
                    b_escape = b_op.copy(stack=False)
                    b_escape.push(m_escape)
                    if b_escape.is_checkmate():
                        return 10000.0, "Permite una red de mate del oponente tras el jaque."
                    for m_followup in b_escape.legal_moves:
                        if b_escape.is_capture(m_followup):
                            # USE SEE TO CHECK IF CAPTURE IS ACTUALLY WINNING MATERIAL
                            mat_neto, es_suic, exp_sub = self.evaluador_intercambios.simular_secuencia_intercambio(b_escape, m_followup)
                            if mat_neto >= 3.0 and mat_neto > max_material_op:
                                t_p_f = b_escape.piece_at(m_followup.to_square)
                                max_material_op = mat_neto
                                exp_op = f"Permite un jaque del rival seguido de un ataque ganador en {chess.square_name(m_followup.to_square)} (+{mat_neto:.1f})."

        return max_material_op, exp_op

    def evaluar_consecuencias_intercambio(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        to_sq = move.to_square
        piece = board.piece_at(move.from_square)
        if not piece:
            return 0.0, ""

        color = piece.color
        temp_board = board.copy(stack=False)
        temp_board.push(move)

        enemy_color = temp_board.turn

        if not temp_board.is_attacked_by(enemy_color, to_sq):
            return 0.0, ""

        enemy_captures = [m for m in temp_board.legal_moves if m.to_square == to_sq]
        if not enemy_captures:
            return 0.0, ""

        enemy_move = enemy_captures[0]
        temp_board.push(enemy_move)

        our_recaptures = [m for m in temp_board.legal_moves if m.to_square == to_sq]
        if not our_recaptures:
            return 0.0, ""

        recapture_move = our_recaptures[0]
        recapturing_piece = temp_board.piece_at(recapture_move.from_square)
        temp_board.push(recapture_move)

        penalty = 0.0
        explicaciones = []

        if recapturing_piece and recapturing_piece.piece_type == chess.PAWN:
            file_idx = chess.square_file(to_sq)
            file_name = chess.FILE_NAMES[file_idx]

            pawns_before = sum(
                1 for r in range(8)
                if board.piece_at(chess.square(file_idx, r)) and
                board.piece_at(chess.square(file_idx, r)).color == color and
                board.piece_at(chess.square(file_idx, r)).piece_type == chess.PAWN
            )
            pawns_after = sum(
                1 for r in range(8)
                if temp_board.piece_at(chess.square(file_idx, r)) and
                temp_board.piece_at(chess.square(file_idx, r)).color == color and
                temp_board.piece_at(chess.square(file_idx, r)).piece_type == chess.PAWN
            )

            if pawns_after >= 2 and pawns_after > pawns_before:
                penalty -= 30.0
                explicaciones.append(f"Evita el intercambio en {chess.square_name(to_sq)} porque genera peones doblados en la columna {file_name}")

        king_sq = temp_board.king(color)
        if king_sq is not None:
            king_file = chess.square_file(king_sq)
            if king_file in (6, 2):
                shield_files = [f for f in [king_file - 1, king_file, king_file + 1] if 0 <= f <= 7]

                shield_pawns_before = sum(
                    1 for f in shield_files for r in range(8)
                    if board.piece_at(chess.square(f, r)) and
                    board.piece_at(chess.square(f, r)).color == color and
                    board.piece_at(chess.square(f, r)).piece_type == chess.PAWN
                )
                shield_pawns_after = sum(
                    1 for f in shield_files for r in range(8)
                    if temp_board.piece_at(chess.square(f, r)) and
                    temp_board.piece_at(chess.square(f, r)).color == color and
                    temp_board.piece_at(chess.square(f, r)).piece_type == chess.PAWN
                )

                if shield_pawns_after < shield_pawns_before:
                    penalty -= 35.0
                    explicaciones.append("Evita el intercambio porque destruye la cobertura de peones que protege al Rey")

        if penalty < 0:
            return penalty, ". ".join(explicaciones) + "."
        return 0.0, ""

    def evaluar_jugada_posicional(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        es_segura, razon_insegura = self.es_casilla_segura(board, move)
        if not es_segura:
            return -100.0, f"[Insegura] {razon_insegura}"

        mat_perdido, exp_op = self.evaluar_amenazas_rival_tras_movimiento(board, move)
        if mat_perdido >= 9000.0:
            return -10000.0, f"[FATAL] {exp_op}"
        if mat_perdido > 0.0:
            return -100.0, f"[Refutada por Pérdida Material] {exp_op}"

        # Penalización por oscilación/repetición pasiva de pieza (ej: Rg8 -> Rh8 -> Rg8)
        if len(board.move_stack) >= 2:
            prev_move = board.move_stack[-2]
            if move.from_square == prev_move.to_square and move.to_square == prev_move.from_square:
                if not board.is_capture(move) and not board.gives_check(move):
                    p_curr = board.piece_at(move.from_square)
                    p_name = chess.piece_name(p_curr.piece_type) if p_curr else "pieza"
                    return -40.0, f"Evita oscilación pasiva: Regresar {p_name} a {chess.square_name(move.to_square)} no desarrolla el juego."

        score_intercambio_pos, exp_intercambio_pos = self.evaluador_intercambios.evaluar_intercambio_posicional(board, move)
        score_intercambio_est, exp_intercambio_est = self.evaluar_consecuencias_intercambio(board, move)
        if score_intercambio_est < 0:
            return score_intercambio_est, exp_intercambio_est

        score_des, exp_des = self.evaluador_desarrollo.evaluar_desarrollo_movimiento(board, move)
        score_pie, exp_pie = self.evaluador_piezas.evaluar_mejora_pieza(board, move)
        score_peo, exp_peo = self.evaluador_peones.evaluar_estructura_peones(board, move)
        # Sobredefensa: concepto POSICIONAL (libera piezas por exceso de defensores).
        # Vive aqui, NO en el SEE de intercambios.py (que es puro balance de material).
        score_sob, exp_sob = self.evaluador_sobredefensa.evaluar_sobredefensa_movimiento(board, move)

        total_score = score_des + score_pie + score_peo + score_intercambio_pos + score_sob

        explicaciones = [exp for exp in [exp_des, exp_pie, exp_peo, exp_intercambio_pos, exp_sob] if exp]

        if total_score > 0 and explicaciones:
            explicacion_final = " ".join(explicaciones)
        else:
            piece = board.piece_at(move.from_square)
            piece_name = "pieza"
            if piece:
                names = {chess.PAWN: "peón", chess.KNIGHT: "caballo", chess.BISHOP: "alfil",
                         chess.ROOK: "torre", chess.QUEEN: "dama", chess.KING: "rey"}
                piece_name = names.get(piece.piece_type, "pieza")
            to_sq_name = chess.square_name(move.to_square)
            total_score = max(total_score, 1.0)
            explicacion_final = f"Mueve posicionalmente {piece_name} a {to_sq_name} manteniendo la solidez estructural."

        return total_score, explicacion_final

    def obtener_mejores_movimientos_posicionales(self, board: chess.Board) -> List[Dict]:
        resultados = []
        for move in board.legal_moves:
            score, exp = self.evaluar_jugada_posicional(board, move)
            if score > -9000.0:
                resultados.append({
                    "move": move,
                    "score": score,
                    "explanation": exp
                })
        resultados.sort(key=lambda x: x["score"], reverse=True)
        return resultados
