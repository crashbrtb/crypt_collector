"""Textos da interface e do log, em português e inglês."""

_language = "pt"
_ORDER = ("pt", "en")

# chave: (português, inglês)
TEXTS = {
    # ------------------------------------------------------------- aplicativo
    "app.title": ("Crypt Collector", "Crypt Collector"),
    "app.developed_by": ("Desenvolvido por:", "Developed by:"),
    "app.busy": ("Há uma operação em andamento. Aguarde ela terminar.",
                 "An operation is in progress. Wait for it to finish."),

    "tab.run": ("Execução", "Execution"),
    "tab.crypts": ("Criptas", "Crypts"),
    "tab.parameters": ("Parâmetros", "Parameters"),

    "mode.common": ("Comum", "Common"),
    "mode.epic": ("Épica", "Epic"),
    "mode.rare": ("Rara", "Rare"),
    "mode.any": ("Qualquer", "Any"),

    # ---------------------------------------------------------------- criptas
    "crypts.select_all": ("Selecionar tudo", "Select all"),
    "crypts.clear": ("Limpar", "Clear"),
    "crypts.quantity": ("Qtd. de criptas:", "Crypt quantity:"),
    "crypts.hint": (
        "Escolha o mesmo tipo de cripta que está filtrado no menu Criptas e Arenas do jogo e marque as "
        "imagens das criptas que devem ser exploradas. Em \"Qualquer\", a primeira cripta da lista é "
        "explorada sem conferir a imagem.",
        "Pick the same crypt type that is filtered in the game's Crypts and Arenas menu and mark the "
        "images of the crypts to explore. In \"Any\", the first crypt of the list is explored without "
        "checking its image."),
    "crypts.any_active": ("Modo \"Qualquer\" ativo: explora qualquer cripta da lista.",
                          "\"Any\" mode active: explores any crypt in the list."),
    "crypts.no_images": ("Nenhuma imagem encontrada em {folder}.", "No images found in {folder}."),

    # -------------------------------------------------------------- parâmetros
    "params.intro": ("Ajustes da execução e do navegador.", "Execution and browser settings."),
    "params.save": ("💾 Salvar parâmetros", "💾 Save parameters"),
    "params.saved": ("Parâmetros salvos.", "Parameters saved."),
    "params.invalid": ("Valor inválido em \"{name}\".", "Invalid value in \"{name}\"."),

    "param.run.speedups_per_march": ("Acelerações por marcha", "Speedups per march"),
    "param.run.speedups_per_march.help": (
        "Quantas vezes o botão Usar é clicado em cada marcha.",
        "How many times the Use button is clicked on each march."),
    "param.timing.click_delay": ("Espera após cada clique (s)", "Wait after each click (s)"),
    "param.timing.click_delay.help": (
        "Tempo para o jogo reagir a um clique antes do próximo passo. Aumente se a conexão for lenta.",
        "Time for the game to react to a click before the next step. Increase it on a slow connection."),
    "param.timing.scroll_delta": ("Passo da rolagem", "Scroll step"),
    "param.timing.scroll_delta.help": (
        "Quanto a roda do mouse gira a cada rolagem da lista de criptas (100 = um clique da roda).",
        "How far the mouse wheel turns on each scroll of the crypt list (100 = one wheel notch)."),
    "param.timing.max_scrolls": ("Máximo de rolagens", "Maximum scrolls"),
    "param.timing.max_scrolls.help": (
        "Limite de rolagens por passada na lista, caso o fim dela não seja detectado.",
        "Limit of scrolls per pass over the list, in case its end is not detected."),
    "param.timing.list_passes": ("Passadas na lista", "List passes"),
    "param.timing.list_passes.help": (
        "Quantas vezes a lista é percorrida do início ao fim antes de desistir de achar a cripta.",
        "How many times the list is searched from top to bottom before giving up on finding the crypt."),
    "param.timing.march_timeout": ("Tempo máximo da marcha (s)", "March timeout (s)"),
    "param.timing.march_timeout.help": (
        "Tempo máximo de espera pelo fechamento da tela de aceleração.",
        "Longest wait for the speedup screen to close."),
    "param.vision.match_threshold": ("Limiar de semelhança", "Match threshold"),
    "param.vision.match_threshold.help": (
        "De 0 a 1: o quanto a tela precisa se parecer com a imagem de referência. Diminua (ex.: 0.75) "
        "se as criptas não forem reconhecidas.",
        "From 0 to 1: how closely the screen must resemble the reference image. Lower it (e.g. 0.75) "
        "if crypts are not recognised."),
    "param.browser.cdp_port": ("Porta CDP", "CDP port"),
    "param.browser.cdp_port.help": (
        "Porta de depuração remota do Chrome (--remote-debugging-port).",
        "Chrome's remote debugging port (--remote-debugging-port)."),
    "param.browser.game_url": ("Endereço do jogo", "Game address"),
    "param.browser.game_url.help": ("Página aberta ao iniciar o Chrome.", "Page opened when Chrome starts."),
    "param.browser.executable_path": ("Executável do navegador", "Browser executable"),
    "param.browser.executable_path.help": (
        "Vazio = localizar o Chrome, Edge ou Brave automaticamente.",
        "Empty = locate Chrome, Edge or Brave automatically."),

    # ------------------------------------------------------------------ status
    "status.calibration_missing": ("✖ Calibração incompleta ({count} passo(s) faltando)",
                                   "✖ Calibration incomplete ({count} step(s) missing)"),
    "status.calibration_ok": ("✔ Calibrado em {date} ({width}x{height})",
                              "✔ Calibrated on {date} ({width}x{height})"),
    "status.selection": ("{type} · {count} imagem(ns) selecionada(s)", "{type} · {count} image(s) selected"),
    "status.crypts": ("Criptas: {selection}", "Crypts: {selection}"),
    "status.quantity": ("Quantidade: {count}   ·   acelerações por marcha: {speedups}",
                        "Quantity: {count}   ·   speedups per march: {speedups}"),
    "status.calibration": ("Calibração: {text}", "Calibration: {text}"),
    "status.browser": ("Navegador: porta CDP {port} · {state}", "Browser: CDP port {port} · {state}"),
    "status.connected": ("conectado à aba do jogo", "connected to the game tab"),
    "status.not_connected": ("não conectado", "not connected"),

    # ---------------------------------------------------------------- execução
    "run.btn_open_game": ("1 · Abrir jogo no Chrome", "1 · Open game in Chrome"),
    "run.btn_calibrate": ("2 · Calibrar", "2 · Calibrate"),
    "run.btn_start": ("▶ Iniciar", "▶ Start"),
    "run.btn_running": ("⏳ Executando...", "⏳ Running..."),
    "run.btn_stop": ("■ Parar", "■ Stop"),
    "run.btn_logs": ("Abrir pasta de logs", "Open logs folder"),
    "run.log_title": ("Log da execução", "Execution log"),
    "run.esc_hint": ("Segure ESC para interromper uma execução, de qualquer janela.",
                     "Hold ESC to stop a run, from any window."),

    "run.opened_now": (
        "Chrome aberto. Faça o login no jogo e espere ele carregar antes de calibrar ou iniciar.",
        "Chrome opened. Log in to the game and wait for it to load before calibrating or starting."),
    "run.already_open": ("Navegador já estava aberto: conectado à aba do jogo.",
                         "The browser was already open: connected to the game tab."),
    "run.open_failed": ("Não foi possível abrir o jogo: {error}", "Could not open the game: {error}"),
    "run.game_not_open": (
        "O jogo não foi encontrado. Abra-o com \"1 · Abrir jogo no Chrome\", faça o login e inicie de novo.",
        "The game was not found. Open it with \"1 · Open game in Chrome\", log in and start again."),
    "run.close_wizard": ("Feche a janela de calibração antes de iniciar.",
                         "Close the calibration window before starting."),
    "run.missing_calibration": ("Calibração incompleta. Passos que faltam: {steps}.",
                                "Calibration incomplete. Missing steps: {steps}."),
    "run.no_selection": ("Nenhuma imagem de cripta selecionada na aba Criptas.",
                         "No crypt image selected in the Crypts tab."),
    "run.no_quantity": ("Informe a quantidade de criptas na aba Criptas.",
                        "Enter the crypt quantity in the Crypts tab."),
    "run.viewport_resized": ("Janela do jogo ajustada para o tamanho calibrado ({width}x{height}).",
                             "Game window resized to the calibrated size ({width}x{height})."),
    "run.viewport_rescaled": (
        "A página está em {width}x{height} e a calibração foi feita em {cal_width}x{cal_height}; as "
        "coordenadas serão reescaladas. Recalibre se os cliques caírem no lugar errado.",
        "The page is {width}x{height} and the calibration was made at {cal_width}x{cal_height}; "
        "coordinates will be rescaled. Recalibrate if clicks land in the wrong place."),
    "run.images": ("{count} imagem(ns)", "{count} image(s)"),
    "run.start": ("Iniciando: {target} cripta(s) · {mode}", "Starting: {target} crypt(s) · {mode}"),
    "run.round": ("--- volta {round}/{target} ---", "--- round {round}/{target} ---"),
    "run.progress": ("{done}/{target} criptas exploradas · {failures} erro(s)",
                     "{done}/{target} crypts explored · {failures} error(s)"),
    "run.reconnecting": ("Conexão com o jogo perdida ({error}); reconectando...",
                         "Connection to the game lost ({error}); reconnecting..."),
    "run.too_many_failures": ("{count} voltas seguidas sem sucesso; execução encerrada.",
                              "{count} rounds in a row without success; run stopped."),
    "run.store_closed": ("Loja fechada.", "Store closed."),
    "run.popup_closed": ("Janela aberta fechada.", "Open window closed."),
    "run.any_selected": ("Modo Qualquer: indo para a primeira cripta da lista.",
                         "Any mode: going to the first crypt of the list."),
    "run.crypt_found": ("Cripta encontrada: {name} (semelhança {score:.2f}).",
                        "Crypt found: {name} (similarity {score:.2f})."),
    "run.list_did_not_move": ("A lista de criptas não se moveu com a rolagem.",
                              "The crypt list did not move when scrolled."),
    "run.list_restart": ("Fim da lista; voltando ao início (passada {current}/{total}).",
                         "End of the list; back to the top (pass {current}/{total})."),
    "run.list_exhausted": (
        "Nenhuma das criptas selecionadas apareceu na lista (melhor palpite: {best}, semelhança {score:.2f}).",
        "None of the selected crypts showed up in the list (best guess: {best}, similarity {score:.2f})."),
    "run.search_failed": ("Erro na busca da cripta.", "Crypt search failed."),
    "run.explore_retry": ("Botão Explorar não encontrado; tentando outra posição ({attempt}/{total}).",
                          "Explore button not found; trying another position ({attempt}/{total})."),
    "run.map_located": ("Cripta localizada no mapa em ({x}, {y}) (semelhança {score:.2f}).",
                        "Crypt located on the map at ({x}, {y}) (similarity {score:.2f})."),
    "run.map_learned": ("Aparência da cripta {name} no mapa memorizada.",
                        "Map appearance of crypt {name} memorised."),
    "run.explore_failed": ("Erro na cripta: botão Explorar não encontrado.",
                           "Crypt error: Explore button not found."),
    "run.invading": ("Invadindo a cripta.", "Invading the crypt."),
    "run.speedup_failed": ("Erro ao acelerar a marcha: tela de aceleração não apareceu.",
                           "Speedup error: the speedup screen did not show up."),
    "run.waiting_march": ("Aguardando o fechamento da tela de aceleração...",
                          "Waiting for the speedup screen to close..."),
    "run.march_timeout": ("A tela de aceleração não fechou no tempo limite.",
                          "The speedup screen did not close within the timeout."),
    "run.waiting_return": ("Marcha chegou; aguardando {seconds}s pelo retorno.",
                           "March arrived; waiting {seconds}s for the return."),
    "run.finished": ("--- Execução finalizada: {done}/{target} criptas exploradas, {failures} erro(s) ---",
                     "--- Run finished: {done}/{target} crypts explored, {failures} error(s) ---"),
    "run.cancelled": ("--- Execução interrompida pelo usuário ---", "--- Run stopped by the user ---"),
    "run.stopping": ("Interrupção solicitada; parando no próximo ponto seguro...",
                     "Stop requested; stopping at the next safe point..."),
    "run.unexpected": ("Falha inesperada: {error}", "Unexpected failure: {error}"),

    # -------------------------------------------------------------- assistente
    "wizard.window_title": ("Calibração dos controles do jogo", "Game controls calibration"),
    "wizard.steps": ("Passos", "Steps"),
    "wizard.steps_hint": ("Clique em um passo para refazer só ele.", "Click a step to redo only that one."),
    "wizard.close": ("Fechar", "Close"),
    "wizard.auto_advance": ("Avançar automaticamente\n(faz no jogo o clique marcado)",
                            "Advance automatically\n(performs the marked click in the game)"),
    "wizard.test": ("🔎 Testar este passo", "🔎 Test this step"),
    "wizard.refresh": ("📷 Atualizar captura", "📷 Refresh capture"),
    "wizard.skip": ("Pular", "Skip"),
    "wizard.redo": ("Refazer", "Redo"),
    "wizard.defer_store": ("Deixar a loja para o final", "Leave the store for the end"),
    "wizard.store_deferred": (
        "Os dois passos da loja foram para o fim da calibração. Ao chegar neles, abra a loja no jogo "
        "(ou espere ela abrir) e atualize a captura.",
        "The two store steps were moved to the end of the calibration. When you reach them, open the store "
        "in the game (or wait for it to open) and refresh the capture."),
    "wizard.progress": ("Passo {current} de {total}", "Step {current} of {total}"),
    "wizard.optional": ("opcional", "optional"),
    "wizard.kind_click": ("ponto de clique — será clicado no jogo", "click point — will be clicked in the game"),
    "wizard.kind_button_area": ("área de botão — o centro será clicado no jogo",
                                "button area — its centre will be clicked in the game"),
    "wizard.kind_validation_area": ("área de validação — nada é clicado",
                                    "validation area — nothing is clicked"),
    "wizard.prompt_click": ("Clique sobre a captura, no ponto.", "Click on the capture, at the point."),
    "wizard.prompt_area": ("Arraste sobre a captura para marcar a área (ou clique em dois cantos opostos).",
                           "Drag over the capture to mark the area (or click two opposite corners)."),
    "wizard.already_done": ("Já calibrado — marque de novo para substituir.",
                            "Already calibrated — mark again to replace."),
    "wizard.capturing": ("Capturando a tela do jogo...", "Capturing the game screen..."),
    "wizard.capture_failed": ("✖ Não foi possível capturar: {error}", "✖ Could not capture: {error}"),
    "wizard.capture_empty": ("✖ A captura veio vazia. O jogo está aberto na aba conectada?",
                             "✖ The capture is empty. Is the game open on the connected tab?"),
    "wizard.capture_done": ("Captura de {width}x{height} px.", "Capture of {width}x{height} px."),
    "wizard.capture_first": ("Capture a tela primeiro (botão \"Atualizar captura\").",
                             "Capture the screen first (\"Refresh capture\" button)."),
    "wizard.login_first": (
        "O Chrome foi aberto agora. Faça o login no jogo, espere o mapa carregar e clique em "
        "\"Atualizar captura\" para começar.",
        "Chrome has just been opened. Log in to the game, wait for the map to load and click "
        "\"Refresh capture\" to begin."),
    "wizard.busy": ("Aguarde: o jogo está sendo operado pelo passo anterior.",
                    "Wait: the game is being driven by the previous step."),
    "wizard.point_saved": ("✔ Ponto gravado em {x}, {y}.", "✔ Point saved at {x}, {y}."),
    "wizard.first_corner": ("✔ Primeiro canto em {x}, {y} — agora clique no canto oposto.",
                            "✔ First corner at {x}, {y} — now click the opposite corner."),
    "wizard.area_saved": ("✔ Área de {width}x{height} px gravada.", "✔ Area of {width}x{height} px saved."),
    "wizard.area_too_small": ("✖ A área marcada é pequena demais. Marque de novo.",
                              "✖ The marked area is too small. Mark it again."),
    "wizard.low_contrast": (
        "⚠ Esta área quase não tem detalhe (contraste {contrast:.0f}) e seria \"encontrada\" em qualquer "
        "fundo liso. Marque de novo, pegando o desenho ou o texto do botão.",
        "⚠ This area has almost no detail (contrast {contrast:.0f}) and would be \"found\" on any flat "
        "background. Mark it again, including the button's graphics or text."),
    "wizard.icon_known": ("✔ Ícone reconhecido: {name} (semelhança {score:.2f}, escala {scale:.2f}).",
                          "✔ Icon recognised: {name} (similarity {score:.2f}, scale {scale:.2f})."),
    "wizard.icon_unknown": (
        "⚠ Nenhum ícone de cripta conhecido foi reconhecido nesta área (melhor palpite: {name}, "
        "semelhança {score:.2f}). Confira se a área cobre o ícone da primeira cripta da lista.",
        "⚠ No known crypt icon was recognised in this area (best guess: {name}, similarity {score:.2f}). "
        "Check that the area covers the icon of the first crypt in the list."),
    "wizard.pressing": ("Clicando em \"{title}\" no jogo antes de seguir...",
                        "Clicking \"{title}\" in the game before moving on..."),
    "wizard.press_ok": ("✔ Clique em ({x}, {y}); a tela mudou ({change:.0f}%).",
                        "✔ Clicked ({x}, {y}); the screen changed ({change:.0f}%)."),
    "wizard.press_done": ("✔ Clique em ({x}, {y}) feito.", "✔ Clicked ({x}, {y})."),
    "wizard.press_no_change": (
        "✖ Clique em ({x}, {y}) e a tela NÃO mudou ({change:.1f}%). O jogo continua na tela deste passo: "
        "refaça o passo, ou navegue no jogo e atualize a captura.",
        "✖ Clicked ({x}, {y}) and the screen DID NOT change ({change:.1f}%). The game is still on this "
        "step's screen: redo the step, or navigate in the game and refresh the capture."),
    "wizard.press_failed": ("✖ Não foi possível operar o jogo: {error}", "✖ Could not drive the game: {error}"),
    "wizard.viewport_changed": (
        "a janela do jogo mudou de tamanho depois da captura; refaça este passo",
        "the game window changed size after the capture; redo this step"),
    "wizard.testing": ("Testando...", "Testing..."),
    "wizard.not_calibrated": ("Este passo ainda não foi calibrado.", "This step has not been calibrated yet."),
    "wizard.nothing_to_test": ("Este passo só marca uma área; não há o que testar.",
                               "This step only marks an area; there is nothing to test."),
    "wizard.image_found": ("✔ Imagem encontrada em ({x}, {y}), semelhança {score:.2f}.",
                           "✔ Image found at ({x}, {y}), similarity {score:.2f}."),
    "wizard.image_not_found": (
        "✖ Imagem não encontrada na tela agora (melhor semelhança {score:.2f}). Ela está visível?",
        "✖ Image not found on screen right now (best similarity {score:.2f}). Is it visible?"),
    "wizard.step_cleared": ("Passo apagado. Marque de novo sobre a captura.",
                            "Step cleared. Mark it again on the capture."),
    "wizard.still_missing": ("Ainda faltam passos obrigatórios: {steps}.",
                             "Required steps are still missing: {steps}."),
    "wizard.complete_title": ("Calibração concluída", "Calibration complete"),
    "wizard.complete": ("Todos os passos obrigatórios foram gravados. Pode fechar esta janela.",
                        "All required steps have been saved. You can close this window."),

    # ------------------------------------------------------------------ passos
    "step.watchtower_button.title": ("Torre de vigia", "Watchtower"),
    "step.watchtower_button.text": (
        "Com o jogo no mapa, clique no ícone da LUNETA (torre de vigia), que abre o menu.",
        "With the game on the map, click the SPYGLASS (watchtower) icon that opens the menu."),
    "step.crypts_tab.title": ("Menu Criptas e Arenas", "Crypts and Arenas menu"),
    "step.crypts_tab.text": (
        "Clique na aba CRIPTAS E ARENAS.\n"
        "Antes, deixe o filtro do jogo mostrando só criptas RARAS, no nível desejado, e tenha ao menos "
        "uma chave: assim o botão Abrir também pode ser calibrado.",
        "Click the CRYPTS AND ARENAS tab.\n"
        "Beforehand, set the game's filter to show only RARE crypts, at the level you want, and have at "
        "least one key: that way the Open button can be calibrated too."),
    "step.crypt_icon_area.title": ("Ícone da cripta", "Crypt icon"),
    "step.crypt_icon_area.text": (
        "Marque a área do ÍCONE da PRIMEIRA cripta da lista.\n"
        "É aqui que as imagens das criptas selecionadas são conferidas.",
        "Mark the area of the ICON of the FIRST crypt in the list.\n"
        "This is where the images of the selected crypts are checked."),
    "step.crypt_list_area.title": ("Lista de criptas", "Crypt list"),
    "step.crypt_list_area.text": (
        "Marque a LISTA inteira: do topo da primeira linha até o fim da última linha visível.\n"
        "Com ela, a cripta é procurada em todas as linhas visíveis de uma vez. Sem ela, só na primeira.",
        "Mark the whole LIST: from the top of the first row to the bottom of the last visible row.\n"
        "With it, the crypt is searched for in every visible row at once. Without it, only in the first."),
    "step.go_button.title": ("Botão Ir", "Go button"),
    "step.go_button.text": (
        "Marque a área do botão IR (GO) dessa mesma primeira cripta.\n"
        "O centro da área será clicado e o mapa irá até a cripta.",
        "Mark the area of the GO button of that same first crypt.\n"
        "The centre of the area will be clicked and the map will travel to the crypt."),
    "step.store_marker.title": ("Loja aberta", "Store open"),
    "step.store_marker.text": (
        "A loja costuma abrir sozinha depois do Ir. Com a LOJA aberta, marque uma parte fixa dela, bem rente "
        "(o ícone Bonus Sales, por exemplo). É por essa imagem que a loja é reconhecida. Nada é clicado.\n"
        "Se a loja não abriu, use \"Deixar a loja para o final\".",
        "The store usually opens by itself after Go. With the STORE open, mark a fixed part of it, tightly "
        "(the Bonus Sales icon, for example). The store is recognised by this image. Nothing is clicked.\n"
        "If the store did not open, use \"Leave the store for the end\"."),
    "step.store_close_button.title": ("Fechar loja (X)", "Close store (X)"),
    "step.store_close_button.text": (
        "Marque a área do X que FECHA a loja, bem rente.\n"
        "O centro da área será clicado e a loja fechará. A imagem do X também serve para fechar outras "
        "janelas que fiquem abertas.",
        "Mark the area of the X that CLOSES the store, tightly.\n"
        "The centre of the area will be clicked and the store will close. The image of the X is also used "
        "to close other windows left open."),
    "step.crypt_on_map.title": ("Cripta no mapa", "Crypt on the map"),
    "step.crypt_on_map.text": ("Clique na CRIPTA, no mapa.", "Click the CRYPT, on the map."),
    "step.open_button.title": ("Botão Abrir", "Open button"),
    "step.open_button.text": (
        "Clique no botão ABRIR (OPEN), que as criptas raras mostram antes do Explorar.\n"
        "Pule este passo se a tela já mostra o botão Explorar.",
        "Click the OPEN button, which rare crypts show before Explore.\n"
        "Skip this step if the screen already shows the Explore button."),
    "step.explore_button.title": ("Botão Explorar", "Explore button"),
    "step.explore_button.text": (
        "Marque a área do botão EXPLORAR (EXPLORE), bem rente.\n"
        "A imagem dele confirma que a cripta abriu. O centro da área será clicado e a marcha sairá.",
        "Mark the area of the EXPLORE button, tightly.\n"
        "Its image confirms that the crypt opened. The centre of the area will be clicked and the march "
        "will leave."),
    "step.speedup_button.title": ("Botão Acelerar", "Speed up button"),
    "step.speedup_button.text": ("Clique no botão ACELERAR (SPEED UP) da marcha.",
                                 "Click the march's SPEED UP button."),
    "step.march_icon.title": ("Ícone da marcha", "March icon"),
    "step.march_icon.text": (
        "Marque a área do ícone da marcha (os 3 soldados marchando) na tela de aceleração.\n"
        "A imagem dele confirma que a tela de aceleração está aberta. Nada é clicado.",
        "Mark the area of the march icon (the 3 marching soldiers) on the speedup screen.\n"
        "Its image confirms that the speedup screen is open. Nothing is clicked."),
    "step.use_button.title": ("Botão Usar", "Use button"),
    "step.use_button.text": ("Por último, clique no botão USAR (USE) de uma aceleração.",
                             "Finally, click the USE button of a speedup."),
}


def set_language(code: str):
    global _language
    if code in _ORDER:
        _language = code


def tr(key: str, **values) -> str:
    """O texto da chave no idioma atual; a própria chave quando ela não existe."""
    entry = TEXTS.get(key)
    if entry is None:
        return key
    text = entry[_ORDER.index(_language)]
    return text.format(**values) if values else text
