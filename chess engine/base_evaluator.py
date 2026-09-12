"""
Interfaz base para todos los evaluadores del motor de ajedrez.
Garantiza que todos los modulos sigan el mismo patron de diseno.
"""

import chess
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any


class BaseEvaluator(ABC):
    """
    Interfaz base abstracta para todos los evaluadores del motor.
    
    Todos los evaluadores deben implementar el metodo evaluar()
    que recibe un tablero y un movimiento, y retorna un score
    junto con una explicacion en lenguaje natural.
    """
    
    @abstractmethod
    def evaluar(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalua un movimiento en la posicion dada.
        
        Args:
            board: Posicion actual del tablero
            move: Movimiento candidato a evaluar
            
        Returns:
            Tuple[float, str]: (score, explicacion)
                - score: Valor numerico de la evaluacion
                - explicacion: Descripcion en lenguaje natural
        """
        pass
    
    def evaluar_posicion(self, board: chess.Board) -> Dict[str, Any]:
        """
        Evalua la posicion completa (opcional, override si aplica).
        
        Args:
            board: Posicion actual del tablero
            
        Returns:
            Dict con score y explicacion de la posicion
        """
        return {"score": 0.0, "explanation": ""}
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"