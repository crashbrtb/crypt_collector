"""Textos da interface e do log, em português e inglês."""

_language = "pt"
_ORDER = ("pt", "en")

# chave: (português, inglês)
TEXTS = {
    # ------------------------------------------------------------- aplicativo
    "app.title": ("Crypt Collector", "Crypt Collector"),
    "app.network": ("pela rede do jogo, sem cliques na tela", "through the game network, no screen clicks"),
    "app.busy": ("Há uma execução em andamento. Pare antes.", "A run is in progress. Stop it first."),
    "app.confirm_close": ("Há uma execução em andamento. Parar e fechar?", "A run is in progress. Stop and close?"),
    "app.restart_language": ("O idioma muda ao abrir o aplicativo de novo.",
                             "The language changes the next time the app opens."),

    "tab.run": ("Execução", "Execution"),
    "tab.lanes": ("Capitães e criptas", "Captains and crypts"),
    "tab.combine": ("Combinar", "Combine"),
    "tab.parameters": ("Parâmetros", "Parameters"),

    "kind.common": ("Comum", "Common"),
    "kind.rare": ("Rara", "Rare"),
    "kind.epic": ("Épica", "Epic"),
    "kind.abandoned": ("Abandonada", "Abandoned"),
    "kind.th_common": ("Caça ao tesouro", "Treasure hunt"),
    "kind.th_rare": ("Caça ao tesouro rara", "Rare treasure hunt"),
    "kind.th_epic": ("Caça ao tesouro épica", "Epic treasure hunt"),

    # ---------------------------------------------------------------- execução
    "run.open_game": ("1 · Abrir jogo no Chrome", "1 · Open game in Chrome"),
    "run.connect": ("2 · Conectar", "2 · Connect"),
    "run.start": ("▶ Iniciar", "▶ Start"),
    "run.stop": ("■ Parar", "■ Stop"),
    "run.logs": ("📂 Logs", "📂 Logs"),
    "run.not_connected": ("Não conectado. Abra o jogo, faça o login e clique em Conectar.",
                          "Not connected. Open the game, log in and click Connect."),
    "run.connected": ("Conectado · cidade em {pos} · {caps} capitães, {home} em casa",
                      "Connected · city at {pos} · {caps} captains, {home} at home"),
    "run.keys": ("Chaves", "Keys"),
    "run.hint": (
        "Tudo é feito pela rede, de dentro da aba do jogo: o Chrome pode ficar atrás de outras janelas e o mouse "
        "fica livre. Se o jogo travar, a página é recarregada (F5) e, se não voltar, o Chrome é reiniciado. "
        "Para parar: ■ Parar ou segure Esc.",
        "Everything goes through the network, from inside the game tab: Chrome can stay behind other windows "
        "and the mouse stays free. If the game freezes the page is reloaded (F5) and, if it does not come back, "
        "Chrome is restarted. To stop: ■ Stop or hold Esc."),

    # --------------------------------------------------------- capitães/criptas
    "presets.label": ("Seleção salva:", "Saved selection:"),
    "presets.load": ("Carregar", "Load"),
    "presets.save": ("💾 Salvar", "💾 Save"),
    "presets.delete": ("Excluir", "Delete"),
    "presets.ask_name": ("Nome da seleção:", "Selection name:"),
    "presets.saved": ("Seleção \"{name}\" salva (capitães, criptas, armaduras e artefatos).",
                      "Selection \"{name}\" saved (captains, crypts, armour and artifacts)."),
    "presets.loaded": ("Seleção \"{name}\" carregada.", "Selection \"{name}\" loaded."),
    "presets.confirm_delete": ("Excluir a seleção \"{name}\"?", "Delete the selection \"{name}\"?"),
    "lanes.search": ("🔍 Procurar no mapa", "🔍 Search the map"),
    "lanes.hint": (
        "Até 3 capitães. Cada um faz uma família e um nível de cripta (ex. Épica 35): marque uma ou mais "
        "imagens desse nível. Vários capitães podem fazer o mesmo tipo; nunca vão à mesma cripta. Quantidade 0 = "
        "sem limite. Embaixo de cada imagem: quantas há por perto e a distância da mais perto.",
        "Up to 3 captains. Each one does one crypt family and level (e.g. Epic 35): mark one or more images of "
        "that level. Several captains may do the same type; they never go to the same crypt. Quantity 0 = no "
        "limit. Under each image: how many are nearby and the distance of the closest."),
    "lanes.captain": ("Capitão", "Captain"),
    "lanes.kind": ("Cripta:", "Crypt:"),
    "lanes.level": ("Nível:", "Level:"),
    "lanes.quantity": ("Qtd.:", "Qty:"),
    "lanes.gear": ("🛡 Equipamento", "🛡 Equipment"),
    "lanes.all": ("Todas", "All"),
    "lanes.none": ("Nenhuma", "None"),
    "lanes.loading": ("Carregando os dados do jogo (a primeira vez demora uns 2 minutos)...",
                      "Loading the game data (the first time takes about 2 minutes)..."),
    "lanes.fallback": ("Sem alcatrão/chave:", "Out of tar/keys:"),
    "lanes.fallback.stop": ("parar", "stop"),
    "lanes.fallback.help": ("ajudar o capitão {n}", "help captain {n}"),
    "lanes.captain_taken": ("Esse capitão já está na faixa {n}.", "That captain is already in lane {n}."),

    # ------------------------------------------------------------ equipamento
    "gear.title": ("Equipamento", "Equipment"),
    "gear.slot": ("Armadura", "Armour"),
    "gear.artifact": ("Artefato", "Artifact"),
    "gear.empty": ("(não mexer)", "(leave as is)"),
    "gear.hint": ("Clique num espaço e dê dois cliques numa peça da lista. Botão direito esvazia o espaço. "
                  "Espaço vazio não é mexido. Antes da primeira cripta o capitão veste o que estiver aqui.",
                  "Click a slot and double-click a piece in the list. Right click empties the slot. An empty "
                  "slot is left as it is. Before the first crypt the captain wears what is set here."),
    "gear.copy": ("Copiar do jogo", "Copy from game"),
    "gear.clear": ("Limpar", "Clear"),
    "gear.ok": ("OK", "OK"),
    "gear.filter": ("Filtrar por nome...", "Filter by name..."),
    "gear.durability": ("durab.", "dur."),
    "gear.in_lane": ("na faixa {n}", "in lane {n}"),
    "gear.hero": ("Herói", "Hero"),
    "gear.worn_here": ("vestida nele", "worn by this captain"),
    "gear.need_connect": ("Conecte ao jogo primeiro (aba Execução).", "Connect to the game first (Execution tab)."),
    "gear.need_captain": ("Escolha o capitão da faixa primeiro.", "Choose the lane's captain first."),

    # -------------------------------------------------------------- situação
    "status.off": ("desligada", "off"),
    "status.away": ("capitão fora, aguardando voltar", "captain away, waiting for him"),
    "status.done": ("concluída", "done"),
    "status.no_crypt": ("nenhuma cripta livre por perto; procurando de novo", "no free crypt nearby; searching again"),
    "status.helping": ("ajudando o capitão {n}", "helping captain {n}"),
    "status.no_supply": ("sem alcatrão ou chave", "out of tar or keys"),
    "status.no_key": ("sem chave", "no key"),
    "status.no_tar": ("sem alcatrão", "no tar"),
    "status.marching": ("explorando {pos}", "exploring {pos}"),
    "status.slow": ("marcha demorando", "march taking long"),
    "status.stopped_errors": ("parada por erros", "stopped after errors"),

    # ------------------------------------------------------------------- erros
    "err.same_captain": ("{name} está em mais de uma faixa.", "{name} is in more than one lane."),
    "err.no_types": ("Faixa {lane}: marque pelo menos uma imagem de cripta.",
                     "Lane {lane}: mark at least one crypt image."),
    "err.no_lanes": ("Nenhuma faixa ativa com capitão. Configure na aba Capitães e criptas.",
                     "No active lane with a captain. Set it up in the Captains and crypts tab."),
    "err.gear_conflict": ("A mesma peça ou o mesmo artefato está em mais de um capitão.",
                          "The same piece or artifact is set for more than one captain."),
    "err.captain_missing": ("{name} não está nesta conta.", "{name} is not in this account."),
    "err.unrecoverable": ("O jogo não voltou depois de várias tentativas. Execução parada.",
                          "The game did not come back after several attempts. Run stopped."),

    # --------------------------------------------------------------------- log
    "log.loading_catalog": ("Carregando os dados do jogo (criptas, capitães, imagens)...",
                            "Loading the game data (crypts, captains, images)..."),
    "log.catalog_ready": ("Dados do jogo prontos: {n} tipos de cripta.", "Game data ready: {n} crypt types."),
    "log.browser_launched": ("Chrome aberto. Faça o login no jogo e espere o mapa carregar.",
                             "Chrome opened. Log in to the game and wait for the map to load."),
    "log.browser_ready": ("O Chrome com o jogo já estava aberto.", "The Chrome with the game was already open."),
    "log.connecting": ("Conectando à aba do jogo...", "Connecting to the game tab..."),
    "log.connected": ("Conectado ao jogo.", "Connected to the game."),
    "log.search_done": ("{n} criptas dos tipos escolhidos num raio de {r}.",
                        "{n} crypts of the chosen types within {r}."),
    "log.types": ("tipo(s)", "type(s)"),
    "log.quantity": ("qtd.", "qty"),
    "log.gear_applied": ("{n} troca(s) de equipamento", "{n} equipment change(s)"),
    "log.someone_going": ("cripta {pos} já tem marcha a caminho; fica de fora",
                          "crypt {pos} already has a march on the way; skipped"),
    "log.slot": ("{name} na posição {pos} da lista de capitães", "{name} in position {pos} of the captain list"),
    "log.slot_out": ("no lugar de {name}", "replacing {name}"),
    "log.no_slot": ("não há posição livre na lista de 3 capitães (os outros estão fora)",
                    "no free position in the 3-captain list (the others are away)"),
    "log.opened": ("cripta rara aberta com a chave", "rare crypt opened with the key"),
    "log.no_key": ("sem {name} para abrir a cripta rara", "no {name} to open the rare crypt"),
    "log.no_tar": ("{name} insuficiente: precisa {need}, tem {have}", "not enough {name}: needs {need}, has {have}"),
    "log.no_speedups": ("acabaram as acelerações de marcha", "out of march speedups"),
    "log.slow": ("a marcha já leva {s} s", "the march has taken {s} s"),
    "log.crypt_done": ("cripta concluída", "crypt done"),
    "log.partial": ("a cripta ficou com {left} de saúde (alcatrão a menos); o próximo envio leva mais",
                    "the crypt was left with {left} health (not enough tar); the next march carries more"),
    "log.taken": ("a cripta acabou antes da chegada (outro jogador)", "the crypt ended before arrival (another player)"),
    "log.helping": ("passa a ajudar o capitão {n} ({name}) nas criptas {kind} {level}",
                    "now helping captain {n} ({name}) with {kind} {level} crypts"),
    "log.help_done": ("o capitão {n} terminou; ajuda concluída", "captain {n} is done; help finished"),
    "log.lane_no_supply": ("faixa parada", "lane stopped"),
    "log.lane_done": ("concluída: {n} cripta(s)", "done: {n} crypt(s)"),
    "log.lane_stopped": ("faixa parada depois de vários erros seguidos", "lane stopped after several errors in a row"),
    "log.tab_lost": ("a conexão com a aba do jogo caiu", "the connection to the game tab was lost"),
    "log.frozen": ("o jogo está há {s} s sem falar com o servidor (travado?)",
                   "the game has not talked to the server for {s} s (frozen?)"),
    "log.recovering": ("⚠ {reason}. Recuperando o jogo...", "⚠ {reason}. Recovering the game..."),
    "log.reloaded": ("Página recarregada (F5); esperando o jogo voltar...",
                     "Page reloaded (F5); waiting for the game to come back..."),
    "log.restarting": ("O jogo não voltou com F5: reiniciando o Chrome...",
                       "The game did not come back with F5: restarting Chrome..."),
    "log.recovered": ("Jogo de volta; continuando as criptas.", "Game is back; resuming the crypts."),
    "log.recover_failed": ("recuperação ({step}) falhou: {err}", "recovery ({step}) failed: {err}"),
    "log.recover_wait": ("Nova tentativa de recuperar em 60 s.", "Trying to recover again in 60 s."),
    "log.finished": ("Execução terminada.", "Run finished."),
    "log.cancelled": ("Execução interrompida.", "Run stopped."),
    "log.stopping": ("Parando...", "Stopping..."),
    "log.crypts": ("criptas", "crypts"),
    "log.tar": ("de alcatrão", "tar"),
    "log.speedups": ("acelerações", "speedups"),
    "log.keys": ("chaves", "keys"),

    # ---------------------------------------------------------------- combinar
    "combine.title": ("Combinar", "Combine"),
    "combine.cat.materiais": ("Materiais", "Materials"),
    "combine.cat.gemas": ("Gemas", "Gems"),
    "combine.cat.encantamentos": ("Encantamentos", "Enchantments"),
    "combine.filter": ("Filtrar por nome...", "Filter by name..."),
    "combine.only_stock": ("Só com estoque", "Only with stock"),
    "combine.refresh": ("🔄 Ler estoque", "🔄 Read stock"),
    "combine.level": ("Até o nível:", "Up to level:"),
    "combine.quantity": ("Quantidade:", "Quantity:"),
    "combine.gamble": ("Tentar além do garantido (bônus)", "Try beyond the guaranteed (bonus)"),
    "combine.start": ("⚗ Combinar", "⚗ Combine"),
    "combine.hint": (
        "Selecione um ou mais itens (Ctrl/Shift + clique). Cada combinação gasta 4 do nível e dá 1 do seguinte; "
        "às vezes vem 1 de bônus. Quantidade: itens no nível escolhido, ou max = o total que o estoque garante (coluna Total possível). Só gasta o "
        "necessário, de cima para baixo. \"Tentar além\" evolui o resto de baixo para cima contando com os bônus. "
        "Os itens selecionados combinam em paralelo e não interferem nas criptas.",
        "Select one or more items (Ctrl/Shift + click). Each combination spends 4 of a level and gives 1 of the "
        "next; sometimes 1 extra comes as a bonus. Quantity: items at the chosen level, or max = the total the stock "
        "guarantees. Only what is needed is spent, top down. \"Try beyond\" evolves the rest bottom up counting on "
        "bonuses. Selected items combine in parallel and do not interfere with the crypts."),
    "combine.col.item": ("Item", "Item"),
    "combine.col.level": ("Nv", "Lv"),
    "combine.col.guaranteed": ("Total possível", "Total possible"),
    "combine.need_refresh": ("Clique em \"Ler estoque\" com o jogo aberto.", "Click \"Read stock\" with the game open."),
    "combine.reading": ("Lendo o estoque...", "Reading the stock..."),
    "combine.ready": ("Estoque atualizado.", "Stock updated."),
    "combine.running": ("Combinando... (o andamento aparece no log da aba Execução)",
                        "Combining... (progress shows in the Execution tab log)"),
    "combine.stopped": ("Combinação interrompida.", "Combination stopped."),
    "combine.select": ("Selecione pelo menos um item na lista.", "Select at least one item in the list."),
    "combine.bad_qty": ("Quantidade: um número ou max.", "Quantity: a number or max."),
    "combine.confirm": ("Combinar {n} item(ns) até o nível {level}, quantidade {qty}?\n\n{items}",
                        "Combine {n} item(s) up to level {level}, quantity {qty}?\n\n{items}"),
    "combine.log_start": ("Combinando {n} item(ns) até o nível {level}...",
                          "Combining {n} item(s) up to level {level}..."),
    "combine.log_done": ("Combinação terminada.", "Combination finished."),

    # -------------------------------------------------------------- parâmetros
    "params.intro": ("Ajustes da execução e do navegador.", "Execution and browser settings."),
    "params.save": ("💾 Salvar parâmetros", "💾 Save parameters"),
    "params.saved": ("Parâmetros salvos.", "Parameters saved."),
    "params.invalid": ("Valores inválidos: {fields}", "Invalid values: {fields}"),
    "choice.spyglass": ("Luneta (busca do jogo)", "Spyglass (game search)"),
    "choice.scan": ("Varredura do mapa (blocos)", "Map scan (blocks)"),

    "param.run.search_mode": ("Como achar as criptas", "How to find crypts"),
    "param.run.search_mode.help": (
        "Luneta: a mesma busca da luneta do jogo, por tipo, num raio. Varredura: lê os blocos do mapa em volta "
        "da cidade (até 200).",
        "Spyglass: the game's own spyglass search, by type, within a radius. Scan: reads the map blocks around "
        "the city (up to 200)."),
    "param.run.search_radius": ("Raio da busca", "Search radius"),
    "param.run.search_radius.help": ("Distância máxima da cidade. A mais perto é sempre a escolhida.",
                                     "Maximum distance from the city. The closest one is always chosen."),
    "param.run.search_every": ("Buscar de novo a cada (s)", "Search again every (s)"),
    "param.run.search_every.help": ("Intervalo entre buscas no mapa.", "Interval between map searches."),
    "param.run.check_marches": ("Conferir marchas a caminho", "Check marches on the way"),
    "param.run.check_marches.help": (
        "Antes de mandar, lê o bloco do mapa da cripta: se houver marcha de alguém indo para ela, ela fica de fora.",
        "Before sending, reads the crypt's map block: if someone's march is heading to it, it is skipped."),
    "param.run.min_time_left": ("Validade mínima da cripta (s)", "Minimum crypt time left (s)"),
    "param.run.min_time_left.help": ("Cripta que some antes disso não é escolhida.",
                                     "A crypt that disappears sooner is not chosen."),
    "param.run.speedup": ("Acelerar as marchas", "Speed up marches"),
    "param.run.speedup.help": ("Usa a aceleração de marcha (item 2102) logo depois de mandar.",
                               "Uses the march speedup (item 2102) right after sending."),
    "param.run.speedups_per_march": ("Acelerações por marcha", "Speedups per march"),
    "param.run.speedups_per_march.help": (
        "No máximo. O jogo para de aceitar quando faltam ~20 s para chegar.",
        "At most. The game stops accepting them when ~20 s are left."),
    "param.run.tar_margin": ("Folga de alcatrão", "Tar margin"),
    "param.run.tar_margin.help": (
        "Multiplica o alcatrão calculado pelo dano medido do capitão. O que sobra volta para a cidade.",
        "Multiplies the tar computed from the captain's measured damage. What is left comes back to the city."),
    "param.run.march_timeout": ("Aviso de marcha demorada (s)", "Slow march warning (s)"),
    "param.run.march_timeout.help": ("Só avisa no log.", "Only a warning in the log."),
    "param.run.freeze_seconds": ("Jogo travado depois de (s)", "Game frozen after (s)"),
    "param.run.freeze_seconds.help": (
        "Sem nenhum pedido do jogo ao servidor por esse tempo, a página é recarregada.",
        "With no request from the game to the server for this long, the page is reloaded."),
    "param.run.reload_wait": ("Espera depois do F5 (s)", "Wait after F5 (s)"),
    "param.run.reload_wait.help": ("Se o jogo não voltar nesse tempo, o Chrome é reiniciado.",
                                   "If the game is not back within this time, Chrome is restarted."),
    "param.run.restart_wait": ("Espera depois de reiniciar o Chrome (s)", "Wait after restarting Chrome (s)"),
    "param.run.restart_wait.help": ("Tempo para o jogo abrir e logar sozinho.",
                                    "Time for the game to open and log in by itself."),
    "param.run.max_recoveries": ("Recuperações seguidas", "Recoveries in a row"),
    "param.run.max_recoveries.help": ("Depois disso a execução para.", "After that the run stops."),
    "param.browser.cdp_port": ("Porta CDP", "CDP port"),
    "param.browser.cdp_port.help": ("Porta de depuração do Chrome do jogo.", "Debugging port of the game's Chrome."),
    "param.browser.game_url": ("Endereço do jogo", "Game address"),
    "param.browser.game_url.help": ("Página aberta ao iniciar o Chrome.", "Page opened when Chrome starts."),
    "param.browser.executable_path": ("Navegador", "Browser"),
    "param.browser.executable_path.help": ("Vazio = procura Chrome, Edge ou Brave.",
                                           "Empty = finds Chrome, Edge or Brave."),
    "param.browser.profile_dir": ("Perfil do navegador", "Browser profile"),
    "param.browser.profile_dir.help": (
        "Vazio = browser_profile ao lado do programa. O perfil guarda o login do jogo.",
        "Empty = browser_profile next to the program. The profile keeps the game login."),
}


def set_language(code: str):
    global _language
    if code in _ORDER:
        _language = code


def tr(key: str, **values) -> str:
    pair = TEXTS.get(key)
    if pair is None:
        text = key
    else:
        text = pair[_ORDER.index(_language)]
    if values:
        try:
            text = text.format(**values)
        except (KeyError, IndexError, ValueError):
            pass
    return text
