import os
import werkzeug
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '3.0.0'
import json
from flask import Flask, render_template, jsonify, request, send_from_directory
from game_engine import GameEngine

app = Flask(__name__)
engine = GameEngine()

# Ruta a la carpeta de imágenes personalizada (soporta ejecución desde raíz o subcarpeta)
for img_dir in [
    os.path.abspath(os.path.join(app.root_path, "imagenes")),
    os.path.abspath(os.path.join(app.root_path, "..", "imagenes"))
]:
    if os.path.exists(img_dir):
        CUSTOM_IMAGES_DIR = img_dir
        break
else:
    CUSTOM_IMAGES_DIR = os.path.abspath(os.path.join(app.root_path, "imagenes"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/custom_images/<path:filename>")
def serve_custom_image(filename):
    """Sirve imágenes personalizadas almacenadas en la carpeta imagenes."""
    return send_from_directory(CUSTOM_IMAGES_DIR, filename)

@app.route("/api/board_state", methods=["GET"])
def get_board_state():
    return jsonify(engine.get_board_state())

@app.route("/api/elo_profiles", methods=["GET"])
def get_elo_profiles():
    """Devuelve los perfiles de heurísticas activadas de 400 a 2600+ y MAX."""
    candidate_roots = [
        app.root_path,
        os.path.abspath(os.path.join(app.root_path, ".."))
    ]
    target_path = None
    for r in candidate_roots:
        p1 = os.path.join(r, "estadisticas", "estadisticas_55_tecnicas_chesscom_perfiles.json")
        p2 = os.path.join(r, "estadisticas", "combinado_800_a_2299_perfiles_elo.json")
        if os.path.exists(p1):
            target_path = p1
            break
        elif os.path.exists(p2):
            target_path = p2
            break

    if target_path and os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"success": True, "profiles": data, "source": os.path.basename(target_path)})
    return jsonify({"success": False, "profiles": {}}), 404

@app.route("/api/new_game", methods=["POST"])
def new_game():
    data = request.get_json() or {}
    player_color = data.get("color", "white")
    game_mode = data.get("game_mode", "pve")
    use_king_zone = str(data.get("use_king_zone_filter", "false")).lower() == "true"
    try:
        depth = int(data.get("depth", 2))
    except (ValueError, TypeError):
        depth = 2
    strategy = data.get("strategy", "tactico")
    engine_version = data.get("engine_version", "minimax2")
    engine_config = data.get("engine_config", {}) or {}

    result = engine.reset_game(player_color=player_color, game_mode=game_mode, depth=depth, strategy=strategy, use_king_zone_filter=use_king_zone, engine_version=engine_version, config=engine_config)
    return jsonify(result)

@app.route("/api/set_game_mode", methods=["POST"])
def set_game_mode():
    try:
        data = request.get_json() or {}
        player_color = data.get("color", "white")
        game_mode = data.get("game_mode", "pve")
        use_king_zone = str(data.get("use_king_zone_filter", "false")).lower() == "true"
        depth = data.get("depth")
        strategy = data.get("strategy")
        engine_version = data.get("engine_version")
        engine_config = data.get("engine_config") or None
        tree_mode = data.get("tree_mode", "cut")
        time_limit_raw = data.get("time_limit")
        time_limit = None
        if time_limit_raw and time_limit_raw != "off":
            try:
                time_limit = float(time_limit_raw)
            except (ValueError, TypeError):
                time_limit = None

        if depth is not None:
            try:
                depth = int(depth)
            except (ValueError, TypeError):
                depth = 2

        result = engine.set_game_mode(game_mode=game_mode, player_color=player_color, depth=depth, strategy=strategy, tree_mode=tree_mode, time_limit=time_limit, use_king_zone_filter=use_king_zone, engine_version=engine_version, config=engine_config)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route("/api/load_pgn", methods=["POST"])
def load_pgn():
    data = request.get_json() or {}
    pgn_text = data.get("pgn", "")
    depth = data.get("depth")
    strategy = data.get("strategy")
    engine_config = data.get("engine_config") or None
    if engine_config is not None:
        engine.engine_config = engine_config

    if depth is not None:
        try:
            engine.engine_depth = int(depth)
        except (ValueError, TypeError):
            engine.engine_depth = 2
    if strategy is not None:
        engine.engine_strategy = strategy

    result = engine.load_pgn(pgn_text)
    return jsonify(result)

@app.route("/api/legal_moves", methods=["GET"])
def legal_moves():
    square = request.args.get("square", "")
    move_index_str = request.args.get("move_index")
    try:
        move_index = int(move_index_str) if move_index_str is not None else None
    except (ValueError, TypeError):
        move_index = None

    dests = engine.get_legal_destinations(square, move_index=move_index)
    return jsonify({"square": square, "destinations": dests})

@app.route("/api/move", methods=["POST"])
def move():
    data = request.get_json() or {}
    from_sq = data.get("from")
    to_sq = data.get("to")
    promotion = data.get("promotion")

    depth = data.get("depth")
    strategy = data.get("strategy")
    engine_version = data.get("engine_version")
    engine_config = data.get("engine_config") or None
    truncate_at = data.get("truncate_at")

    tree_mode = data.get("tree_mode", "cut")
    time_limit_raw = data.get("time_limit")
    time_limit = None
    if time_limit_raw and time_limit_raw != "off":
        try:
            time_limit = float(time_limit_raw)
        except (ValueError, TypeError):
            time_limit = None

    depth_val = None
    if depth is not None:
        try:
            depth_val = int(depth)
            engine.engine_depth = depth_val
        except (ValueError, TypeError):
            depth_val = 2
            engine.engine_depth = 2
    if strategy is not None:
        engine.engine_strategy = strategy

    if truncate_at is not None:
        try:
            truncate_at = int(truncate_at)
        except (ValueError, TypeError):
            truncate_at = None

    if not from_sq or not to_sq:
        return jsonify({"success": False, "message": "Faltan las casillas de origen o destino."})

    res = engine.make_move(from_sq, to_sq, promotion=promotion, truncate_at=truncate_at, depth=depth_val, strategy=strategy, tree_mode=tree_mode, time_limit=time_limit, engine_version=engine_version, config=engine_config)
    return jsonify(res)

@app.route("/api/analyze", methods=["GET"])
def analyze():
    move_index_str = request.args.get("move_index")
    depth_str = request.args.get("depth")
    strategy = request.args.get("strategy")
    engine_version = request.args.get("engine_version")
    try:
        engine_config = json.loads(request.args.get("engine_config", "null")) if request.args.get("engine_config") else None
    except Exception:
        engine_config = None

    tree_mode = request.args.get("tree_mode", "cut")
    time_limit_raw = request.args.get("time_limit")
    time_limit = None
    if time_limit_raw and time_limit_raw != "off":
        try:
            time_limit = float(time_limit_raw)
        except (ValueError, TypeError):
            time_limit = None

    try:
        move_index = int(move_index_str) if move_index_str is not None else None
    except (ValueError, TypeError):
        move_index = None

    try:
        depth = int(depth_str) if depth_str is not None else None
    except (ValueError, TypeError):
        depth = None

    res = engine.analyze_position(move_index=move_index, depth=depth, strategy=strategy, tree_mode=tree_mode, time_limit=time_limit, engine_version=engine_version, config=engine_config)
    return jsonify(res)

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
