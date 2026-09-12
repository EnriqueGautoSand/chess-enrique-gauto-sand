import chess
from typing import Tuple, List, Dict, Any, Optional

try:
    from ..constantes import VALORES_PIEZAS
except ImportError:
    try:
        from constantes import VALORES_PIEZAS
    except ImportError:
        from ..constantes import VALORES_PIEZAS


class IntercambiosEvaluator:
    """
    Evaluador de Secuencias de Intercambio y Calidad de Piezas (Tactico y Posicional).
    Calcula matematicamente el saldo neto de material en la secuencia completa
    de capturas/recapturas sobre una casilla, e identifica si la jugada deja colgada alguna otra pieza de mayor valor,
    o entrega la Dama/Pieza mayor a cambio de piezas inferiores.

    El SEE (Static Exchange Evaluation) simula la secuencia de capturas y recapturas
    sobre una casilla para determinar si el intercambio es favorable, equivalente o desfavorable.
    Por ejemplo: si un caballo captura un alfil en una casilla defendida por un peon,
    el SEE calcula: +3.25 (alfil capturado) - 3.0 (caballo perdido) = +0.25 (favorable).
    """

    def _calcular_see(self, board: chess.Board, move: chess.Move) -> float:
        """
        Calcula el balance SEE (Static Exchange Evaluation) exacto, incluyendo
        correctamente rayos-X y baterías, simulando las capturas en orden de menor a mayor valor.
        Retorna la ganancia material neta para el bando que realiza 'move'.
        """
        piece = board.piece_at(move.from_square)
        if not piece:
            return 0.0

        moving_val = VALORES_PIEZAS.get(piece.piece_type, 1.0)
        target_val = 0.0
        
        target = board.piece_at(move.to_square)
        if target:
            target_val = VALORES_PIEZAS.get(target.piece_type, 1.0)
        elif board.is_en_passant(move):
            target_val = 1.0

        gain = [target_val]

        temp_board = board.copy(stack=False)
        temp_board.remove_piece_at(move.from_square)
        
        if board.is_en_passant(move):
            ep_rank = 4 if piece.color == chess.WHITE else 3
            ep_file = chess.square_file(move.to_square)
            temp_board.remove_piece_at(chess.square(ep_file, ep_rank))
            
        to_sq = move.to_square
        current_color = not piece.color
        current_attacker_val = moving_val

        while True:
            attackers = temp_board.attackers(current_color, to_sq)
            if not attackers:
                break

            min_val = 100000.0
            min_sq = -1
            for sq in attackers:
                p = temp_board.piece_at(sq)
                val = VALORES_PIEZAS.get(p.piece_type, 1.0)
                if val < min_val:
                    min_val = val
                    min_sq = sq

            if min_sq == -1:
                break

            if min_val >= VALORES_PIEZAS.get(chess.KING, 200.0):
                if temp_board.attackers(not current_color, to_sq):
                    break

            gain.append(current_attacker_val)
            current_attacker_val = min_val
            temp_board.remove_piece_at(min_sq)
            current_color = not current_color

        n = len(gain)
        score = 0.0
        for i in range(n - 1, 0, -1):
            score = max(0.0, gain[i] - score)

        return gain[0] - score

    def simular_secuencia_intercambio(self, board: chess.Board, move: chess.Move, is_secondary: bool = False) -> Tuple[float, bool, str]:
        """
        Simula la secuencia completa de capturas y recapturas usando un SEE robusto,
        y comprueba si el movimiento deja colgada otra pieza de mayor valor.
        """
        piece = board.piece_at(move.from_square)
        if not piece:
            return 0.0, False, ""

        to_sq = move.to_square
        target = board.piece_at(to_sq)
        es_captura = board.is_capture(move)

        before_board = board.copy(stack=False)
        board.push(move)
        try:
            if board.is_checkmate():
                return 10000.0, False, "Jaque mate directo alcanzado."

            our_color = piece.color
            enemy_color = not our_color
            
            material_neto = self._calcular_see(before_board, move)
            es_suicida = (material_neto < -0.5)

            max_material_perdido_secundario = 0.0
            exp_colgado = ""

            if not is_secondary and not board.is_check():
                for sq, t_p in board.piece_map().items():
                    if t_p.color != our_color or t_p.piece_type == chess.KING:
                        continue
                    if sq == to_sq:
                        continue
                        
                    if board.is_attacked_by(enemy_color, sq):
                        tar_val = VALORES_PIEZAS.get(t_p.piece_type, 1.0)
                        
                        is_attacked_before = before_board.is_attacked_by(enemy_color, sq)
                        is_defended_before = before_board.is_attacked_by(our_color, sq)
                        
                        was_undefended = (is_attacked_before and not is_defended_before)
                            
                        is_defended = board.is_attacked_by(our_color, sq)
                        if not is_defended:
                            if not was_undefended:
                                if tar_val > max_material_perdido_secundario:
                                    max_material_perdido_secundario = tar_val
                                    exp_colgado = f"Deja desprotegido/a el {chess.piece_name(t_p.piece_type)} en {chess.square_name(sq)} permitiendo captura del rival (+{tar_val:.1f})."
                        else:
                            enemy_attackers = board.attackers(enemy_color, sq)
                            if enemy_attackers:
                                min_val = 10000.0
                                min_sq = None
                                for a_sq in enemy_attackers:
                                    p_att = board.piece_at(a_sq)
                                    val = VALORES_PIEZAS.get(p_att.piece_type, 1.0)
                                    if val < min_val:
                                        min_val = val
                                        min_sq = a_sq
                                        
                                if min_sq is not None:
                                    hypo_move = chess.Move(min_sq, sq)
                                    ganancia_rival = self._calcular_see(board, hypo_move)
                                    
                                    if ganancia_rival > 0.5:
                                        ganancia_rival_antes = 0.0
                                        enemy_attackers_before = before_board.attackers(enemy_color, sq)
                                        if enemy_attackers_before:
                                            min_val_bef = 10000.0
                                            min_sq_bef = None
                                            for a_sq in enemy_attackers_before:
                                                p_att = before_board.piece_at(a_sq)
                                                val = VALORES_PIEZAS.get(p_att.piece_type, 1.0)
                                                if val < min_val_bef:
                                                    min_val_bef = val
                                                    min_sq_bef = a_sq
                                            if min_sq_bef is not None:
                                                hypo_move_bef = chess.Move(min_sq_bef, sq)
                                                ganancia_rival_antes = self._calcular_see(before_board, hypo_move_bef)
                                                
                                        if ganancia_rival > ganancia_rival_antes + 0.1:
                                            if ganancia_rival > max_material_perdido_secundario:
                                                max_material_perdido_secundario = ganancia_rival
                                                exp_colgado = f"Deja {chess.piece_name(t_p.piece_type)} en {chess.square_name(sq)} en intercambio desfavorable (-{ganancia_rival:.1f})."

            material_neto_final = material_neto - max_material_perdido_secundario
            es_suicida = (material_neto_final < -0.5)

            names = {chess.PAWN: "peon", chess.KNIGHT: "caballo", chess.BISHOP: "alfil", chess.ROOK: "torre", chess.QUEEN: "dama", chess.KING: "rey"}
            p_name = names.get(piece.piece_type, "pieza")
            sq_name = chess.square_name(to_sq)

            if es_suicida:
                exp = exp_colgado or f"Intercambio suicida en {sq_name}: Mueve {p_name} resultando en perdida neta de material ({material_neto_final:+.1f})."
            elif es_captura and material_neto_final > 0:
                exp = f"Captura favorable en {sq_name}: {p_name} captura pieza con ganancia neta ({material_neto_final:+.1f})."
            elif es_captura and abs(material_neto_final) <= 0.5:
                exp = f"Captura equivalente en {sq_name}: {p_name} captura pieza sin perdida neta."
            elif not es_captura and max_material_perdido_secundario > 0:
                exp = exp_colgado or f"Mueve {p_name} a {sq_name} pero deja material vulnerable ({material_neto_final:+.1f})."
            else:
                exp = f"Mueve {p_name} a {sq_name} sin intercambio de material."

            return material_neto_final, es_suicida, exp
        finally:
            board.pop()

    def evaluar_calidad_alfil(self, board: chess.Board, square: int, color: chess.Color) -> Tuple[str, float]:
        sq_color = (chess.square_file(square) + chess.square_rank(square)) % 2
        
        friendly_pawns_same_color = 0
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if p and p.color == color and p.piece_type == chess.PAWN:
                p_color = (chess.square_file(sq) + chess.square_rank(sq)) % 2
                if p_color == sq_color:
                    friendly_pawns_same_color += 1

        if friendly_pawns_same_color <= 2:
            return "bueno", 15.0
        elif friendly_pawns_same_color >= 4:
            return "malo", -15.0
        return "neutral", 0.0

    def evaluar_calidad_caballo(self, board: chess.Board, square: int, color: chess.Color) -> Tuple[str, float]:
        rank = chess.square_rank(square)
        file = chess.square_file(square)
        
        is_advanced = (rank in (3, 4, 5) if color == chess.WHITE else rank in (2, 3, 4))
        
        defenders = board.attackers(color, square)
        is_pawn_supported = any(board.piece_at(d) and board.piece_at(d).piece_type == chess.PAWN for d in defenders)

        enemy_color = not color
        enemy_pawn_attacks = False
        pawn_att_squares = board.attackers(enemy_color, square)
        for sq in pawn_att_squares:
            p = board.piece_at(sq)
            if p and p.piece_type == chess.PAWN:
                enemy_pawn_attacks = True
                break

        if is_advanced and is_pawn_supported and not enemy_pawn_attacks:
            return "bueno", 20.0
        elif rank in (0, 7) or file in (0, 7):
            return "malo", -10.0
        return "neutral", 0.0

    def evaluar_peon_pasado_defendible(self, board: chess.Board, square: int, color: chess.Color) -> Tuple[bool, float, str]:
        piece = board.piece_at(square)
        if not piece or piece.piece_type != chess.PAWN:
            return False, 0.0, ""

        file = chess.square_file(square)
        rank = chess.square_rank(square)
        enemy_color = not color

        files_to_check = [f for f in (file - 1, file, file + 1) if 0 <= f <= 7]
        ranks_to_check = range(rank + 1, 8) if color == chess.WHITE else range(0, rank)

        has_enemy_pawn = False
        for f in files_to_check:
            for r in ranks_to_check:
                p = board.piece_at(chess.square(f, r))
                if p and p.color == enemy_color and p.piece_type == chess.PAWN:
                    has_enemy_pawn = True
                    break
            if has_enemy_pawn:
                break

        if not has_enemy_pawn:
            defenders = board.attackers(color, square)
            is_defended = len(defenders) > 0
            bonus = 25.0 + (rank * 3.0 if color == chess.WHITE else (7 - rank) * 3.0)
            status = "defendible" if is_defended else "avanzado"
            return True, bonus, f"Peon pasado {status} en {chess.square_name(square)} camino a la coronacion."

        return False, 0.0, ""

    def evaluar_intercambio_posicional(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        from_sq = move.from_square
        to_sq = move.to_square

        piece = board.piece_at(from_sq)
        target = board.piece_at(to_sq)

        if not piece:
            return 0.0, ""

        color = piece.color
        enemy_color = not color
        score_pos = 0.0
        explicaciones = []

        if target and target.piece_type in (chess.BISHOP, chess.KNIGHT):
            if piece.piece_type == chess.BISHOP:
                tipo_nuestro, _ = self.evaluar_calidad_alfil(board, from_sq, color)
            else:
                tipo_nuestro, _ = self.evaluar_calidad_caballo(board, from_sq, color)

            if target.piece_type == chess.BISHOP:
                tipo_rival, _ = self.evaluar_calidad_alfil(board, to_sq, enemy_color)
            else:
                tipo_rival, _ = self.evaluar_calidad_caballo(board, to_sq, enemy_color)

            if tipo_nuestro == "malo" and tipo_rival == "bueno":
                score_pos += 25.0
                explicaciones.append(f"Intercambia su {chess.piece_name(piece.piece_type)} malo por el {chess.piece_name(target.piece_type)} bueno del oponente")
            elif tipo_nuestro == "bueno" and tipo_rival == "malo":
                score_pos -= 20.0
                explicaciones.append(f"Evita entregar su {chess.piece_name(piece.piece_type)} bueno a cambio de una pieza inferior")

        is_passed, bonus_passed, exp_passed = self.evaluar_peon_pasado_defendible(board, to_sq, color)
        if is_passed:
            score_pos += bonus_passed
            explicaciones.append(exp_passed)

        if explicaciones:
            return score_pos, ". ".join(explicaciones) + "."
        return 0.0, ""

    def evaluar_par_alfiles(self, board: chess.Board, color: chess.Color) -> Tuple[float, str]:
        """
        Evalua el bonus por tener el par de alfiles.
        El par de alfiles vale aproximadamente +0.5 peones en posicion abierta.
        """
        alfiles_propios = 0
        alfiles_rivales = 0
        
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.BISHOP:
                if piece.color == color:
                    alfiles_propios += 1
                else:
                    alfiles_rivales += 1
        
        if alfiles_propios == 2 and alfiles_rivales < 2:
            peones_centro = 0
            for sq in [chess.D4, chess.E4, chess.D5, chess.E5]:
                p = board.piece_at(sq)
                if p and p.piece_type == chess.PAWN:
                    peones_centro += 1
            
            if peones_centro <= 1:
                return 5.0, "Par de alfiles en posicion abierta: ventaja posicional."
            else:
                return 2.5, "Par de alfiles: ventaja moderada."
        
        return 0.0, ""