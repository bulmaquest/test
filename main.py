"""
BulmaFlix – Desktop IPTV Player para Windows
Execute:  python main.py
Build .exe:  build.bat
"""

# ── Auto-install de dependências ─────────────────────────────────────────────
import sys
import subprocess


def _ensure_deps():
    pkgs = {"customtkinter": "customtkinter", "PIL": "Pillow", "requests": "requests"}
    missing = [pkg for mod, pkg in pkgs.items() if not _can_import(mod)]
    if missing:
        print(f"[BulmaFlix] Instalando: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *missing])
        print("[BulmaFlix] Dependências instaladas.")


def _can_import(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


_ensure_deps()

# ── Imports principais ────────────────────────────────────────────────────────
import os
import re
import socket
import ipaddress
import threading
import tkinter as tk
import webbrowser
from io import BytesIO
from urllib.parse import urlparse

import customtkinter as ctk
from PIL import Image, ImageDraw
import requests

# ── Constantes visuais ────────────────────────────────────────────────────────
BATCH_SIZE = 40
CARD_W = 168
CARD_H = 200
THUMB_W, THUMB_H = 152, 92
M3U_TIMEOUT = 30
IMG_TIMEOUT = 8
ACCENT = "#f5c518"
BG_DARK = "#111111"
BG_NAV = "#0d0d0d"
BG_CARD = "#1e1e2e"
BG_FILTER = "#16162a"
FG_DIM = "#888888"

# Locais padrão do VLC no Windows
VLC_PATHS = [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
]

# ── Regex para filtro de canais 24h ──────────────────────────────────────────
_24H_RE = re.compile(
    r"\b(24\s*h(ours?|oras?|rs?)?|ao\s*vivo\s*24h?|24x7)\b", re.IGNORECASE
)


# ── Parser M3U ────────────────────────────────────────────────────────────────
def _attr(line: str, key: str) -> str:
    m = re.search(rf'{re.escape(key)}="([^"]*)"', line, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def parse_m3u(text: str) -> list[dict]:
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            url_line = ""
            j = i + 1
            while j < len(lines):
                cand = lines[j].strip()
                if cand and not cand.startswith("#"):
                    url_line = cand
                    i = j
                    break
                j += 1
            if url_line:
                name_m = re.search(r",(.+)$", line)
                name = name_m.group(1).strip() if name_m else "Unknown"
                channels.append({
                    "name": name,
                    "url": url_line,
                    "logo": _attr(line, "tvg-logo"),
                    "group": _attr(line, "group-title") or "Geral",
                })
        i += 1
    return channels


def is_24h(ch: dict) -> bool:
    return bool(_24H_RE.search(f"{ch['name']} {ch['group']}"))


# ── Lançador de player ────────────────────────────────────────────────────────
def play_stream(url: str) -> str:
    """Tenta abrir o stream. Retorna '' em sucesso ou mensagem de erro."""
    for vlc in VLC_PATHS:
        if os.path.exists(vlc):
            subprocess.Popen([vlc, url])
            return ""
    try:
        subprocess.Popen(["vlc", url])
        return ""
    except FileNotFoundError:
        pass
    try:
        subprocess.Popen(["mpv", url])
        return ""
    except FileNotFoundError:
        pass
    try:
        webbrowser.open(url)
        return ""
    except Exception:
        pass
    return (
        "Nenhum player encontrado.\n"
        "Instale o VLC Player para reproduzir o canal.\n"
        "Baixe em: https://www.videolan.org/vlc/"
    )


# ── Imagem placeholder para thumbnails ───────────────────────────────────────
def _make_placeholder() -> ctk.CTkImage:
    img = Image.new("RGB", (THUMB_W, THUMB_H), color="#12121f")
    d = ImageDraw.Draw(img)
    cx, cy = THUMB_W // 2, THUMB_H // 2
    d.rectangle([cx - 22, cy - 15, cx + 22, cy + 15], outline="#444", width=2)
    d.rectangle([cx - 13, cy + 15, cx + 13, cy + 20], fill="#444")
    d.line([cx - 22, cy + 20, cx + 22, cy + 20], fill="#444", width=2)
    return ctk.CTkImage(img, size=(THUMB_W, THUMB_H))


_PLACEHOLDER: ctk.CTkImage | None = None


def get_placeholder() -> ctk.CTkImage:
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        _PLACEHOLDER = _make_placeholder()
    return _PLACEHOLDER


# ── Verificação anti-SSRF para thumbnails ────────────────────────────────────
def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if not host:
        return False
    try:
        addrs = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        for _, _, _, _, sockaddr in addrs:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


# ── Widget: Card de Canal ─────────────────────────────────────────────────────
class ChannelCard(ctk.CTkFrame):
    def __init__(self, parent, channel: dict, play_callback, **kwargs):
        super().__init__(
            parent,
            width=CARD_W,
            height=CARD_H,
            fg_color=BG_CARD,
            corner_radius=10,
            **kwargs,
        )
        self.channel = channel
        self._play_callback = play_callback
        self._thumb_loaded = False
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._build()

    def _build(self):
        self._thumb_lbl = ctk.CTkLabel(
            self,
            text="",
            image=get_placeholder(),
            width=CARD_W,
            height=THUMB_H,
            fg_color="#12121f",
            corner_radius=8,
            cursor="hand2",
        )
        self._thumb_lbl.pack(padx=8, pady=(8, 4))

        self._name_lbl = ctk.CTkLabel(
            self,
            text=self.channel["name"],
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f0f0f0",
            wraplength=CARD_W - 20,
            justify="left",
            anchor="w",
            cursor="hand2",
        )
        self._name_lbl.pack(padx=10, pady=(0, 2), fill="x")

        self._group_lbl = ctk.CTkLabel(
            self,
            text=self.channel["group"],
            font=ctk.CTkFont(size=10),
            text_color=FG_DIM,
            anchor="w",
            cursor="hand2",
        )
        self._group_lbl.pack(padx=10, pady=(0, 8), fill="x")

        for w in (self, self._thumb_lbl, self._name_lbl, self._group_lbl):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_click(self, _=None):
        self._play_callback(self.channel)

    def _on_enter(self, _=None):
        self.configure(border_width=2, border_color=ACCENT)

    def _on_leave(self, _=None):
        self.configure(border_width=0)

    def load_thumbnail(self):
        if self._thumb_loaded or not self.channel.get("logo"):
            return
        threading.Thread(target=self._fetch_thumb, daemon=True).start()

    def _fetch_thumb(self):
        url = self.channel["logo"]
        if not _is_safe_url(url):
            return
        try:
            resp = requests.get(
                url,
                timeout=IMG_TIMEOUT,
                headers={"User-Agent": "BulmaFlix/1.0"},
            )
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
            ctk_img = ctk.CTkImage(img, size=(THUMB_W, THUMB_H))
            self._thumb_loaded = True
            self.after(0, lambda: self._apply_thumb(ctk_img))
        except Exception:
            pass

    def _apply_thumb(self, ctk_img):
        try:
            self._thumb_lbl.configure(image=ctk_img, fg_color="transparent")
        except Exception:
            pass


# ── Janela principal ──────────────────────────────────────────────────────────
class BulmaFlixApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("BulmaFlix – IPTV Player")
        self.geometry("1100x720")
        self.minsize(640, 480)
        self.configure(fg_color=BG_DARK)

        self._all_channels: list[dict] = []
        self._filtered: list[dict] = []
        self._displayed = 0
        self._loading_m3u = False
        self._loading_batch = False
        self._last_cols = 0
        self._cards: list[ChannelCard] = []

        self._build_ui()
        # Check grid resize periodically
        self.after(300, self._check_resize)

    # ── Construção da UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=BG_NAV, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Try to load logo image; fall back to text
        logo_path = self._resource("bulmaflix.png")
        if os.path.exists(logo_path):
            try:
                logo_img = ctk.CTkImage(Image.open(logo_path), size=(124, 16))
                ctk.CTkLabel(header, image=logo_img, text="").pack(
                    side="left", padx=16, pady=10
                )
            except Exception:
                self._text_logo(header)
        else:
            self._text_logo(header)

        self._count_lbl = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(size=12), text_color="#aaa"
        )
        self._count_lbl.pack(side="right", padx=16)

        # URL bar
        url_bar = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=0, height=54)
        url_bar.pack(fill="x")
        url_bar.pack_propagate(False)

        self._url_var = tk.StringVar()
        url_entry = ctk.CTkEntry(
            url_bar,
            textvariable=self._url_var,
            placeholder_text="Cole aqui a URL da lista M3U (.m3u / .m3u8)…",
            height=36,
            font=ctk.CTkFont(size=13),
        )
        url_entry.pack(side="left", padx=(14, 8), pady=9, fill="x", expand=True)
        url_entry.bind("<Return>", lambda _: self._on_load())

        self._load_btn = ctk.CTkButton(
            url_bar,
            text="⬇  Carregar",
            width=130,
            height=36,
            fg_color=ACCENT,
            text_color="#111",
            hover_color="#d4a90e",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_load,
        )
        self._load_btn.pack(side="left", pady=9, padx=(0, 14))

        # Filter bar
        filter_bar = ctk.CTkFrame(self, fg_color=BG_FILTER, corner_radius=0, height=46)
        filter_bar.pack(fill="x")
        filter_bar.pack_propagate(False)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_filter_change())
        ctk.CTkEntry(
            filter_bar,
            textvariable=self._search_var,
            placeholder_text="🔍  Buscar canal…",
            width=220,
            height=30,
        ).pack(side="left", padx=(14, 8), pady=8)

        self._group_var = tk.StringVar(value="Todas as categorias")
        self._group_box = ctk.CTkComboBox(
            filter_bar,
            variable=self._group_var,
            values=["Todas as categorias"],
            width=210,
            height=30,
            command=lambda _: self._on_filter_change(),
        )
        self._group_box.pack(side="left", padx=(0, 8), pady=8)

        self._status_lbl = ctk.CTkLabel(
            filter_bar, text="", font=ctk.CTkFont(size=12), text_color="#aaa"
        )
        self._status_lbl.pack(side="left", padx=8)

        self._result_lbl = ctk.CTkLabel(
            filter_bar, text="", font=ctk.CTkFont(size=12), text_color=ACCENT
        )
        self._result_lbl.pack(side="right", padx=14)

        # Scrollable channel grid
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=BG_DARK, corner_radius=0)
        self._scroll.pack(fill="both", expand=True)

        # Scroll detection
        try:
            self._scroll._parent_canvas.bind(
                "<MouseWheel>", lambda e: self.after(50, self._maybe_load_more)
            )
        except Exception:
            pass
        self.bind_all("<MouseWheel>", lambda _: self.after(50, self._maybe_load_more))

        # "Load more" button
        self._load_more_btn = ctk.CTkButton(
            self._scroll,
            text="Carregar mais…",
            width=200,
            height=34,
            fg_color="#2a2a3e",
            hover_color="#3a3a4e",
            command=self._load_next_batch,
        )

    def _text_logo(self, parent):
        ctk.CTkLabel(
            parent,
            text="▶ BulmaFlix",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=ACCENT,
        ).pack(side="left", padx=16, pady=10)

    # ── Eventos ───────────────────────────────────────────────────────────────
    def _on_load(self):
        url = self._url_var.get().strip()
        if not url:
            self._set_status("Cole a URL da lista M3U primeiro.")
            return
        if self._loading_m3u:
            return
        self._loading_m3u = True
        self._load_btn.configure(state="disabled", text="Carregando…")
        self._set_status("Baixando lista M3U…")
        self._clear_grid()
        threading.Thread(target=self._fetch_m3u, args=(url,), daemon=True).start()

    def _on_filter_change(self):
        search = self._search_var.get().strip().lower()
        group = self._group_var.get().strip()
        filtered = self._all_channels
        if search:
            filtered = [
                c for c in filtered
                if search in c["name"].lower() or search in c["group"].lower()
            ]
        if group and group != "Todas as categorias":
            filtered = [c for c in filtered if c["group"] == group]
        self._filtered = filtered
        self._displayed = 0
        self._clear_grid()
        self._result_lbl.configure(text=f"{len(filtered):,} canais".replace(",", "."))
        self._load_next_batch()

    def _maybe_load_more(self):
        try:
            canvas = self._scroll._parent_canvas
            yview = canvas.yview()
            if yview[1] > 0.85 and self._displayed < len(self._filtered):
                self._load_next_batch()
        except Exception:
            pass

    # ── Fetch M3U (background thread) ────────────────────────────────────────
    def _fetch_m3u(self, url: str):
        try:
            resp = requests.get(
                url,
                timeout=M3U_TIMEOUT,
                headers={"User-Agent": "BulmaFlix/1.0"},
                stream=True,
            )
            resp.raise_for_status()
            chunks = []
            total = 0
            for chunk in resp.iter_content(65536):
                chunks.append(chunk)
                total += len(chunk)
                if total > 50 * 1024 * 1024:
                    break
            raw = b"".join(chunks).decode("utf-8", errors="replace")
            channels = parse_m3u(raw)
            before = len(channels)
            channels = [c for c in channels if not is_24h(c)]
            removed = before - len(channels)
            self.after(0, lambda: self._on_m3u_loaded(channels, removed))
        except Exception as exc:
            self.after(0, lambda: self._on_m3u_error(str(exc)))

    def _on_m3u_loaded(self, channels: list[dict], removed: int):
        self._loading_m3u = False
        self._load_btn.configure(state="normal", text="⬇  Carregar")
        self._all_channels = channels
        total_str = f"{len(channels):,}".replace(",", ".")
        removed_str = f"{removed:,}".replace(",", ".")
        self._count_lbl.configure(
            text=f"{total_str} canais  •  {removed_str} canal(is) 24h removido(s)"
        )
        groups = sorted({c["group"] for c in channels})
        self._group_box.configure(values=["Todas as categorias"] + groups)
        self._group_var.set("Todas as categorias")
        self._filtered = channels
        self._displayed = 0
        self._result_lbl.configure(text=f"{total_str} canais")
        self._set_status(f"Lista carregada com sucesso!")
        self._load_next_batch()

    def _on_m3u_error(self, msg: str):
        self._loading_m3u = False
        self._load_btn.configure(state="normal", text="⬇  Carregar")
        self._set_status(f"Erro: {msg}")

    # ── Grid de canais ────────────────────────────────────────────────────────
    def _clear_grid(self):
        for card in self._cards:
            card.destroy()
        self._cards.clear()
        try:
            self._load_more_btn.grid_forget()
        except Exception:
            pass

    def _load_next_batch(self):
        if self._loading_batch:
            return
        start = self._displayed
        end = min(start + BATCH_SIZE, len(self._filtered))
        if start >= end:
            return

        self._loading_batch = True
        try:
            self._load_more_btn.grid_forget()
        except Exception:
            pass

        cols = self._get_cols()
        batch = self._filtered[start:end]
        self._displayed = end

        for ch in batch:
            idx = len(self._cards)
            row, col = divmod(idx, cols)
            card = ChannelCard(
                self._scroll,
                ch,
                play_callback=self._on_play,
                cursor="hand2",
            )
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nw")
            self._cards.append(card)
            # Lazy load thumbnail after a small stagger to avoid UI freeze
            delay = (idx % BATCH_SIZE) * 40
            self.after(delay, card.load_thumbnail)

        self._loading_batch = False

        if self._displayed < len(self._filtered):
            next_row = (len(self._cards) + cols - 1) // cols
            self._load_more_btn.grid(
                row=next_row, column=0, columnspan=cols, pady=16, sticky="ew"
            )

    def _get_cols(self) -> int:
        w = self._scroll.winfo_width()
        if w < 50:
            w = self.winfo_width() - 20
        return max(1, w // (CARD_W + 16))

    def _check_resize(self):
        """Re-layout grid when window width changes."""
        cols = self._get_cols()
        if cols != self._last_cols and self._cards:
            self._last_cols = cols
            for idx, card in enumerate(self._cards):
                row, col = divmod(idx, cols)
                card.grid(row=row, column=col, padx=8, pady=8, sticky="nw")
            if self._displayed < len(self._filtered):
                next_row = (len(self._cards) + cols - 1) // cols
                self._load_more_btn.grid(
                    row=next_row, column=0, columnspan=cols, pady=16, sticky="ew"
                )
        self.after(400, self._check_resize)

    # ── Playback ──────────────────────────────────────────────────────────────
    def _on_play(self, channel: dict):
        err = play_stream(channel["url"])
        if err:
            self._show_play_dialog(channel, err)

    def _show_play_dialog(self, channel: dict, error_msg: str):
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Reproduzir: {channel['name']}")
        dlg.geometry("440x210")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(fg_color="#1a1a2e")

        ctk.CTkLabel(
            dlg,
            text=error_msg,
            font=ctk.CTkFont(size=12),
            wraplength=400,
            text_color="#f87171",
            justify="center",
        ).pack(pady=(20, 8), padx=20)

        ctk.CTkLabel(
            dlg,
            text="Copie o link e abra manualmente no VLC ou MPV:",
            font=ctk.CTkFont(size=11),
            text_color="#aaa",
        ).pack(pady=4)

        def copy_url():
            self.clipboard_clear()
            self.clipboard_append(channel["url"])
            copy_btn.configure(text="✓ Copiado!")
            dlg.after(2000, lambda: copy_btn.configure(text="📋  Copiar URL"))

        copy_btn = ctk.CTkButton(
            dlg,
            text="📋  Copiar URL",
            width=150,
            height=34,
            fg_color=ACCENT,
            text_color="#111",
            hover_color="#d4a90e",
            command=copy_url,
        )
        copy_btn.pack(pady=12)

        ctk.CTkButton(
            dlg,
            text="Fechar",
            width=100,
            height=30,
            fg_color="#2a2a3e",
            hover_color="#3a3a4e",
            command=dlg.destroy,
        ).pack()

    # ── Utilitários ───────────────────────────────────────────────────────────
    def _set_status(self, text: str):
        self._status_lbl.configure(text=text)

    @staticmethod
    def _resource(filename: str) -> str:
        """Resolve caminho de recurso (funciona tanto em dev quanto no .exe)."""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "static", filename)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = BulmaFlixApp()
    app.protocol("WM_DELETE_WINDOW", app.destroy)
    app.mainloop()
