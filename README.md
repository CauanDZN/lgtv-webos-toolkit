# LG webOS: limpeza possível + launcher próprio

Kit pra tirar o máximo de privacidade/anúncio possível de uma LG webOS **sem** desbloquear a TV
(sem ADB, sem `pm disable-user` — isso não existe em webOS), e instalar por cima um launcher
estilo Apple TV. Nada aqui desativa ou apaga app da TV: a "limpeza" é por menu e DNS, e o launcher
é só mais um app, removível a qualquer momento.

| Arquivo | Pra quê |
|---|---|
| `backup.py` | Foto do estado atual da TV (firmware, apps, entradas, ajustes). Só lê, nunca escreve. |
| `install.py` | Empacota e instala o launcher — equivalente Windows do `install.sh` original (que só roda em macOS). |
| `test_fake_tv.py` | Testa `backup.py` e `install.py` contra uma TV simulada, sem precisar de hardware. |
| `install-home-watch-task.ps1` | Registra `home-watch.py` (do submódulo abaixo) como tarefa agendada do Windows, pra reabrir o launcher sozinho se cair. |
| `webos-vibehack/` (submódulo) | O launcher em si — fork de [OmkarK97/webos-vibehack](https://github.com/OmkarK97/webos-vibehack), fixado no commit `31a518a` que foi revisado aqui: só fala com a TV na rede local, sem telemetria, sem `eval`. |

## Clonar

```
git clone --recurse-submodules https://github.com/CauanDZN/lgtv-webos-toolkit.git
```
(esqueceu `--recurse-submodules`? `git submodule update --init`)

## Passo 0: gravar o estado atual (antes de mexer em qualquer coisa)

```
pip install websockets pillow
python backup.py 192.168.10.XXX
```
Aparece um aviso na TV pedindo pareamento — aceite com o controle. Fica salvo em
`backup/<data-hora>/`. Anote também, antes do Passo 1, o valor atual de cada opção que for mudar.

## Passo 1: ajustes de privacidade e anúncios (menus da TV)

Os nomes mudam conforme versão/idioma do webOS. Procurar em
Configurações → Todas as configurações → Geral → Sistema → Configurações adicionais (e na Home):

- Live Plus / reconhecimento automático de conteúdo (ACR): **desligar**
- Anúncios personalizados / "Limitar rastreamento de anúncios": **ligar o limite**
- Promoção na tela inicial / recomendações: **desligar**
- Coleta de dados de uso / informações de visualização: **desligar**
- Atualizações automáticas: deixe como está (é segurança, não é anúncio)

## Passo 2: DNS bloqueador de anúncios

TV → Rede → Wi-Fi → sua rede → Editar → DNS manual: primário `94.140.14.14`, secundário
`94.140.15.15` (AdGuard DNS). Não bloqueia anúncio do YouTube. Teste se Netflix/YouTube ainda tocam
depois. Alternativa pra casa toda: o mesmo DNS no roteador.

## Passo 3: launcher estilo Apple TV

Na TV:
1. Conta grátis em webostv.developer.lge.com, instalar o app **Developer Mode** pela LG Content Store.
2. Abrir o app, ligar **Dev Mode Status** (a TV reinicia) e depois **Key Server**.
3. Ele mostra IP e uma chave (passphrase) — **não salve essa chave em arquivo nem em chat**.

No PC (Node.js + Python):
```
npm i -g @webos-tools/cli
ares-setup-device -a lgtv -i "host=192.168.10.XXX" -i "port=9922" -i "username=prisoner"
ares-novacom --device lgtv --getkey
ares-setup-device -m lgtv -i "privatekey=lgtv_webos" -i "passphrase=<chave da TV>"
```
Escolha o dock em `webos-vibehack/app/config.js` (padrão: `netflix, amazon, youtube, hotstar` — troque
pelos seus; ids com `python webos-vibehack/sync-apps.py 192.168.10.XXX --list`).

```
python install.py --host 192.168.10.XXX --dry-run     # só mostra os comandos
python install.py --host 192.168.10.XXX               # instala e abre
```

Pro botão Home abrir o launcher, webOS exige um "vigia" rodando em outro aparelho na mesma rede:
```
python webos-vibehack/home-watch.py 192.168.10.XXX
```
Se for o seu PC, só funciona com ele ligado — pra isso existe o `install-home-watch-task.ps1`
(Windows), que registra isso como tarefa agendada:
```
.\install-home-watch-task.ps1 -TvHost 192.168.10.XXX
```
Apertar Home duas vezes em 3s mantém a home original da LG. Rode `install.py` de novo depois de
instalar/remover apps da TV.

**Para desfazer:** `ares-install -d lgtv -r com.gathin.tvhome` (remove só o launcher), ou apague o
app Developer Mode (remove tudo, inclusive a porta SSH que ele abre). Desligue Key Server e Dev
Mode quando não for mais instalar nada.

## Passo 4: root

Não feito aqui. Depende do firmware exato, pode inutilizar a TV e muda a garantia — fora do escopo
deste kit.

## Testes

```
python3 test_fake_tv.py
```
`backup.py` e `install.py` contra uma TV simulada (WebSocket + servidor HTTP falsos) — não precisa
de TV real nem rede.

**Não testado:** os comandos `ares-*` de verdade contra hardware — isso só confirma na sua TV.

## Créditos

O launcher em `webos-vibehack/` é trabalho de [OmkarK97](https://github.com/OmkarK97) e
[Gathin](https://github.com/Gathin23) (design/layout originais do
[tv-vibehack](https://github.com/Gathin23/tv-vibehack) pra Android TV) — veja a licença MIT dele
no próprio submódulo. Os scripts deste repositório (`backup.py`, `install.py`, `test_fake_tv.py`,
`install-home-watch-task.ps1`) são meus.
