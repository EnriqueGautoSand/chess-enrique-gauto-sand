"""
Detector de situaciones de tablas.

Detecta:
1. Tres repeticiones de posicion
2. Material insuficiente
3. Regla de 50 jugadas
4. Ahogado (stalemate)
5. Tendencia a tablas por material
"""

import chess
from typing import Tuple, Dict

try:
    from .constantes import VALORES_PIEZAS
except ImportError:
    from constantes import VALORES_PIEZAS


class TablasDetector:
    """
    Detector de situaciones de tablas y tendencia a tablas.
    """
    
    def detectar_tablas(self, board: chess.Board) -> Tuple[bool, str, str]:
        """
        Detecta si la posicion es tablas o tiene tendencia a tablas.
        
        Returns:
            Tuple[bool, str, str]: (es_tablas, tipo, explicacion)
        """
        if board.is_stalemate():
            return True, "ahogado", "Posicion de ahogado: el rey no esta en jaque pero no hay jugadas legales."
        
        if board.is_insufficient_material():
            return True, "material_insuficiente", "Material insuficiente para dar mate."
        
        if board.is_seventyfive_moves():
            return True, "regla_75", "Regla de 75 jugadas sin captura ni movimiento de peon."
        
        if board.is_fivefold_repetition():
            return True, "quinta_repeticion", "La posicion se ha repetido 5 veces."
        
        if board.can_claim_fifty_moves():
            return True, "regla_50", "Se puede reclamar tablas por regla de 50 jugadas."
        
        if board.can_claim_threefold_repetition():
            return True, "triple_repeticion", "Se puede reclamar tablas por triple repeticion."
        
        material = self._analizar_material(board)
        if material["es_tablas_probable"]:
            return False, "tablas_probables", material["explicacion"]
        
        return False, "ninguna", ""
    
    def _analizar_material(self, board: chess.Board) -> Dict:
        """
        Analiza el material para determinar si hay tendencia a tablas.
        """
        piezas_blancas = {}
        piezas_negras = {}
        
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece:
                continue
            if piece.color == chess.WHITE:
                piezas_blancas[piece.piece_type] = piezas_blancas.get(piece.piece_type, 0) + 1
            else:
                piezas_negras[piece.piece_type] = piezas_negras.get(piece.piece_type, 0) + 1
        
        if (piezas_blancas.get(chess.BISHOP, 0) == 1 and 
            piezas_negras.get(chess.BISHOP, 0) == 1 and
            piezas_blancas.get(chess.QUEEN, 0) == 0 and
            piezas_negras.get(chess.QUEEN, 0) == 0 and
            piezas_blancas.get(chess.ROOK, 0) == 0 and
            piezas_negras.get(chess.ROOK, 0) == 0):
            
            alfil_blanco_sq = None
            alfil_negro_sq = None
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if p and p.piece_type == chess.BISHOP:
                    if p.color == chess.WHITE:
                        alfil_blanco_sq = sq
                    else:
                        alfil_negro_sq = sq
            
            if alfil_blanco_sq is not None and alfil_negro_sq is not None:
                color_blanco = (chess.square_file(alfil_blanco_sq) + chess.square_rank(alfil_blanco_sq)) % 2
                color_negro = (chess.square_file(alfil_negro_sq) + chess.square_rank(alfil_negro_sq)) % 2
                
                if color_blanco == color_negro:
                    return {
                        "es_tablas_probable": True,
                        "explicacion": "Alfiles del mismo color: tendencia a tablas en final."
                    }
        
        return {"es_tablas_probable": False, "explicacion": ""}
    
    def evaluar_tendencia_tablas(self, board: chess.Board) -> Tuple[float, str]:
        """
        Devuelve un score de tendencia a tablas.
        Score cercano a 0 = posicion tablifera.
        """
        es_tablas, tipo, exp = self.detectar_tablas(board)
        
        if es_tablas:
            return 0.0, f"TABLAS: {exp}"
        
        if tipo == "tablas_probables":
            return 5.0, f"Tendencia a tablas: {exp}"
        
        return 100.0, ""