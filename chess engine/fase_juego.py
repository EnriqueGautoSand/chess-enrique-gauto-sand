"""
Detector de fase de juego y ajuste de pesos de evaluacion.

Fases:
- APERTURA (jugadas 1-10): Priorizar desarrollo y centro
- MEDIO_JUEGO (jugadas 11-30): Priorizar tactica y actividad
- FINAL (jugadas 31+): Priorizar estructura de peones y rey activo
"""

import chess
from typing import Dict, List

try:
    from .constantes import VALORES_PIEZAS
except ImportError:
    from constantes import VALORES_PIEZAS


class FaseJuegoDetector:
    """
    Detecta la fase de juego actual y ajusta los pesos de evaluacion.
    """
    
    APERTURA = "apertura"
    MEDIO_JUEGO = "medio_juego"
    FINAL = "final"
    
    PESOS: Dict[str, List[float]] = {
        "desarrollo":       [1.5, 1.0, 0.3],
        "centro":           [1.3, 1.0, 0.7],
        "seguridad_rey":    [1.5, 1.2, 0.5],
        "actividad_piezas": [0.8, 1.3, 1.0],
        "estructura_peones":[0.7, 1.0, 1.5],
        "material":         [1.0, 1.0, 1.2],
        "rey_activo":       [0.3, 0.5, 1.5],
    }
    
    def detectar_fase(self, board: chess.Board) -> str:
        """
        Detecta la fase de juego basada en material y numero de jugadas.
        """
        fullmove = board.fullmove_number
        
        material_mayor = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type in (chess.QUEEN, chess.ROOK, chess.KNIGHT, chess.BISHOP):
                material_mayor += 1
        
        if fullmove <= 10 and material_mayor >= 12:
            return self.APERTURA
        elif fullmove <= 30 or material_mayor >= 6:
            return self.MEDIO_JUEGO
        else:
            return self.FINAL
    
    def obtener_peso(self, categoria: str, board: chess.Board) -> float:
        """
        Obtiene el peso para una categoria de evaluacion segun la fase.
        """
        fase = self.detectar_fase(board)
        idx = {self.APERTURA: 0, self.MEDIO_JUEGO: 1, self.FINAL: 2}[fase]
        pesos = self.PESOS.get(categoria, [1.0, 1.0, 1.0])
        return pesos[idx]
    
    def ajustar_score(self, score: float, categoria: str, board: chess.Board) -> float:
        """
        Ajusta un score segun la fase de juego.
        """
        return score * self.obtener_peso(categoria, board)