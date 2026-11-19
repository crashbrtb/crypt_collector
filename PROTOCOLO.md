# Protocolo das criptas (capturado em 18/11/2026, conta Crash, reino 282)

Captura: `captures/rec_20261118_190043_cripta.jsonl` (gravador do Autoattack, `aa_record.py --port 9222`),
uma cripta rara 30 (tipo 3512) e uma épica 35 (tipo 2733) feitas à mão com o Carter (capitão 8).
O formato dos pedidos (MessagePack LE do jogo, sessão, cauda de cursores) é o do Autoattack
(`app/tbcodec.py`, `app/gamelink.py`). Na lista abaixo, "objeto" é o que vai em `build_request`.

## Dados estáticos

- Tabela 7 (objetos do mapa): criptas têm `r[1] == 7`. `r[3]` nome (vector; o inglês separa a família:
  Crypt, Rare Crypt, Epic Crypt, Abandoned Crypt, Treasure Hunt...), `r[5]` JSON `{"icon", "visual"}`
  (ícone no CDN Unity, ex. `trillium_crypt_72`), `r[6][0]` `{69: saúde}`, `r[14][0]` `{chave: 1}` nas raras
  (itens 80..84 Chave do Dragão), `r[15]` nível.
- Itens: 13 Alcatrão (criptas comuns), 28 Alcatrão de carvão, 29 Alcatrão Sangrento (abandonadas), 32 Alcatrão épico, 34 Alcatrão raro,
  69 Saúde da cripta, 2102 aceleração de marcha.

## Achar criptas

| rota | objeto | resposta |
|---|---|---|
| 26001 (luneta) | `[pos_cidade, [raio, [[]], [[]], [tipos], [[True]*7], True], 0, False]` | `[[[[id], tipo, [k,x,y], 1000000], ...]]` |
| 312 (bloco do mapa) | `[[blocos], [0, ...], [], []]` | por bloco `[bloco, versão, hex, ?, objetos, entidades]` |

- Bloco = `(y // 20) * 50 + x // 20` (blocos de 20×20, 50 colunas).
- `entidades` (b[5]): `[[id], tipo, 0, ?, 0, nível, 0, 0, [k,x,y], [dono], ?, ?]` — criptas e monstros.
- `objetos` (b[4]): cidades, marchas... Marcha = tipo 1: `r[1]` `[alvo]`, `r[2]` `[dono]`, `r[11]` capitão,
  `r[17]` origem, `r[18]` destino, `r[19]` estado (7 indo, 5 voltando, 6 parada), `r[21]`/`r[22]` início/fim.
  Uma marcha em movimento aparece no bloco de origem e no de destino: para saber se alguém vai para uma
  cripta basta ler o bloco dela.

## Ficha da cripta (601)

Objeto `[[[[id], 0, 2147483647]]]`. Cripta que sumiu não volta. `rec[1][2]` tipo, `rec[1][4]` quando some,
`rec[1][13]` posição, `rec[5]` `{69: [69, saúde]}`, `rec[25]` explorações já feitas, `rec[32]` fechada (rara
antes de abrir).

A saúde cai com o alcatrão que os capitães levam; várias marchas podem bater na mesma cripta e ela some
quando chega a 0.

## Explorar

| # | rota | objeto | o que é |
|---|---|---|---|
| 1 | 14004 | `[[id_cripta]]` | abre a cripta rara (gasta a chave de `r[14]`); só nas fechadas |
| 2 | 701 | `[7, 1, 0, 0, [cidade], [cidade], [k,x,y], None, [capitão], tipo, None, 0, [], 0, {alcatrão: qtd}, [], 4]` | manda o capitão |
| 3 | 300053 | `[[marcha], [[2102, 1]]]` | acelera; resposta `[uuid, [[2102,1]], n]`, ou `[uuid, [], n]` quando o jogo não usou (faltam ~20 s) |

- `{alcatrão: qtd}`: 34 nas raras, 32 nas épicas, 29 nas abandonadas; comuns levam o "Alcatrão" (item 13; o 28 Alcatrão de carvão não serve).
- O alcatrão que sobra **volta** com o capitão: a marcha na volta (601 da marcha) tem `rec[5]` `{32: [32, sobra]}`.
  Raro: mandou 44.800, voltaram 17.920 (gastou 26.880 em 850.000 de saúde: 31,6 por alcatrão).
  Épico: mandou 53.200, voltaram 11.536 (gastou 41.664 em 1.450.000: 34,8 por alcatrão). O dano por
  alcatrão é do capitão (Carter 34,8 no épico; Cleópatra ~7): o app mede a cada cripta e guarda em
  `config.json` → `tar_learned`.
- Pouco alcatrão não é recusado: a cripta só perde parte da saúde e fica no mapa.
- Só os capitães da lista de 3 da marcha podem ir (`hero 20 not available` fora dela). Troca da lista:
  rota 905 `[[[posição, 0]]]` e `[[[posição, capitão]]]` (Autoattack, 08/11).

## Marcha (601 da marcha)

`rec[1][13]` origem e `rec[1][14]` destino da perna atual (na volta o destino é a cidade), `rec[1][15]`/`[16]`
início e fim da perna. `rec[1][12]` não serve para saber a perna (vale 5 nas duas depois das acelerações).
O capitão na cidade (rec[9] `c[3]`) aponta para a marcha enquanto está fora e volta para a cidade no fim.
Ida + volta com 3 acelerações: ~40 s.

# Evolução de materiais, gemas e encantamentos (18/11/2026)

Captura `captures/rec_20261118_213323_evolucao.jsonl`; gemas e encantamentos conferidos com uma evolução cada.

| rota | objeto | resposta |
|---|---|---|
| 1008 | `[item, 0]` | `[[{item: 4}, {}, 1], [{próximo: 1}, ...], n]`; bônus: `{item: 1, próximo: 1}` |

- Gasta 4 do nível e devolve 1 do nível seguinte; ~14% das vezes devolve também 1 do nível gasto. Não gasta
  mais nada. O "evoluir tudo" do jogo exige premium.
- Tabela 8: `r[1]` categoria (7 materiais, 8 gemas, 9 encantamentos), `r[10]` nível 1..8. Uma cadeia = mesma
  categoria e mesmo nome; o passo entre ids varia (materiais da pena +20, gemas +9/+10, feitiços +9/+100/+1).
- Ferramenta: `app/evolution.py` e `python evoluir.py <materiais|gemas|encantamentos> ...`.
