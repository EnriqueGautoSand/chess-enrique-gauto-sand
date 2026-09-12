import chess
import chess.polyglot
import time
from typing import Dict, Any, Optional, Tuple, List

try:
    from .constantes import VALORES_PIEZAS
    from .intercambios.intercambios import IntercambiosEvaluator
    from .jaques import JaquesEvaluator
    from .capturas import CapturasEvaluator
    from .amenazas import AmenazasEvaluator
    from .clavadas import ClavadasEvaluator
    from .descubierta import DescubiertaEvaluator
    from .posicional.posicional import PosicionalEvaluator
    from .defensa_adaptativa import DefensaAdaptativaEvaluator
    from .finales import FinalesEvaluator
except ImportError:
    from constantes import VALORES_PIEZAS
    from intercambios.intercambios import IntercambiosEvaluator
    from jaques import JaquesEvaluator
    from capturas import CapturasEvaluator
    from amenazas import AmenazasEvaluator
    from clavadas import ClavadasEvaluator
    from descubierta import DescubiertaEvaluator
    from posicional.posicional import PosicionalEvaluator
    from defensa_adaptativa import DefensaAdaptativaEvaluator
    from finales import FinalesEvaluator

class Minimax2Engine:
    """
    Motor de Ajedrez Táctico Selectivo (Shannon Type B).
    Solo evalúa ramas forzadas: Jaques, Capturas y Amenazas (tanto propias como del rival).
    Busca líneas que resulten en quietud (quiescencia) y ganancia material al alcanzar la profundidad máxima.
    """

    def __init__(self, default_depth: int = 4):
        self.default_depth = default_depth
        self._eval_cache = {}
        self.intercambios = IntercambiosEvaluator()
        self.jaques_eval = JaquesEvaluator()
        self.capturas_eval = CapturasEvaluator()
        self.amenazas_eval = AmenazasEvaluator()
        self.clavadas_eval = ClavadasEvaluator()
        self.descubierta_eval = DescubiertaEvaluator()
        self.posicional_eval = PosicionalEvaluator()
        self.defensa_eval = DefensaAdaptativaEvaluator()
        self.finales_eval = FinalesEvaluator()
        
        # Atributos mock para ser compatible con GameEngine
        class MockTT:
            def __init__(self_tt, cache_dict):
                self_tt.cache_dict = cache_dict
            def clear(self_tt):
                self_tt.cache_dict.clear()
        self.transposition_table = MockTT(self._eval_cache)
        
    def explicar_movimiento_realizado(self, board_before: chess.Board, move: chess.Move, depth: int = 2, strategy: str = "tactico") -> Dict[str, Any]:
        """
        Genera la explicación pedagógica y detallada de una jugada para Minimax2,
        desglosando jaques, capturas materiales (SEE), tenedores/amenazas, clavadas,
        ataques a la descubierta y planes posicionales, incluyendo la línea profunda
        de cálculo (PV) y el balance neto al final de la secuencia.
        """
        temp = board_before.copy(stack=False)
        temp.push(move)
        if temp.is_checkmate():
            piece = board_before.piece_at(move.from_square)
            p_name = chess.piece_name(piece.piece_type) if piece else "pieza"
            to_name = chess.square_name(move.to_square)
            return {
                "type": "tactica",
                "category": "Jaque Mate",
                "explanation": f"¡Jaque mate directo con {p_name} en {to_name}!"
            }

        score_jaq, exp_jaq = self.jaques_eval.evaluar_jaque_movimiento(board_before, move)
        score_cap, exp_cap = self.capturas_eval.evaluar_captura_movimiento(board_before, move)
        score_ame, exp_ame = self.amenazas_eval.evaluar_amenazas_movimiento(board_before, move)
        score_clav, exp_clav = self.clavadas_eval.evaluar_clavada_movimiento(board_before, move)
        score_desc, exp_desc = self.descubierta_eval.evaluar_descubierta_movimiento(board_before, move)

        mat_neto, es_suicida, exp_int = self.intercambios.simular_secuencia_intercambio(board_before, move)
        score_pos, exp_pos = self.posicional_eval.evaluar_jugada_posicional(board_before, move)
        score_fin, exp_fin = self.finales_eval.evaluar_movimiento_final(board_before, move)

        cat = "Plan Posicional"
        typ = "posicional"
        base_exp = exp_pos

        if score_jaq >= 9000:
            typ, cat, base_exp = "tactica", "Jaque Mate", exp_jaq
        elif score_cap > 0:
            typ, cat, base_exp = "tactica", "Captura Material", exp_cap
        elif score_jaq > 0:
            typ, cat, base_exp = "tactica", "Jaque al Rey", exp_jaq
        elif score_clav > 0:
            typ, cat, base_exp = "tactica", "Clavada", exp_clav
        elif score_desc > 0:
            typ, cat, base_exp = "tactica", "Ataque Descubierto", exp_desc
        elif score_ame > 0:
            typ, cat, base_exp = "tactica", "Amenaza Tactica", exp_ame
        elif mat_neto > 0:
            typ, cat, base_exp = "tactica", "Intercambio Favorable", exp_int
        elif score_fin > 0:
            typ, cat, base_exp = "posicional", "Final de Peones", exp_fin

        # Rollout táctico de continuación (PV / Línea profunda)
        work_board = board_before.copy(stack=True)
        work_board.push(move)
        pv_moves = [move]
        for d in range(1, 3):
            if work_board.is_game_over():
                break
            _, reply = self.buscar_linea_selectiva(work_board, depth=d, alpha=-9999999.0, beta=9999999.0)
            if not reply:
                break
            pv_moves.append(reply)
            work_board.push(reply)

        mat_inicial = self.evaluar_material(board_before)
        mat_final = self.evaluar_material(work_board)
        diff_mat = (-mat_final - mat_inicial) if (len(pv_moves) % 2 == 1) else (mat_final - mat_inicial)
        diff_mat_peones = diff_mat / 10.0

        pv_san = []
        tb = board_before.copy(stack=False)
        for m in pv_moves:
            pv_san.append(tb.san(m))
            tb.push(m)

        line_str = " -> ".join(pv_san)

        if len(pv_moves) > 1 and abs(diff_mat_peones) >= 0.5:
            if diff_mat_peones > 0:
                final_note = f" [Línea calculada]: {line_str} (ganancia material neta de +{diff_mat_peones:.1f} al final de la secuencia)."
            else:
                final_note = f" [Línea calculada]: {line_str} (balance final: {diff_mat_peones:+.1f})."
        elif len(pv_moves) > 1 and cat == "Amenaza Tactica":
            final_note = f" [Línea calculada]: {line_str} (presión directa para forzar la respuesta del rival)."
        else:
            final_note = ""

        full_exp = (base_exp + " " + final_note).strip()

        return {
            "type": typ,
            "category": cat,
            "explanation": full_exp
        }

    def evaluar_material(self, board: chess.Board) -> float:
        """Suma de material estático."""
        score = 0.0
        for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            val = VALORES_PIEZAS.get(pt, 1.0)
            score += val * int.bit_count(board.pieces_mask(pt, board.turn))
            score -= val * int.bit_count(board.pieces_mask(pt, not board.turn))
        return score * 10.0

    def _hay_captura_favorable_rival(self, board: chess.Board) -> bool:
        """
        Devuelve True si el bando que tiene el turno AHORA MISMO (board.turn) dispone de
        alguna captura ventajosa usando SEE.
        No modifica el tablero (no hace push/pop).
        """
        for move in board.legal_moves:
            if board.is_capture(move):
                ganancia = self.intercambios._calcular_see(board, move)
                if ganancia >= 0:
                    return True
        return False

    def _pieza_propia_amenazada(self, board: chess.Board) -> bool:
        """
        Devuelve True si el bando a mover (board.turn) tiene alguna pieza propia colgada
        o amenazada por un atacante de menor valor. Esto obliga a considerar jugadas
        defensivas (no solo jaques/capturas/amenazas propias) al filtrar movimientos.
        """
        color = board.turn
        for square in chess.SQUARES:
            pieza = board.piece_at(square)
            if pieza and pieza.color == color and pieza.piece_type != chess.KING:
                if board.is_attacked_by(not color, square):
                    val_pieza = VALORES_PIEZAS.get(pieza.piece_type, 0)
                    defendida = board.is_attacked_by(color, square)
                    if not defendida:
                        return True
                    for att_sq in board.attackers(not color, square):
                        atacante = board.piece_at(att_sq)
                        if atacante:
                            val_atacante = VALORES_PIEZAS.get(atacante.piece_type, 0)
                            if val_atacante < val_pieza:
                                return True
        return False

    def _es_quietud(self, board: chess.Board) -> bool:
        """
        Devuelve True si la posición es 'quieta' para el jugador que le toca jugar (board.turn).
        Quieta = No estamos en jaque, el rival no tiene mate en 1 contra nosotros, y no nos pueden capturar piezas gratis o de mayor valor.
        Como es el turno de 'board.turn', evaluamos las amenazas que el rival (not board.turn) tiene SOBRE NOSOTROS en este momento.
        """
        if board.is_check():
            return False

        # Generar movimientos del rival temporalmente para ver si nos amenazan (haciendo jugada nula)
        board.push(chess.Move.null())
        if board.is_checkmate():
            board.pop()
            return False # Nos daban mate

        # Verificar si el rival puede capturarnos algo
        hay_captura = self._hay_captura_favorable_rival(board)
        board.pop()

        return not hay_captura

    def _es_amenaza(self, board: chess.Board, move: chess.Move) -> bool:
        """Determina si un movimiento es una 'amenaza' (ataca algo de valor)."""
        pieza = board.piece_at(move.from_square)
        if not pieza:
            return False
            
        atacante_sq = move.to_square
        val_atacante = VALORES_PIEZAS.get(pieza.piece_type, 0)
        color_rival = not pieza.color
        
        # Simular ataques desde to_square
        if pieza.piece_type == chess.KNIGHT:
            attacks_bb = chess.BB_KNIGHT_ATTACKS[atacante_sq]
        elif pieza.piece_type == chess.KING:
            attacks_bb = chess.BB_KING_ATTACKS[atacante_sq]
        elif pieza.piece_type == chess.PAWN:
            attacks_bb = chess.BB_PAWN_ATTACKS[pieza.color][atacante_sq]
        else:
            # Para deslizantes (Torre, Alfil, Dama), es más seguro usar push/pop
            board.push(move)
            atacados = board.attacks(atacante_sq)
            for sq in atacados:
                victima = board.piece_at(sq)
                if victima and victima.color == color_rival:
                    val_victima = VALORES_PIEZAS.get(victima.piece_type, 0)
                    if val_victima >= val_atacante or not board.is_attacked_by(color_rival, sq):
                        board.pop()
                        return True
            board.pop()
            return False
            
        # Para saltadores, usamos el bitboard directamente sin modificar el tablero
        if attacks_bb:
            for sq in chess.SquareSet(attacks_bb):
                victima = board.piece_at(sq)
                if victima and victima.color == color_rival and sq != move.to_square:
                    val_victima = VALORES_PIEZAS.get(victima.piece_type, 0)
                    if val_victima >= val_atacante or not board.is_attacked_by(color_rival, sq):
                        return True
        return False

    def _filtrar_movimientos_tacticos(self, board: chess.Board) -> List[chess.Move]:
        """Filtra las jugadas para devolver solo evasiones, jaques, capturas y amenazas."""
        legales = list(board.legal_moves)
        
        move_scores = {}
        
        def get_move_score(move: chess.Move) -> float:
            if move in move_scores:
                return move_scores[move]
                
            score = 0.0
            if board.is_capture(move):
                ganancia = self.intercambios._calcular_see(board, move)
                score = 1000.0 + ganancia * 10.0
            elif board.gives_check(move):
                score = 500.0
            move_scores[move] = score
            return score

        if board.is_check():
            return sorted(legales, key=get_move_score, reverse=True)

        tacticas = []
        for move in legales:
            if board.is_capture(move):
                ganancia = self.intercambios._calcular_see(board, move)
                move_scores[move] = 1000.0 + ganancia * 10.0
                if ganancia >= -0.5 or board.gives_check(move):
                    tacticas.append(move)
            elif board.gives_check(move):
                tacticas.append(move)
            elif self._es_amenaza(board, move):
                tacticas.append(move)

        if self._pieza_propia_amenazada(board):
            vistos = set(tacticas)
            for move in legales:
                if move not in vistos:
                    if board.is_capture(move):
                        ganancia = self.intercambios._calcular_see(board, move)
                        move_scores[move] = 1000.0 + ganancia * 10.0
                        if ganancia < -0.5 and not board.gives_check(move):
                            continue # Poda SEE de capturas suicidas defensivas
                    tacticas.append(move)
                    vistos.add(move)

        return sorted(tacticas, key=get_move_score, reverse=True)

    def buscar_linea_selectiva(self, board: chess.Board, depth: int, alpha: float, beta: float) -> Tuple[float, Optional[chess.Move]]:
        cache_key = board._transposition_key()
        cache_entry = self._eval_cache.get(cache_key)
        
        if cache_entry is not None and cache_entry['depth'] >= depth:
            if cache_entry['flag'] == 'EXACT':
                return cache_entry['score'], cache_entry['move']
            elif cache_entry['flag'] == 'LOWERBOUND':
                alpha = max(alpha, cache_entry['score'])
            elif cache_entry['flag'] == 'UPPERBOUND':
                beta = min(beta, cache_entry['score'])
            
            if alpha >= beta:
                return cache_entry['score'], cache_entry['move']

        original_alpha = alpha

        if board.is_game_over():
            if board.is_checkmate():
                # El jugador que debe mover está en jaque mate. Es la peor situación posible.
                return -99999.0, None
            return 0.0, None # Tablas

        if depth <= 0:
            # evaluar_material ya devuelve la perspectiva de board.turn
            score = self.evaluar_material(board)
            self._eval_cache[cache_key] = {'depth': depth, 'score': score, 'flag': 'EXACT', 'move': None}
            return score, None

        is_root = (depth == self.default_depth)
        stand_pat = self.evaluar_material(board)

        movimientos_tacticos = self._filtrar_movimientos_tacticos(board)
        
        if not movimientos_tacticos:
            score = stand_pat
            self._eval_cache[cache_key] = {'depth': depth, 'score': score, 'flag': 'EXACT', 'move': None}
            return score, None

        is_quiet = self._es_quietud(board)
        if is_root or not is_quiet:
            best = -9999999.0
        else:
            best = stand_pat
        
        if not is_root and best >= beta:
            self._eval_cache[cache_key] = {'depth': depth, 'score': best, 'flag': 'LOWERBOUND', 'move': None}
            return best, None
            
        alpha = max(alpha, best)
        mejor_move = None

        for move in movimientos_tacticos:
            board.push(move)
            # Llamada recursiva con alfa y beta invertidos y negados, propio del framework negamax
            score_sub, _ = self.buscar_linea_selectiva(board, depth - 1, -beta, -alpha)
            score_sub = -score_sub
            board.pop()

            if score_sub > best:
                best = score_sub
                mejor_move = move

            alpha = max(alpha, best)
            if alpha >= beta:
                break

        flag = 'EXACT'
        if best <= original_alpha:
            flag = 'UPPERBOUND'
        elif best >= beta:
            flag = 'LOWERBOUND'
            
        self._eval_cache[cache_key] = {'depth': depth, 'score': best, 'flag': flag, 'move': mejor_move}
        return best, mejor_move

    def evaluar_posicion(self, board: chess.Board, config: Optional[Dict[str, Any]] = None) -> float:
        """
        Calcula la evaluación estática rápida de la posición en decipeones (10.0 = 1 peón).
        Devuelve el valor desde la perspectiva de board.turn.
        """
        if board.is_checkmate():
            return -1000.0
        if board.is_stalemate() or board.is_insufficient_material():
            return 0.0

        try:
            try:
                import cpp_engine.minimax_cpp as minimax_cpp
            except ImportError:
                import minimax_cpp
            fen = board.fen()
            minimax_config = minimax_cpp.MinimaxConfig()
            if config:
                for key, value in config.items():
                    if hasattr(minimax_config, key):
                        if key == "max_quiescence_depth":
                            setattr(minimax_config, key, int(value))
                        else:
                            setattr(minimax_config, key, bool(value))
            score_cp = minimax_cpp.evaluate_fen(fen, minimax_config)
            return float(score_cp) / 10.0
        except Exception:
            return self.evaluar_material(board)

    def seleccionar_movimiento(self, board: chess.Board, depth: Optional[int] = None, strategy: str = "tactico", tree_mode: str = "cut", time_limit: Optional[float] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Interfaz compatible con app.py para seleccionar la jugada, AHORA ACELERADA POR C++.
        """
        if depth is None:
            depth = self.default_depth
        else:
            try:
                depth = int(depth)
            except (ValueError, TypeError):
                depth = self.default_depth

        movimientos_legales = list(board.legal_moves)
        if not movimientos_legales:
            return {"success": False, "message": "No hay movimientos legales."}

        start_time = time.time()
        
        try:
            try:
                import cpp_engine.minimax_cpp as minimax_cpp
            except ImportError:
                import minimax_cpp
            # Usar el motor en C++
            fen = board.fen()
            minimax_config = minimax_cpp.MinimaxConfig()
            if config:
                for key, value in config.items():
                    if hasattr(minimax_config, key):
                        if key == "max_quiescence_depth":
                            setattr(minimax_config, key, int(value))
                        else:
                            setattr(minimax_config, key, bool(value))
            
            history_moves = [m.uci() for m in board.move_stack]
            if hasattr(minimax_cpp, "search_root"):
                res_cpp = minimax_cpp.search_root(fen, depth, strategy, minimax_config, history=history_moves)
                best_move_str = res_cpp.get("move_uci", "")
                raw_score_cp = res_cpp.get("score", 0)
                score = float(raw_score_cp) / 10.0
            else:
                best_move_str = minimax_cpp.get_best_move(fen, depth, strategy, minimax_config, history=history_moves)
                score = float(minimax_cpp.evaluate_fen(fen, minimax_config)) / 10.0

            if best_move_str and best_move_str != "0000" and best_move_str != "error":
                best_move = chess.Move.from_uci(best_move_str)
            else:
                best_move = None
        except (ImportError, AttributeError):
            # Fallback al motor original en Python
            score, best_move = self.buscar_linea_selectiva(board, depth, -9999999.0, 9999999.0)

        if best_move is None:
            # Fallback posicional superficial
            max_s = -999999.0
            fallback_move = movimientos_legales[0]
            for move in movimientos_legales:
                board.push(move)
                s = -self.evaluar_material(board)
                if not self._hay_captura_favorable_rival(board):
                    s += 10.0
                board.pop()
                if s > max_s:
                    max_s = s
                    fallback_move = move
            best_move = fallback_move
            score = max_s

        # Generar explicación pedagógica detallada del movimiento elegido
        exp_info = self.explicar_movimiento_realizado(board, best_move, depth=depth, strategy=strategy)
        exp = exp_info.get("explanation", "Secuencia táctica calculada.")
        mov_type = exp_info.get("type", "tactica")
        mov_cat = exp_info.get("category", "tactico_selectivo")

        # =====================================================================
        # CONTROL INTELIGENTE DE EMPATES Y REPETICIONES (Anti-Draw / Pro-Draw)
        # =====================================================================
        if best_move in movimientos_legales:
            board.push(best_move)
            is_rep = board.is_repetition(2) or board.is_repetition(3) or (board.halfmove_clock >= 90)
            board.pop()

            if is_rep and score >= 5.0:
                # Motor va ganando: evitar tablas buscando la mejor alternativa legal no repetitiva
                alt_best = None
                alt_score = -999999.0
                for m in movimientos_legales:
                    if m == best_move:
                        continue
                    board.push(m)
                    rep_m = board.is_repetition(2) or board.is_repetition(3)
                    sub_s = -self.evaluar_posicion(board, config)
                    board.pop()
                    if not rep_m and sub_s > alt_score:
                        alt_score = sub_s
                        alt_best = m
                if alt_best:
                    print(f"[Anti-Draw] Evitando repetición en posición ganadora (+{score:.1f} dp). Jugada progresiva: {alt_best}")
                    best_move = alt_best
                    score = alt_score
                    exp = "Evitando repetición/tablas en posición ganadora (Buscando la victoria)"
                    mov_cat = "anti_tablas"
            elif not is_rep and score <= -15.0:
                # Motor va perdiendo: si alguna jugada legal fuerza tablas por repetición, buscarla activamente
                for m in movimientos_legales:
                    board.push(m)
                    rep_m = board.is_repetition(3)
                    board.pop()
                    if rep_m:
                        print(f"[Pro-Draw] Forzando tablas por repetición en posición desventajosa ({score:.1f} dp). Jugada salvadora: {m}")
                        best_move = m
                        score = 0.0
                        exp = "Forzando tablas por repetición/jaque continuo (Salvando la partida)"
                        mov_cat = "salvacion_tablas"
                        break

        tiempo_total = time.time() - start_time
        print(f"[Minimax2] Depth: {depth}, Time: {tiempo_total:.3f}s, Score: {score}, Move: {best_move}")

        return {
            "success": True,
            "move_uci": best_move.uci(),
            "move_san": board.san(best_move),
            "type": mov_type,
            "category": mov_cat,
            "score": score,
            "depth_evaluated": depth,
            "strategy": strategy,
            "explanation": exp
        }