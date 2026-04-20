import os
import threading
import customtkinter as ctk
from tkinter import filedialog
import yt_dlp

# ─── Appearance ───────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Quality map ──────────────────────────────────────────────────────────────
QUALITY_MAP = {
    "720p":           "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "Full HD (1080p)": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "2K":             "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "4K":             "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "8K":             "bestvideo[height<=4320]+bestaudio/best[height<=4320]",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BulmaFlix Downloader")
        self.geometry("780x540")
        self.resizable(False, False)

        self._build_ui()
        self._download_thread: threading.Thread | None = None

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 16, "pady": 8}

        # Logo / title
        title = ctk.CTkLabel(
            self, text="🎬  BulmaFlix Downloader",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(pady=(20, 4))

        subtitle = ctk.CTkLabel(
            self, text="Baixe vídeos e playlists com yt-dlp",
            font=ctk.CTkFont(size=13),
            text_color="gray70",
        )
        subtitle.pack(pady=(0, 16))

        # ── URL ──
        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.pack(fill="x", **pad)

        ctk.CTkLabel(url_frame, text="URL do vídeo / playlist:", anchor="w").pack(
            fill="x"
        )
        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://www.youtube.com/watch?v=...",
            height=36,
        )
        self.url_entry.pack(fill="x", pady=(4, 0))

        # ── Destino ──
        dest_frame = ctk.CTkFrame(self, fg_color="transparent")
        dest_frame.pack(fill="x", **pad)

        ctk.CTkLabel(dest_frame, text="Pasta de destino:", anchor="w").pack(fill="x")

        dest_row = ctk.CTkFrame(dest_frame, fg_color="transparent")
        dest_row.pack(fill="x", pady=(4, 0))

        self.dest_entry = ctk.CTkEntry(
            dest_row,
            placeholder_text="Selecione a pasta de destino…",
            height=36,
        )
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            dest_row,
            text="Procurar",
            width=100,
            height=36,
            command=self._browse_folder,
        ).pack(side="left")

        # ── Qualidade ──
        quality_frame = ctk.CTkFrame(self, fg_color="transparent")
        quality_frame.pack(fill="x", **pad)

        ctk.CTkLabel(quality_frame, text="Qualidade:", anchor="w").pack(fill="x")

        self.quality_combo = ctk.CTkComboBox(
            quality_frame,
            values=list(QUALITY_MAP.keys()),
            state="readonly",
            height=36,
        )
        self.quality_combo.set("Full HD (1080p)")
        self.quality_combo.pack(fill="x", pady=(4, 0))

        # ── Progresso ──
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", **pad)

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Aguardando…",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        )
        self.status_label.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=18)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(6, 0))

        # ── Botão ──
        self.download_btn = ctk.CTkButton(
            self,
            text="⬇  Iniciar Download",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_download,
        )
        self.download_btn.pack(pady=20, padx=16, fill="x")

        # ── Log ──
        log_frame = ctk.CTkFrame(self, fg_color="transparent")
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.log_box = ctk.CTkTextbox(log_frame, height=90, state="disabled")
        self.log_box.pack(fill="both", expand=True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Selecione a pasta de destino")
        if folder:
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, folder)

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    def _set_progress(self, value: float):
        """value in [0.0, 1.0]"""
        self.progress_bar.set(max(0.0, min(1.0, value)))

    # ── Download ──────────────────────────────────────────────────────────────

    def _start_download(self):
        url = self.url_entry.get().strip()
        dest = self.dest_entry.get().strip()
        quality = self.quality_combo.get()

        if not url:
            self._log("⚠  Por favor, insira uma URL.")
            return
        if not dest:
            self._log("⚠  Por favor, selecione a pasta de destino.")
            return
        if not os.path.isdir(dest):
            self._log("⚠  Pasta de destino inválida.")
            return

        if self._download_thread and self._download_thread.is_alive():
            self._log("⚠  Um download já está em andamento.")
            return

        self.download_btn.configure(state="disabled")
        self._set_progress(0)
        self._set_status("Iniciando…")

        self._download_thread = threading.Thread(
            target=self._run_download,
            args=(url, dest, quality),
            daemon=True,
        )
        self._download_thread.start()

    def _progress_hook(self, d: dict):
        status = d.get("status")

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0
            percent = d.get("_percent_str", "").strip()
            speed_str = d.get("_speed_str", "").strip()
            eta_str = d.get("_eta_str", "").strip()

            if total:
                ratio = downloaded / total
                self.after(0, self._set_progress, ratio)

            status_text = f"⬇  {percent}  •  {speed_str}  •  ETA: {eta_str}"
            self.after(0, self._set_status, status_text)

        elif status == "finished":
            filename = d.get("filename", "")
            self.after(0, self._log, f"✔  Processando: {os.path.basename(filename)}")
            self.after(0, self._set_status, "Finalizando (mesclando áudio/vídeo)…")
            self.after(0, self._set_progress, 1.0)

        elif status == "error":
            self.after(0, self._log, "✘  Erro durante o download.")

    def _run_download(self, url: str, dest: str, quality: str):
        fmt = QUALITY_MAP.get(quality, QUALITY_MAP["Full HD (1080p)"])

        ydl_opts = {
            # Output template
            "outtmpl": os.path.join(dest, "%(title)s.%(ext)s"),
            # Format selection
            "format": fmt,
            # Merge via ffmpeg
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferredformat": "mp4",
                }
            ],
            # Progress
            "progress_hooks": [self._progress_hook],
            # Browser simulation / anti-block
            "http_headers": {"User-Agent": USER_AGENT},
            "nocheckcertificate": False,
            "no_cache_dir": True,
            # Playlist / rate controls
            "sleep_interval": 2,
            "max_sleep_interval": 5,
            "ignoreerrors": True,
            # Quiet except hooks
            "quiet": True,
            "no_warnings": False,
        }

        try:
            self.after(0, self._log, f"🔍  Processando: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.after(0, self._log, "✅  Download concluído!")
            self.after(0, self._set_status, "✅  Concluído!")
        except Exception as exc:
            self.after(0, self._log, f"✘  Erro: {exc}")
            self.after(0, self._set_status, "Erro no download.")
        finally:
            self.after(0, self.download_btn.configure, {"state": "normal"})


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()
