import os
import math
import numpy as np
import chess
import onnxruntime as ort

PIECE_TO_TOKEN = {
    chess.PAWN: 1,
    chess.KNIGHT: 2,
    chess.BISHOP: 3,
    chess.ROOK: 4,
    chess.QUEEN: 5,
    chess.KING: 6
}

def fen_to_model_inputs(fen_str: str):
    board = chess.Board(fen_str)
    tokens = np.zeros((1, 64), dtype=np.int64)
    for sq in range(64):
        piece = board.piece_at(sq)
        if piece is not None:
            base_id = PIECE_TO_TOKEN[piece.piece_type]
            if piece.color == chess.BLACK:
                base_id += 6
            tokens[0, sq] = base_id

    stm = 1.0 if board.turn == chess.WHITE else -1.0
    k_w = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
    q_w = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
    k_b = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
    q_b = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0
    in_chk = 1.0 if board.is_check() else 0.0

    val_map = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    mat_w = sum(len(board.pieces(pt, chess.WHITE)) * val_map[pt] for pt in val_map)
    mat_b = sum(len(board.pieces(pt, chess.BLACK)) * val_map[pt] for pt in val_map)
    mat_diff = (mat_w - mat_b) / 39.0
    mat_total = (mat_w + mat_b) / 78.0

    context = np.array([[stm, k_w, q_w, k_b, q_b, in_chk, mat_diff, mat_total]], dtype=np.float32)
    return tokens, context

def extract_rich_features_for_onnx(fen_str: str):
    board = chess.Board(fen_str)
    square_features = np.zeros((1, 64, 18), dtype=np.float32)
    
    # 1. Piezas en cada casilla
    for pt in range(1, 7):
        for sq in board.pieces(pt, chess.WHITE):
            square_features[0, sq, pt - 1] = 1.0
        for sq in board.pieces(pt, chess.BLACK):
            square_features[0, sq, pt + 5] = 1.0
            
    # 2. Mapas de ataque, control, clavadas y outposts
    w_pawns = board.pieces(chess.PAWN, chess.WHITE)
    b_pawns = board.pieces(chess.PAWN, chess.BLACK)
    
    for sq in range(64):
        w_att = len(board.attackers(chess.WHITE, sq))
        b_att = len(board.attackers(chess.BLACK, sq))
        square_features[0, sq, 12] = w_att / 4.0
        square_features[0, sq, 13] = b_att / 4.0
        square_features[0, sq, 14] = (w_att - b_att) / 4.0
        
        if board.piece_at(sq) is not None:
            if board.is_pinned(chess.WHITE, sq) or board.is_pinned(chess.BLACK, sq):
                square_features[0, sq, 15] = 1.0
                
        if board.is_attacked_by(chess.WHITE, sq, occupied=w_pawns):
            square_features[0, sq, 16] = 1.0
        if board.is_attacked_by(chess.BLACK, sq, occupied=b_pawns):
            square_features[0, sq, 17] = 1.0
            
    # 3. Contexto Global (8 dimensiones)
    stm = 1.0 if board.turn == chess.WHITE else -1.0
    k_w = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
    q_w = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
    k_b = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
    q_b = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0
    in_chk = 1.0 if board.is_check() else 0.0
    
    val_map = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    mat_w = sum(len(board.pieces(pt, chess.WHITE)) * val_map[pt] for pt in val_map)
    mat_b = sum(len(board.pieces(pt, chess.BLACK)) * val_map[pt] for pt in val_map)
    mat_diff = (mat_w - mat_b) / 39.0
    mat_total = (mat_w + mat_b) / 78.0
    
    context = np.array([[stm, k_w, q_w, k_b, q_b, in_chk, mat_diff, mat_total]], dtype=np.float32)
    return square_features, context

class TokenTransformerEvaluator:
    """Evaluador para modelos basados en tokens de 64 casillas (Mini 75k y Medium 238k)."""
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.session = None
        self.input_tokens_name = None
        self.input_context_name = None
        self.output_name = None
        self._load()

    def _load(self):
        if not os.path.exists(self.model_path):
            return
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(self.model_path, opts, providers=['CPUExecutionProvider'])
            
            inputs = self.session.get_inputs()
            self.input_tokens_name = inputs[0].name
            self.input_context_name = inputs[1].name if len(inputs) > 1 else "context_meta"
            self.output_name = self.session.get_outputs()[0].name
            print(f"[OK] Cargado exitosamente Token Transformer: {os.path.basename(self.model_path)}")
        except Exception as e:
            print(f"[TokenTransformer] Error al cargar {self.model_path}: {e}")
            self.session = None

    def evaluate_fen(self, fen_str: str) -> float:
        if self.session is None:
            return 0.0
        try:
            tokens, context = fen_to_model_inputs(fen_str)
            feeds = {
                self.input_tokens_name: tokens,
                self.input_context_name: context
            }
            res = self.session.run([self.output_name], feeds)
            val_norm = float(res[0][0][0])
            val_clamped = max(-0.999, min(0.999, val_norm))
            return math.atanh(val_clamped) * 400.0
        except Exception:
            return 0.0

class RichTransformerEvaluator:
    """Evaluador para modelos basados en embeddings enriquecidos de 18 canales."""
    def __init__(self, model_path: str, invert_polarity: bool = False):
        self.model_path = model_path
        self.invert_polarity = invert_polarity
        self.session = None
        self._load()

    def _load(self):
        if not os.path.exists(self.model_path):
            return
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(self.model_path, opts, providers=['CPUExecutionProvider'])
            
            inputs = self.session.get_inputs()
            self.input_sq_name = inputs[0].name
            self.input_ctx_name = inputs[1].name
            self.output_name = self.session.get_outputs()[0].name
            print(f"[OK] Cargado exitosamente Rich Transformer: {os.path.basename(self.model_path)}")
        except Exception as e:
            print(f"[RichTransformer] Error al cargar {self.model_path}: {e}")
            self.session = None

    def evaluate_fen(self, fen_str: str) -> float:
        if self.session is None:
            return 0.0
        try:
            sq_feat, ctx = extract_rich_features_for_onnx(fen_str)
            res = self.session.run([self.output_name], {
                self.input_sq_name: sq_feat,
                self.input_ctx_name: ctx
            })
            val = float(res[0][0][0])
            if self.invert_polarity:
                val = -val
            val_clamped = max(-0.999, min(0.999, val))
            return math.atanh(val_clamped) * 400.0
        except Exception:
            return 0.0

class MultiFENTransformerEvaluator:
    """Evaluador para el modelo de Partida Completa / Multi-FEN (18D casillas + 8D ctx + 10D material directo)."""
    def __init__(self, model_path: str, invert_polarity: bool = False):
        self.model_path = model_path
        self.invert_polarity = invert_polarity
        self.session = None
        self._load()

    def _load(self):
        if not os.path.exists(self.model_path):
            return
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(self.model_path, opts, providers=['CPUExecutionProvider'])
            
            inputs = self.session.get_inputs()
            self.input_sq = inputs[0].name
            self.input_ctx = inputs[1].name
            self.input_mat = inputs[2].name
            self.output_val = self.session.get_outputs()[1].name
            print(f"[OK] Cargado exitosamente Multi-FEN Transformer: {os.path.basename(self.model_path)}")
        except Exception as e:
            print(f"[MultiFENTransformer] Error al cargar {self.model_path}: {e}")
            self.session = None

    def evaluate_fen(self, fen_str: str) -> float:
        if self.session is None or not fen_str:
            return 0.0
        try:
            board = chess.Board(fen_str)
            # 1. Piezas
            sq_feat = np.zeros((1, 64, 18), dtype=np.float32)
            for pt in range(1, 7):
                for sq in board.pieces(pt, chess.WHITE):
                    sq_feat[0, sq, pt - 1] = 1.0
                for sq in board.pieces(pt, chess.BLACK):
                    sq_feat[0, sq, pt + 5] = 1.0
            w_pawns = board.pieces(chess.PAWN, chess.WHITE)
            b_pawns = board.pieces(chess.PAWN, chess.BLACK)
            for sq in range(64):
                w_att = len(board.attackers(chess.WHITE, sq))
                b_att = len(board.attackers(chess.BLACK, sq))
                sq_feat[0, sq, 12] = w_att / 4.0
                sq_feat[0, sq, 13] = b_att / 4.0
                sq_feat[0, sq, 14] = (w_att - b_att) / 4.0
                if board.piece_at(sq) is not None:
                    if board.is_pinned(chess.WHITE, sq) or board.is_pinned(chess.BLACK, sq):
                        sq_feat[0, sq, 15] = 1.0
                if board.is_attacked_by(chess.WHITE, sq, occupied=w_pawns):
                    sq_feat[0, sq, 16] = 1.0
                if board.is_attacked_by(chess.BLACK, sq, occupied=b_pawns):
                    sq_feat[0, sq, 17] = 1.0

            # 2. Contexto
            stm = 1.0 if board.turn == chess.WHITE else -1.0
            k_w = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
            q_w = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
            k_b = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
            q_b = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0
            in_chk = 1.0 if board.is_check() else 0.0
            val_map = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
            mat_w = sum(len(board.pieces(pt, chess.WHITE)) * val_map[pt] for pt in val_map)
            mat_b = sum(len(board.pieces(pt, chess.BLACK)) * val_map[pt] for pt in val_map)
            mat_diff = (mat_w - mat_b) / 39.0
            mat_total = (mat_w + mat_b) / 78.0
            ctx = np.array([[stm, k_w, q_w, k_b, q_b, in_chk, mat_diff, mat_total]], dtype=np.float32)

            # 3. Vector Material 10D
            pieces_order = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]
            mat10_list = [len(board.pieces(p, chess.WHITE))/8.0 for p in pieces_order] + [len(board.pieces(p, chess.BLACK))/8.0 for p in pieces_order]
            mat10 = np.array([mat10_list], dtype=np.float32)

            # Comprobar si el modelo espera [B, 64, 18] o [B, 1, 64, 18]
            in_shape = self.session.get_inputs()[0].shape
            if len(in_shape) == 4:
                sq_feed = np.expand_dims(sq_feat, 1)
                ctx_feed = np.expand_dims(ctx, 1)
                mat_feed = np.expand_dims(mat10, 1)
            else:
                sq_feed = sq_feat
                ctx_feed = ctx
                mat_feed = mat10

            res = self.session.run([self.output_val], {
                self.input_sq: sq_feed,
                self.input_ctx: ctx_feed,
                self.input_mat: mat_feed
            })
            val = float(res[0].flatten()[-1])
            if self.invert_polarity:
                val = -val
            val_clamped = max(-0.999, min(0.999, val))
            return math.atanh(val_clamped) * 400.0
        except Exception as e:
            return 0.0

    def evaluate_batch(self, fen_list: list) -> list:
        if self.session is None or not fen_list:
            return [0.0] * (len(fen_list) if isinstance(fen_list, list) else 1)
        try:
            B = len(fen_list)
            sq_batch = np.zeros((B, 64, 18), dtype=np.float32)
            ctx_batch = np.zeros((B, 8), dtype=np.float32)
            mat_batch = np.zeros((B, 10), dtype=np.float32)
            pieces_order = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]
            val_map = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

            for i, fen_str in enumerate(fen_list):
                board = chess.Board(fen_str)
                for pt in range(1, 7):
                    for sq in board.pieces(pt, chess.WHITE):
                        sq_batch[i, sq, pt - 1] = 1.0
                    for sq in board.pieces(pt, chess.BLACK):
                        sq_batch[i, sq, pt + 5] = 1.0
                w_pawns = board.pieces(chess.PAWN, chess.WHITE)
                b_pawns = board.pieces(chess.PAWN, chess.BLACK)
                for sq in range(64):
                    w_att = len(board.attackers(chess.WHITE, sq))
                    b_att = len(board.attackers(chess.BLACK, sq))
                    sq_batch[i, sq, 12] = w_att / 4.0
                    sq_batch[i, sq, 13] = b_att / 4.0
                    sq_batch[i, sq, 14] = (w_att - b_att) / 4.0
                    if board.piece_at(sq) is not None:
                        if board.is_pinned(chess.WHITE, sq) or board.is_pinned(chess.BLACK, sq):
                            sq_batch[i, sq, 15] = 1.0
                    if board.is_attacked_by(chess.WHITE, sq, occupied=w_pawns):
                        sq_batch[i, sq, 16] = 1.0
                    if board.is_attacked_by(chess.BLACK, sq, occupied=b_pawns):
                        sq_batch[i, sq, 17] = 1.0

                stm = 1.0 if board.turn == chess.WHITE else -1.0
                k_w = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
                q_w = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
                k_b = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
                q_b = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0
                in_chk = 1.0 if board.is_check() else 0.0
                mat_w = sum(len(board.pieces(pt, chess.WHITE)) * val_map[pt] for pt in val_map)
                mat_b = sum(len(board.pieces(pt, chess.BLACK)) * val_map[pt] for pt in val_map)
                ctx_batch[i] = [stm, k_w, q_w, k_b, q_b, in_chk, (mat_w - mat_b)/39.0, (mat_w + mat_b)/78.0]
                mat_batch[i] = [len(board.pieces(p, chess.WHITE))/8.0 for p in pieces_order] + [len(board.pieces(p, chess.BLACK))/8.0 for p in pieces_order]

            res = self.session.run([self.output_val], {
                self.input_sq: sq_batch,
                self.input_ctx: ctx_batch,
                self.input_mat: mat_batch
            })
            vals = res[0].flatten()
            out_scores = []
            for v in vals:
                val = float(v)
                if self.invert_polarity:
                    val = -val
                val_clamped = max(-0.999, min(0.999, val))
                out_scores.append(math.atanh(val_clamped) * 400.0)
            return out_scores
        except Exception as e:
            return [0.0] * len(fen_list)

    def evaluate_sequence(self, fen_list) -> float:
        if isinstance(fen_list, list) and len(fen_list) > 0:
            return self.evaluate_fen(fen_list[-1])
        return self.evaluate_fen(str(fen_list))

HERE = os.path.dirname(os.path.abspath(__file__))
TRANSFORMER_DIR = os.path.join(HERE, "transformer")

MINI_ONNX_PATH = os.path.join(TRANSFORMER_DIR, "chess_mini_transformer.onnx")
MEDIUM_ONNX_PATH = os.path.join(TRANSFORMER_DIR, "chess_medium_transformer.onnx")
MODEL_8x256_PATH = os.path.join(TRANSFORMER_DIR, "chess_rich_n_heads8dim256_transformer.onnx")
MODEL_4x128_PATH = os.path.join(TRANSFORMER_DIR, "chess_rich_n_heads4dim128_transformer.onnx")
TOTAL_128_4_ONNX_PATH = os.path.join(TRANSFORMER_DIR, "chess_rich_transformer_aperturas_finales.onnx")
TOTAL_V2_ONNX_PATH = os.path.join(TRANSFORMER_DIR, "chess_rich_transformer_aperturas_finalesV2.onnx")
MULTIFEN_ONNX_PATH = os.path.join(TRANSFORMER_DIR, "chess_dual_head_transformer_256_1M_dynamic.onnx")
if not os.path.exists(MULTIFEN_ONNX_PATH):
    MULTIFEN_ONNX_PATH = os.path.join(TRANSFORMER_DIR, "chess_dual_head_transformer_256_1M.onnx")
if not os.path.exists(MULTIFEN_ONNX_PATH):
    MULTIFEN_ONNX_PATH = os.path.join(TRANSFORMER_DIR, "chess_full_game_transformer_Mult_FEN_V1.onnx")

evaluator_mini = TokenTransformerEvaluator(MINI_ONNX_PATH)
evaluator_medium = TokenTransformerEvaluator(MEDIUM_ONNX_PATH)
evaluator_8x256 = RichTransformerEvaluator(MODEL_8x256_PATH)
evaluator_4x128 = RichTransformerEvaluator(MODEL_4x128_PATH)
evaluator_total_128_4 = RichTransformerEvaluator(TOTAL_128_4_ONNX_PATH)
evaluator_total_v2 = RichTransformerEvaluator(TOTAL_V2_ONNX_PATH, invert_polarity=True)
evaluator_multifen = MultiFENTransformerEvaluator(MULTIFEN_ONNX_PATH, invert_polarity=False)

# Registrar callbacks en los motores C++
try:
    import engine_T_mini_cpp
    if evaluator_mini.session is not None:
        engine_T_mini_cpp.set_transformer_callback(evaluator_mini.evaluate_fen)
        print("[OK] Callback registrado en engine_T_mini_cpp")
except Exception:
    pass

try:
    import engine_T_medium_cpp
    if evaluator_medium.session is not None:
        engine_T_medium_cpp.set_transformer_callback(evaluator_medium.evaluate_fen)
        print("[OK] Callback registrado en engine_T_medium_cpp")
except Exception:
    pass

try:
    import engine_transformer_8x256_cpp
    if evaluator_8x256.session is not None:
        engine_transformer_8x256_cpp.set_transformer_callback(evaluator_8x256.evaluate_fen)
        print("[OK] Callback registrado en engine_transformer_8x256_cpp")
except Exception:
    pass

try:
    import engine_transformer_4x128_cpp
    if evaluator_4x128.session is not None:
        engine_transformer_4x128_cpp.set_transformer_callback(evaluator_4x128.evaluate_fen)
        print("[OK] Callback registrado en engine_transformer_4x128_cpp")
except Exception:
    pass

try:
    import engine_Total_transformer128_4_cpp
    if evaluator_total_128_4.session is not None:
        engine_Total_transformer128_4_cpp.set_transformer_callback(evaluator_total_128_4.evaluate_fen)
        print("[OK] Callback registrado en engine_Total_transformer128_4_cpp")
except Exception:
    pass

try:
    import engine_T_total_V2_cpp
    if evaluator_total_v2.session is not None:
        engine_T_total_V2_cpp.set_transformer_callback(evaluator_total_v2.evaluate_fen)
        print("[OK] Callback registrado en engine_T_total_V2_cpp")
except Exception:
    pass

try:
    import engine_multiFEN_cpp
    if evaluator_multifen.session is not None:
        engine_multiFEN_cpp.set_transformer_callback(evaluator_multifen.evaluate_fen)
        print("[OK] Callback registrado en engine_multiFEN_cpp (Fast T=1)")
except Exception:
    pass

try:
    import engine_1M_FEN_cpp
    if evaluator_multifen.session is not None:
        if hasattr(engine_1M_FEN_cpp, 'set_transformer_batch_callback'):
            engine_1M_FEN_cpp.set_transformer_batch_callback(evaluator_multifen.evaluate_batch)
        engine_1M_FEN_cpp.set_transformer_callback(evaluator_multifen.evaluate_fen)
        print("[OK] Callback registrado en engine_1M_FEN_cpp (Dual-Head 1M Transformer Dynamic Batch)")
except Exception:
    pass

try:
    import motorNegamax_cpp
    if evaluator_multifen.session is not None:
        motorNegamax_cpp.set_transformer_callback(evaluator_multifen.evaluate_fen)
        print("[OK] Callback registrado en motorNegamax_cpp (Policy + Tactical Negamax)")
except Exception:
    pass




