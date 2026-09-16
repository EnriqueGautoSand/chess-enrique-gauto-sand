import re
import sys
import os
import time
import threading

# Asegurar que el módulo chess engine sea importable independientemente del directorio de trabajo
for candidate in [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "chess engine")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chess engine"))
]:
    if os.path.exists(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)

import chess
from typing import Dict, List, Any, Optional

try:
    from engine import HumanChessEngine
    from minimax2 import Minimax2Engine
    try:
        import transformer_evaluator
    except Exception:
        pass
except ImportError:
    pass

class CppEngineAdapter:
    """Adaptador para conectar motores C++ pybind11 con la interfaz web."""
    def __init__(self, mod_name: str, name_label: str, default_depth: int = 2):
        self.mod_name = mod_name
        self.name_label = name_label
        self.default_depth = default_depth
        self._cache = {}
        
        class MockTT:
            def __init__(self_tt, cache_dict, mod_ref):
                self_tt.cache_dict = cache_dict
                self_tt.mod_ref = mod_ref
            def clear(self_tt):
                self_tt.cache_dict.clear()
                try:
                    m = self_tt.mod_ref()
                    if m and hasattr(m, "clear_tt"):
                        m.clear_tt()
                except Exception:
                    pass
        self.transposition_table = MockTT(self._cache, lambda: self._get_mod())

    def _get_mod(self):
        try:
            return __import__(self.mod_name)
        except ImportError:
            try:
                import sys, os
                here = os.path.dirname(os.path.abspath(__file__))
                for root_dir in [here, os.path.abspath(os.path.join(here, ".."))]:
                    if root_dir not in sys.path:
                        sys.path.insert(0, root_dir)
                    ce_dir = os.path.join(root_dir, "chess engine")
                    if os.path.exists(ce_dir) and ce_dir not in sys.path:
                        sys.path.insert(0, ce_dir)
                    cpp_dir = os.path.join(ce_dir, "cpp_engine")
                    if os.path.exists(cpp_dir) and cpp_dir not in sys.path:
                        sys.path.insert(0, cpp_dir)
                return __import__(self.mod_name)
            except Exception as e:
                print(f"[Error cargando {self.mod_name}]: {e}", file=sys.stderr)
                return None

    def seleccionar_movimiento(self, board: chess.Board, depth: Optional[int] = None, strategy: str = "tactico", tree_mode: str = "cut", time_limit: Optional[float] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        mod = self._get_mod()
        d = int(depth) if depth is not None else self.default_depth
        tl = float(time_limit) if time_limit is not None else 40.0
        fen = board.fen()
        history_moves = [m.uci() for m in board.move_stack]
        
        if mod:
            if hasattr(mod, "search_root"):
                res = mod.search_root(fen, d, strategy, tl, history_moves)
                move_uci = res.get("move_uci", "")
                score = float(res.get("score", 0.0))
                if move_uci:
                    move = chess.Move.from_uci(move_uci)
                    san = board.san(move)
                    exp = f"[{self.name_label}] Jugada calculada con búsqueda profunda y evaluación de red."
                    return {
                        "success": True,
                        "move_uci": move_uci,
                        "move_san": san,
                        "score": score,
                        "explanation": exp,
                        "type": "posicional" if "Transformer" in self.name_label else "tactica",
                        "category": self.name_label
                    }
            elif hasattr(mod, "get_best_move"):
                move_uci = mod.get_best_move(fen, d)
                if move_uci:
                    try:
                        move = chess.Move.from_uci(move_uci)
                        san = board.san(move)
                    except Exception:
                        san = move_uci
                    exp = f"[{self.name_label}] Jugada calculada con Mini-Transformer posicional y poda táctica."
                    return {
                        "success": True,
                        "move_uci": move_uci,
                        "move_san": san,
                        "score": 0.0,
                        "explanation": exp,
                        "type": "posicional",
                        "category": self.name_label
                    }
        legal = list(board.legal_moves)
        if not legal:
            return {"success": False, "message": "No hay movimientos legales."}
        fallback_move = legal[0]
        return {
            "success": True,
            "move_uci": fallback_move.uci(),
            "move_san": board.san(fallback_move),
            "score": 0.0,
            "explanation": f"[{self.name_label}] Jugada fallback.",
            "type": "posicional",
            "category": self.name_label
        }

    def explicar_movimiento_realizado(self, board_before: chess.Board, move: chess.Move, depth: int = 2, strategy: str = "tactico") -> Dict[str, Any]:
        p = board_before.piece_at(move.from_square)
        p_name = chess.piece_name(p.piece_type) if p else "pieza"
        to_name = chess.square_name(move.to_square)
        return {
            "type": "posicional" if "Transformer" in self.name_label else "tactica",
            "category": self.name_label,
            "explanation": f"[{self.name_label}] {p_name.capitalize()} hacia {to_name} (evaluado con red y árbol de búsqueda)."
        }

class GameEngine:
    """
    Motor de Juego para la Interfaz Web.
    Mantiene el estado de la partida actual, el historial de jugadas en formato SAN/FEN,
    el tablero de python-chess y la integración con el HumanChessEngine para la IA y explicaciones.
    """

    def __init__(self, player_color: str = "white", game_mode: str = "pve", depth: int = 2, strategy: str = "tactico"):
        self.player_color = player_color.lower()  # "white" o "black"
        self.game_mode = game_mode.lower()        # "pvp" o "pve"
        self.engine_depth = depth
        self.engine_strategy = strategy
        self.engine_version = "minimax2"
        self.engine_config = {}

        self.board = chess.Board()
        self.move_history: List[Dict[str, Any]] = []
        self.initial_grid = self.build_grid_from_board(chess.Board())

        self.ai_engine_1 = HumanChessEngine(default_depth=depth)
        self.ai_engine_2 = Minimax2Engine(default_depth=depth)
        self.ai_engine_original = CppEngineAdapter("engine_original_cpp", "Negamax Clásico C++", default_depth=depth)
        self.ai_engine_nnue = CppEngineAdapter("engine_NNUE_cpp", "Red Neuronal NNUE (C++)", default_depth=depth)
        self.ai_engine_t_mini = CppEngineAdapter("engine_T_mini_cpp", "Mini-Transformer 75k (C++)", default_depth=depth)
        self.ai_engine_t_medium = CppEngineAdapter("engine_T_medium_cpp", "Medium-Transformer 238k (C++)", default_depth=depth)
        self.ai_engine_t_8x256 = CppEngineAdapter("engine_transformer_8x256_cpp", "Rich-Transformer 8x256 (C++)", default_depth=depth)
        self.ai_engine_t_4x128 = CppEngineAdapter("engine_transformer_4x128_cpp", "Rich-Transformer 4x128 (C++)", default_depth=depth)
        self.ai_engine_total_128_4 = CppEngineAdapter("engine_Total_transformer128_4_cpp", "Total Transformer 128x4 (C++)", default_depth=depth)
        self.ai_engine_total_v2 = CppEngineAdapter("engine_T_total_V2_cpp", "Total Transformer V2 (700k Aperturas y Finales, C++)", default_depth=depth)
        self.ai_engine_1m_fen = CppEngineAdapter("engine_1M_FEN_cpp", "Dual-Head Transformer 1M (4.4M params, C++)", default_depth=depth)
        self.lock = threading.RLock()

    @property
    def ai_engine(self):
        v = (self.engine_version or "").lower()
        if v in ("engine_1m_fen", "engine_1m_fen_cpp", "engine_multifen", "engine_multifen_cpp", "1m_fen", "transformer_1m"):
            return self.ai_engine_1m_fen
        elif v in ("engine_t_total_v2", "engine_t_total_v2_cpp", "total_v2", "engine_total_v2", "total_transformer_v2"):
            return self.ai_engine_total_v2
        elif v in ("engine_total_transformer128_4", "engine_total_transformer128_4_cpp", "total_transformer128_4", "total_128_4"):
            return self.ai_engine_total_128_4
        elif v in ("engine_t_8x256", "engine_transformer_8x256_cpp", "transformer_8x256"):
            return self.ai_engine_t_8x256
        elif v in ("engine_t_4x128", "engine_transformer_4x128_cpp", "transformer_4x128"):
            return self.ai_engine_t_4x128
        elif v in ("engine_t_medium", "engine_t_medium_cpp", "transformer_medium"):
            return self.ai_engine_t_medium
        elif v in ("engine_t_mini", "engine_t_mini_cpp", "transformer_mini"):
            return self.ai_engine_t_mini
        elif v in ("engine_nnue", "engine_nnue_cpp", "nnue"):
            return self.ai_engine_nnue
        elif v in ("engine_original", "engine_original_cpp", "cpp_original"):
            return self.ai_engine_original
        elif v in ("minimax1", "human"):
            return self.ai_engine_1
        else:
            return self.ai_engine_2

    def reset_game(self, player_color: str = "white", game_mode: str = "pve", depth: int = 2, strategy: str = "tactico", use_king_zone_filter: bool = False, engine_version: str = "minimax2", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Reinicia la partida con los parámetros especificados."""
        with self.lock:
            self.player_color = player_color.lower()
            self.game_mode = game_mode.lower()
            self.engine_depth = depth
            self.engine_version = engine_version
            self.engine_config = config if config is not None else {}
        self.engine_strategy = strategy
        self.ai_engine_1.default_depth = depth
        if hasattr(self.ai_engine_1, "mate_forzado_eval"):
            self.ai_engine_1.mate_forzado_eval.use_king_zone_filter = use_king_zone_filter
        self.ai_engine_2.default_depth = depth

        self.board = chess.Board()
        self.move_history = []
        self.initial_grid = self.build_grid_from_board(chess.Board())
        self.ai_engine.transposition_table.clear()

        # Si jugamos como Negras en PvE, la IA debe mover primero como Blancas
        ai_move_info = None
        if self.game_mode == "pve" and self.player_color == "black":
            ai_move_info = self.make_ai_move()

        return {
            "success": True,
            "state": self.get_board_state(),
            "ai_move": ai_move_info
        }

    def set_game_mode(self, game_mode: str, player_color: str = "white", depth: Optional[int] = None, strategy: Optional[str] = None, tree_mode: str = "cut", time_limit: Optional[float] = None, use_king_zone_filter: bool = False, engine_version: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Cambia el modo de juego (pvp o pve) y el color del jugador sin reiniciar el tablero ni el historial.
        Si se cambia a PvE y es el turno del motor, la IA responde inmediatamente.
        """
        with self.lock:
            self.game_mode = game_mode.lower()
            self.player_color = player_color.lower()
            if hasattr(self.ai_engine_1, "mate_forzado_eval"):
                self.ai_engine_1.mate_forzado_eval.use_king_zone_filter = use_king_zone_filter
            if engine_version:
                self.engine_version = engine_version

        if depth is not None:
            self.engine_depth = depth
        if strategy is not None:
            self.engine_strategy = strategy
        if config is not None:
            self.engine_config = config

        ai_move_result = None
        if self.game_mode == "pve" and not self.board.is_game_over():
            engine_color = chess.BLACK if self.player_color == "white" else chess.WHITE
            if self.board.turn == engine_color:
                ai_move_result = self.make_ai_move(tree_mode=tree_mode, time_limit=time_limit, config=self.engine_config)

        return {
            "success": True,
            "state": self.get_board_state(),
            "ai_move": ai_move_result
        }

    def load_pgn(self, pgn_text: str) -> Dict[str, Any]:
        """Carga un historial de jugadas en formato PGN o lista SAN."""
        with self.lock:
            self.board = chess.Board()
            self.move_history = []
            self.initial_grid = self.build_grid_from_board(chess.Board())
        self.ai_engine.transposition_table.clear()

        clean_text = re.sub(r'\{[^}]*\}', '', pgn_text)
        clean_text = re.sub(r';[^\n]*', '', clean_text)
        clean_text = re.sub(r'\d+\.\.\.', '', clean_text)
        clean_text = re.sub(r'\d+\.', '', clean_text)
        clean_text = re.sub(r'(1-0|0-1|1/2-1/2|\*)', ' ', clean_text)

        tokens = clean_text.strip().split()

        parsed_count = 0
        for token in tokens:
            token = token.strip()
            if not token:
                continue

            try:
                move = self.board.parse_san(token)
            except ValueError:
                try:
                    move = chess.Move.from_uci(token)
                except ValueError:
                    continue

            if move in self.board.legal_moves:
                fen_before = self.board.fen()
                board_before = self.board.copy(stack=False)

                san = self.board.san(move)
                from_sq = chess.square_name(move.from_square)
                to_sq = chess.square_name(move.to_square)

                exp_info = self.ai_engine.explicar_movimiento_realizado(board_before, move, depth=self.engine_depth, strategy=self.engine_strategy)

                self.board.push(move)
                fen_after = self.board.fen()

                self.move_history.append({
                    "from": from_sq,
                    "to": to_sq,
                    "san": san,
                    "uci": move.uci(),
                    "fen_before": fen_before,
                    "fen_after": fen_after,
                    "fen_grid": self.build_grid_from_fen(fen_after),
                    "explanation": exp_info.get("explanation", ""),
                    "type": exp_info.get("type", "posicional"),
                    "category": exp_info.get("category", "")
                })
                parsed_count += 1

        return {
            "success": parsed_count > 0,
            "parsed_moves": parsed_count,
            "state": self.get_board_state()
        }

    def truncate_history(self, target_index: int):
        """
        Trunca el historial hasta target_index para permitir jugar una variante nueva desde una posición del pasado.
        """
        with self.lock:
            if 0 <= target_index < len(self.move_history):
                target_entry = self.move_history[target_index]
                fen_to_restore = target_entry.get("fen_after", target_entry.get("fen_before"))
                self.move_history = self.move_history[:target_index + 1]
                self.board = chess.Board(fen_to_restore)
            elif target_index < 0:
                self.move_history.clear()
                self.board.reset()

    def get_board_for_move_index(self, move_index: Optional[int] = None) -> chess.Board:
        """Devuelve un objeto chess.Board representativo del índice del historial dado (siempre una copia independiente)."""
        with self.lock:
            if move_index is None or move_index >= len(self.move_history):
                return self.board.copy(stack=False)
            if move_index < 0:
                return chess.Board()
            
            entry = self.move_history[move_index]
            fen = entry.get("fen_after", entry.get("fen_before"))
            return chess.Board(fen)

    def get_legal_destinations(self, square_name: str, move_index: Optional[int] = None) -> List[str]:
        with self.lock:
            target_board = self.get_board_for_move_index(move_index)
            try:
                from_square = chess.parse_square(square_name)
            except ValueError:
                return []

        legal_dests = []
        for move in target_board.legal_moves:
            if move.from_square == from_square:
                legal_dests.append(chess.square_name(move.to_square))
        
        return list(set(legal_dests))

    def make_move(self, from_sq: str, to_sq: str, promotion: Optional[str] = None, truncate_at: Optional[int] = None, depth: Optional[int] = None, strategy: Optional[str] = None, tree_mode: str = "cut", time_limit: Optional[float] = None, engine_version: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ejecuta un movimiento. Si truncate_at está definido, deshace las jugadas posteriores para ramificar una nueva variante.
        """
        with self.lock:
            if depth is not None:
                try:
                    self.engine_depth = int(depth)
                except (ValueError, TypeError):
                    pass
            if strategy is not None:
                self.engine_strategy = strategy
            if engine_version is not None:
                self.engine_version = engine_version
            if config is not None:
                self.engine_config = config

            if truncate_at is not None:
                self.truncate_history(truncate_at)

            if self.board.is_game_over():
                return {"success": False, "message": "La partida ya ha finalizado."}

            fen_before = self.board.fen()
            board_before = self.board.copy(stack=False)

            try:
                from_square = chess.parse_square(from_sq)
                to_square = chess.parse_square(to_sq)
                piece = self.board.piece_at(from_square)
                
                promo_choice = promotion if promotion else "q"
                uci_str = f"{from_sq}{to_sq}"
                if piece and piece.piece_type == chess.PAWN:
                    target_rank = chess.square_rank(to_square)
                    if (piece.color == chess.WHITE and target_rank == 7) or (piece.color == chess.BLACK and target_rank == 0):
                        uci_str += promo_choice.lower()
                
                move = chess.Move.from_uci(uci_str)
            except ValueError:
                return {"success": False, "message": "Formato de casilla o movimiento inválido."}

            if move in self.board.legal_moves:
                san = self.board.san(move)
                start_t = time.time()
                exp_info = self.ai_engine.explicar_movimiento_realizado(board_before, move, depth=self.engine_depth, strategy=self.engine_strategy)
                elapsed_s = round(time.time() - start_t, 2)
                self.board.push(move)
                fen_after = self.board.fen()

                self.move_history.append({
                    "from": from_sq,
                    "to": to_sq,
                    "san": san,
                    "uci": move.uci(),
                    "fen_before": fen_before,
                    "fen_after": fen_after,
                    "fen_grid": self.build_grid_from_fen(fen_after),
                    "explanation": exp_info.get("explanation", f"Movimiento ejecutado: {san}"),
                    "type": exp_info.get("type", "posicional"),
                    "category": exp_info.get("category", ""),
                    "time_seconds": elapsed_s
                })
                
                ai_move_result = None

                is_ai_turn = (self.game_mode == "pve") and not self.board.is_game_over()
                if is_ai_turn:
                    engine_color = chess.BLACK if self.player_color == "white" else chess.WHITE
                    if self.board.turn == engine_color:
                        ai_move_result = self.make_ai_move(tree_mode=tree_mode, time_limit=time_limit, config=self.engine_config)

                return {
                    "success": True,
                    "san": san,
                    "state": self.get_board_state(),
                    "ai_move": ai_move_result
                }
            else:
                return {"success": False, "message": "Movimiento ilegal según las reglas del ajedrez."}

    def make_ai_move(self, depth: Optional[int] = None, strategy: Optional[str] = None, tree_mode: str = "cut", time_limit: Optional[float] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ejecuta la jugada seleccionada por el motor de ajedrez humano.
        """
        with self.lock:
            if self.board.is_game_over():
                return None
    
            try:
                eval_depth = int(depth) if depth is not None else int(self.engine_depth)
            except (ValueError, TypeError):
                eval_depth = 2
        eval_strategy = strategy if strategy is not None else self.engine_strategy

        fen_before = self.board.fen()
        board_before = self.board.copy(stack=False)
        start_t = time.time()
        cfg = config if config is not None else self.engine_config
        res = self.ai_engine.seleccionar_movimiento(self.board, depth=eval_depth, strategy=eval_strategy, tree_mode=tree_mode, time_limit=time_limit, config=cfg)
        elapsed_s = round(time.time() - start_t, 2)
        if not res.get("success"):
            return None

        move_uci = res.get("move_uci")
        if move_uci is None:
            # El motor no encontro jugada (todas suicidas o posicion especial)
            # Fallback: usar la primera jugada legal
            legal = list(self.board.legal_moves)
            if not legal:
                return None
            move = legal[0]
            move_uci = move.uci()
        else:
            move = chess.Move.from_uci(move_uci)

        if move in self.board.legal_moves:
            san = self.board.san(move)
            from_sq = chess.square_name(move.from_square)
            to_sq = chess.square_name(move.to_square)

            self.board.push(move)
            fen_after = self.board.fen()

            move_info = {
                "from": from_sq,
                "to": to_sq,
                "san": san,
                "uci": move_uci,
                "fen_before": fen_before,
                "fen_after": fen_after,
                "fen_grid": self.build_grid_from_fen(fen_after),
                "explanation": res.get("explanation", ""),
                "type": res.get("type", "posicional"),
                "category": res.get("category", ""),
                "time_seconds": elapsed_s
            }
            self.move_history.append(move_info)

            return {
                "success": True,
                "move_san": san,
                "move_uci": move_uci,
                "explanation": res.get("explanation", ""),
                "type": res.get("type", "posicional"),
                "category": res.get("category", ""),
                "score": res.get("score", 0.0)
            }

        return None

    def analyze_position(self, move_index: Optional[int] = None, depth: Optional[int] = None, strategy: Optional[str] = None, tree_mode: str = "cut", time_limit: Optional[float] = None, engine_version: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Genera una evaluación completa de la posición (actual o de un índice del historial),
        incluyendo la sugerencia de movimiento del motor y la explicación de la jugada anterior del oponente.
        """
        with self.lock:
            try:
                eval_depth = int(depth) if depth is not None else int(self.engine_depth)
            except (ValueError, TypeError):
                eval_depth = 2
            eval_strategy = strategy if strategy is not None else self.engine_strategy
            if engine_version is not None:
                self.engine_version = engine_version
    
            target_board = self.get_board_for_move_index(move_index)

        # 1. Explicación de la jugada anterior (si existe)
        previous_move_info = None
        effective_index = len(self.move_history) - 1 if move_index is None else move_index

        if 0 <= effective_index < len(self.move_history):
            prev_entry = self.move_history[effective_index]
            mover_color = "Blancas" if (effective_index % 2 == 0) else "Negras"
            
            previous_move_info = {
                "san": prev_entry.get("san", ""),
                "color": mover_color,
                "title": f"Última jugada ({mover_color}): {prev_entry.get('san', '')}",
                "explanation": prev_entry.get("explanation", "Movimiento ejecutado."),
                "type": prev_entry.get("type", "posicional"),
                "category": prev_entry.get("category", "")
            }

        # 2. Sugerencia del motor para la posición analizada
        if target_board.is_game_over():
            msg = "Partida Finalizada: "
            final_eval_white = 0.0
            mate_in_val = None
            if target_board.is_checkmate():
                winner = "Negras" if target_board.turn == chess.WHITE else "Blancas"
                msg += f"Jaque Mate. Ganan las {winner}."
                final_eval_white = -1000.0 if target_board.turn == chess.WHITE else 1000.0
                mate_in_val = 0
            else:
                msg += "Tablas (Empate)."

            return {
                "title": "Fin de Partida",
                "move_san": "-",
                "move_uci": None,
                "type": "info",
                "category": "fin_partida",
                "score": 0.0,
                "eval_white": final_eval_white,
                "mate_in": mate_in_val,
                "turn": "white" if target_board.turn == chess.WHITE else "black",
                "explanation": msg,
                "previous_move": previous_move_info
            }

        cfg = config if config is not None else self.engine_config
        ai_analysis = self.ai_engine.seleccionar_movimiento(target_board, depth=eval_depth, strategy=eval_strategy, tree_mode=tree_mode, time_limit=time_limit, config=cfg)

        turn_name = "Blancas" if target_board.turn == chess.WHITE else "Negras"
        analysis_title = f"Análisis en Tiempo Real (Sugerencia para {turn_name})"
        if move_index is not None and move_index < len(self.move_history) - 1:
            analysis_title = f"Análisis Histórico (Jugada #{move_index + 1} - Turno: {turn_name})"

        raw_score = ai_analysis.get("score", 0.0)
        eval_white = raw_score if target_board.turn == chess.WHITE else -raw_score

        mate_in = ai_analysis.get("mate_in")
        if mate_in is None:
            if ai_analysis.get("category") == "Jaque Mate" or abs(eval_white) >= 500:
                n_mate = self.find_forced_mate(target_board, max_depth=eval_depth)
                if n_mate is not None:
                    mate_in = n_mate if eval_white >= 0 else -n_mate

        return {
            "title": analysis_title,
            "move_san": ai_analysis.get("move_san", "-"),
            "move_uci": ai_analysis.get("move_uci"),
            "type": ai_analysis.get("type", "posicional"),
            "category": ai_analysis.get("category", "tactico"),
            "score": raw_score,
            "eval_white": eval_white,
            "mate_in": mate_in,
            "turn": "white" if target_board.turn == chess.WHITE else "black",
            "explanation": ai_analysis.get("explanation", "Posición evaluada correctamente."),
            "previous_move": previous_move_info
        }

    def find_forced_mate(self, board_obj: chess.Board, max_depth: int = 3) -> Optional[int]:
        """
        Calcula la cantidad exacta de jugadas para Mate Forzado (1 para Mate en 1, 2 para Mate en 2, 3 para Mate en 3).
        Aislando completamente el objeto Board para evitar mutaciones indeseadas y filtrando por jaques/capturas para velocidad extrema.
        """
        try:
            work_board = board_obj.copy(stack=True)
            if work_board.is_checkmate():
                return 0
            if work_board.is_game_over():
                return None

            attacker_color = work_board.turn

            def search_mate(b: chess.Board, depth_remaining: int) -> bool:
                if b.is_checkmate():
                    return True
                if depth_remaining <= 0 or b.is_game_over():
                    return False

                is_attacker = (b.turn == attacker_color)
                moves = list(b.legal_moves)
                if not moves:
                    return False

                if is_attacker:
                    tactical_moves = [m for m in moves if b.gives_check(m) or b.is_capture(m)]
                    candidate_moves = tactical_moves if tactical_moves else moves
                    for move in candidate_moves:
                        b.push(move)
                        won = search_mate(b, depth_remaining - 1)
                        b.pop()
                        if won:
                            return True
                    return False
                else:
                    for move in moves:
                        b.push(move)
                        won = search_mate(b, depth_remaining - 1)
                        b.pop()
                        if not won:
                            return False
                    return True

            for n in range(1, max_depth + 1):
                depth_ply = 2 * n - 1
                for move in list(work_board.legal_moves):
                    if work_board.gives_check(move) or work_board.is_capture(move) or n == 1:
                        work_board.push(move)
                        if search_mate(work_board, depth_ply - 1):
                            work_board.pop()
                            return n
                        work_board.pop()

            return None
        except Exception:
            return None

    def get_position_eval(self, board_obj: Optional[chess.Board] = None) -> float:
        """
        Calcula la evaluación estática rápida de la posición desde la perspectiva de las Blancas (eval_white en decipeones, donde 10.0 = 1 peón).
        Si board_obj es None, evalúa self.board.
        """
        with self.lock:
            target = board_obj.copy(stack=False) if board_obj is not None else self.board.copy(stack=False)
            curr_version = self.engine_version
            curr_cfg = self.engine_config

        if target.is_checkmate():
            return -1000.0 if target.turn == chess.WHITE else 1000.0
        if target.is_stalemate() or target.is_insufficient_material():
            return 0.0

        try:
            if curr_version == "minimax2" and hasattr(self.ai_engine_2, "evaluar_posicion"):
                score_turn = self.ai_engine_2.evaluar_posicion(target, config=curr_cfg)
            else:
                score_turn = self.ai_engine_1.evaluar_estado_estatico(target)
            
            # score_turn viene desde la perspectiva de target.turn. Convertir a perspectiva de Blancas:
            return score_turn if target.turn == chess.WHITE else -score_turn
        except Exception:
            return 0.0

    def get_board_state(self) -> Dict[str, Any]:
        """Devuelve el estado completo y serializado de la partida."""
        with self.lock:
            grid = self.build_grid_from_board(self.board)
            eval_white = self.get_position_eval(self.board)
            
            last_move_data = None
            if self.move_history:
                last = self.move_history[-1]
                last_move_data = {
                    "from": last["from"],
                    "to": last["to"],
                    "san": last["san"],
                    "uci": last["uci"]
                }

            res_msg = "En curso"
            if self.board.is_game_over():
                if self.board.is_checkmate():
                    winner = "Negras" if self.board.turn == chess.WHITE else "Blancas"
                    res_msg = f"¡Jaque Mate! Ganan las {winner}."
                elif self.board.is_stalemate():
                    res_msg = "Tablas por Rey Ahogado."
                elif self.board.is_insufficient_material():
                    res_msg = "Tablas por Material Insuficiente."
                else:
                    res_msg = "Tablas."
            elif self.board.is_check():
                res_msg = "¡Jaque!"

            return {
                "turn": "white" if self.board.turn == chess.WHITE else "black",
                "is_check": self.board.is_check(),
                "is_game_over": self.board.is_game_over(),
                "result_message": res_msg,
                "last_move": last_move_data,
                "grid": grid,
                "initial_grid": self.initial_grid,
                "history": self.move_history,
                "player_color": self.player_color,
                "game_mode": self.game_mode,
                "eval_white": eval_white,
                "engine_version": self.engine_version
            }

    def build_grid_from_board(self, board_obj: chess.Board) -> List[List[Dict[str, Any]]]:
        """Convierte un objeto Board en una matriz 8x8 serializable."""
        grid = []
        for r in range(7, -1, -1):
            row = []
            for f in range(8):
                sq = chess.square(f, r)
                piece = board_obj.piece_at(sq)
                square_name = chess.square_name(sq)
                
                if piece:
                    color = "white" if piece.color == chess.WHITE else "black"
                    piece_type = piece.symbol().lower()
                    row.append({
                        "square": square_name,
                        "color": color,
                        "type": piece_type
                    })
                else:
                    row.append({
                        "square": square_name,
                        "color": None,
                        "type": None
                    })
            grid.append(row)
        return grid

    def build_grid_from_fen(self, fen: str) -> List[List[Dict[str, Any]]]:
        """Convierte una cadena FEN en una matriz 8x8 serializable."""
        temp_board = chess.Board(fen)
        return self.build_grid_from_board(temp_board)