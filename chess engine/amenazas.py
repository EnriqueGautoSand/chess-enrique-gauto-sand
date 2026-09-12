import chess
from typing import Tuple, List, Dict, Any

try:
    from .constantes import VALORES_PIEZAS
except ImportError:
    from constantes import VALORES_PIEZAS

class AmenazasEvaluator:
    """
    Evaluador de Amenazas Tácticas.
    Evalúa ataques a piezas de mayor valor, clavadas, tenedores, y ataques en enfilada (rayos X / skewers).
    Calcula el valor material real de las piezas atrapadas en tenedores y enfiladas.
    """

    def evaluar_amenazas_movimiento(self, board: chess.Board, move: chess.Move) -> Tuple[float, str]:
        """
        Evalúa las amenazas creadas por un movimiento (tenedores, clavadas, enfiladas/rayos X y ataques a piezas valiosas).
        Calcula matemáticamente el valor material de las piezas atrapadas.
        """
        piece = board.piece_at(move.from_square)
        if not piece:
            return 0.0, ""

        moving_val = VALORES_PIEZAS.get(piece.piece_type, 1.0)
        to_sq = move.to_square
        our_color = piece.color
        enemy_color = not our_color

        board.push(move)

        # 1. Tenedor (Fork): Atacar 2 o más piezas enemigas valiosas a la vez
        attacked_squares = board.attacks(to_sq)
        attacked_valuable_pieces = []

        for sq in attacked_squares:
            target_piece = board.piece_at(sq)
            if target_piece and target_piece.color == enemy_color:
                t_val = VALORES_PIEZAS.get(target_piece.piece_type, 1.0)
                if t_val >= 3.0 or target_piece.piece_type == chess.KING:
                    attacked_valuable_pieces.append((sq, target_piece))

        if len(attacked_valuable_pieces) >= 2:
            max_trapped_val = 0.0
            for sq, t_p in attacked_valuable_pieces:
                if t_p.piece_type != chess.KING:
                    t_val = VALORES_PIEZAS.get(t_p.piece_type, 1.0)
                    if t_val > max_trapped_val:
                        max_trapped_val = t_val

            score_tenedor = 45.0 + (max_trapped_val * 10.0)
            names = [chess.piece_name(p.piece_type) for _, p in attacked_valuable_pieces]
            names_str = " y ".join(list(set(names)))
            to_sq_name = chess.square_name(to_sq)
            piece_name = chess.piece_name(piece.piece_type)
            board.pop()
            return score_tenedor, f"Tenedor táctico: Mueve {piece_name} a {to_sq_name} amenazando a {names_str} simultáneamente (valor atrapado: +{max_trapped_val:.1f})."

        # 2. Ataque en Enfilada / Rayos X (Skewer): Jaque o ataque a pieza frente a otra pieza valiosa en la misma línea
        if piece.piece_type in (chess.ROOK, chess.QUEEN, chess.BISHOP):
            rays = self.detectar_enfilada_rayos_x(board, to_sq, enemy_color)
            if rays:
                board.pop()
                return 55.0, rays

        # 3. Amenaza simple a pieza de mayor valor
        best_threat_score = 0.0
        best_exp = ""

        for sq, target_piece in attacked_valuable_pieces:
            if target_piece.piece_type == chess.KING:
                continue
            t_val = VALORES_PIEZAS.get(target_piece.piece_type, 1.0)
            if t_val > moving_val:
                gain_diff = t_val - moving_val
                score = 35.0 + (gain_diff * 10.0)
                if score > best_threat_score:
                    best_threat_score = score
                    t_name = chess.piece_name(target_piece.piece_type)
                    p_name = chess.piece_name(piece.piece_type)
                    to_sq_name = chess.square_name(to_sq)
                    best_exp = f"Mueve {p_name} a {to_sq_name} amenazando a {t_name} enemiga de mayor valor en {chess.square_name(sq)}."

        board.pop()
        return best_threat_score, best_exp

    def detectar_enfilada_rayos_x(self, board: chess.Board, sq: int, enemy_color: chess.Color) -> str:
        """
        Detecta si desde 'sq' una línea ataca a un Rey/Dama enemigo con otra pieza valiosa detrás en el rayo.
        """
        piece = board.piece_at(sq)
        if not piece:
            return ""

        directions = []
        if piece.piece_type in (chess.ROOK, chess.QUEEN):
            directions.extend([1, -1, 8, -8])
        if piece.piece_type in (chess.BISHOP, chess.QUEEN):
            directions.extend([7, -7, 9, -9])

        for d in directions:
            curr = sq
            pieces_in_line = []
            while True:
                if d in (1, -7, 9) and chess.square_file(curr) == 7:
                    break
                if d in (-1, 7, -9) and chess.square_file(curr) == 0:
                    break
                curr += d
                if not (0 <= curr <= 63):
                    break

                p = board.piece_at(curr)
                if p:
                    if p.color == enemy_color:
                        pieces_in_line.append((curr, p))
                    else:
                        break

            if len(pieces_in_line) >= 2:
                p1 = pieces_in_line[0][1]
                p2 = pieces_in_line[1][1]
                val1 = VALORES_PIEZAS.get(p1.piece_type, 1.0)
                val2 = VALORES_PIEZAS.get(p2.piece_type, 1.0)
                if val1 >= 5.0 or p1.piece_type == chess.KING:
                    if val2 >= 3.0:
                        sq1_name = chess.square_name(pieces_in_line[0][0])
                        sq2_name = chess.square_name(pieces_in_line[1][0])
                        return f"Ataque en enfilada (Rayos X) desde {chess.square_name(sq)} alineando a {chess.piece_name(p1.piece_type)} en {sq1_name} y {chess.piece_name(p2.piece_type)} en {sq2_name}."
        return ""

    def evaluar_defensa_de_amenazas(self, board: chess.Board, move: chess.Move, amenazas_oponente: List[Dict]) -> Tuple[float, str]:
        """
        Evalúa si la jugada defiende una pieza propia amenazada por el oponente.
        Solo se considera casilla segura si el destino no está atacado desfavorablemente por el rival.
        """
        if not amenazas_oponente:
            return 0.0, ""

        from_sq = move.from_square
        to_sq = move.to_square
        piece = board.piece_at(from_sq)
        if not piece:
            return 0.0, ""

        for amenaza in amenazas_oponente:
            target_sq = amenaza.get("target_square")
            target_piece = board.piece_at(target_sq) if target_sq is not None else None

            if target_sq == from_sq:
                enemy_color = not piece.color
                # Verificar si la casilla destino to_sq está atacada por el oponente
                if board.is_attacked_by(enemy_color, to_sq):
                    # Si la casilla destino está atacada, comprobar si tenemos defensores suficientes
                    is_defended = board.is_attacked_by(piece.color, to_sq)
                    if not is_defended:
                        continue  # No es casilla segura, es entrega directa
                    moving_val = VALORES_PIEZAS.get(piece.piece_type, 1.0)
                    min_attacker_val = min(
                        [VALORES_PIEZAS.get(board.piece_at(sq).piece_type, 1.0) 
                         for sq in board.attackers(enemy_color, to_sq) if board.piece_at(sq)] or [9.0]
                    )
                    if min_attacker_val < moving_val:
                        continue  # Pieza de menor valor la ataca (ej. Alfil atacando Torre en d5), no es seguro
                
                sq_name = chess.square_name(to_sq)
                p_name = chess.piece_name(target_piece.piece_type) if target_piece else "pieza"
                return 35.0, f"Retira {p_name} amenazada moviéndola a casilla segura en {sq_name}."

        return 0.0, ""