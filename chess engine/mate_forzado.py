"""
Modulo de Deteccion de Mate Forzado y Mate Imparable.

Conceptos:
- Mate forzado: Secuencia de jugadas forzadas (generalmente jaques) donde el rival
  tiene respuestas limitadas y no puede evitar el mate. Ejemplo: mate en 2 con
  jaque doble seguido de mate.
  
- Mate imparable: Amenaza de mate que el rival no puede evitar aunque tenga jugadas
  legales. No es una secuencia forzada de jaques, pero las piezas del rival no
  llegan a tiempo a defender. Ejemplo: amenaza de mate en 1 que el rival no puede
  cubrir porque sus piezas estan lejos.

Evaluacion bidireccional:
- Si el MOTOR puede forzar mate al rival: +INFINITO (SCORE_MATE_FORZADO)
- Si el RIVAL puede forzar mate al motor: -INFINITO (-SCORE_MATE_FORZADO)
"""
import chess
from typing import Tuple, Optional, List

try:
    from .constantes import SCORE_MATE
except ImportError:
    from constantes import SCORE_MATE

# Score para mate forzado/imparable (mayor que SCORE_MATE para prioridad absoluta)
SCORE_MATE_FORZADO = 99999.0


class MateForzadoEvaluator:
    """
    Evaluador de mate forzado y mate imparable optimizado.
    Usa búsqueda limitada en profundidad para detectar secuencias de mate sin clonar tableros.
    """

    def __init__(self, max_depth_mate: int = 5, use_king_zone_filter: bool = False):
        """
        max_depth_mate: Profundidad máxima para buscar mate forzado.
        use_king_zone_filter: Si es True, aplica el pre-filtro Bitboard de zona del rey. Por defecto False.
        """
        self.max_depth_mate = max_depth_mate
        self.use_king_zone_filter = use_king_zone_filter
        self._cache_mate = {}

    def clear_cache(self):
        """Limpia la caché de evaluaciones de mate por posición."""
        self._cache_mate.clear()

    def _es_zona_rey_amenazada(self, board: chess.Board) -> bool:
        """
        Pre-filtro Bitboard opcional de la zona del rey enemigo.
        """
        if not self.use_king_zone_filter:
            return True
        enemy_color = not board.turn
        king_sq = board.king(enemy_color)
        if king_sq is None:
            return True
        king_zone_bb = chess.BB_KING_ATTACKS[king_sq] | chess.BB_SQUARES[king_sq]
        our_color = board.turn
        attackers_count = len(board.attackers(our_color, king_sq))
        attackers_zone = board.attacks_mask(our_color) & king_zone_bb
        return bool(attackers_count or attackers_zone)

    def detectar_mate_en_n(self, board: chess.Board, depth: int) -> Tuple[bool, int, Optional[chess.Move]]:
        """
        Detecta si el lado que mueve puede dar mate en 'depth' jugadas o menos.
        Solo busca secuencias forzadas: cada jugada nuestra debe ser jaque.
        Retorna (hay_mate, jugadas_para_mate, mejor_movimiento).
        """
        if depth <= 0:
            return False, 0, None

        if not self._es_zona_rey_amenazada(board):
            return False, 0, None

        # Lookup en caché por hash Zobrist
        zobrist = chess.polyglot.zobrist_hash(board)
        cache_key = (zobrist, depth, board.turn, "mate_en_n")
        if cache_key in self._cache_mate:
            return self._cache_mate[cache_key]

        # Caso base: mate en 1
        for move in board.legal_moves:
            if board.gives_check(move):
                board.push(move)
                is_mate = board.is_checkmate()
                board.pop()
                if is_mate:
                    res = (True, 1, move)
                    self._cache_mate[cache_key] = res
                    return res

        if depth == 1:
            res = (False, 0, None)
            self._cache_mate[cache_key] = res
            return res

        # Buscar mate forzado: solo considerar jugadas que dan jaque
        for move in board.legal_moves:
            if not board.gives_check(move):
                continue

            board.push(move)
            rival_puede_defender = False
            for rival_move in board.legal_moves:
                board.push(rival_move)
                hay_mate, _, _ = self.detectar_mate_en_n(board, depth - 2)
                board.pop()
                if not hay_mate:
                    rival_puede_defender = True
                    break

            board.pop()
            if not rival_puede_defender:
                res = (True, depth, move)
                self._cache_mate[cache_key] = res
                return res

        res = (False, 0, None)
        self._cache_mate[cache_key] = res
        return res

    def detectar_mate_imparable(self, board: chess.Board, depth: int = 3) -> Tuple[bool, int, Optional[chess.Move], str]:
        """
        Detecta mate imparable: amenaza de mate que el rival no puede evitar.
        Retorna (hay_mate_imparable, jugadas_para_mate, movimiento, explicacion).
        """
        if depth <= 0:
            return False, 0, None, ""

        if not self._es_zona_rey_amenazada(board):
            return False, 0, None, ""

        zobrist = chess.polyglot.zobrist_hash(board)
        cache_key = (zobrist, depth, board.turn, "mate_imparable")
        if cache_key in self._cache_mate:
            return self._cache_mate[cache_key]

        enemy_color = not board.turn
        king_sq = board.king(enemy_color)
        king_zone = (chess.BB_KING_ATTACKS[king_sq] | chess.BB_SQUARES[king_sq]) if king_sq is not None else 0

        for move in board.legal_moves:
            # Pre-filtro inteligente: solo investigar amenaza de mate imparable si la jugada da jaque,
            # entra a la zona del rey rival o si nuestras piezas ya atacan la zona del rey rival.
            to_sq_bb = chess.BB_SQUARES[move.to_square]
            if not (board.gives_check(move) or (to_sq_bb & king_zone) or (board.attacks_mask(board.turn) & king_zone)):
                continue

            board.push(move)

            # Si damos jaque mate directamente, no es "imparable" a futuro, es mate ya mismo
            # (Esto lo maneja evaluar_movimiento_mate, pero por completitud si cae aqui)
            if board.is_checkmate():
                board.pop()
                continue

            # Verificar si el rival tiene ALGUNA jugada que evite un mate forzado nuestro
            todas_llevan_a_mate = True
            has_legal = False
            for rival_move in board.legal_moves:
                has_legal = True
                board.push(rival_move)
                
                # Despues de la respuesta del rival, ¿tenemos mate forzado?
                hay_mate, _, _ = self.detectar_mate_en_n(board, depth - 1)
                
                board.pop()
                
                if not hay_mate:
                    todas_llevan_a_mate = False
                    break # El rival puede defenderse de esta amenaza

            board.pop()
            
            # Si el rival no tenia jugadas (y no era mate, ergo rey ahogado), o si todas llevan a mate
            if has_legal and todas_llevan_a_mate:
                san = board.san(move)
                res = (True, depth + 1, move, f"Mate imparable: {san} inicia secuencia inevitable para el rival.")
                self._cache_mate[cache_key] = res
                return res

        res = (False, 0, None, "")
        self._cache_mate[cache_key] = res
        return res

    def evaluar_mate_bidireccional(self, board: chess.Board, depth: int = None) -> Tuple[float, str, Optional[chess.Move]]:
        """
        Evaluacion bidireccional de mate forzado/imparable.
        """
        if depth is None:
            depth = self.max_depth_mate

        hay_mate_nuestro, dist, move = self.detectar_mate_en_n(board, depth)
        if hay_mate_nuestro:
            score = SCORE_MATE_FORZADO - (dist * 100)
            san = board.san(move) if move else "?"
            return score, f"Mate forzado en {dist} jugadas. Mejor: {san}.", move

        hay_imparable, dist_imp, move_imp, exp_imp = self.detectar_mate_imparable(board, min(depth, 3))
        if hay_imparable:
            score = SCORE_MATE_FORZADO - (dist_imp * 100) - 50
            return score, exp_imp, move_imp

        # Simular turno del rival para mate contra nosotros
        board.turn = not board.turn
        hay_mate_rival, dist_rival, _ = self.detectar_mate_en_n(board, depth)
        hay_imparable_rival, dist_imp_r, _, exp_imp_r = self.detectar_mate_imparable(board, min(depth, 3))
        board.turn = not board.turn  # Restaurar turno original

        if hay_mate_rival:
            score = -(SCORE_MATE_FORZADO - (dist_rival * 100))
            return score, f"PELIGRO: El rival puede forzar mate en {dist_rival} jugadas.", None

        if hay_imparable_rival:
            score = -(SCORE_MATE_FORZADO - (dist_imp_r * 100) - 50)
            return score, f"PELIGRO: {exp_imp_r}", None

        return 0.0, "", None

    def evaluar_movimiento_mate(self, board: chess.Board, move: chess.Move, depth: int = None) -> Tuple[float, str]:
        """
        Evalua un movimiento especifico en terminos de mate forzado/imparable sin clonar tableros ni duplicar bucles.
        """
        if depth is None:
            depth = self.max_depth_mate

        board.push(move)

        if board.is_checkmate():
            board.pop()
            return SCORE_MATE_FORZADO, "Jaque mate directo."

        # Verificar si tras nuestra jugada el rival tiene mate forzado o imparable
        hay_mate_rival, dist_rival, _ = self.detectar_mate_en_n(board, depth)
        if hay_mate_rival:
            board.pop()
            return -(SCORE_MATE_FORZADO - (dist_rival * 100)), f"Permite mate forzado del rival en {dist_rival} jugadas."

        hay_imp_rival, dist_imp_r, _, exp_imp_r = self.detectar_mate_imparable(board, min(depth, 3))
        if hay_imp_rival:
            board.pop()
            return -(SCORE_MATE_FORZADO - (dist_imp_r * 100) - 50), f"Permite mate imparable del rival: {exp_imp_r}"

        board.pop()
        return 0.0, ""