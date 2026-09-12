"""
Constantes compartidas para el Motor de Ajedrez Humano Explicable.
Unica fuente de verdad para valores de piezas, nombres y casillas estrategicas.
"""

import chess
from typing import Dict, Set, List

# ═══════════════════════════════════════════════════════════
# VALORES DE PIEZAS - Escala humana estandar (unica fuente)
# ═══════════════════════════════════════════════════════════
VALORES_PIEZAS: Dict[int, float] = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.25,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
    chess.KING: 200.0
}

# ═══════════════════════════════════════════════════════════
# NOMBRES EN ESPANOL (unica fuente)
# ═══════════════════════════════════════════════════════════
PIECE_NAMES_ES: Dict[int, str] = {
    chess.PAWN: "peon",
    chess.KNIGHT: "caballo",
    chess.BISHOP: "alfil",
    chess.ROOK: "torre",
    chess.QUEEN: "dama",
    chess.KING: "rey"
}

# ═══════════════════════════════════════════════════════════
# CASILLAS ESTRATEGICAS
# ═══════════════════════════════════════════════════════════
CASILLAS_CENTRO: Set[int] = {chess.D4, chess.E4, chess.D5, chess.E5}

CASILLAS_AMPLIO_CENTRO: Set[int] = {
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C6, chess.D6, chess.E6, chess.F6
}

# ═══════════════════════════════════════════════════════════
# UMBRALES DE EVALUACION
# ═══════════════════════════════════════════════════════════
SCORE_MATE: float = 10000.0
SCORE_MATE_RIVAL: float = -1000.0
UMBRAL_DESCARTE_DEFENSA: float = -20.0
FACTOR_RECURSION: float = 0.15
TOP_CANDIDATOS: int = 5

# ═══════════════════════════════════════════════════════════
# FILAS INICIALES POR COLOR
# ═══════════════════════════════════════════════════════════
FILAS_INICIALES: Dict[bool, int] = {
    chess.WHITE: 0,
    chess.BLACK: 7
}

# ═══════════════════════════════════════════════════════════
# DIRECCIONES DE MOVIMIENTO PARA PIEZAS DESLIZANTES
# ═══════════════════════════════════════════════════════════
DIRECCIONES_ALFIL: List[int] = [7, -7, 9, -9]
DIRECCIONES_TORRE: List[int] = [1, -1, 8, -8]
DIRECCIONES_DAMA: List[int] = [7, -7, 9, -9, 1, -1, 8, -8]