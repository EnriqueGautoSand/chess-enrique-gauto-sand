"""
Evaluador de iniciativa.

La iniciativa mide quien dicta el ritmo de la partida.
Factores:
- Numero de amenazas activas
- Piezas desarrolladas vs sin desarrollar
- Control del centro
- Presion sobre el rey enemigo
"""

import chess
from typing import Tuple

try:
    from .constantes import VALORES_PIEZAS, CASILLAS_CENTRO
except ImportError:
    from constantes import VALORES_PIEZAS, CASILLAS_CENTRO


class IniciativaEvaluator:
    """
    Evaluador de iniciativa.
    Score positivo = nosotros tenemos iniciativa.
    """
    
    def evaluar_iniciativa(self, board: chess.Board) -> Tuple[float, str]:
        """
        Evalua la iniciativa de ambos bandos.
        """
        our_color = board.turn
        enemy_color = not our_color
        
        our_threats = self._contar_amenazas(board, our_color)
        our_development = self._contar_desarrollo(board, our_color)
        our_center = self._contar_control_centro(board, our_color)
        our_king_pressure = self._evaluar_presion_rey(board, our_color)
        
        enemy_threats = self._contar_amenazas(board, enemy_color)
        enemy_development = self._contar_desarrollo(board, enemy_color)
        enemy_center = self._contar_control_centro(board, enemy_color)
        enemy_king_pressure = self._evaluar_presion_rey(board, enemy_color)
        
        our_score = (our_threats * 3 + our_development * 2 + 
                     our_center * 2 + our_king_pressure * 4)
        enemy_score = (enemy_threats * 3 + enemy_development * 2 + 
                       enemy_center * 2 + enemy_king_pressure * 4)
        
        diferencia = our_score - enemy_score
        
        if diferencia > 10:
            return 15.0, "Tenemos fuerte iniciativa: dictamos el ritmo de la partida."
        elif diferencia > 5:
            return 8.0, "Tenemos ligera iniciativa."
        elif diferencia < -10:
            return -15.0, "El rival tiene fuerte iniciativa."
        elif diferencia < -5:
            return -8.0, "El rival tiene ligera iniciativa."
        
        return 0.0, ""
    
    def _contar_amenazas(self, board: chess.Board, color: chess.Color) -> int:
        """Cuenta amenazas activas de un color."""
        amenazas = 0
        enemy_color = not color
        
        # Filtro de bitboard para piezas valiosas del oponente (excluyendo peones y rey)
        enemy_valuable = board.occupied_co[enemy_color] & ~board.pawns & ~board.kings
        for sq in chess.scan_reversed(enemy_valuable):
            attackers = board.attackers(color, sq)
            if attackers:
                amenazas += 1
        return amenazas
    
    def _contar_desarrollo(self, board: chess.Board, color: chess.Color) -> int:
        """Cuenta piezas menores desarrolladas."""
        # Interseccion de mascara de caballos y alfiles con las piezas del color,
        # excluyendo las piezas en la fila de inicio
        fila_mask = chess.BB_RANK_1 if color == chess.WHITE else chess.BB_RANK_8
        menores_desarrolladas = board.occupied_co[color] & (board.knights | board.bishops) & ~fila_mask
        return int.bit_count(menores_desarrolladas)
    
    def _contar_control_centro(self, board: chess.Board, color: chess.Color) -> int:
        """Cuenta casillas centrales controladas."""
        control = 0
        for sq in CASILLAS_CENTRO:
            if board.is_attacked_by(color, sq):
                control += 1
        return control
    
    def _evaluar_presion_rey(self, board: chess.Board, color: chess.Color) -> int:
        """Evalua presion sobre el rey enemigo."""
        enemy_color = not color
        rey_sq = board.king(enemy_color)
        if rey_sq is None:
            return 0
        
        presion = 0
        for sq in chess.scan_reversed(board.occupied_co[color]):
            dist = max(abs(chess.square_file(sq) - chess.square_file(rey_sq)),
                      abs(chess.square_rank(sq) - chess.square_rank(rey_sq)))
            if dist <= 2:
                presion += 1
        return presion