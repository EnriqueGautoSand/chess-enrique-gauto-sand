"""
Evaluador de clavadas (pins) absolutas y relativas.

Clavada absoluta: Pieza que no puede moverse porque expone al REY.
Clavada relativa: Pieza que no deberia moverse porque expone pieza valiosa.
"""

import chess
import chess.polyglot
from typing import Tuple, List, Dict, Optional

try:
    from .constantes import VALORES_PIEZAS, PIECE_NAMES_ES, DIRECCIONES_ALFIL, DIRECCIONES_TORRE, DIRECCIONES_DAMA
    from .base_evaluator import BaseEvaluator
except ImportError:
    from constantes import VALORES_PIEZAS, PIECE_NAMES_ES, DIRECCIONES_ALFIL, DIRECCIONES_TORRE, DIRECCIONES_DAMA
    from base_evaluator import BaseEvaluator


class ClavadasEvaluator(BaseEvaluator):
    """
    Evaluador de clavadas (pins) absolutas y relativas.
    
    Logica de deteccion:
    1. Para cada pieza deslizante propia (Alfil, Torre, Dama)
    2. Trazar rayos en sus direcciones de ataque
    3. Si encuentra: pieza enemiga -> pieza enemiga valiosa/rey = CLAVADA
    """
    
    def detectar_clavadas_propias(self, board: chess.Board, color: Optional[chess.Color] = None) -> List[Dict]:
        """
        Detecta clavadas que el bando especificado ejerce sobre el rival.
        Si color es None, usa board.turn.
        """
        our_color = color if color is not None else board.turn
        
        if not hasattr(self, "_cache_clavadas"):
            self._cache_clavadas = {}
        cache_key = (chess.polyglot.zobrist_hash(board), our_color, "propias")
        if cache_key in self._cache_clavadas:
            return self._cache_clavadas[cache_key]

        clavadas = []
        enemy_color = not our_color
        
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.color != our_color:
                continue
            if piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
                continue
            
            if piece.piece_type == chess.BISHOP:
                direcciones = DIRECCIONES_ALFIL
            elif piece.piece_type == chess.ROOK:
                direcciones = DIRECCIONES_TORRE
            else:
                direcciones = DIRECCIONES_DAMA
            
            for d in direcciones:
                clavada = self._trazar_rayo_clavada(board, sq, d, enemy_color)
                if clavada:
                    clavadas.append(clavada)
        
        if len(self._cache_clavadas) > 5000:
            self._cache_clavadas.clear()
        self._cache_clavadas[cache_key] = clavadas
        return clavadas
    
    def detectar_clavadas_rivales(self, board: chess.Board, color: Optional[chess.Color] = None) -> List[Dict]:
        """
        Detecta clavadas que el RIVAL ejerce sobre el bando especificado.
        Si color es None, usa board.turn.
        """
        our_color = color if color is not None else board.turn
        
        if not hasattr(self, "_cache_clavadas"):
            self._cache_clavadas = {}
        cache_key = (chess.polyglot.zobrist_hash(board), our_color, "rivales")
        if cache_key in self._cache_clavadas:
            return self._cache_clavadas[cache_key]

        clavadas = []
        enemy_color = not our_color
        
        target_bb = board.occupied_co[our_color]

        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.color != enemy_color:
                continue
            if piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
                continue
            
            # Pre-filtro Bitboard: si no hay piezas del objetivo en los rayos de sq, omitir
            if piece.piece_type == chess.BISHOP:
                if not (chess.BB_DIAG_MASKS[sq] & target_bb):
                    continue
                direcciones = DIRECCIONES_ALFIL
            elif piece.piece_type == chess.ROOK:
                if not ((chess.BB_RANK_MASKS[sq] | chess.BB_FILE_MASKS[sq]) & target_bb):
                    continue
                direcciones = DIRECCIONES_TORRE
            else:
                if not ((chess.BB_DIAG_MASKS[sq] | chess.BB_RANK_MASKS[sq] | chess.BB_FILE_MASKS[sq]) & target_bb):
                    continue
                direcciones = DIRECCIONES_DAMA
            
            for d in direcciones:
                clavada = self._trazar_rayo_clavada(board, sq, d, our_color)
                if clavada:
                    clavadas.append(clavada)
        
        if len(self._cache_clavadas) > 5000:
            self._cache_clavadas.clear()
        self._cache_clavadas[cache_key] = clavadas
        return clavadas
    
    def _trazar_rayo_clavada(self, board: chess.Board, origen: int, 
                              direccion: int, color_objetivo: chess.Color) -> Optional[Dict]:
        """
        Traza un rayo desde 'origen' en 'direccion'.
        Busca: pieza_color_objetivo -> pieza_valiosa/rey del mismo color.
        """
        curr = origen
        primera_pieza = None
        primera_casilla = None
        
        while True:
            if direccion in (1, -7, 9) and chess.square_file(curr) == 7:
                break
            if direccion in (-1, 7, -9) and chess.square_file(curr) == 0:
                break
            
            curr += direccion
            if not (0 <= curr <= 63):
                break
            
            p = board.piece_at(curr)
            if p:
                if primera_pieza is None:
                    if p.color == color_objetivo:
                        primera_pieza = p
                        primera_casilla = curr
                    else:
                        break
                else:
                    if p.color == color_objetivo:
                        val1 = VALORES_PIEZAS.get(primera_pieza.piece_type, 1.0)
                        val2 = VALORES_PIEZAS.get(p.piece_type, 1.0)
                        
                        es_absoluta = (p.piece_type == chess.KING)
                        es_relativa = (val2 > val1 and val2 >= 3.0)
                        
                        if es_absoluta or es_relativa:
                            return {
                                "tipo": "absoluta" if es_absoluta else "relativa",
                                "pieza_clavada": primera_pieza,
                                "casilla_clavada": primera_casilla,
                                "pieza_detras": p,
                                "casilla_detras": curr,
                                "valor_en_juego": val1 if es_absoluta else min(val2, 9.0),
                                "direccion": direccion
                            }
                    break
        
        return None
    
    def evaluar_clavada_movimiento(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalua si un movimiento crea o explota una clavada.
        """
        piece = board.piece_at(move.from_square)
        if not piece:
            return 0.0, ""
        
        our_color = piece.color
        clavadas_antes = self.detectar_clavadas_propias(board, our_color)
        
        board.push(move)
        clavadas_despues = self.detectar_clavadas_propias(board, our_color)
        board.pop()
        
        nuevas_clavadas = [c for c in clavadas_despues 
                          if c["casilla_clavada"] not in [x["casilla_clavada"] for x in clavadas_antes]]
        
        if nuevas_clavadas:
            mejor = max(nuevas_clavadas, key=lambda x: x["valor_en_juego"])
            tipo = mejor["tipo"]
            pieza_clavada = PIECE_NAMES_ES.get(mejor["pieza_clavada"].piece_type, "pieza")
            pieza_detras = PIECE_NAMES_ES.get(mejor["pieza_detras"].piece_type, "pieza")
            sq_name = chess.square_name(mejor["casilla_clavada"])
            
            score = 40.0 + (mejor["valor_en_juego"] * 5.0)
            if mejor["tipo"] == "absoluta":
                score += 20.0
                if mejor["pieza_clavada"].piece_type == chess.QUEEN:
                    score += 250.0
                    return score, f"¡Clavada Letal a la Dama!: Clava absolutamente la {pieza_clavada} enemiga en {sq_name} contra el {pieza_detras}, paralizando a la Dama."
            
            return score, f"Crea clavada {tipo}: {pieza_clavada} en {sq_name} no puede moverse porque expone al {pieza_detras}."
        
        for clavada in clavadas_antes:
            if move.to_square == clavada["casilla_clavada"]:
                pieza_clavada = PIECE_NAMES_ES.get(clavada["pieza_clavada"].piece_type, "pieza")
                sq_name = chess.square_name(move.to_square)
                score = 35.0 + (clavada["valor_en_juego"] * 3.0)
                return score, f"Explota clavada: ataca {pieza_clavada} clavado en {sq_name}."
        
        return 0.0, ""
    
    def evaluar(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """Implementacion de la interfaz base."""
        return self.evaluar_clavada_movimiento(board, move)