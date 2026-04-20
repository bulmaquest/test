# BulmaFlix 🎬

Player IPTV desktop para Windows com interface moderna e carregamento sob demanda.

## Como Usar

### Execução direta (Python)

```bat
python main.py
```
As dependências são instaladas automaticamente na primeira execução.

### Gerar o executável (.exe)

Execute o script de build no Windows:

```bat
build.bat
```

O `.exe` será gerado em `dist\BulmaFlix.exe`. Basta copiar para qualquer pasta e executar — sem precisar instalar Python.

## Recursos

- ⚡ **Carregamento sob demanda** — canais são exibidos em lotes de 40; rola para carregar mais
- 🚀 **Download assíncrono** — a lista M3U é baixada em background sem travar a janela
- 🖼️ **Lazy loading de capas** — thumbnails carregam progressivamente em background
- 📺 **Reprodução via VLC / MPV** — detecta o player instalado automaticamente
- 🔍 **Busca e filtro por categoria** — pesquisa em tempo real
- 🚫 **Filtro de canais 24h** — canais de loop/24 horas são removidos automaticamente
- 🎨 **Interface moderna** — tema escuro com `customtkinter`, grid responsivo, hover effects
- 📦 **Auto-instalação de dependências** — roda apenas com Python instalado

## Reprodução de Streams

O BulmaFlix tenta abrir o canal nas seguintes ordens:
1. **VLC Player** (detecta automaticamente em `Program Files`)
2. **MPV** (se estiver no PATH)
3. **Navegador padrão** (fallback)
4. Se nenhum for encontrado, mostra um diálogo para copiar a URL manualmente

> 💡 Recomendado: instale o [VLC Player](https://www.videolan.org/vlc/) para melhor compatibilidade com streams IPTV.

## Requisitos

- Python 3.10+ (para executar via `python main.py`)
- Para o `.exe`: apenas Windows (sem Python necessário)

## Dependências Python

| Pacote          | Uso                                   |
|-----------------|---------------------------------------|
| customtkinter   | Interface gráfica moderna dark-theme  |
| Pillow          | Carregamento e redimensionamento de imagens |
| requests        | Download da lista M3U e thumbnails    |
| pyinstaller     | Geração do executável `.exe` (build)  |

## Estrutura do Projeto

```
test/
├── main.py                  # App desktop (entry point principal)
├── build.bat                # Script para gerar o .exe no Windows
├── requirements.txt         # Dependências Python
├── static/
│   └── bulmaflix.png        # Logo
├── app.py                   # (legado) versão web Flask — não necessária
└── README.md
```

