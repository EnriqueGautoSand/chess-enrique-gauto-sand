// Tablero Interactivo y Módulo de Análisis del Motor - Frontend Javascript

const pieceUnicodeMap = {
    'wp': '♟', 'wr': '♜', 'wn': '♞', 'wb': '♝', 'wq': '♛', 'wk': '♚',
    'bp': '♟', 'br': '♜', 'bn': '♞', 'bb': '♝', 'bq': '♛', 'bk': '♚'
};

class ChessBoardUI {
    constructor() {
        // Elementos DOM del Tablero
        this.boardElement = document.getElementById('chessboard');
        this.gameModeSelect = document.getElementById('game-mode-select');
        this.colorSelect = document.getElementById('color-select');
        this.boardSizeSelect = document.getElementById('board-size-select');
        this.themeSelect = document.getElementById('theme-select');
        this.btnNewGame = document.getElementById('btn-new-game');
        this.btnFlipBoard = document.getElementById('btn-flip-board');
        this.turnIndicator = document.getElementById('turn-indicator');
        this.turnText = document.getElementById('turn-text');
        this.statusMessage = document.getElementById('status-message');
        this.moveHistoryElement = document.getElementById('move-history');
        this.promotionModal = document.getElementById('promotion-modal');
        this.btnCopyPgn = document.getElementById('btn-copy-pgn');
        this.btnCopyFen = document.getElementById('btn-copy-fen');
        this.btnCopyExplanations = document.getElementById('btn-copy-explanations');
        this.btnPastePgn = document.getElementById('btn-paste-pgn');
        this.toastMsg = document.getElementById('toast-msg');

        // Modal de Pegar PGN
        this.pasteModal = document.getElementById('paste-modal');
        this.pastePgnInput = document.getElementById('paste-pgn-input');
        this.btnCancelPaste = document.getElementById('btn-cancel-paste');
        this.btnConfirmPaste = document.getElementById('btn-submit-paste') || document.getElementById('btn-confirm-paste');
        this.btnClosePasteModal = document.getElementById('btn-close-paste-modal');

        // Botones de Navegación de Historial (< > Deshacer/Rehacer)
        this.btnNavFirst = document.getElementById('btn-nav-first');
        this.btnNavPrev = document.getElementById('btn-nav-prev');
        this.btnNavNext = document.getElementById('btn-nav-next');
        this.btnNavLast = document.getElementById('btn-nav-last');
        this.navStepIndicator = document.getElementById('nav-step-indicator');
        this.eloCoachingBanner = document.getElementById('elo-coaching-banner');

        // Elementos DOM del Módulo de Análisis (Panel Derecho)
        this.eloLevelSelect = document.getElementById('elo-level-select');
        this.eloBadgeCount = document.getElementById('elo-badge-count');
        this.eloBadgeInfo = document.getElementById('elo-badge-info');
        this.btnToggleAllFlags = document.getElementById('btn-toggle-all-flags');
        this.eloProfiles = {};

        this.analysisDepthSelect = document.getElementById('analysis-depth');
        this.analysisStrategySelect = document.getElementById('analysis-strategy');
        this.engineVersionSelect = document.getElementById('engine-version');
        this.treeModeSelect = document.getElementById('tree-mode-select');
        this.timeLimitSelect = document.getElementById('time-limit-select');
        this.kingZoneFilterSelect = document.getElementById('king-zone-filter-select');
        this.analysisTitle = document.getElementById('analysis-title');
        this.analysisTypeBadge = document.getElementById('analysis-type-badge');
        this.analysisBody = document.getElementById('analysis-body');
        this.btnLiveAnalysis = document.getElementById('btn-live-analysis');
        this.recommendedMoveSan = document.getElementById('recommended-move-san');
        this.moveScore = document.getElementById('move-score');
        this.btnSuggestMove = document.getElementById('btn-suggest-move');

        // Indicador Animado de Carga "Analizando..."
        this.analysisLoadingIndicator = document.getElementById('analysis-loading-indicator');
        this.loadingDotsElement = document.getElementById('loading-dots');
        this.loadingTimerInterval = null;

        // Sección de la Jugada Anterior del Oponente
        this.previousMoveBox = document.getElementById('previous-move-box');
        this.prevMoveTitle = document.getElementById('prev-move-title');
        this.prevMoveExplanation = document.getElementById('prev-move-explanation');

        this.filesTop = document.getElementById('files-top');
        this.filesBottom = document.getElementById('files-bottom');
        this.ranksLeft = document.getElementById('ranks-left');
        this.ranksRight = document.getElementById('ranks-right');

        // Elementos DOM de la Barra de Evaluación Vertical
        this.evalBarWrapper = document.getElementById('eval-bar-wrapper');
        this.evalBar = document.getElementById('eval-bar');
        this.evalBarWhite = document.getElementById('eval-bar-white');
        this.evalBarBlack = document.getElementById('eval-bar-black');
        this.evalScoreText = document.getElementById('eval-score-text');

        // Estado del Tablero y Análisis
        this.selectedSquare = null;
        this.legalDestinations = [];
        this.currentGameState = null;
        this.isFlipped = false;
        this.pendingMove = null;
        this.pieceTheme = 'lichess';
        
        this.viewedHistoryIndex = null; // null significa "Última posición en Tiempo Real"
        this.analysisDebounceTimer = null;
        this.latestAnalysisRequestId = 0;
        this.currentAbortController = null;
        this.isProcessingMove = false;
        this.draggedSquare = null;
        this.legalMovesMap = {};
        this.justDropped = false;

        this.init();
    }

    init() {
        if (this.btnNewGame) this.btnNewGame.addEventListener('click', () => this.startNewGame());
        if (this.btnFlipBoard) this.btnFlipBoard.addEventListener('click', () => this.toggleFlipBoard());
        
        // Al cambiar de modo de juego (PvP vs PvE) o de color, MANTENER la partida actual intacta sin resetear el tablero
        if (this.gameModeSelect) this.gameModeSelect.addEventListener('change', () => this.changeGameMode());
        if (this.colorSelect) this.colorSelect.addEventListener('change', () => this.changeGameMode());

        if (this.btnCopyPgn) this.btnCopyPgn.addEventListener('click', () => this.copyPgnToClipboard());
        if (this.btnCopyFen) this.btnCopyFen.addEventListener('click', () => this.copyFenToClipboard());
        if (this.btnCopyExplanations) this.btnCopyExplanations.addEventListener('click', () => this.copyExplanationsToClipboard());

        // Los selectores de configuración del motor ya no disparan análisis automático.
        // El usuario debe hacer clic en "Pedir Sugerencia" para calcular.

        // Selector de Tamaño del Tablero Configurable
        if (this.boardSizeSelect) {
            const savedSize = localStorage.getItem('chess_board_size') || 'large';
            this.boardSizeSelect.value = savedSize;
            this.setBoardSize(savedSize);

            this.boardSizeSelect.addEventListener('change', (e) => {
                const newSize = e.target.value;
                this.setBoardSize(newSize);
                localStorage.setItem('chess_board_size', newSize);
            });
        }

        // Modal Pegar PGN
        if (this.btnPastePgn) this.btnPastePgn.addEventListener('click', () => this.openPasteModal());
        if (this.btnCancelPaste) this.btnCancelPaste.addEventListener('click', () => this.closePasteModal());
        if (this.btnConfirmPaste) this.btnConfirmPaste.addEventListener('click', () => this.confirmPastePgn());
        if (this.btnClosePasteModal) this.btnClosePasteModal.addEventListener('click', () => this.closePasteModal());

        // Botones de Promoción de Peón
        document.querySelectorAll('.btn-promotion').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetBtn = e.target.closest('.btn-promotion');
                if (targetBtn) {
                    const piece = targetBtn.getAttribute('data-piece');
                    this.completePromotion(piece);
                }
            });
        });

        // Botones de Navegación de Historial (⏮, ◀, ▶, ⏭)
        if (this.btnNavFirst) this.btnNavFirst.addEventListener('click', () => this.navigateHistory(-1));
        if (this.btnNavPrev) this.btnNavPrev.addEventListener('click', () => this.navigateStep(-1));
        if (this.btnNavNext) this.btnNavNext.addEventListener('click', () => this.navigateStep(1));
        if (this.btnNavLast) this.btnNavLast.addEventListener('click', () => this.navigateHistory(null));

        // Atajos de teclado para navegación de jugadas (< > Flechas Izq/Der, Home, End)
        document.addEventListener('keydown', (e) => {
            if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
            if (this.pasteModal && !this.pasteModal.classList.contains('hidden')) return;

            if (e.key === 'ArrowLeft' || e.key === '<' || e.key === ',') {
                e.preventDefault();
                this.navigateStep(-1);
            } else if (e.key === 'ArrowRight' || e.key === '>' || e.key === '.') {
                e.preventDefault();
                this.navigateStep(1);
            } else if (e.key === 'Home') {
                e.preventDefault();
                this.navigateHistory(-1);
            } else if (e.key === 'End') {
                e.preventDefault();
                this.navigateHistory(null);
            }
        });

        if (this.themeSelect) {
            const savedTheme = localStorage.getItem('chess_piece_theme') || 'lichess';
            this.pieceTheme = savedTheme;
            this.themeSelect.value = savedTheme;

            this.themeSelect.addEventListener('change', (e) => {
                this.pieceTheme = e.target.value;
                localStorage.setItem('chess_piece_theme', this.pieceTheme);
                this.renderBoard();
            });
        }

        // Eventos del Módulo de Análisis
        // Los selectores de configuración ya no disparan análisis automáticamente.
        // Solo el botón "Pedir Sugerencia" lo activa bajo demanda.
        if (this.btnSuggestMove) this.btnSuggestMove.addEventListener('click', () => this.requestSuggestion());
        if (this.btnLiveAnalysis) {
            this.btnLiveAnalysis.addEventListener('click', () => {
                this.viewedHistoryIndex = null;
                this.btnLiveAnalysis.classList.add('hidden');
                this.renderBoard();
                this.updateHistoryUI();
                this.scheduleRefreshAnalysis(0);
            });
        }

        // Selector de Versión del Motor (por defecto Táctico Selectivo Minimax 2)
        if (this.engineVersionSelect) {
            this.engineVersionSelect.value = 'minimax2';
            this.engineVersionSelect.addEventListener('change', () => this.onEngineVersionChanged());
        }

        // Eventos de Nivel de Elo y Heurísticas MinimaxConfig
        if (this.eloLevelSelect) {
            this.eloLevelSelect.addEventListener('change', (e) => this.onEloLevelChanged(e.target.value));
        }
        if (this.btnToggleAllFlags) {
            this.btnToggleAllFlags.addEventListener('click', () => this.toggleAllFlags());
        }
        document.querySelectorAll('[data-engine-flag]').forEach(cb => {
            cb.addEventListener('change', () => this.onManualFlagChanged());
        });
        this.loadEloProfiles().then(() => {
            this.startNewGame();
        });
    }

    setBoardSize(size) {
        document.body.classList.remove('board-size-small', 'board-size-medium', 'board-size-large', 'board-size-huge', 'board-size-auto');
        document.body.classList.add(`board-size-${size}`);
        this.renderLabels();
        this.renderBoard();
    }

    async changeGameMode() {
        const gameMode = this.gameModeSelect ? this.gameModeSelect.value : 'pvp';
        const color = this.colorSelect ? this.colorSelect.value : 'white';
        const depth = this.analysisDepthSelect ? parseInt(this.analysisDepthSelect.value) : 2;
        const strategy = this.analysisStrategySelect ? this.analysisStrategySelect.value : 'tactico';
        const engineVersion = this.engineVersionSelect ? this.engineVersionSelect.value : 'minimax2';
        const treeMode = this.getTreeMode();
        const timeLimit = this.getTimeLimit();

        try {
            const res = await fetch('/api/set_game_mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    game_mode: gameMode,
                    color: color,
                    depth: depth,
                    strategy: strategy,
                    engine_version: engineVersion,
                    tree_mode: treeMode,
                    time_limit: timeLimit,
                    engine_config: this.getEngineConfig()
                })
            });
            if (!res.ok) {
                console.warn(`[set_game_mode] Respuesta del servidor no OK (Status ${res.status})`);
                return;
            }
            const data = await res.json();
            if (data && data.success) {
                this.updateBoardState(data);
            }
        } catch (err) {
            console.error("Error al cambiar modo de juego:", err);
        }
    }

    async startNewGame() {
        const color = this.colorSelect ? this.colorSelect.value : 'white';
        const gameMode = this.gameModeSelect ? this.gameModeSelect.value : 'pvp';
        const depth = this.analysisDepthSelect ? parseInt(this.analysisDepthSelect.value) : 2;
        const strategy = this.analysisStrategySelect ? this.analysisStrategySelect.value : 'tactico';
        const engineVersion = this.engineVersionSelect ? this.engineVersionSelect.value : 'minimax2';

        try {
            const res = await fetch('/api/new_game', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ color, game_mode: gameMode, depth, strategy, engine_version: engineVersion, engine_config: this.getEngineConfig() })
            });
            const data = await res.json();
            this.viewedHistoryIndex = null;
            this.updateBoardState(data);
        } catch (err) {
            console.error("Error al iniciar nueva partida:", err);
        }
    }

    openPasteModal() {
        if (this.pasteModal) this.pasteModal.classList.remove('hidden');
        if (this.pastePgnInput) this.pastePgnInput.value = '';
    }

    closePasteModal() {
        if (this.pasteModal) this.pasteModal.classList.add('hidden');
    }

    async confirmPastePgn() {
        if (!this.pastePgnInput) return;
        const pgnText = this.pastePgnInput.value.trim();
        if (!pgnText) {
            alert("Por favor pega un historial de jugadas válido.");
            return;
        }

        const depth = this.analysisDepthSelect ? this.analysisDepthSelect.value : 2;
        const strategy = this.analysisStrategySelect ? this.analysisStrategySelect.value : 'tactico';
        const engineVersion = this.engineVersionSelect ? this.engineVersionSelect.value : 'minimax2';

        try {
            const res = await fetch('/api/load_pgn', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pgn: pgnText, depth, strategy, engine_version: engineVersion, engine_config: this.getEngineConfig() })
            });
            const data = await res.json();
            if (data.success) {
                this.closePasteModal();
                this.viewedHistoryIndex = null;
                this.updateBoardState(data);
                this.showToast("¡Partida cargada con éxito!");
            } else {
                alert("No se pudieron interpretar las jugadas del PGN.");
            }
        } catch (err) {
            console.error("Error al cargar PGN:", err);
            alert("Error de conexión al cargar PGN.");
        }
    }

    showToast(message) {
        if (!this.toastMsg) return;
        this.toastMsg.textContent = message;
        this.toastMsg.classList.remove('hidden');
        setTimeout(() => {
            this.toastMsg.classList.add('hidden');
        }, 3000);
    }

    updateBoardState(stateOrData, { skipAnalysis = false } = {}) {
        if (!stateOrData) return;
        this.currentGameState = stateOrData.state ? stateOrData.state : stateOrData;
        this.legalMovesMap = (this.currentGameState && this.currentGameState.legal_moves_map) ? this.currentGameState.legal_moves_map : {};
        this.selectedSquare = null;
        this.legalDestinations = [];
        this.justDropped = false;
        this.renderLabels();
        this.renderBoard();
        this.updateStatusUI();
        this.updateHistoryUI();
        this.updatePreviousMoveUIInstant();

        // Actualizar la barra de evaluación inmediatamente con la evaluación de la posición actual
        if (this.currentGameState && typeof this.currentGameState.eval_white === 'number') {
            this.updateEvalBar({
                eval_white: this.currentGameState.eval_white,
                turn: this.currentGameState.turn,
                is_game_over: this.currentGameState.is_game_over,
                is_checkmate: this.currentGameState.is_check && this.currentGameState.is_game_over
            });
        }

        if (!skipAnalysis) {
            this.scheduleRefreshAnalysis(100);
        }
    }

    updatePreviousMoveUIInstant() {
        if (!this.previousMoveBox) return;

        const history = (this.currentGameState && this.currentGameState.history) ? this.currentGameState.history : [];
        const total = history.length;

        if (total === 0 || this.viewedHistoryIndex === -1) {
            this.previousMoveBox.classList.add('hidden');
            return;
        }

        const effIdx = (this.viewedHistoryIndex === null) ? total - 1 : this.viewedHistoryIndex;

        if (effIdx >= 0 && effIdx < total) {
            const moveData = history[effIdx];
            const moverColor = (effIdx % 2 === 0) ? "Blancas" : "Negras";
            
            this.previousMoveBox.classList.remove('hidden');
            if (this.prevMoveTitle) {
                this.prevMoveTitle.textContent = `Última jugada (${moverColor}): ${moveData.san || ''}`;
            }
            if (this.prevMoveExplanation) {
                this.prevMoveExplanation.textContent = moveData.explanation || `Movimiento ejecutado con ${moveData.san || 'pieza'}.`;
            }
        } else {
            this.previousMoveBox.classList.add('hidden');
        }
    }

    scheduleRefreshAnalysis(delayMs = 500) {
        if (this.analysisDebounceTimer) {
            clearTimeout(this.analysisDebounceTimer);
            this.analysisDebounceTimer = null;
        }
        
        // Actualizar la explicación de la jugada anterior AL INSTANTE (0ms) sin esperar a la API
        this.updatePreviousMoveUIInstant();

        if (delayMs <= 0) {
            this.refreshAnalysis();
        } else {
            this.analysisDebounceTimer = setTimeout(() => {
                this.refreshAnalysis();
            }, delayMs);
        }
    }

    getTreeMode() {
        return this.treeModeSelect ? this.treeModeSelect.value : 'cut';
    }

    getTimeLimit() {
        return this.timeLimitSelect ? this.timeLimitSelect.value : 'off';
    }
    getEngineConfig() {
        const cfg = {};
        if (this.eloLevelSelect && this.eloProfiles && this.eloProfiles[this.eloLevelSelect.value]) {
            const prof = this.eloProfiles[this.eloLevelSelect.value];
            Object.assign(cfg, prof.config || {});
            if (prof.recommended_qdepth !== undefined) {
                cfg['max_quiescence_depth'] = prof.recommended_qdepth;
            }
        }
        document.querySelectorAll('[data-engine-flag]').forEach(cb => {
            if (cb.dataset && cb.dataset.engineFlag) {
                cfg[cb.dataset.engineFlag] = cb.checked;
            }
        });
        if (this.eloLevelSelect) {
            cfg['elo_profile'] = this.eloLevelSelect.value;
            if (this.eloLevelSelect.value === '-1') {
                cfg['is_sublevel_minus_one'] = true;
            }
        }
        return cfg;
    }

    async onEngineVersionChanged() {
        const isMinimax1 = (this.engineVersionSelect && this.engineVersionSelect.value === 'minimax1');
        if (this.eloBadgeInfo) {
            if (isMinimax1) {
                this.eloBadgeInfo.innerHTML = `<span style="color:#fbbf24;">⚡ Minimax 1 (Clásico C++): Fuerza bruta fija (no utiliza flags de Elo)</span>`;
            } else {
                const eloVal = this.eloLevelSelect ? this.eloLevelSelect.value : 'MAX';
                this.applyEloProfile(eloVal, false);
            }
        }
        await this.changeGameMode();
        this.scheduleRefreshAnalysis(0);
    }

    async loadEloProfiles() {
        try {
            const res = await fetch('/api/elo_profiles');
            const data = await res.json();
            if (data.success && data.profiles) {
                this.eloProfiles = data.profiles;
                if (this.eloLevelSelect) {
                    const selectedVal = this.eloLevelSelect.value || 'MAX';
                    const keys = Object.keys(data.profiles).sort((a, b) => {
                        if (a === 'MAX') return -1;
                        if (b === 'MAX') return 1;
                        return parseInt(b) - parseInt(a);
                    });
                    this.eloLevelSelect.innerHTML = '';
                    keys.forEach(k => {
                        const prof = data.profiles[k];
                        const opt = document.createElement('option');
                        opt.value = k;
                        const isSublevel = !isNaN(parseInt(k)) && parseInt(k) <= 300;
                        const icon = k === 'MAX' ? '🏆' : (isSublevel ? '🌱' : '🎯');
                        const label = k === 'MAX' 
                            ? '🏆 MAX - Todas las 55 Heurísticas (Maestro 2600+)' 
                            : `${icon} ${prof.elo_range} (${prof.total_active_techniques}/55 técnicas)`;
                        opt.textContent = label;
                        if (k === selectedVal) opt.selected = true;
                        this.eloLevelSelect.appendChild(opt);
                    });
                    if (!this.eloLevelSelect.value) {
                        this.eloLevelSelect.value = 'MAX';
                    }
                }
                const currentElo = this.eloLevelSelect ? this.eloLevelSelect.value : 'MAX';
                this.applyEloProfile(currentElo, false);
            }
        } catch (err) {
            console.warn('No se pudieron cargar perfiles de Elo:', err);
        }
    }

    onEloLevelChanged(eloVal) {
        this.applyEloProfile(eloVal, true);
        this.changeGameMode();
    }

    applyEloProfile(eloVal, showToast = false) {
        if (!this.eloProfiles || !this.eloProfiles[eloVal]) return;
        const prof = this.eloProfiles[eloVal];
        const cfg = prof.config || {};

        let activeCount = 0;
        document.querySelectorAll('[data-engine-flag]').forEach(cb => {
            const flagName = cb.dataset.engineFlag;
            if (flagName in cfg) {
                cb.checked = Boolean(cfg[flagName]);
                if (cb.checked) activeCount++;
            }
        });

        if (this.eloBadgeCount) {
            this.eloBadgeCount.textContent = `${activeCount}/55`;
        }

        const isMinimax1 = (this.engineVersionSelect && this.engineVersionSelect.value === 'minimax1');
        if (this.eloBadgeInfo) {
            const recDepth = prof.recommended_depth || 4;
            const recQDepth = prof.recommended_qdepth !== undefined ? prof.recommended_qdepth : 8;
            const isSublevel = !isNaN(parseInt(eloVal)) && parseInt(eloVal) <= 300;
            const label = eloVal === 'MAX' ? 'Perfil MAX' : (isSublevel ? prof.elo_range : `Perfil Elo ${eloVal}`);
            if (isMinimax1) {
                this.eloBadgeInfo.innerHTML = `<span style="color:#fbbf24;">⚡ Minimax 1 (Clásico C++): Fuerza bruta fija | Flags de Elo aplican en Minimax 2</span>`;
            } else {
                this.eloBadgeInfo.textContent = `✨ ${label}: ${activeCount}/55 técnicas | Depth: ${recDepth} | Quiescence: ${recQDepth} plies`;
            }
        }

        if (prof.recommended_depth && this.analysisDepthSelect) {
            this.analysisDepthSelect.value = String(prof.recommended_depth);
        }

        if (showToast) {
            const isSublevel = !isNaN(parseInt(eloVal)) && parseInt(eloVal) <= 300;
            const toastLabel = eloVal === 'MAX' ? 'MAX' : (isSublevel ? prof.elo_range : 'Elo ' + eloVal);
            this.showToast(`Perfil ${toastLabel} aplicado (${activeCount} técnicas activadas)`);
        }

        this.updateEloCoachingBanner(eloVal);
    }

    onEngineVersionChanged() {
        const currentElo = this.eloLevelSelect ? this.eloLevelSelect.value : 'MAX';
        this.applyEloProfile(currentElo, false);
        this.updateEloCoachingBanner(currentElo);
        this.changeGameMode();
    }

    updateEloCoachingBanner(eloVal) {
        if (!this.eloCoachingBanner) return;
        const currentElo = eloVal || (this.eloLevelSelect ? this.eloLevelSelect.value : 'MAX');
        const isMinimax2 = (this.engineVersionSelect && this.engineVersionSelect.value === 'minimax2');
        
        if (!isMinimax2 || currentElo === 'MAX' || !this.eloProfiles || !this.eloProfiles[currentElo]) {
            this.eloCoachingBanner.style.display = 'none';
            this.eloCoachingBanner.innerHTML = '';
            return;
        }

        const prof = this.eloProfiles[currentElo];
        const cfg = prof.config || {};
        const recDepth = prof.recommended_depth || 2;
        const recQDepth = prof.recommended_qdepth || 2;
        
        // Buscar siguiente nivel de Elo en orden ascendente
        const numericKeys = Object.keys(this.eloProfiles)
            .filter(k => k !== 'MAX')
            .map(k => parseInt(k))
            .sort((a, b) => a - b);
        
        const currentNum = parseInt(currentElo);
        const nextNum = numericKeys.find(k => k > currentNum);
        const nextKey = nextNum ? String(nextNum) : 'MAX';
        const nextProf = this.eloProfiles[nextKey] || {};
        const nextDepth = nextProf.recommended_depth || (recDepth + 2);
        const nextQDepth = nextProf.recommended_qdepth || (recQDepth + 2);

        // Cálculo de plies y profundidad para ganarle
        const targetDepthToWin = recDepth + 2; // e.g. Depth 4 para vencer a Depth 2
        const targetMoves = targetDepthToWin / 2;
        const currentMoves = recDepth / 2;

        // Detectar debilidades explotables en el perfil actual con distinción T+1 vs T+2
        const weaknesses = [];
        if (currentElo === '-1' || cfg.is_sublevel_minus_one) {
            weaknesses.push("👑 <strong>Salida caótica de Dama o Rey</strong>: En la apertura sacará inmediatamente su Dama o su Rey a casillas tempranas. Aunque no se dejará piezas gratis en 1 ni mate en 1, puedes acosarlo y desarrollar tus piezas ganando tiempos.");
        }
        if (!cfg.use_forks) {
            weaknesses.push("⚔️ <strong>Tenedores directos (T+1)</strong>: El motor no vigila bifurcaciones de caballo ni de peón. Busca ataques dobles de 1 jugada contra su Rey y piezas mayores.");
        } else if (!cfg.use_tactica_avanzada) {
            weaknesses.push("🎯 <strong>Combinaciones preparadas (T+2/T+3)</strong>: Aunque el motor vigila tenedores directos (T+1), es ciego a combinaciones de 2 jugadas como el ataque Fegatello o desvíos tras un cambio.");
        }
        if (!cfg.use_pins_and_skewers) {
            weaknesses.push("📌 <strong>Clavadas y enfiladas</strong>: No detecta piezas clavadas; clava sus caballos o alfiles contra su Rey o Dama.");
        }
        if (!cfg.use_discovered_attacks) {
            weaknesses.push("⚡ <strong>Ataques a la descubierta</strong>: No vigila rayos X generados al retirar una pieza intermedia.");
        }
        if (!cfg.use_mating_net_radar || !cfg.use_back_rank_safety) {
            weaknesses.push("👑 <strong>Primera fila y redes de mate</strong>: Ceguera ante amenazas de mate en 2 jugadas en su primera fila (puedes atacarlo con torre + caballo/alfil).");
        }
        if (!cfg.use_retreat_safety) {
            weaknesses.push("🛡️ <strong>Amenazas de peón</strong>: No siempre retira piezas atacadas por peones; avanza peones para ganar tiempos.");
        }
        if (!cfg.use_trapped_pieces) {
            weaknesses.push("🕸️ <strong>Piezas atrapadas</strong>: No vigila casillas de escape de sus alfiles/caballos; puedes asfixiarlos.");
        }
        if (!cfg.use_see) {
            weaknesses.push("🔢 <strong>Recuento de defensores</strong>: Tiende a entrar en casillas sobre-defendidas si tiene 1 atacante.");
        }
        if (!cfg.use_pawn_structure) {
            weaknesses.push("♟️ <strong>Estructura de peones</strong>: No penaliza peones doblados o aislados; crear debilidades de peón te dará ventaja posicional.");
        }

        // Técnicas que se habilitan en el siguiente nivel
        const nextCfg = nextProf.config || {};
        const techNames = {
            'use_early_queen_penalty': 'Penalización por sacar Dama prematura',
            'use_preserve_castling_rights': 'Preservación de enroque',
            'use_mate_endgames': 'Mates elementales de final',
            'use_endgame_eval': 'Evaluación de finales',
            'use_pst': 'Piece-Square Tables (PST: juego posicional y control central)',
            'use_forks': 'Tenedores y ataques dobles directos (T+1)',
            'use_pins_and_skewers': 'Clavadas y enfiladas',
            'use_discovered_attacks': 'Ataques a la descubierta',
            'use_see': 'SEE (Recuento de defensores)',
            'use_king_safety': 'Seguridad del Rey',
            'use_back_rank_safety': 'Seguridad de primera fila',
            'use_castling_incentive': 'Incentivo de enroque',
            'use_retreat_safety': 'Retirada segura de piezas',
            'use_mating_net_radar': 'Radar de redes de mate',
            'use_trapped_pieces': 'Radar de piezas atrapadas',
            'use_opening_development': 'Desarrollo armónico de apertura',
            'use_pawn_structure': 'Estructura de peones',
            'use_tactica_avanzada': 'Forma Táctica T+2/T+3 (Combinaciones preparadas)'
        };

        const newTechniques = [];
        for (const [k, name] of Object.entries(techNames)) {
            if (!cfg[k] && nextCfg[k]) {
                newTechniques.push(name);
            }
        }

        const currentTitle = prof.elo_range ? prof.elo_range : `Elo ${currentElo}`;
        const nextTitle = nextProf.elo_range ? nextProf.elo_range : (nextKey === 'MAX' ? 'MAX (2600+)' : `Elo ${nextKey}`);
        const currentMovesText = recDepth % 2 === 0 ? `${recDepth / 2} jugadas completas` : `${recDepth} ply (${recDepth / 2} jugada)`;
        const targetMovesText = targetDepthToWin % 2 === 0 ? `${targetDepthToWin / 2} jugadas completas` : `${targetDepthToWin} plies (${targetDepthToWin / 2} jugadas)`;

        let html = `
            <div class="elo-coaching-header">
                <span>💡 Guía Táctica para Superar ${currentTitle}</span>
                <span class="elo-coaching-badge">Meta: ${nextTitle}</span>
            </div>
            <div class="elo-coaching-row">
                🧠 <strong>Cálculo para Ganarle:</strong> Este nivel piensa a <strong>Profundidad ${recDepth} (${currentMovesText})</strong> + <strong>${recQDepth} plies de capturas</strong>. Para superarlo, calcula a <strong>Profundidad ${targetDepthToWin} (${targetMovesText})</strong> y adelántate a sus respuestas.
            </div>
        `;

        if (weaknesses.length > 0) {
            html += `
                <div class="elo-coaching-row" style="margin-top: 5px;">
                    <strong>🎯 Puntos débiles a explotar en este nivel:</strong>
                    ${weaknesses.slice(0, 3).map(w => `<div class="elo-coaching-weakness">${w}</div>`).join('')}
                </div>
            `;
        }

        if (newTechniques.length > 0) {
            html += `
                <div class="elo-coaching-row" style="margin-top: 5px;">
                    <strong>🚀 En el siguiente nivel (${nextTitle}) se habilita:</strong>
                    <div class="elo-coaching-next">✨ ${newTechniques.join(' • ')} (Depth ${nextDepth}, Quiescence ${nextQDepth} plies).</div>
                </div>
            `;
        } else {
            html += `
                <div class="elo-coaching-row" style="margin-top: 5px;">
                    <strong>🚀 Próximo Nivel (${nextTitle}):</strong>
                    <div class="elo-coaching-next">Profundidad ${nextDepth} plies | Quiescence ${nextQDepth} plies | ${nextProf.total_active_techniques || 'Más'} técnicas activas.</div>
                </div>
            `;
        }

        this.eloCoachingBanner.innerHTML = html;
        this.eloCoachingBanner.style.display = 'block';
    }

    onManualFlagChanged() {
        let activeCount = 0;
        document.querySelectorAll('[data-engine-flag]').forEach(cb => {
            if (cb.checked) activeCount++;
        });
        if (this.eloBadgeCount) {
            this.eloBadgeCount.textContent = `${activeCount}/55`;
        }
        const isMinimax1 = (this.engineVersionSelect && this.engineVersionSelect.value === 'minimax1');
        if (this.eloBadgeInfo) {
            if (isMinimax1) {
                this.eloBadgeInfo.innerHTML = `<span style="color:#fbbf24;">⚡ Minimax 1 (Clásico C++): Fuerza bruta fija | Flags de Elo aplican en Minimax 2</span>`;
            } else {
                this.eloBadgeInfo.textContent = `Personalizado: ${activeCount}/55 técnicas activas`;
            }
        }
    }

    toggleAllFlags() {
        const checkboxes = document.querySelectorAll('[data-engine-flag]');
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => cb.checked = !allChecked);
        if (this.btnToggleAllFlags) {
            this.btnToggleAllFlags.textContent = allChecked ? "Activar Todas" : "Desactivar Todas";
        }
        this.onManualFlagChanged();
        if (!allChecked && this.eloLevelSelect) {
            this.eloLevelSelect.value = "MAX";
            this.applyEloProfile("MAX", false);
        }
    }


    startLoadingAnimation(customText = "Analizando") {
        if (!this.analysisLoadingIndicator) return;
        this.analysisLoadingIndicator.classList.remove('hidden');
        let count = 1;
        if (this.loadingTimerInterval) clearInterval(this.loadingTimerInterval);
        
        if (this.loadingDotsElement) {
            this.loadingDotsElement.textContent = '.';
        }

        const loadingTextElem = this.analysisLoadingIndicator.querySelector('.loading-text');
        if (loadingTextElem && loadingTextElem.childNodes.length > 0) {
            loadingTextElem.childNodes[0].nodeValue = `${customText} `;
        }

        this.loadingTimerInterval = setInterval(() => {
            count = (count % 3) + 1;
            const dots = '.'.repeat(count);
            if (this.loadingDotsElement) {
                this.loadingDotsElement.textContent = dots;
            }
        }, 350);
    }

    stopLoadingAnimation() {
        if (this.loadingTimerInterval) {
            clearInterval(this.loadingTimerInterval);
            this.loadingTimerInterval = null;
        }
        if (this.analysisLoadingIndicator) {
            this.analysisLoadingIndicator.classList.add('hidden');
        }
    }

    applyOptimisticMove(fromSquare, toSquare) {
        const grid = this.getActiveGrid();
        if (!grid || grid.length === 0) return;

        let pieceObj = null;
        for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
                if (grid[r][f] && grid[r][f].square === fromSquare) {
                    pieceObj = grid[r][f];
                    grid[r][f] = null;
                    break;
                }
            }
        }
        if (pieceObj) {
            for (let r = 0; r < 8; r++) {
                for (let f = 0; f < 8; f++) {
                    const fileChar = String.fromCharCode(97 + f);
                    const rankChar = String(8 - r);
                    if (`${fileChar}${rankChar}` === toSquare) {
                        grid[r][f] = { ...pieceObj, square: toSquare };
                        break;
                    }
                }
            }
        }
    }

    async refreshAnalysis() {
        const requestId = ++this.latestAnalysisRequestId;

        if (this.currentAbortController) {
            try {
                this.currentAbortController.abort();
            } catch (e) {}
        }
        this.currentAbortController = new AbortController();

        const depth = this.analysisDepthSelect ? this.analysisDepthSelect.value : 2;
        const strategy = this.analysisStrategySelect ? this.analysisStrategySelect.value : 'tactico';
        const engineVersion = this.engineVersionSelect ? this.engineVersionSelect.value : 'minimax2';
        const treeMode = this.getTreeMode();
        const timeLimit = this.getTimeLimit();

        let url = `/api/analyze?depth=${encodeURIComponent(depth)}&strategy=${encodeURIComponent(strategy)}&engine_version=${encodeURIComponent(engineVersion)}&tree_mode=${encodeURIComponent(treeMode)}&time_limit=${encodeURIComponent(timeLimit)}&engine_config=${encodeURIComponent(JSON.stringify(this.getEngineConfig()))}`;
        if (this.viewedHistoryIndex !== null) {
            url += `&move_index=${encodeURIComponent(this.viewedHistoryIndex)}`;
        }

        try {
            this.startLoadingAnimation("Analizando posición");
            const res = await fetch(url, { signal: this.currentAbortController.signal });
            if (!res.ok) return;
            const data = await res.json();

            // Si ha habido una solicitud más nueva mientras esta se procesaba, descartar la respuesta obsoleta
            if (requestId !== this.latestAnalysisRequestId) return;

            this.renderAnalysisUI(data);
        } catch (err) {
            if (err.name === 'AbortError') return;
            console.error("Error al refrescar análisis:", err);
        } finally {
            if (requestId === this.latestAnalysisRequestId) {
                this.stopLoadingAnimation();
            }
        }
    }

    renderAnalysisUI(data) {
        if (!data) return;
        if (this.analysisTitle) this.analysisTitle.textContent = data.title || "Análisis del Motor";
        
        if (this.previousMoveBox) {
            if (data.previous_move) {
                this.previousMoveBox.classList.remove('hidden');
                if (this.prevMoveTitle) this.prevMoveTitle.textContent = data.previous_move.title || "Última jugada";
                if (this.prevMoveExplanation) this.prevMoveExplanation.textContent = data.previous_move.explanation || "Movimiento ejecutado.";
            } else {
                this.previousMoveBox.classList.add('hidden');
            }
        }

        if (this.recommendedMoveSan) {
            this.recommendedMoveSan.textContent = data.move_san || "-";
        }

        const rawType = (data.category || data.type || "tactico").toLowerCase();
        let badgeClass = "badge-tactical";
        let badgeText = "Táctico";

        if (rawType.includes("posicional") || rawType.includes("desarrollo")) {
            badgeClass = "badge-positional";
            badgeText = "Posicional";
        } else if (rawType.includes("jaque")) {
            badgeClass = "badge-check";
            badgeText = "Jaque";
        } else if (rawType.includes("captura")) {
            badgeClass = "badge-tactical";
            badgeText = "Captura";
        }

        if (this.analysisTypeBadge) {
            this.analysisTypeBadge.className = `badge ${badgeClass}`;
            this.analysisTypeBadge.textContent = badgeText;
        }

        if (this.analysisBody) {
            this.analysisBody.textContent = data.explanation || "Haz un movimiento o solicita sugerencia para ver la explicación detallada.";
        }

        if (this.btnLiveAnalysis) {
            if (this.viewedHistoryIndex !== null) {
                this.btnLiveAnalysis.classList.remove('hidden');
            } else {
                this.btnLiveAnalysis.classList.add('hidden');
            }
        }

        // Re-habilitar el botón de sugerencia si estaba bloqueado por un cálculo
        if (this.btnSuggestMove) this.btnSuggestMove.disabled = false;
        if (this._pendingSuggestionUnlock) {
            this._pendingSuggestionUnlock();
            this._pendingSuggestionUnlock = null;
        }

        this.updateEvalBar(data);
    }

    updateEvalBar(data) {
        if (!data || (!this.evalBarWhite && !this.evalBarBlack)) return;

        let evalWhite = 0.0;
        let isMate = false;

        if (typeof data.eval_white === 'number') {
            evalWhite = data.eval_white;
        } else if (typeof data.score === 'number') {
            const turn = data.turn || (this.currentGameState ? this.currentGameState.turn : 'white');
            evalWhite = (turn === 'white') ? data.score : -data.score;
        }

        // Convertir puntuación del motor (escala estática de piezas / 10) a unidades de peones
        let pawnEval = evalWhite / 10.0;

        // Detección de Jaque Mate / Ventaja Decisiva
        if (Math.abs(evalWhite) >= 500) {
            isMate = true;
            pawnEval = evalWhite > 0 ? 100 : -100;
        }

        // Calcular porcentaje de relleno para el lado de las Blancas (sigmoide estándar de ajedrez)
        let whitePercent = 50;
        if (isMate) {
            whitePercent = evalWhite > 0 ? 100 : 0;
        } else {
            whitePercent = 100 / (1 + Math.pow(10, -pawnEval / 4));
            whitePercent = Math.max(5, Math.min(95, whitePercent));
        }

        if (this.evalBarBlack && this.evalBarWhite) {
            if (this.isFlipped) {
                // Tablero Girado (Negras abajo): Blancas arriba, Negras abajo
                this.evalBarWhite.style.height = `${whitePercent}%`;
                this.evalBarBlack.style.height = `${100 - whitePercent}%`;
            } else {
                // Tablero Normal (Blancas abajo): Negras arriba, Blancas abajo
                this.evalBarBlack.style.height = `${100 - whitePercent}%`;
                this.evalBarWhite.style.height = `${whitePercent}%`;
            }
        }

        // Formatear etiqueta de texto (0.0, +1.5, -2.4, +M1, -M2)
        let labelText = "0.0";
        if (typeof data.mate_in === 'number' && data.mate_in !== 0) {
            isMate = true;
            const sign = data.mate_in > 0 ? "+" : "-";
            labelText = `${sign}M${Math.abs(data.mate_in)}`;
        } else if (isMate) {
            labelText = evalWhite > 0 ? "+M" : "-M";
        } else {
            const formatted = Math.abs(pawnEval).toFixed(1);
            if (pawnEval > 0.05) {
                labelText = `+${formatted}`;
            } else if (pawnEval < -0.05) {
                labelText = `-${formatted}`;
            } else {
                labelText = "0.0";
            }
        }

        if (this.evalScoreText) {
            this.evalScoreText.textContent = labelText;
            
            // Posicionar verticalmente la etiqueta acompañando la divisoria
            const topOffsetPercent = this.isFlipped ? whitePercent : (100 - whitePercent);
            const clampedOffset = Math.max(8, Math.min(88, topOffsetPercent));
            this.evalScoreText.style.top = `calc(${clampedOffset}% - 11px)`;
        }

        if (this.moveScore) {
            this.moveScore.textContent = `Puntaje: ${labelText}`;
        }
    }

    renderLabels() {
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];

        const currentFiles = this.isFlipped ? [...files].reverse() : files;
        const currentRanks = this.isFlipped ? [...ranks].reverse() : ranks;

        if (this.filesTop) this.filesTop.innerHTML = currentFiles.map(f => `<span>${f}</span>`).join('');
        if (this.filesBottom) this.filesBottom.innerHTML = currentFiles.map(f => `<span>${f}</span>`).join('');
        if (this.ranksLeft) this.ranksLeft.innerHTML = currentRanks.map(r => `<span>${r}</span>`).join('');
        if (this.ranksRight) this.ranksRight.innerHTML = currentRanks.map(r => `<span>${r}</span>`).join('');
    }

    getActiveGrid() {
        if (!this.currentGameState) return [];

        if (this.viewedHistoryIndex !== null) {
            if (this.viewedHistoryIndex === -1 && this.currentGameState.initial_grid) {
                return this.currentGameState.initial_grid;
            }
            if (this.currentGameState.history && this.viewedHistoryIndex >= 0 && this.viewedHistoryIndex < this.currentGameState.history.length) {
                const hist = this.currentGameState.history[this.viewedHistoryIndex];
                if (hist.fen_grid) return hist.fen_grid;
            }
        }

        return this.currentGameState.grid;
    }

    getActiveTurn() {
        if (!this.currentGameState) return "white";
        if (this.viewedHistoryIndex === null) return this.currentGameState.turn;
        if (this.viewedHistoryIndex === -1) return "white";
        return (this.viewedHistoryIndex % 2 === 0) ? "black" : "white";
    }

    renderBoard() {
        if (!this.boardElement) return;
        this.boardElement.innerHTML = '';
        if (!this.currentGameState) return;

        const grid = this.getActiveGrid();
        if (!grid || grid.length === 0) return;

        const ranks = [0, 1, 2, 3, 4, 5, 6, 7];
        const files = this.isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
        const displayRanks = this.isFlipped ? [...ranks].reverse() : ranks;

        for (let rIdx of displayRanks) {
            const row = grid[rIdx];
            for (let fIdx of files) {
                const cell = row ? row[fIdx] : null;
                const fileChar = String.fromCharCode(97 + fIdx);
                const rankChar = String(8 - rIdx);
                const squareName = (cell && cell.square) ? cell.square : `${fileChar}${rankChar}`;

                const isLight = (fIdx + (8 - rIdx)) % 2 !== 0;

                const squareElem = document.createElement('div');
                squareElem.className = `square ${isLight ? 'light' : 'dark'}`;
                squareElem.dataset.square = squareName;

                if (this.selectedSquare === squareName) {
                    squareElem.classList.add('selected');
                }

                if (this.viewedHistoryIndex !== null && this.currentGameState.history) {
                    if (this.viewedHistoryIndex >= 0 && this.viewedHistoryIndex < this.currentGameState.history.length) {
                        const hMove = this.currentGameState.history[this.viewedHistoryIndex];
                        if (hMove.from === squareName || hMove.to === squareName) {
                            squareElem.classList.add('last-move');
                        }
                    }
                } else if (this.currentGameState.last_move) {
                    const lm = this.currentGameState.last_move;
                    if (lm.from === squareName || lm.to === squareName) {
                        squareElem.classList.add('last-move');
                    }
                }

                const activeTurn = this.getActiveTurn();
                const isLive = (this.viewedHistoryIndex === null);
                const hasCheck = isLive ? this.currentGameState.is_check : (this.viewedHistoryIndex >= 0 && this.currentGameState.history && this.currentGameState.history[this.viewedHistoryIndex] && (this.currentGameState.history[this.viewedHistoryIndex].san || '').includes('+'));
                if (cell && hasCheck && cell.type === 'k' && cell.color === activeTurn) {
                    squareElem.classList.add('in-check');
                }

                if (cell && cell.type && cell.color) {
                    const pieceKey = (cell.color === 'white' ? 'w' : 'b') + cell.type;
                    const pieceElem = document.createElement('div');
                    pieceElem.className = 'piece';
                    pieceElem.dataset.square = squareName;
                    pieceElem.draggable = true;

                    if (this.pieceTheme === 'lichess' || this.pieceTheme === 'staunton') {
                        const filePrefix = (this.pieceTheme === 'lichess') ? 'lichess_' : '';
                        pieceElem.style.backgroundImage = `url('/static/images/pieces/${filePrefix}${pieceKey}.svg')`;
                        pieceElem.style.borderRadius = '0';
                        pieceElem.style.border = 'none';
                        pieceElem.style.boxShadow = 'none';
                        pieceElem.textContent = '';
                    } else if (this.pieceTheme === 'unicode') {
                        pieceElem.style.backgroundImage = 'none';
                        pieceElem.style.borderRadius = '0';
                        pieceElem.style.border = 'none';
                        pieceElem.style.boxShadow = 'none';
                        pieceElem.classList.add('unicode-piece');
                        pieceElem.classList.add(cell.color === 'white' ? 'white-piece' : 'black-piece');
                        pieceElem.textContent = pieceUnicodeMap[pieceKey] || '';
                    } else if (this.pieceTheme === 'gemini_svg') {
                        pieceElem.style.backgroundImage = `url('/static/images/pieces/gemini_svg_${pieceKey}.svg')`;
                        pieceElem.style.borderRadius = '0';
                        pieceElem.style.border = 'none';
                        pieceElem.style.boxShadow = 'none';
                        pieceElem.style.filter = 'drop-shadow(0px 3px 5px rgba(0,0,0,0.5))';
                        pieceElem.textContent = '';
                    } else if (this.pieceTheme && this.pieceTheme.startsWith('custom')) {
                        pieceElem.style.backgroundImage = `url('/static/images/pieces/${this.pieceTheme}_${pieceKey}.png')`;
                        pieceElem.style.borderRadius = '0';
                        pieceElem.style.border = 'none';
                        pieceElem.style.boxShadow = 'none';
                        pieceElem.style.filter = 'drop-shadow(0px 4px 6px rgba(0,0,0,0.5))';
                        pieceElem.textContent = '';
                    }

                    pieceElem.addEventListener('dragstart', (e) => this.handleDragStart(e, squareName));
                    pieceElem.addEventListener('dragend', (e) => this.handleDragEnd(e));
                    pieceElem.addEventListener('dragover', (e) => {
                        e.preventDefault();
                        if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
                    });
                    squareElem.appendChild(pieceElem);
                }

                if (this.legalDestinations.includes(squareName)) {
                    if (cell && cell.type) {
                        const ring = document.createElement('div');
                        ring.className = 'legal-ring';
                        squareElem.appendChild(ring);
                    } else {
                        const dot = document.createElement('div');
                        dot.className = 'legal-dot';
                        squareElem.appendChild(dot);
                    }
                }

                squareElem.addEventListener('click', () => this.handleSquareClick(squareName));
                squareElem.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
                });
                squareElem.addEventListener('drop', (e) => this.handleDrop(e, squareName));

                this.boardElement.appendChild(squareElem);
            }
        }

        this.updateNavIndicatorUI();
    }

    clearLegalMoveIndicators() {
        if (!this.boardElement) return;
        this.boardElement.querySelectorAll('.legal-dot, .legal-ring').forEach(el => el.remove());
        this.boardElement.querySelectorAll('.square.selected').forEach(el => el.classList.remove('selected'));
    }

    highlightLegalMoveIndicators() {
        if (!this.boardElement) return;
        this.clearLegalMoveIndicators();

        if (this.selectedSquare) {
            const selectedElem = this.boardElement.querySelector(`.square[data-square="${this.selectedSquare}"]`);
            if (selectedElem) selectedElem.classList.add('selected');
        }

        if (!this.legalDestinations || this.legalDestinations.length === 0) return;

        for (const dest of this.legalDestinations) {
            const sqElem = this.boardElement.querySelector(`.square[data-square="${dest}"]`);
            if (!sqElem) continue;

            const cell = this.getCellInfo(dest);
            if (cell && cell.type) {
                const ring = document.createElement('div');
                ring.className = 'legal-ring';
                sqElem.appendChild(ring);
            } else {
                const dot = document.createElement('div');
                dot.className = 'legal-dot';
                sqElem.appendChild(dot);
            }
        }
    }

    getLegalDestinationsForSquare(squareName) {
        if (this.viewedHistoryIndex === null && this.legalMovesMap) {
            return this.legalMovesMap[squareName] ? [...this.legalMovesMap[squareName]] : [];
        }
        return null;
    }

    async handleSquareClick(squareName) {
        if (this.isProcessingMove) return;
        if (this.justDropped) {
            this.justDropped = false;
            return;
        }

        if (this.selectedSquare && this.legalDestinations && this.legalDestinations.includes(squareName)) {
            await this.attemptMove(this.selectedSquare, squareName);
            return;
        }

        if (this.selectedSquare === squareName) {
            this.selectedSquare = null;
            this.legalDestinations = [];
            this.clearLegalMoveIndicators();
            return;
        }

        const cell = this.getCellInfo(squareName);
        const activeTurn = this.getActiveTurn();

        if (cell && cell.color === activeTurn) {
            this.selectedSquare = squareName;
            const fastDests = this.getLegalDestinationsForSquare(squareName);
            if (fastDests !== null) {
                // Modo tiempo real: resolución instantánea en 0ms sin esperar al servidor
                this.legalDestinations = fastDests;
                this.highlightLegalMoveIndicators();
            } else {
                // Modo histórico: consultar al servidor
                await this.fetchLegalMoves(squareName);
                this.highlightLegalMoveIndicators();
            }
        } else {
            if (cell && cell.color && this.viewedHistoryIndex !== null) {
                const isUserPiece = cell.color === (this.colorSelect ? this.colorSelect.value : 'white');
                if (isUserPiece && activeTurn !== cell.color) {
                    const opponentName = (activeTurn === 'white') ? "Blancas" : "Negras";
                    this.showToast(`Es el turno de las ${opponentName} en la Jugada #${this.viewedHistoryIndex + 1}. Retrocede 1 jugada más con (◀) para cambiar tu movimiento.`);
                }
            }
            this.selectedSquare = null;
            this.legalDestinations = [];
            this.clearLegalMoveIndicators();
        }
    }

    async fetchLegalMoves(squareName) {
        try {
            let url = `/api/legal_moves?square=${squareName}`;
            if (this.viewedHistoryIndex !== null) {
                url += `&move_index=${encodeURIComponent(this.viewedHistoryIndex)}`;
            }
            const res = await fetch(url);
            const data = await res.json();
            this.legalDestinations = data.destinations || [];
        } catch (err) {
            console.error("Error al obtener movimientos legales:", err);
            this.legalDestinations = [];
        }
    }

    handleDragStart(e, squareName) {
        if (this.isProcessingMove) {
            e.preventDefault();
            return;
        }

        const cell = this.getCellInfo(squareName);
        const activeTurn = this.getActiveTurn();
        if (cell && cell.color === activeTurn) {
            this.selectedSquare = squareName;
            this.draggedSquare = squareName;

            // Iluminación instantánea de opciones válidas (0ms)
            const fastDests = this.getLegalDestinationsForSquare(squareName);
            if (fastDests !== null) {
                this.legalDestinations = fastDests;
                this.highlightLegalMoveIndicators();
            } else {
                this.fetchLegalMoves(squareName).then(() => {
                    if (this.draggedSquare === squareName || this.selectedSquare === squareName) {
                        this.highlightLegalMoveIndicators();
                    }
                });
            }

            if (e.target && e.target.classList) {
                e.target.classList.add('dragging');
            }

            if (e.dataTransfer) {
                e.dataTransfer.setData('text/plain', squareName);
                e.dataTransfer.effectAllowed = 'move';
            }
        } else {
            if (cell && cell.color && this.viewedHistoryIndex !== null) {
                const isUserPiece = cell.color === (this.colorSelect ? this.colorSelect.value : 'white');
                if (isUserPiece && activeTurn !== cell.color) {
                    const opponentName = (activeTurn === 'white') ? "Blancas" : "Negras";
                    this.showToast(`Es el turno de las ${opponentName} en la Jugada #${this.viewedHistoryIndex + 1}. Retrocede 1 jugada más con (◀) para cambiar tu movimiento.`);
                }
            }
            e.preventDefault();
        }
    }

    handleDragEnd(e) {
        if (e.target && e.target.classList) {
            e.target.classList.remove('dragging');
        }
        if (this.boardElement) {
            this.boardElement.querySelectorAll('.piece.dragging').forEach(p => p.classList.remove('dragging'));
        }
        this.draggedSquare = null;
    }

    async handleDrop(e, targetSquare) {
        e.preventDefault();
        this.justDropped = true;
        setTimeout(() => { this.justDropped = false; }, 250);

        if (this.boardElement) {
            this.boardElement.querySelectorAll('.piece.dragging').forEach(p => p.classList.remove('dragging'));
        }

        if (this.isProcessingMove) return;

        const fromSquare = (e.dataTransfer && e.dataTransfer.getData('text/plain')) || this.draggedSquare || this.selectedSquare;
        this.draggedSquare = null;

        if (!fromSquare || !targetSquare || fromSquare === targetSquare) {
            this.clearLegalMoveIndicators();
            this.selectedSquare = null;
            this.legalDestinations = [];
            return;
        }

        // Determinar destinos legales ya calculados o en caché
        let legalDests = this.legalDestinations;
        if (!legalDests || legalDests.length === 0) {
            const fast = this.getLegalDestinationsForSquare(fromSquare);
            if (fast && fast.length > 0) legalDests = fast;
        }

        if (legalDests && legalDests.includes(targetSquare)) {
            await this.attemptMove(fromSquare, targetSquare);
        } else {
            // Si no es un destino legal, limpiar indicadores
            this.clearLegalMoveIndicators();
            this.selectedSquare = null;
            this.legalDestinations = [];
        }
    }

    async attemptMove(fromSquare, toSquare) {
        const cell = this.getCellInfo(fromSquare);
        
        const targetRank = toSquare[1];
        if (cell && cell.type === 'p' && (targetRank === '8' || targetRank === '1')) {
            this.pendingMove = { from: fromSquare, to: toSquare };
            if (this.promotionModal) this.promotionModal.classList.remove('hidden');
            return;
        }

        await this.executeMove(fromSquare, toSquare);
    }

    async completePromotion(promotionPiece) {
        if (this.promotionModal) this.promotionModal.classList.add('hidden');
        if (this.pendingMove) {
            await this.executeMove(this.pendingMove.from, this.pendingMove.to, promotionPiece);
            this.pendingMove = null;
        }
    }

    async executeMove(fromSquare, toSquare, promotion = null) {
        if (this.isProcessingMove) return;
        this.isProcessingMove = true;

        this.selectedSquare = null;
        this.legalDestinations = [];
        this.clearLegalMoveIndicators();

        const depth = this.analysisDepthSelect ? this.analysisDepthSelect.value : 2;
        const strategy = this.analysisStrategySelect ? this.analysisStrategySelect.value : 'tactico';
        const engineVersion = this.engineVersionSelect ? this.engineVersionSelect.value : 'minimax2';
        const treeMode = this.getTreeMode();
        const timeLimit = this.getTimeLimit();

        const truncateIdx = (this.viewedHistoryIndex !== null) ? this.viewedHistoryIndex : null;

        // Snapshot de seguridad para revertir si la petición falla
        const gridSnapshot = JSON.parse(JSON.stringify(this.getActiveGrid() || []));
        const turnSnapshot = this.currentGameState ? this.currentGameState.turn : 'white';

        // Renderizado instantáneo local para cero retraso en UI
        this.applyOptimisticMove(fromSquare, toSquare);
        
        const isPvE = (this.gameModeSelect ? this.gameModeSelect.value : 'pvp') === 'pve';
        if (isPvE) {
            const userColor = this.colorSelect ? this.colorSelect.value : 'white';
            const engineColor = (userColor === 'white') ? 'black' : 'white';
            if (this.currentGameState) {
                this.currentGameState.turn = engineColor;
            }
            this.updateStatusUI();
            this.renderBoard();
            this.startLoadingAnimation("🤖 El motor está calculando su respuesta");
        } else {
            this.renderBoard();
            this.startLoadingAnimation("Procesando jugada...");
        }

        try {
            const res = await fetch('/api/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    from: fromSquare,
                    to: toSquare,
                    promotion: promotion,
                    depth: depth,
                    strategy: strategy,
                    engine_version: engineVersion,
                    tree_mode: treeMode,
                    time_limit: timeLimit,
                    truncate_at: truncateIdx,
                    engine_config: this.getEngineConfig()
                })
            });
            if (!res.ok) {
                if (this.currentGameState) {
                    this.currentGameState.grid = gridSnapshot;
                    this.currentGameState.turn = turnSnapshot;
                }
                this.renderBoard();
                this.updateStatusUI();
                alert("Error de comunicación con el servidor.");
                return;
            }
            const data = await res.json();

            if (data.success) {
                this.viewedHistoryIndex = null;
                this.updateBoardState(data, { skipAnalysis: true });
                this.clearSuggestionUI();
            } else {
                if (this.currentGameState) {
                    this.currentGameState.grid = gridSnapshot;
                    this.currentGameState.turn = turnSnapshot;
                }
                this.renderBoard();
                this.updateStatusUI();
                alert(data.message || "Movimiento no permitido.");
            }
        } catch (err) {
            console.error("Error al realizar movimiento:", err);
            if (this.currentGameState) {
                this.currentGameState.grid = gridSnapshot;
                this.currentGameState.turn = turnSnapshot;
            }
            this.renderBoard();
            this.updateStatusUI();
        } finally {
            this.stopLoadingAnimation();
            this.isProcessingMove = false;
        }
    }

    // Limpia el panel de sugerencia para que el usuario sepa que debe pedir una nueva.
    clearSuggestionUI() {
        if (this.recommendedMoveSan) this.recommendedMoveSan.textContent = '-';
        if (this.analysisBody) this.analysisBody.textContent = 'Haz clic en "💡 Pedir Sugerencia" para que el motor calcule la mejor jugada para vos.';
        if (this.moveScore) this.moveScore.textContent = 'Puntaje: -';
        if (this.analysisTitle) this.analysisTitle.textContent = 'Sugerencia bajo demanda';
        if (this.btnSuggestMove) this.btnSuggestMove.disabled = false;
    }

    // Calcula la sugerencia solo cuando el usuario la solicita explícitamente.
    requestSuggestion() {
        if (this.btnSuggestMove) this.btnSuggestMove.disabled = true;
        this.startLoadingAnimation('💡 Calculando sugerencia');
        this.scheduleRefreshAnalysis(0);
        // Re-habilitar el botón al terminar (lo hace stopLoadingAnimation/renderAnalysisUI)
        const origRender = this.renderAnalysisUI.bind(this);
        const origStop = this.stopLoadingAnimation.bind(this);
        const self = this;
        this._pendingSuggestionUnlock = () => {
            if (self.btnSuggestMove) self.btnSuggestMove.disabled = false;
        };
    }

    getCellInfo(squareName) {
        const grid = this.getActiveGrid();
        if (!grid) return null;
        for (let row of grid) {
            if (!row) continue;
            for (let cell of row) {
                if (cell && cell.square === squareName) return cell;
            }
        }
        return null;
    }

    toggleFlipBoard() {
        this.isFlipped = !this.isFlipped;
        this.renderLabels();
        this.renderBoard();
        this.refreshAnalysis();
    }

    updateStatusUI() {
        if (!this.currentGameState) return;

        const activeTurn = this.getActiveTurn();
        const isWhite = activeTurn === 'white';
        if (this.turnIndicator) {
            this.turnIndicator.className = `turn-badge ${isWhite ? 'white-turn' : 'black-turn'}`;
            const iconSpan = this.turnIndicator.querySelector('.badge-icon');
            if (iconSpan) iconSpan.textContent = isWhite ? '⚪' : '⚫';
        }
        const isPvE = (this.gameModeSelect ? this.gameModeSelect.value : 'pvp') === 'pve';
        const userColor = this.colorSelect ? this.colorSelect.value : 'white';
        const engineColor = (userColor === 'white') ? 'black' : 'white';
        const isEngineTurn = isPvE && (activeTurn === engineColor) && (this.viewedHistoryIndex === null);

        if (this.turnDot) {
            this.turnDot.className = 'turn-indicator-dot ' + (isWhite ? 'white-turn' : 'black-turn');
            this.turnDot.textContent = isWhite ? '⚪' : '⚫';
        }
        if (this.turnText) {
            let label = isWhite ? 'Blancas' : 'Negras';
            if (isEngineTurn) {
                label += ' (Motor pensando...)';
            }
            this.turnText.textContent = label;
        }

        if (this.statusMessage) {
            if (this.viewedHistoryIndex !== null) {
                if (this.viewedHistoryIndex === -1) {
                    this.statusMessage.textContent = "Revisando: Posición inicial";
                } else {
                    const total = this.currentGameState.history ? this.currentGameState.history.length : 0;
                    this.statusMessage.textContent = `Revisando jugada ${this.viewedHistoryIndex + 1} de ${total}`;
                }
            } else if (isEngineTurn) {
                this.statusMessage.textContent = "🤖 Calculando jugada...";
            } else {
                this.statusMessage.textContent = this.currentGameState.result_message || 
                    (this.currentGameState.is_check ? "¡Jaque!" : "En curso");
            }
        }
    }

    updateHistoryUI() {
        if (!this.moveHistoryElement || !this.currentGameState || !this.currentGameState.history) return;

        const history = this.currentGameState.history;
        if (history.length === 0) {
            this.moveHistoryElement.innerHTML = '<div class="history-empty">No hay movimientos aún</div>';
            return;
        }

        let html = '';
        const isLive = (this.viewedHistoryIndex === null);
        for (let i = 0; i < history.length; i += 2) {
            const moveNum = Math.floor(i / 2) + 1;
            const wMove = history[i];
            const bMove = history[i + 1];

            const wSelected = (this.viewedHistoryIndex === i || (isLive && i === history.length - 1)) ? 'selected-move' : '';
            const bSelected = (this.viewedHistoryIndex === i + 1 || (isLive && i + 1 === history.length - 1)) ? 'selected-move' : '';

            const wHtml = wMove ? `<span class="move-btn ${wSelected}" data-index="${i}">${wMove.san}</span>` : '';
            const bHtml = bMove ? `<span class="move-btn ${bSelected}" data-index="${i + 1}">${bMove.san}</span>` : '';

            html += `
                <div class="history-row">
                    <span>${moveNum}.</span>
                    <span>${wHtml}</span>
                    <span>${bHtml}</span>
                </div>
            `;
        }

        this.moveHistoryElement.innerHTML = html;

        const activeBtn = this.moveHistoryElement.querySelector('.selected-move');
        if (activeBtn) {
            activeBtn.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
            this.moveHistoryElement.scrollTop = this.moveHistoryElement.scrollHeight;
        }

        this.moveHistoryElement.querySelectorAll('.move-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.getAttribute('data-index'));
                this.navigateHistory(idx);
            });
        });
    }

    navigateHistory(index) {
        const total = this.currentGameState && this.currentGameState.history ? this.currentGameState.history.length : 0;
        
        if (total === 0 || index === null || index >= total - 1) {
            this.viewedHistoryIndex = null;
        } else if (index < -1) {
            this.viewedHistoryIndex = -1;
        } else {
            this.viewedHistoryIndex = index;
        }

        this.selectedSquare = null;
        this.legalDestinations = [];
        this.renderBoard();
        this.updateStatusUI();
        this.updateHistoryUI();
        this.updatePreviousMoveUIInstant();
        this.clearSuggestionUI();
        this.scheduleRefreshAnalysis(50);
    }

    navigateStep(delta) {
        const total = this.currentGameState && this.currentGameState.history ? this.currentGameState.history.length : 0;
        if (total === 0) return;

        let currentIndex = (this.viewedHistoryIndex === null) ? total - 1 : this.viewedHistoryIndex;
        let newIndex = currentIndex + delta;

        if (newIndex >= total - 1) {
            this.navigateHistory(null);
        } else if (newIndex < -1) {
            this.navigateHistory(-1);
        } else {
            this.navigateHistory(newIndex);
        }
    }

    updateNavIndicatorUI() {
        if (!this.navStepIndicator) return;
        const total = this.currentGameState && this.currentGameState.history ? this.currentGameState.history.length : 0;
        if (total === 0) {
            this.navStepIndicator.textContent = "Posición inicial";
        } else if (this.viewedHistoryIndex === null) {
            this.navStepIndicator.textContent = `Jugada #${total} (Última)`;
        } else if (this.viewedHistoryIndex === -1) {
            this.navStepIndicator.textContent = "Posición inicial";
        } else {
            this.navStepIndicator.textContent = `Jugada #${this.viewedHistoryIndex + 1} / ${total}`;
        }

        const isAtStart = total === 0 || this.viewedHistoryIndex === -1;
        const isAtEnd = total === 0 || this.viewedHistoryIndex === null;

        if (this.btnNavFirst) this.btnNavFirst.disabled = isAtStart;
        if (this.btnNavPrev) this.btnNavPrev.disabled = isAtStart;
        if (this.btnNavNext) this.btnNavNext.disabled = isAtEnd;
        if (this.btnNavLast) this.btnNavLast.disabled = isAtEnd;
    }

    copyPgnToClipboard() {
        if (!this.currentGameState || !this.currentGameState.history || this.currentGameState.history.length === 0) {
            alert("No hay movimientos en el historial para copiar.");
            return;
        }

        const history = this.currentGameState.history;
        let pgnLines = [];
        for (let i = 0; i < history.length; i += 2) {
            const num = Math.floor(i / 2) + 1;
            const w = history[i] ? history[i].san : '';
            const b = history[i + 1] ? history[i + 1].san : '';
            pgnLines.push(`${num}. ${w} ${b}`.trim());
        }

        const pgnText = pgnLines.join(' ');
        navigator.clipboard.writeText(pgnText).then(() => {
            this.showToast("¡Historial copiado al portapapeles!");
        }).catch(err => {
            console.error("Error al copiar al portapapeles:", err);
        });
    }

    getCurrentFEN() {
        if (this.viewedHistoryIndex !== null && this.currentGameState && this.currentGameState.history) {
            if (this.viewedHistoryIndex === -1) {
                return "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
            }
            if (this.viewedHistoryIndex >= 0 && this.viewedHistoryIndex < this.currentGameState.history.length) {
                const hMove = this.currentGameState.history[this.viewedHistoryIndex];
                if (hMove.fen_after) return hMove.fen_after;
            }
        }

        if (this.viewedHistoryIndex === null && this.currentGameState && this.currentGameState.history && this.currentGameState.history.length > 0) {
            const lastMove = this.currentGameState.history[this.currentGameState.history.length - 1];
            if (lastMove.fen_after) return lastMove.fen_after;
        }

        return this.generateFenFromGrid();
    }

    generateFenFromGrid() {
        const grid = this.getActiveGrid();
        if (!grid || grid.length === 0) {
            return "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
        }

        let fenRows = [];
        for (let r = 0; r < 8; r++) {
            let rowStr = "";
            let emptyCount = 0;
            for (let f = 0; f < 8; f++) {
                const cell = grid[r][f];
                if (cell && cell.type && cell.color) {
                    if (emptyCount > 0) {
                        rowStr += emptyCount;
                        emptyCount = 0;
                    }
                    const char = cell.type.toLowerCase();
                    rowStr += (cell.color === 'white') ? char.toUpperCase() : char;
                } else {
                    emptyCount++;
                }
            }
            if (emptyCount > 0) {
                rowStr += emptyCount;
            }
            fenRows.push(rowStr);
        }

        const positionPart = fenRows.join('/');
        const turnPart = (this.getActiveTurn() === 'white') ? 'w' : 'b';
        
        let castling = "";
        if (grid[7] && grid[7][4] && grid[7][4].type === 'k' && grid[7][4].color === 'white') {
            if (grid[7][7] && grid[7][7].type === 'r' && grid[7][7].color === 'white') castling += "K";
            if (grid[7][0] && grid[7][0].type === 'r' && grid[7][0].color === 'white') castling += "Q";
        }
        if (grid[0] && grid[0][4] && grid[0][4].type === 'k' && grid[0][4].color === 'black') {
            if (grid[0][7] && grid[0][7].type === 'r' && grid[0][7].color === 'black') castling += "k";
            if (grid[0][0] && grid[0][0].type === 'r' && grid[0][0].color === 'black') castling += "q";
        }
        if (!castling) castling = "-";

        const totalMoves = (this.currentGameState && this.currentGameState.history) ? this.currentGameState.history.length : 0;
        const moveNumber = (this.viewedHistoryIndex !== null) ? Math.max(1, Math.floor((this.viewedHistoryIndex + 1) / 2) + 1) : Math.floor(totalMoves / 2) + 1;

        return `${positionPart} ${turnPart} ${castling} - 0 ${moveNumber}`;
    }

    copyFenToClipboard() {
        const fenText = this.getCurrentFEN();
        if (!fenText) {
            alert("No se pudo obtener el código FEN.");
            return;
        }

        navigator.clipboard.writeText(fenText).then(() => {
            this.showToast("¡Código FEN copiado al portapapeles!");
        }).catch(err => {
            console.error("Error al copiar FEN al portapapeles:", err);
            prompt("Código FEN de la posición actual:", fenText);
        });
    }

    copyExplanationsToClipboard() {
        if (!this.currentGameState || !this.currentGameState.history || this.currentGameState.history.length === 0) {
            alert("No hay movimientos en el historial para copiar.");
            return;
        }

        const history = this.currentGameState.history;
        const depth = this.analysisDepthSelect ? this.analysisDepthSelect.value : 2;
        const strategy = this.analysisStrategySelect ? this.analysisStrategySelect.value : 'tactico';
        const engineVersion = this.engineVersionSelect ? this.engineVersionSelect.value : 'minimax2';
        const treeMode = this.getTreeMode();
        const timeLimit = this.getTimeLimit();
        const gameMode = this.gameModeSelect ? this.gameModeSelect.value : 'pvp';
        const playerColor = this.colorSelect ? this.colorSelect.value : 'white';
        const kingZoneFilterElement = document.getElementById('king-zone-filter-select');
        const kingZoneFilter = kingZoneFilterElement ? (kingZoneFilterElement.value === 'true' ? 'ON' : 'OFF') : 'ON';

        let lines = [];
        lines.push("=== REPORTE DE PARTIDA Y EXPLICACIONES DEL MOTOR ===");
        lines.push(`Modo de Juego: ${gameMode.toUpperCase()} | Color Jugador: ${playerColor.toUpperCase()}`);
        const engineFlags = this.getEngineConfig();
        const flagsOn = Object.keys(engineFlags).filter(k => engineFlags[k]);
        const flagsOff = Object.keys(engineFlags).filter(k => !engineFlags[k]);
        lines.push(`Configuración del Motor: Engine=${engineVersion} | Depth=${depth} | Estrategia=${strategy} | Modo Árbol=${treeMode} | Radar Bitboard=${kingZoneFilter}`);
        lines.push(`Técnicas ON (${flagsOn.length}: ${flagsOn.join(', ')})`);
        lines.push(`Técnicas OFF (${flagsOff.length}: ${flagsOff.length > 0 ? flagsOff.join(', ') : 'ninguna'});`);
        lines.push("====================================================");
        lines.push("");

        for (let i = 0; i < history.length; i++) {
            const moveNum = Math.floor(i / 2) + 1;
            const item = history[i];
            const moverColor = (i % 2 === 0) ? "Blancas" : "Negras";
            const san = item.san || item.uci || "";
            const cat = item.category || item.type || "movimiento";
            const exp = item.explanation || "Turno Humano / Movimiento ejecutado.";
            const timeStr = (typeof item.time_seconds === 'number') ? ` | Tiempo: ${item.time_seconds}s` : "";

            lines.push(`${moveNum}. (${moverColor}) ${san} [${cat}]${timeStr}`);
            lines.push(`   Explicación: ${exp}`);
            lines.push("");
        }

        const reportText = lines.join("\n");
        navigator.clipboard.writeText(reportText).then(() => {
            this.showToast("¡Historial con explicaciones copiado al portapapeles!");
        }).catch(err => {
            console.error("Error al copiar explicaciones al portapapeles:", err);
        });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.chessUI = new ChessBoardUI();
    });
} else {
    window.chessUI = new ChessBoardUI();
}
