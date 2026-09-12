import chess
import chess.polyglot
import time
from typing import Dict, List, Any, Optional, Tuple
from collections import OrderedDict

try:
    from .jaques import JaquesEvaluator
    from .capturas import CapturasEvaluator
    from .amenazas import AmenazasEvaluator
    from .intercambios.intercambios import IntercambiosEvaluator
    from .posicional.posicional import PosicionalEvaluator
    from .defensa_adaptativa import DefensaAdaptativaEvaluator
    from .clavadas import ClavadasEvaluator
    from .descubierta import DescubiertaEvaluator
    from .tablas import TablasDetector
    from .fase_juego import FaseJuegoDetector
    from .finales import FinalesEvaluator
    from .iniciativa import IniciativaEvaluator
    from .profilaxis import ProfilaxisEvaluator
    from .mate_forzado import MateForzadoEvaluator, SCORE_MATE_FORZADO
    from .constantes import VALORES_PIEZAS, SCORE_MATE, FACTOR_RECURSION, TOP_CANDIDATOS
except ImportError:
    from jaques import JaquesEvaluator
    from capturas import CapturasEvaluator
    from amenazas import AmenazasEvaluator
    from intercambios.intercambios import IntercambiosEvaluator
    from posicional.posicional import PosicionalEvaluator
    from defensa_adaptativa import DefensaAdaptativaEvaluator
    from clavadas import ClavadasEvaluator
    from descubierta import DescubiertaEvaluator
    from tablas import TablasDetector
    from fase_juego import FaseJuegoDetector
    from finales import FinalesEvaluator
    from iniciativa import IniciativaEvaluator
    from profilaxis import ProfilaxisEvaluator
    from mate_forzado import MateForzadoEvaluator, SCORE_MATE_FORZADO
    from constantes import VALORES_PIEZAS, SCORE_MATE, FACTOR_RECURSION, TOP_CANDIDATOS

# ═══════════════════════════════════════════════════════════════════════════
# BACKEND DEL MINIMAX - Opción hardcodeada
# ═══════════════════════════════════════════════════════════════════════════
# El minimax original de Python (buscar_linea_tactica_alfabeta) se conserva
# COMPLETO en este archivo como referencia.
#
#   MINIMAX_BACKEND = "cpp"    → usa el port C++ (engine_original.cpp), [POR DEFECTO]
#   MINIMAX_BACKEND = "python" → usa el minimax original de Python de este archivo
try:
    import engine_original_cpp
except ImportError:
    try:
        from . import engine_original_cpp
    except ImportError:
        engine_original_cpp = None

ENGINE_ORIGINAL_CPP_OK = engine_original_cpp is not None

MINIMAX_BACKEND = "cpp" if ENGINE_ORIGINAL_CPP_OK else "python"


class TranspositionTable:
    """
    Tabla de transposición con límite de tamaño, política LRU, envejecimiento (aging)
    y reutilización de árbol entre turnos.
    Almacena entradas con tipo de bound (exact, lower, upper), profundidad evaluada y edad.
    """
    
    # Constantes de tipo de bound
    BOUND_EXACT = 0   # valor exacto
    BOUND_LOWER = 1   # cota inferior (fail-high)
    BOUND_UPPER = 2   # cota superior (fail-low)
    
    def __init__(self, max_size: int = 150000):
        self.max_size = max_size
        self.table: OrderedDict = OrderedDict()
        self.current_age: int = 0
    
    def get(self, key: int) -> Optional[Tuple]:
        if key in self.table:
            self.table.move_to_end(key)
            return self.table[key]
        return None
    
    def put(self, key: int, value: Tuple):
        if key in self.table:
            self.table.move_to_end(key)
        else:
            if len(self.table) >= self.max_size:
                self.table.popitem(last=False)
        self.table[key] = value
    
    def lookup(self, board: 'chess.Board', depth: int, alpha: float, beta: float) -> Optional[Tuple]:
        """
        Busca una posición en la tabla usando únicamente Zobrist hash.
        Devuelve (score, move, exp) si la profundidad almacenada >= depth y el bound es usable.
        """
        zobrist = chess.polyglot.zobrist_hash(board)
        entry = self.get(zobrist)
        if entry is None:
            return None
        
        # entry = (score, move, exp, bound_flag, entry_depth, entry_age)
        score, move, exp, bound_flag, entry_depth, entry_age = entry
        
        # Validar que el movimiento almacenado sea una jugada legal en la posición actual
        if move is not None and move not in board.legal_moves:
            return None
        
        if entry_depth >= depth:
            if bound_flag == self.BOUND_EXACT:
                return (score, move, exp)
            if bound_flag == self.BOUND_LOWER and score >= beta:
                return (score, move, exp)
            if bound_flag == self.BOUND_UPPER and score <= alpha:
                return (score, move, exp)
        
        return None

    def get_stored_move(self, board: 'chess.Board') -> Optional[chess.Move]:
        """Devuelve el mejor movimiento almacenado previamente para move ordering (incluso si entry_depth < depth)."""
        zobrist = chess.polyglot.zobrist_hash(board)
        entry = self.table.get(zobrist)
        if entry is not None and entry[1] is not None:
            move = entry[1]
            if move in board.legal_moves:
                return move
        return None
    
    def store(self, board: 'chess.Board', depth: int, score: float, move, exp: str,
              alpha: float, beta: float, original_alpha: float):
        """
        Almacena o actualiza una entrada con la profundidad evaluada y edad de turno.
        """
        zobrist = chess.polyglot.zobrist_hash(board)
        
        if score <= original_alpha:
            bound_flag = self.BOUND_UPPER
        elif score >= beta:
            bound_flag = self.BOUND_LOWER
        else:
            bound_flag = self.BOUND_EXACT

        existing = self.table.get(zobrist)
        if existing is not None:
            _, _, _, _, existing_depth, existing_age = existing
            # Sobrescribir si la profundidad es mayor o igual, o si la entrada es vieja
            if depth < existing_depth and existing_age >= self.current_age - 2:
                return
            self.table.move_to_end(zobrist)
        else:
            if len(self.table) >= self.max_size:
                self.table.popitem(last=False)

        self.table[zobrist] = (score, move, exp, bound_flag, depth, self.current_age)

    def clean_old_entries(self, max_age_diff: int = 6):
        """Elimina entradas de la tabla que tengan más de max_age_diff turnos de antigüedad."""
        if not self.table:
            return
        keys_to_remove = [k for k, v in list(self.table.items()) if (self.current_age - v[5]) > max_age_diff]
        for k in keys_to_remove:
            self.table.pop(k, None)
    
    def clear(self):
        self.table.clear()
        self.current_age = 0
        # Mantener sincronizada la tabla de transposición del backend C++
        if ENGINE_ORIGINAL_CPP_OK:
            engine_original_cpp.clear_tt()
    
    def __contains__(self, key: int) -> bool:
        return key in self.table


class HumanChessEngine:
    """
    Motor de Ajedrez Humano Explicable Adaptativo.
    Evalua posiciones mediante simulacion de secuencias de intercambio,
    busqueda tactica recursiva con poda alfa-beta, modulos de defensa adaptativa,
    clavadas, descubierta, deteccion de tablas, fase de juego, finales, iniciativa y profilaxis.
    """

    def __init__(self, default_depth: int = 2):
        self.default_depth = default_depth
        self.jaques_eval = JaquesEvaluator()
        self.capturas_eval = CapturasEvaluator()
        self.amenazas_eval = AmenazasEvaluator()
        self.intercambios_eval = IntercambiosEvaluator()
        self.posicional_eval = PosicionalEvaluator()
        self.defensa_adaptativa_eval = DefensaAdaptativaEvaluator()
        self.clavadas_eval = ClavadasEvaluator()
        self.descubierta_eval = DescubiertaEvaluator()
        self.tablas_detector = TablasDetector()
        self.fase_juego_detector = FaseJuegoDetector()
        self.finales_eval = FinalesEvaluator()
        self.iniciativa_eval = IniciativaEvaluator()
        self.profilaxis_eval = ProfilaxisEvaluator()
        self.mate_forzado_eval = MateForzadoEvaluator(max_depth_mate=3, use_king_zone_filter=True)
        self.transposition_table = TranspositionTable(max_size=100000)

    def evaluar_estado_estatico(self, board: chess.Board) -> float:
        """
        Calcula la evaluacion estatica de material de la posicion.
        """
        if board.is_checkmate():
            return -1000.0

        score_material = 0.0
        for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            val = VALORES_PIEZAS.get(pt, 1.0)
            # pieces_mask devuelve un entero (bitboard) de las piezas, bit_count cuenta los bits en 1.
            score_material += val * int.bit_count(board.pieces_mask(pt, board.turn))
            score_material -= val * int.bit_count(board.pieces_mask(pt, not board.turn))
        
        return score_material * 10.0

    def _ordenar_movimientos(self, board: chess.Board, moves: List[chess.Move], tt_move: Optional[chess.Move] = None) -> List[chess.Move]:
        """
        Ordena movimientos para mejorar la poda alfa-beta usando MVV-LVA.
        Prioridad: tt_move > capturas (MVV-LVA)
        """
        def score_orden(move):
            if tt_move and move == tt_move:
                return 1000000
            score = 0
            if board.is_capture(move):
                target = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                if target and attacker:
                    val_victima = VALORES_PIEZAS.get(target.piece_type, 0)
                    val_atacante = VALORES_PIEZAS.get(attacker.piece_type, 1)
                    score += 10000 + int(val_victima * 100) - int(val_atacante * 10)
            return score
        
        return sorted(moves, key=score_orden, reverse=True)

    def _amenaza_mate_en_1(self, board: chess.Board, move: chess.Move) -> bool:
        """
        Verifica si una jugada amenaza mate en 1.
        Empuja la jugada y verifica si existe alguna jugada del lado que mueve
        que sea jaque mate. Solo verifica jugadas que dan jaque (optimizacion).
        """
        board.push(move)
        amenaza = False
        for m in board.legal_moves:
            if board.gives_check(m):
                board.push(m)
                if board.is_checkmate():
                    amenaza = True
                    board.pop()
                    break
                board.pop()
        board.pop()
        return amenaza

    def _evaluar_movimiento_nodo(self, board: chess.Board, move: chess.Move,
                                  amenazas_op: List) -> Tuple[float, str, bool]:
        """
        Evalua el score directo de un movimiento en un nodo de busqueda.
        Reutiliza amenazas_op (cacheadas por nodo) para evitar recalcular.
        Retorna (score_directo, explicacion, es_suicida).
        
        Prioridad absoluta:
        1. Mate forzado/imparable a favor → +SCORE_MATE_FORZADO
        2. Mate forzado/imparable del rival permitido → -SCORE_MATE_FORZADO (suicida absoluto)
        3. Evaluacion tactica normal
        """
        if not hasattr(self, "_eval_cache"):
            self._eval_cache = {}
            
        zobrist = chess.polyglot.zobrist_hash(board)
        cache_key = (zobrist, move.from_square, move.to_square, move.promotion)
        if cache_key in self._eval_cache:
            return self._eval_cache[cache_key]

        # === PRIORIDAD 1: MATE FORZADO/IMPARABLE (desactivado para delegar a Minimax) ===
        # score_mate, exp_mate = self.mate_forzado_eval.evaluar_movimiento_mate(board, move, depth=1)
        # if score_mate >= SCORE_MATE_FORZADO - 1000:
        #     res = (SCORE_MATE_FORZADO, exp_mate, False)
        #     self._eval_cache[cache_key] = res
        #     return res
        # if score_mate <= -(SCORE_MATE_FORZADO - 1000):
        #     res = (-SCORE_MATE_FORZADO, exp_mate, True)
        #     self._eval_cache[cache_key] = res
        #     return res

        # Solo evaluar jaques si la jugada REALMENTE da jaque (evitar falsos positivos)
        if board.gives_check(move):
            score_jaq, exp_jaq = self.jaques_eval.evaluar_jaque_movimiento(board, move)
        else:
            score_jaq, exp_jaq = 0.0, ""

        mat_neto, es_suicida, exp_int = self.intercambios_eval.simular_secuencia_intercambio(board, move)
        score_cap, exp_cap = self.capturas_eval.evaluar_captura_movimiento(board, move)
        if mat_neto <= 0:
            score_cap = 0.0
        score_ame, exp_ame = self.amenazas_eval.evaluar_amenazas_movimiento(board, move)
        score_clav, exp_clav = self.clavadas_eval.evaluar_clavada_movimiento(board, move)
        score_desc, exp_desc = self.descubierta_eval.evaluar_descubierta_movimiento(board, move)
        score_def, exp_def = self.amenazas_eval.evaluar_defensa_de_amenazas(board, move, amenazas_op)

        # Si el movimiento genera una Clavada Letal a la Dama o Mate, no descartar por es_suicida
        if es_suicida and score_clav < 200.0 and score_jaq < 1000.0:
            return -1.0, exp_int, True

        pen_def, exp_riesgo, _ = self.defensa_adaptativa_eval.evaluar_amenazas_adaptativas_rival(board, move)

        # Solo retornar mate inmediato si REALMENTE da jaque mate
        if score_jaq >= 9000 and pen_def > -20.0:
            board.push(move)
            es_cm = board.is_checkmate()
            board.pop()
            if es_cm:
                return 1000.0, exp_jaq, False
        elif score_jaq > 0.0:
            score_jaq = 35.0

        # No marcar como suicida por penalización defensiva si genera Clavada Letal a la Dama
        if pen_def <= -30.0 and mat_neto <= 0:
            if score_clav < 200.0 and score_jaq < 1000.0:
                return -1.0, exp_riesgo, True

        # La ganancia neta de material (mat_neto) debe tener prioridad sobre meras amenazas o clavadas
        bonus_material = (mat_neto * 120.0) if mat_neto > 0 else 0.0

        score_directo = max(score_jaq, score_cap, score_ame, score_def, score_clav, score_desc) + bonus_material + pen_def

        # Seleccionar la explicación del módulo táctico que realmente aportó el mayor score
        tacticas = [
            (score_jaq, exp_jaq),
            (bonus_material, exp_int if mat_neto > 0 else ""),
            (score_cap, exp_cap),
            (score_clav, exp_clav),
            (score_desc, exp_desc),
            (score_ame, exp_ame),
            (score_def, exp_def)
        ]
        tacticas_validas = [t for t in tacticas if t[0] > 0 and t[1]]
        if tacticas_validas:
            tacticas_validas.sort(key=lambda x: x[0], reverse=True)
            exp = tacticas_validas[0][1]
        else:
            exp = exp_riesgo or exp_int or "responde a la posicion"

        res = (score_directo, exp, False)
        self._eval_cache[cache_key] = res
        return res

    def buscar_linea_tactica_alfabeta(self, board: chess.Board, depth: int, alpha: float, beta: float, is_maximizing: bool, tree_mode: str = "full", start_time: float = None, time_limit: float = None, is_root: bool = False, is_null: bool = False) -> Tuple[float, Optional[chess.Move], str]:
        if start_time is not None and time_limit is not None:
            if time.time() - start_time >= time_limit:
                score = self.evaluar_estado_estatico(board)
                return (score if is_maximizing else -score), None, ""

        if depth <= 0 or board.is_game_over():
            score = self.evaluar_estado_estatico(board)
            return (score if is_maximizing else -score), None, ""

        # Null Move Pruning (NMP)
        if not is_root and not is_null and not board.is_check() and depth >= 3:
            board.push(chess.Move.null())
            if is_maximizing:
                score_null, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 3, beta - 1, beta, False, tree_mode, start_time, time_limit, is_root=False, is_null=True)
                board.pop()
                if score_null >= beta:
                    return beta, None, ""
            else:
                score_null, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 3, alpha, alpha + 1, True, tree_mode, start_time, time_limit, is_root=False, is_null=True)
                board.pop()
                if score_null <= alpha:
                    return alpha, None, ""

        original_alpha = alpha
        tt_entry = self.transposition_table.lookup(board, depth, alpha, beta)
        if tt_entry is not None:
            return tt_entry

        movimientos_legales = list(board.legal_moves)
        if not movimientos_legales:
            score = self.evaluar_estado_estatico(board)
            res = ((score if is_maximizing else -score), None, "")
            self.transposition_table.store(board, depth, res[0], None, res[2], alpha, beta, original_alpha)
            return res

        tt_move = self.transposition_table.get_stored_move(board)
        movimientos_a_evaluar = self._ordenar_movimientos(board, movimientos_legales, tt_move=tt_move)

        mejor_move = None
        mejor_exp = ""

        if is_maximizing:
            max_eval = -9999999.0
            moves_evaluated = 0
            for move in movimientos_a_evaluar:
                if start_time is not None and time_limit is not None and (time.time() - start_time >= time_limit):
                    break

                es_captura_o_jaque = board.is_capture(move) or board.gives_check(move)
                board.push(move)

                # Late Move Reductions (LMR)
                if moves_evaluated >= 4 and depth >= 3 and not es_captura_o_jaque and not board.is_check() and not is_root:
                    score_sub, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 2, alpha, beta, False, tree_mode, start_time, time_limit, is_root=False)
                    if score_sub > alpha:
                        score_sub, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 1, alpha, beta, False, tree_mode, start_time, time_limit, is_root=False)
                else:
                    score_sub, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 1, alpha, beta, False, tree_mode, start_time, time_limit, is_root=False)
                
                board.pop()

                moves_evaluated += 1
                if score_sub > max_eval:
                    max_eval = score_sub
                    mejor_move = move

                alpha = max(alpha, score_sub)
                if beta <= alpha:
                    break

            res = (max_eval, mejor_move, mejor_exp) if mejor_move else (self.evaluar_estado_estatico(board), None, "")
        else:
            min_eval = 9999999.0
            moves_evaluated = 0
            for move in movimientos_a_evaluar:
                if start_time is not None and time_limit is not None and (time.time() - start_time >= time_limit):
                    break

                es_captura_o_jaque = board.is_capture(move) or board.gives_check(move)
                board.push(move)

                # Late Move Reductions (LMR)
                if moves_evaluated >= 4 and depth >= 3 and not es_captura_o_jaque and not board.is_check() and not is_root:
                    score_sub, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 2, alpha, beta, True, tree_mode, start_time, time_limit, is_root=False)
                    if score_sub < beta:
                        score_sub, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 1, alpha, beta, True, tree_mode, start_time, time_limit, is_root=False)
                else:
                    score_sub, _, _ = self.buscar_linea_tactica_alfabeta(board, depth - 1, alpha, beta, True, tree_mode, start_time, time_limit, is_root=False)
                
                board.pop()

                moves_evaluated += 1
                if score_sub < min_eval:
                    min_eval = score_sub
                    mejor_move = move

                beta = min(beta, score_sub)
                if beta <= alpha:
                    break

            res = (min_eval, mejor_move, mejor_exp) if mejor_move else (-self.evaluar_estado_estatico(board), None, "")

        self.transposition_table.store(board, depth, res[0], mejor_move, res[2], alpha, beta, original_alpha)
        return res

    def _extraer_nodo_hoja(self, board: chess.Board, root_move: chess.Move, max_depth: int) -> chess.Board:
        """
        Reconstruye el tablero en el nodo hoja basandose en la Tabla de Transposiciones.
        Llega tan profundo como la linea principal evaluada por el Minimax.
        """
        leaf_board = board.copy(stack=False)
        leaf_board.push(root_move)
        for _ in range(max_depth - 1):
            tt_move = self.transposition_table.get_stored_move(leaf_board)
            if tt_move and tt_move in leaf_board.legal_moves:
                leaf_board.push(tt_move)
            else:
                break
        return leaf_board

    def _calcular_actividad(self, board: chess.Board, color: chess.Color) -> int:
        """
        Calcula la cantidad total de casillas controladas por las piezas de un color.
        """
        casillas_controladas = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == color:
                casillas_controladas += len(board.attacks(sq))
        return casillas_controladas

    def seleccionar_movimiento(self, board: chess.Board, depth: Optional[int] = None, strategy: str = "tactico", tree_mode: str = "cut", time_limit: Optional[float] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Selecciona la mejor jugada adaptativa para la posicion actual.
        """
        self._eval_cache = {}
        if hasattr(self.mate_forzado_eval, "clear_cache"):
            self.mate_forzado_eval.clear_cache()
        if depth is None:
            depth = self.default_depth
        else:
            try:
                depth = int(depth)
            except (ValueError, TypeError):
                depth = self.default_depth

        # Envejecimiento de la tabla de transposición y limpieza de ramas obsoletas
        self.transposition_table.current_age += 1
        self.transposition_table.clean_old_entries(max_age_diff=6)
        if ENGINE_ORIGINAL_CPP_OK:
            engine_original_cpp.age_tt()

        movimientos_legales = list(board.legal_moves)
        if not movimientos_legales:
            return {
                "success": False,
                "message": "No hay movimientos legales disponibles (Fin de partida)."
            }

        # 0. DETECCION DE TABLAS
        es_tablas, tipo_tablas, exp_tablas = self.tablas_detector.detectar_tablas(board)
        if es_tablas:
            return {
                "success": True,
                "move_uci": None,
                "move_san": None,
                "type": "tablas",
                "category": tipo_tablas,
                "score": 0.0,
                "depth_evaluated": depth,
                "strategy": strategy,
                "explanation": exp_tablas
            }

        # 1. JAQUE MATE EN 1 ABSOLUTO
        for move in movimientos_legales:
            temp_b = board.copy(stack=False)
            temp_b.push(move)
            if temp_b.is_checkmate():
                san = board.san(move)
                piece = board.piece_at(move.from_square)
                p_name = chess.piece_name(piece.piece_type) if piece else "pieza"
                to_name = chess.square_name(move.to_square)
                return {
                    "success": True,
                    "move_uci": move.uci(),
                    "move_san": san,
                    "type": "tactica",
                    "category": "Jaque Mate",
                    "score": 1000.0,
                    "depth_evaluated": depth,
                    "strategy": strategy,
                    "explanation": f"Jaque mate directo con {p_name} en {to_name}!"
                }

        # 2. DEFENSA DEL REY EN JAQUE
        if board.is_check():
            candidatos_salida_jaque = []
            for move in movimientos_legales:
                temp_board = board.copy(stack=False)
                temp_board.push(move)

                jaques_rival = self.jaques_eval.obtener_jaques_nuestros(temp_board)
                permite_mate = any(j["score"] >= 9000 for j in jaques_rival) or temp_board.is_checkmate()
                if permite_mate:
                    continue

                mat_neto, es_suic, _ = self.intercambios_eval.simular_secuencia_intercambio(board, move)
                score_cap, exp_cap = self.capturas_eval.evaluar_captura_movimiento(board, move)
                
                score_defensa = 50.0 + (score_cap if score_cap > 0 else 0.0)
                exp = exp_cap if score_cap > 0 else "Defensa del Rey: Mueve para salir del jaque."

                checkers = board.checkers()
                captura_jaqueante = move.to_square in checkers
                if (not es_suic and not captura_jaqueante) or score_cap > 0 or captura_jaqueante:
                    candidatos_salida_jaque.append({
                        "move": move,
                        "score": score_defensa,
                        "explanation": exp
                    })
            
            if candidatos_salida_jaque:
                candidatos_salida_jaque.sort(key=lambda x: x["score"], reverse=True)
                mejor = candidatos_salida_jaque[0]
                m = mejor["move"]
                return {
                    "success": True,
                    "move_uci": m.uci(),
                    "move_san": board.san(m),
                    "type": "tactica",
                    "category": "defensa_jaque",
                    "score": mejor["score"],
                    "depth_evaluated": depth,
                    "strategy": strategy,
                    "explanation": mejor["explanation"]
                }

        # 3. BUSQUEDA TACTICA CON ALFA-BETA (ITERATIVE DEEPENING)
        start_time = time.time()
        limite_efectivo = time_limit if time_limit is not None else 40.0

        # ══════════════════════════════════════════════════════════════════
        # BACKEND C++ (engine_original_cpp) - OPCION HARDCODEADA [POR DEFECTO]
        # El minimax de fuerza bruta portado a C++ (engine_original.cpp).
        # El minimax Python original de más abajo (elif/else) queda INTACTO
        # como referencia y se usa cuando MINIMAX_BACKEND = "python".
        # ══════════════════════════════════════════════════════════════════
        if MINIMAX_BACKEND == "cpp":
            history_moves = [m.uci() for m in board.move_stack]
            res_cpp = engine_original_cpp.search_root(board.fen(), depth, strategy, limite_efectivo, history_moves)
            move_uci_cpp = res_cpp.get("move_uci", "")

            if move_uci_cpp and strategy in ("actividad", "ahogador"):
                move_cpp = chess.Move.from_uci(move_uci_cpp)
                amenazas_op = self.capturas_eval.evaluar_capturas_oponente(board)
                _, exp_nodo, _ = self._evaluar_movimiento_nodo(board, move_cpp, amenazas_op)
                act_cpp = int(res_cpp.get("actividad", 0))
                score_cpp = float(res_cpp.get("score", 0.0))
                if strategy == "actividad":
                    return {
                        "success": True,
                        "move_uci": move_uci_cpp,
                        "move_san": board.san(move_cpp),
                        "type": "estrategia_actividad",
                        "category": "actividad",
                        "score": score_cpp,
                        "depth_evaluated": depth,
                        "strategy": strategy,
                        "explanation": f"[C++] Maximiza diferencia de actividad (Balance: {act_cpp} casillas). {exp_nodo or 'Variante evaluada.'}"
                    }
                else:  # ahogador (C++ solo devuelve jugada si score != 0)
                    return {
                        "success": True,
                        "move_uci": move_uci_cpp,
                        "move_san": board.san(move_cpp),
                        "type": "estrategia_ahogador",
                        "category": "ahogador",
                        "score": score_cpp,
                        "depth_evaluated": depth,
                        "strategy": strategy,
                        "explanation": f"[C++] Minimiza actividad rival ({act_cpp} casillas controladas). {exp_nodo or 'Variante evaluada.'}"
                    }

            if move_uci_cpp:
                # Estrategia "tactico"/"posicional": el minimax C++ entrega la jugada;
                # la explicación y la evaluación posicional siguen en Python.
                move_tac = chess.Move.from_uci(move_uci_cpp)
                score_tac = float(res_cpp.get("score", 0.0))
                exp_tac = "[C++] Mejor jugada calculada por Minimax nativo (fuerza bruta)."
                amenazas_op = self.capturas_eval.evaluar_capturas_oponente(board)
                _, exp_generada, _ = self._evaluar_movimiento_nodo(board, move_tac, amenazas_op)
                if exp_generada:
                    exp_tac = f"[C++] {exp_generada}"
            else:
                move_tac, score_tac, exp_tac = None, 0.0, ""
        elif strategy in ["actividad", "ahogador"]:
            alpha = -9999999.0
            beta = 9999999.0
            root_results = []
            
            tt_move = self.transposition_table.get_stored_move(board)
            movimientos_ordenados = self._ordenar_movimientos(board, movimientos_legales, tt_move)
            
            for move in movimientos_ordenados:
                board.push(move)
                score_sub, _, _ = self.buscar_linea_tactica_alfabeta(
                    board, depth - 1, alpha, beta, False, tree_mode=tree_mode, 
                    start_time=start_time, time_limit=limite_efectivo, is_root=False
                )
                board.pop()
                
                score_eval = score_sub
                if score_eval > alpha:
                    alpha = score_eval
                    
                leaf_board = self._extraer_nodo_hoja(board, move, depth)
                if strategy == "actividad":
                    act_motor = self._calcular_actividad(leaf_board, board.turn)
                    act_rival = self._calcular_actividad(leaf_board, not board.turn)
                    act = act_motor - act_rival
                else:
                    act = self._calcular_actividad(leaf_board, not board.turn)
                
                # Explicación táctica en la raíz
                amenazas_op = self.capturas_eval.evaluar_capturas_oponente(board)
                _, exp_nodo, _ = self._evaluar_movimiento_nodo(board, move, amenazas_op)
                
                root_results.append({
                    "move": move,
                    "score": score_eval,
                    "actividad": act,
                    "exp": exp_nodo or "Variante evaluada."
                })
            
            if root_results:
                pos = [r for r in root_results if r["score"] >= 0.0]
                neg = [r for r in root_results if r["score"] < 0.0]
                
                if strategy == "actividad":
                    # Prioridad absoluta: primero el score táctico (la mejor de las mejores
                    # opciones). SOLO si varias jugadas EMPATAN en ese mejor score táctico,
                    # se desempata por la diferencia de actividad
                    # (actividad del motor - actividad del rival): gana el número más positivo.
                    root_results.sort(key=lambda x: (x["score"], x["actividad"]), reverse=True)
                    mejor = root_results[0]
                    
                    if mejor["score"] != 0.0 or True: # Siempre retorna para actividad
                        return {
                            "success": True,
                            "move_uci": mejor["move"].uci(),
                            "move_san": board.san(mejor["move"]),
                            "type": "estrategia_actividad",
                            "category": "actividad",
                            "score": mejor["score"],
                            "depth_evaluated": depth,
                            "strategy": strategy,
                            "explanation": f"Maximiza diferencia de actividad (Balance: {mejor['actividad']} casillas). {mejor['exp']}"
                        }
                else: # ahogador
                    if pos:
                        if all(r["score"] == 0.0 for r in pos):
                            mejor = pos[0]
                        else:
                            pos.sort(key=lambda x: (x["actividad"], -x["score"]))
                            mejor = pos[0]
                    else:
                        neg.sort(key=lambda x: (x["score"], -x["actividad"]), reverse=True)
                        mejor = neg[0]
                        
                    if mejor["score"] != 0.0:
                        return {
                            "success": True,
                            "move_uci": mejor["move"].uci(),
                            "move_san": board.san(mejor["move"]),
                            "type": "estrategia_ahogador",
                            "category": "ahogador",
                            "score": mejor["score"],
                            "depth_evaluated": depth,
                            "strategy": strategy,
                            "explanation": f"Minimiza actividad rival ({mejor['actividad']} casillas controladas). {mejor['exp']}"
                        }
                    else:
                        score_tac, move_tac, exp_tac = mejor["score"], mejor["move"], mejor["exp"]
            else:
                score_tac, move_tac, exp_tac = self.buscar_linea_tactica_alfabeta(
                    board, depth, -9999999.0, 9999999.0, True, tree_mode=tree_mode, start_time=start_time, time_limit=limite_efectivo, is_root=True
                )
        else:
            # Iterative Deepening puro para estrategia tactico
            mejor_move_tac = None
            mejor_score_tac = 0.0
            
            for d in range(1, depth + 1):
                # Si hemos consumido más del 50% del tiempo estipulado, abortamos para asegurar respuesta en tiempo
                if (time.time() - start_time) > limite_efectivo * 0.5 and d > 2:
                    break
                    
                s_tac, m_tac, _ = self.buscar_linea_tactica_alfabeta(
                    board, d, -9999999.0, 9999999.0, True, tree_mode=tree_mode, start_time=start_time, time_limit=limite_efectivo, is_root=True
                )
                
                # Si saltó el time_limit, descartamos este nivel incompleto
                if (time.time() - start_time) >= limite_efectivo and mejor_move_tac is not None:
                    break
                    
                if m_tac is not None:
                    mejor_move_tac = m_tac
                    mejor_score_tac = s_tac
            
            move_tac = mejor_move_tac
            score_tac = mejor_score_tac
            exp_tac = "Mejor jugada calculada por búsqueda profunda (ID)."
            
            if move_tac:
                amenazas_op = self.capturas_eval.evaluar_capturas_oponente(board)
                _, exp_generada, _ = self._evaluar_movimiento_nodo(board, move_tac, amenazas_op)
                if exp_generada:
                    exp_tac = exp_generada

        # 4. EVALUACION POSICIONAL CON PROFILAXIS
        candidatos_posicionales = []
        for move in movimientos_legales:
            score_pos, exp_pos = self.posicional_eval.evaluar_jugada_posicional(board, move)
            pen_def, exp_r, _ = self.defensa_adaptativa_eval.evaluar_amenazas_adaptativas_rival(board, move)
            
            # Evaluacion profilactica
            score_profil, exp_profil = self.profilaxis_eval.evaluar_profilaxis(board, move)
            
            final_pos_score = score_pos + pen_def + score_profil
            candidatos_posicionales.append({
                "move": move,
                "score": final_pos_score,
                "explanation": exp_pos if pen_def == 0 and score_profil == 0 else f"[Defensa Adaptativa] {exp_r}" if pen_def != 0 else f"[Profilaxis] {exp_profil}",
                "is_tactical": False
            })
        candidatos_posicionales.sort(key=lambda x: x["score"], reverse=True)

        posicionales_seguras = [p for p in candidatos_posicionales if p["score"] > 0.0]

        if strategy == "posicional":
            if posicionales_seguras:
                mejor_pos = posicionales_seguras[0]
                # Solo priorizar tactica sobre posicional si el score tactico
                # es significativamente alto (ganancia real de material o amenaza seria).
                # Umbral: 50 puntos = ventaja clara de al menos un peon con compensacion.
                UMBRAL_URGENCIA_TACTICA = 50.0
                if move_tac and score_tac > UMBRAL_URGENCIA_TACTICA and score_tac > mejor_pos["score"]:
                    return {
                        "success": True,
                        "move_uci": move_tac.uci(),
                        "move_san": board.san(move_tac),
                        "type": "tactica",
                        "category": "tactico",
                        "score": score_tac,
                        "depth_evaluated": depth,
                        "strategy": "posicional",
                        "explanation": f"[Prioridad Tactica] {exp_tac}"
                    }
                m = mejor_pos["move"]
                return {
                    "success": True,
                    "move_uci": m.uci(),
                    "move_san": board.san(m),
                    "type": "posicional",
                    "category": "desarrollo_piezas_peones",
                    "score": mejor_pos["score"],
                    "depth_evaluated": depth,
                    "strategy": "posicional",
                    "explanation": f"[Plan Posicional Prioritario] {mejor_pos['explanation']}"
                }
            elif move_tac:
                # Defensa Crítica en modo posicional: si no hay jugadas posicionales seguras,
                # confiamos ciegamente en la mejor jugada del Minimax (move_tac) para salvarnos.
                return {
                    "success": True,
                    "move_uci": move_tac.uci(),
                    "move_san": board.san(move_tac),
                    "type": "tactica",
                    "category": "defensa_urgente",
                    "score": score_tac,
                    "depth_evaluated": depth,
                    "strategy": "posicional",
                    "explanation": f"[Defensa Tactica Obligada] {exp_tac if exp_tac else 'Respuesta defensiva del Minimax'}"
                }

        score_actual = self.evaluar_estado_estatico(board)
        # 10.0 equivale a 1 peón. Usamos 5.0 para detectar cualquier ventaja/desventaja material real.
        diferencia_tactica = abs(score_tac - score_actual)
        hay_tactica_activa = diferencia_tactica > 5.0 or score_tac >= 900.0 or score_tac <= -900.0

        # Si estamos en estrategia 'tactico', usamos la respuesta del Minimax SIEMPRE.
        # El Minimax ya calculó la mejor jugada para mantener el equilibrio o ganar.
        if strategy == "tactico" and move_tac:
            return {
                "success": True,
                "move_uci": move_tac.uci(),
                "move_san": board.san(move_tac),
                "type": "tactica",
                "category": "tactico",
                "score": score_tac,
                "depth_evaluated": depth,
                "strategy": strategy,
                "explanation": exp_tac if exp_tac else "Mejor jugada calculada por Minimax."
            }

        if posicionales_seguras:
            mejor_pos = posicionales_seguras[0]
            m = mejor_pos["move"]
            return {
                "success": True,
                "move_uci": m.uci(),
                "move_san": board.san(m),
                "type": "posicional",
                "category": "desarrollo_piezas_peones",
                "score": mejor_pos["score"],
                "depth_evaluated": depth,
                "strategy": strategy,
                "explanation": mejor_pos["explanation"]
            }

        # Fallback
        if candidatos_posicionales:
            mejor_pos = candidatos_posicionales[0]
            m = mejor_pos["move"]
            return {
                "success": True,
                "move_uci": m.uci(),
                "move_san": board.san(m),
                "type": "posicional",
                "category": "defensa_cobertura",
                "score": mejor_pos["score"],
                "depth_evaluated": depth,
                "strategy": strategy,
                "explanation": mejor_pos["explanation"]
            }

        m_def = movimientos_legales[0]
        return {
            "success": True,
            "move_uci": m_def.uci(),
            "move_san": board.san(m_def),
            "type": "posicional",
            "category": "movimiento_estandar",
            "score": 0.0,
            "depth_evaluated": depth,
            "strategy": strategy,
            "explanation": "Realiza un movimiento legal estandar."
        }

    def explicar_movimiento_realizado(self, board_before: chess.Board, move: chess.Move, depth: int = 2, strategy: str = "tactico") -> Dict[str, Any]:
        """
        Genera la explicacion detallada de una jugada.
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
                "explanation": f"Jaque mate directo con {p_name} en {to_name}!"
            }

        score_jaq, exp_jaq = self.jaques_eval.evaluar_jaque_movimiento(board_before, move)
        score_cap, exp_cap = self.capturas_eval.evaluar_captura_movimiento(board_before, move)
        score_ame, exp_ame = self.amenazas_eval.evaluar_amenazas_movimiento(board_before, move)
        score_clav, exp_clav = self.clavadas_eval.evaluar_clavada_movimiento(board_before, move)
        score_desc, exp_desc = self.descubierta_eval.evaluar_descubierta_movimiento(board_before, move)

        mat_neto, es_suicida, exp_int = self.intercambios_eval.simular_secuencia_intercambio(board_before, move)
        score_pos, exp_pos = self.posicional_eval.evaluar_jugada_posicional(board_before, move)
        score_fin, exp_fin = self.finales_eval.evaluar_movimiento_final(board_before, move)

        if score_jaq >= 9000:
            return {"type": "tactica", "category": "Jaque Mate", "explanation": exp_jaq}
        if score_cap > 0:
            return {"type": "tactica", "category": "Captura Material", "explanation": exp_cap}
        if score_jaq > 0:
            return {"type": "tactica", "category": "Jaque al Rey", "explanation": exp_jaq}
        if score_clav > 0:
            return {"type": "tactica", "category": "Clavada", "explanation": exp_clav}
        if score_desc > 0:
            return {"type": "tactica", "category": "Ataque Descubierto", "explanation": exp_desc}
        if score_ame > 0:
            return {"type": "tactica", "category": "Amenaza Tactica", "explanation": exp_ame}
        if mat_neto > 0:
            return {"type": "tactica", "category": "Intercambio Favorable", "explanation": exp_int}
        if score_fin > 0:
            return {"type": "posicional", "category": "Final de Peones", "explanation": exp_fin}

        return {"type": "posicional", "category": "Plan Posicional", "explanation": exp_pos}