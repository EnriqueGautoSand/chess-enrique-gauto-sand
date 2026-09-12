import chess
from typing import Tuple, List, Dict, Optional, Any

try:
    from .constantes import VALORES_PIEZAS
except ImportError:
    from constantes import VALORES_PIEZAS

class DefensaAdaptativaEvaluator:
    """
    Evaluador de Defensa Adaptativa Humana y Seguridad Generalizada.
    Utiliza la escala estándar internacional de ajedrez (1 a 9 puntos de material):
    Peón = 1.0 | Caballo = 3.0 | Alfil = 3.25 | Torre = 5.0 | Dama = 9.0 | Rey = 200.0
    
    Analiza de forma exhaustiva TODAS las amenazas del rival tras una jugada candidata
    y aplica la penalización por el PEOR RIESGO encontrado (sin retornos prematuros).
    - Jaque Mate = -1000.0
    - Coronación con Jaque = -50.0
    - Tenedor Real a 2 plies = -45.0
    - Pérdida de Material = Proporcional a la pieza perdible (ej: -90.0 Dama, -50.0 Torre, -30.0 Caballo, -10.0 Peón)
    """

    def evaluar_amenazas_adaptativas_rival(self, board: chess.Board, move: chess.Move) -> Tuple[float, str, str]:
        """
        Simula 'move' en 'board' y evalúa exhaustivamente la peor amenaza del rival.
        Devuelve (penalty_score, razon_riesgo, tipo_amenaza).
        OPTIMIZADO: solo itera sobre capturas del rival y jaques, no sobre todos los legal_moves.
        """
        temp_board = board.copy(stack=False)
        temp_board.push(move)

        if temp_board.is_game_over():
            if temp_board.is_checkmate():
                return -1000.0, "Permite jaque mate del rival.", "mate_rival"
            return 0.0, "", "ninguna"

        our_color = board.turn
        enemy_color = temp_board.turn

        peor_penalty = 0.0
        exp_peor_riesgo = ""
        tipo_peor_amenaza = "seguro"

        def registrar_amenaza(pen: float, exp: str, tipo: str):
            nonlocal peor_penalty, exp_peor_riesgo, tipo_peor_amenaza
            if pen < peor_penalty:
                peor_penalty = pen
                exp_peor_riesgo = exp
                tipo_peor_amenaza = tipo

        # OPTIMIZACION: Generar jugadas de jaque una sola vez
        jaques_oponente = []
        for m_op in temp_board.generate_pseudo_legal_moves():
            if temp_board.gives_check(m_op) and temp_board.is_legal(m_op):
                jaques_oponente.append(m_op)

        # 1. ¿El movimiento permite un Jaque Mate del oponente en 1 jugada?
        for m_op in jaques_oponente:
            b_op = temp_board.copy(stack=False)
            b_op.push(m_op)
            if b_op.is_checkmate():
                san_op = temp_board.san(m_op)
                return -1000.0, f"Permite un Jaque Mate del oponente con {san_op}.", "mate_rival"

        # 2. ¿El movimiento permite al rival coronar un peón con jaque o ganancia de material?
        for m_op in jaques_oponente:
            if m_op.promotion and m_op.promotion in (chess.QUEEN, chess.ROOK):
                b_op = temp_board.copy(stack=False)
                b_op.push(m_op)
                if b_op.is_checkmate():
                    return -1000.0, "Permite coronación con Jaque Mate del rival.", "coronacion_mate"
                registrar_amenaza(-50.0, "Permite coronación con Jaque del rival.", "coronacion_jaque")

        # 3. Detección de Tenedores con Jaque del Rival a 2 plies
        for m_op in jaques_oponente:
            piece_op = temp_board.piece_at(m_op.from_square)
            if not piece_op or piece_op.piece_type not in (chess.KNIGHT, chess.PAWN, chess.BISHOP):
                continue
            b_op = temp_board.copy(stack=False)
            b_op.push(m_op)
            op_to_sq = m_op.to_square

            # Buscar capturas del rival desde la casilla de jaque
            for m_esc in b_op.legal_moves:
                b_esc = b_op.copy(stack=False)
                b_esc.push(m_esc)
                for m_followup in b_esc.legal_moves:
                    if m_followup.from_square == op_to_sq and b_esc.is_capture(m_followup):
                        target_p = b_esc.piece_at(m_followup.to_square)
                        if target_p and target_p.color == our_color:
                            val_tar = VALORES_PIEZAS.get(target_p.piece_type, 1.0)
                            if val_tar >= 3.0:
                                p_name = chess.piece_name(target_p.piece_type)
                                san_op = temp_board.san(m_op)
                                registrar_amenaza(-45.0, f"Permite un tenedor real con {san_op} seguido de la captura de {p_name}.", "tenedor_rival")

        # 4. Detección de TENEDOR DIRECTO del rival (pieza que ataca 2+ piezas propias)
        tenedor_pen, tenedor_exp = self._detectar_tenedor_rival_directo(temp_board, our_color, enemy_color)
        if tenedor_pen < 0:
            registrar_amenaza(tenedor_pen, tenedor_exp, "tenedor_directo")

        # 5. Detección Adaptativa de Piezas Colgadas o Expuestas
        # OPTIMIZACION: usar is_attacked_by en lugar de generar legal_moves para cada captura
        max_perdida_material = 0.0
        exp_material = ""

        our_pieces = temp_board.piece_map()
        for sq, piece in our_pieces.items():
            if piece.color != our_color:
                continue
            
            attackers = temp_board.attackers(enemy_color, sq)
            if not attackers:
                continue
                
            tar_val = VALORES_PIEZAS.get(piece.piece_type, 1.0)
            defenders = temp_board.attackers(our_color, sq)
            
            if not defenders:
                if tar_val > max_perdida_material:
                    max_perdida_material = tar_val
                    p_name = chess.piece_name(piece.piece_type)
                    sq_name = chess.square_name(sq)
                    exp_material = f"Deja desprotegido/a el {p_name} en {sq_name} permitiendo captura del rival (+{tar_val:.1f})."
            else:
                menor_att_val = 999.0
                for att_sq in attackers:
                    att_piece = temp_board.piece_at(att_sq)
                    att_val = VALORES_PIEZAS.get(att_piece.piece_type, 1.0) if att_piece else 1.0
                    if att_val < menor_att_val:
                        menor_att_val = att_val
                        
                net_loss = tar_val - menor_att_val
                if net_loss > 0.0 and net_loss > max_perdida_material:
                    max_perdida_material = net_loss
                    p_name = chess.piece_name(piece.piece_type)
                    sq_name = chess.square_name(sq)
                    exp_material = f"Deja {p_name} en {sq_name} en intercambio desfavorable (-{net_loss:.1f})."

        if max_perdida_material > 0.0:
            penalty = -10.0 * max_perdida_material
            registrar_amenaza(penalty, exp_material, "colgado_material")

        return peor_penalty, exp_peor_riesgo, tipo_peor_amenaza

    def _detectar_tenedor_rival_directo(self, board: chess.Board, our_color: chess.Color, enemy_color: chess.Color) -> Tuple[float, str]:
        """
        Detecta si una pieza rival ataca 2+ piezas propias valiosas simultaneamente.
        Si es un tenedor inevitable, penaliza solo con el valor de la pieza MENOR
        que se pierde (mal menor), no con la suma de todas.
        
        Returns:
            (penalty, explicacion) donde penalty es negativo si hay tenedor.
        """
        peor_tenedor = 0.0
        exp_tenedor = ""
        
        # Filtrar posibles atacantes (el rey rival no suele dar tenedores en el medio juego que no sean evidentes,
        # pero es rapido simplemente iterar sobre las ocupadas del rival)
        for sq in chess.scan_reversed(board.occupied_co[enemy_color]):
            pt = board.piece_type_at(sq)
            
            # Verificar que piezas propias ataca esta pieza rival
            attacks = board.attacks(sq)
            piezas_atacadas = []
            
            for att_sq in attacks:
                target = board.piece_at(att_sq)
                if target and target.color == our_color:
                    val = VALORES_PIEZAS.get(target.piece_type, 1.0)
                    if val >= 3.0:  # Solo piezas valiosas (caballo+)
                        # Verificar si la pieza atacada esta defendida
                        defenders = board.attackers(our_color, att_sq)
                        # Excluir la pieza atacada de sus propios defensores
                        defenders = [d for d in defenders if d != att_sq]
                        piezas_atacadas.append({
                            "sq": att_sq,
                            "piece": target,
                            "val": val,
                            "defendida": len(defenders) > 0,
                            "num_defensores": len(defenders)
                        })
            
            # Tenedor: 2+ piezas valiosas atacadas simultaneamente
            if len(piezas_atacadas) >= 2:
                # Ordenar por valor (mayor primero)
                piezas_atacadas.sort(key=lambda x: x["val"], reverse=True)
                
                # Calcular perdida inevitable (mal menor)
                pieza_menor = piezas_atacadas[-1]  # La de menor valor
                pieza_mayor = piezas_atacadas[0]   # La de mayor valor
                
                if not pieza_menor["defendida"]:
                    # La pieza menor esta indefensa: se pierde
                    perdida = pieza_menor["val"]
                    att_name = chess.piece_name(pt)
                    att_sq_name = chess.square_name(sq)
                    menor_name = chess.piece_name(pieza_menor["piece"].piece_type)
                    menor_sq = chess.square_name(pieza_menor["sq"])
                    mayor_name = chess.piece_name(pieza_mayor["piece"].piece_type)
                    mayor_sq = chess.square_name(pieza_mayor["sq"])
                    
                    # Penalizar con la perdida de la pieza menor (mal menor)
                    penalty = -10.0 * perdida
                    exp = (f"Tenedor de {att_name} en {att_sq_name}: ataca {mayor_name} en {mayor_sq} "
                           f"y {menor_name} en {menor_sq}. Perdida inevitable: {menor_name} (+{perdida:.1f}). "
                           f"Salvar la pieza mayor.")
                    
                    if penalty < peor_tenedor:
                        peor_tenedor = penalty
                        exp_tenedor = exp
                else:
                    # Ambas defendidas: verificar si hay intercambio desfavorable
                    att_val = VALORES_PIEZAS.get(pt, 1.0)
                    if att_val < pieza_menor["val"]:
                        # El atacante vale menos que la pieza atacada
                        perdida = pieza_menor["val"] - att_val
                        penalty = -10.0 * perdida
                        att_name = chess.piece_name(pt)
                        att_sq_name = chess.square_name(sq)
                        menor_name = chess.piece_name(pieza_menor["piece"].piece_type)
                        menor_sq = chess.square_name(pieza_menor["sq"])
                        
                        exp = (f"Tenedor de {att_name} en {att_sq_name}: ataca {menor_name} en {menor_sq}. "
                               f"Intercambio desfavorable (+{perdida:.1f}).")
                        
                        if penalty < peor_tenedor:
                            peor_tenedor = penalty
                            exp_tenedor = exp
        
        return peor_tenedor, exp_tenedor