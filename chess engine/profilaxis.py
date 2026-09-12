"""
Evaluador de profilaxis.

La profilaxis es el arte de prevenir los planes del rival
ANTES de que se materialicen.

Logica:
1. Identificar las amenazas potenciales del rival
2. Priorizar jugadas que neutralicen esos planes
"""

import chess
from typing import Tuple, List, Dict

try:
    from .constantes import VALORES_PIEZAS
except ImportError:
    from constantes import VALORES_PIEZAS


class ProfilaxisEvaluator:
    """
    Evaluador de profilaxis.
    Evalua si un movimiento tiene valor profilactico.
    """
    
    def evaluar_profilaxis(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalua si un movimiento tiene valor profilactico.
        """
        amenazas_rivales = self._identificar_amenazas_rivales(board)
        
        if not amenazas_rivales:
            return 0.0, ""
        
        temp_board = board.copy(stack=False)
        temp_board.push(move)
        
        amenazas_despues = self._identificar_amenazas_rivales(temp_board)
        
        amenazas_neutralizadas = len(amenazas_rivales) - len(amenazas_despues)
        
        if amenazas_neutralizadas > 0:
            ids_despues = set(x["id"] for x in amenazas_despues)
            valor_neutralizado = sum(
                a["valor"] for a in amenazas_rivales 
                if a["id"] not in ids_despues
            )
            
            score = 10.0 + (valor_neutralizado * 3.0)
            return score, f"Jugada profilactica: neutraliza {amenazas_neutralizadas} amenaza(s) rival(es)."
        
        return 0.0, ""
    
    def _identificar_amenazas_rivales(self, board: chess.Board) -> List[Dict]:
        """
        Identifica amenazas potenciales del rival.
        """
        amenazas = []
        enemy_color = not board.turn
        
        board_rival = board.copy(stack=False)
        board_rival.turn = enemy_color
        
        for move in board_rival.legal_moves:
            if board_rival.is_capture(move):
                target = board_rival.piece_at(move.to_square)
                if target:
                    val = VALORES_PIEZAS.get(target.piece_type, 1.0)
                    if val >= 3.0:
                        amenazas.append({
                            "id": f"cap_{move.uci()}",
                            "tipo": "captura",
                            "valor": val,
                            "move": move
                        })
            
            if board_rival.gives_check(move):
                amenazas.append({
                    "id": f"jaq_{move.uci()}",
                    "tipo": "jaque",
                    "valor": 5.0,
                    "move": move
                })
            
            if move.promotion:
                amenazas.append({
                    "id": f"cor_{move.uci()}",
                    "tipo": "coronacion",
                    "valor": 9.0,
                    "move": move
                })
        
        return amenazas