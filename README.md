# BulmaFlix Downloader

Aplicativo de desktop para download de vídeos e playlists usando **yt-dlp** com interface gráfica **CustomTkinter**.

---

## Funcionalidades

| Funcionalidade | Detalhes |
|---|---|
| Seleção de destino | Campo + botão **Procurar** para escolher a pasta de saída |
| Qualidade | Combobox: `720p`, `Full HD (1080p)`, `2K`, `4K`, `8K` |
| Mesclagem via FFmpeg | Configurado automaticamente no `ydl_opts` (formato MP4) |
| Barra de progresso | Percentual, velocidade e ETA em tempo real |
| Prevenção de bloqueio | User-Agent de navegador real, `no_cache_dir`, pausa entre downloads |

---

## Requisitos

- Python 3.10 ou superior  
- [FFmpeg](https://ffmpeg.org/download.html) instalado e disponível no `PATH`

---

## Instalação

```bash
pip install -r requirements.txt
```

---

## Executar

```bash
python downloader.py
```

---

## Gerar executável com PyInstaller

### 1. Instalar PyInstaller

```bash
pip install pyinstaller
```

### 2. Comando de build (arquivo único `.exe`)

```bash
pyinstaller --onefile --windowed --name "BulmaFlixDownloader" \
  --add-data "bulmaflix__2_-removebg-preview.png;." \
  --hidden-import customtkinter \
  --hidden-import yt_dlp \
  --collect-all customtkinter \
  --collect-all yt_dlp \
  downloader.py
```

> **Windows PowerShell** – substitua as quebras de linha (`\`) por `` ` `` ou escreva em uma única linha.

#### Opções explicadas

| Flag | Finalidade |
|---|---|
| `--onefile` | Gera um único `.exe` portátil |
| `--windowed` | Oculta o terminal (modo GUI) |
| `--name` | Nome do executável gerado |
| `--add-data` | Inclui o logo/imagem no bundle (`origem;destino`) |
| `--hidden-import` | Força a inclusão de módulos descobertos dinamicamente |
| `--collect-all` | Coleta todos os dados/sub-módulos do pacote (necessário para CustomTkinter e yt-dlp) |

O executável final estará em `dist/BulmaFlixDownloader.exe`.

---

## Notas sobre FFmpeg

Para qualidades acima de 1080p o yt-dlp precisa mesclar streams separados de vídeo e áudio.  
Certifique-se de que `ffmpeg` e `ffprobe` estão no `PATH` do sistema.  
Ao empacotar com PyInstaller você pode incluir os binários do FFmpeg com `--add-binary "caminho/para/ffmpeg.exe;."`.
