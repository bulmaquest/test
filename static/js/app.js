/**
 * BulmaFlix – Frontend JavaScript
 * On-demand (lazy) loading with IntersectionObserver + HLS.js player
 */

"use strict";

// ─── State ───────────────────────────────────────────────────────────────────
const State = {
  m3uUrl: "",
  currentPage: 1,
  totalPages: 1,
  totalChannels: 0,
  isLoading: false,
  loadingMore: false,
  searchQuery: "",
  groupFilter: "",
  pollInterval: null,
  currentStreamUrl: "",
  hlsInstance: null,
};

// ─── DOM helpers ─────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const grid = () => $("channelGrid");

// ─── Navbar burger ───────────────────────────────────────────────────────────
document.querySelectorAll(".navbar-burger").forEach((burger) => {
  burger.addEventListener("click", () => {
    const target = document.getElementById(burger.dataset.target);
    burger.classList.toggle("is-active");
    target && target.classList.toggle("is-active");
  });
});

// ─── Load M3U list ───────────────────────────────────────────────────────────
async function loadList() {
  const url = $("m3uUrl").value.trim();
  if (!url) {
    showToast("Cole a URL da lista M3U primeiro.", "warning");
    return;
  }

  State.m3uUrl = url;
  State.currentPage = 1;
  State.searchQuery = "";
  State.groupFilter = "";
  $("searchInput").value = "";
  $("groupSelect").value = "";

  // Reset UI
  grid().innerHTML = "";
  $("endOfResults").style.display = "none";
  $("mainContent").style.display = "none";
  showStatus(true, "Iniciando download da lista…");
  $("btnLoad").classList.add("is-loading");

  try {
    const res = await fetch("/api/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (data.status === "ready") {
      onListReady();
    } else {
      startPolling();
    }
  } catch (err) {
    showToast("Erro ao conectar ao servidor.", "danger");
    showStatus(false);
    $("btnLoad").classList.remove("is-loading");
  }
}

// ─── Poll until ready ─────────────────────────────────────────────────────────
function startPolling() {
  State.pollInterval && clearInterval(State.pollInterval);
  State.pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status?url=${encodeURIComponent(State.m3uUrl)}`);
      const data = await res.json();
      updateProgressText(data.status);
      if (data.status === "ready") {
        clearInterval(State.pollInterval);
        onListReady();
      } else if (data.status.startsWith("error")) {
        clearInterval(State.pollInterval);
        showToast("Erro ao carregar lista: " + data.status.replace("error:", ""), "danger");
        showStatus(false);
        $("btnLoad").classList.remove("is-loading");
      }
    } catch (_) {/* network blip – keep polling */}
  }, 1500);
}

function updateProgressText(status) {
  const map = {
    loading: "Baixando e processando a lista M3U…",
    ready:   "Lista pronta!",
  };
  $("statusText").textContent = map[status] || status;
}

// ─── List ready: load first page ─────────────────────────────────────────────
async function onListReady() {
  showStatus(false);
  $("btnLoad").classList.remove("is-loading");
  $("mainContent").style.display = "";
  await populateGroups();
  await loadPage(1, true);
  setupInfiniteScroll();
}

// ─── Populate group filter dropdown ──────────────────────────────────────────
async function populateGroups() {
  try {
    const res = await fetch(`/api/groups?url=${encodeURIComponent(State.m3uUrl)}`);
    const data = await res.json();
    const sel = $("groupSelect");
    // Clear previous options except first
    while (sel.options.length > 1) sel.remove(1);
    data.groups.forEach((g) => {
      const opt = document.createElement("option");
      opt.value = g;
      opt.textContent = g;
      sel.appendChild(opt);
    });
  } catch (_) { /* non-fatal */ }
}

// ─── Load a page of channels ──────────────────────────────────────────────────
async function loadPage(page, reset = false) {
  if (State.isLoading || State.loadingMore) return;
  if (page > 1) {
    State.loadingMore = true;
    $("loadingMore").style.display = "";
  } else {
    State.isLoading = true;
    showSkeletons(12);
  }

  try {
    const params = new URLSearchParams({
      url:    State.m3uUrl,
      page:   page,
      search: State.searchQuery,
      group:  State.groupFilter,
    });
    const res  = await fetch(`/api/channels?${params}`);
    const data = await res.json();

    State.currentPage   = data.page;
    State.totalPages    = data.pages;
    State.totalChannels = data.total;

    if (reset) {
      grid().innerHTML = "";
    } else {
      clearSkeletons();
    }

    renderChannels(data.channels);
    updateCountBadge(data.total);

    const atEnd = data.page >= data.pages;
    $("endOfResults").style.display = atEnd && data.total > 0 ? "" : "none";

    if (data.total === 0) {
      grid().innerHTML =
        `<div class="column is-full has-text-centered has-text-grey py-6">
           <i class="fas fa-tv fa-3x mb-3"></i>
           <p>Nenhum canal encontrado.</p>
         </div>`;
    }
  } catch (err) {
    showToast("Erro ao carregar canais.", "danger");
  } finally {
    State.isLoading     = false;
    State.loadingMore   = false;
    $("loadingMore").style.display = "none";
    clearSkeletons();
  }
}

// ─── Render channel cards ─────────────────────────────────────────────────────
function renderChannels(channels) {
  const fragment = document.createDocumentFragment();
  channels.forEach((ch) => {
    const card = buildCard(ch);
    fragment.appendChild(card);
  });
  grid().appendChild(fragment);

  // Lazy-load thumbnails with IntersectionObserver
  observeThumbs();
}

function buildCard(ch) {
  const card = document.createElement("div");
  card.className = "channel-card";
  card.setAttribute("data-url", ch.url);
  card.setAttribute("data-name", ch.name);
  card.setAttribute("data-group", ch.group);

  const logoSrc = ch.logo
    ? `/api/imgproxy?url=${encodeURIComponent(ch.logo)}`
    : "";

  card.innerHTML = `
    <div class="channel-thumb">
      ${logoSrc
        ? `<img data-src="${logoSrc}" alt="${escHtml(ch.name)}" />`
        : ""}
      <div class="thumb-placeholder">
        <i class="fas fa-tv"></i>
      </div>
    </div>
    <div class="channel-info">
      <div class="channel-name" title="${escHtml(ch.name)}">${escHtml(ch.name)}</div>
      <div class="channel-group">${escHtml(ch.group)}</div>
    </div>
    <div class="play-overlay"><i class="fas fa-play-circle"></i></div>
  `;

  card.addEventListener("click", () => openPlayer(ch));
  return card;
}

// ─── Thumbnail lazy loading ───────────────────────────────────────────────────
let _thumbObserver = null;

function observeThumbs() {
  if (!("IntersectionObserver" in window)) {
    // Fallback: load all immediately
    document.querySelectorAll("img[data-src]").forEach(loadThumb);
    return;
  }
  if (!_thumbObserver) {
    _thumbObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            loadThumb(entry.target);
            _thumbObserver.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "200px" }
    );
  }
  document.querySelectorAll("img[data-src]").forEach((img) => {
    _thumbObserver.observe(img);
  });
}

function loadThumb(img) {
  const src = img.getAttribute("data-src");
  if (!src) return;
  img.removeAttribute("data-src");
  img.src = src;
  img.addEventListener("load", () => {
    img.classList.add("loaded");
    const placeholder = img.nextElementSibling;
    if (placeholder && placeholder.classList.contains("thumb-placeholder")) {
      placeholder.classList.add("hidden");
    }
  });
  img.addEventListener("error", () => {
    // Keep placeholder visible on error
    img.style.display = "none";
  });
}

// ─── Infinite scroll ─────────────────────────────────────────────────────────
let _scrollObserver = null;

function setupInfiniteScroll() {
  if (_scrollObserver) {
    _scrollObserver.disconnect();
  }
  _scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting) {
        const next = State.currentPage + 1;
        if (next <= State.totalPages && !State.loadingMore && !State.isLoading) {
          loadPage(next);
        }
      }
    },
    { rootMargin: "300px" }
  );
  _scrollObserver.observe($("sentinel"));
}

// ─── Search (debounced) ───────────────────────────────────────────────────────
let _searchTimer = null;

function debouncedSearch() {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => {
    State.searchQuery = $("searchInput").value.trim().toLowerCase();
    State.currentPage = 1;
    grid().innerHTML = "";
    $("endOfResults").style.display = "none";
    loadPage(1, true);
  }, 350);
}

function filterByGroup() {
  State.groupFilter = $("groupSelect").value;
  State.currentPage = 1;
  grid().innerHTML = "";
  $("endOfResults").style.display = "none";
  loadPage(1, true);
}

// ─── Skeleton loaders ─────────────────────────────────────────────────────────
function showSkeletons(count) {
  clearSkeletons();
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {
    const card = document.createElement("div");
    card.className = "channel-card skeleton";
    card.innerHTML = `
      <div class="channel-thumb"></div>
      <div class="channel-info">
        <div class="channel-name">&nbsp;</div>
        <div class="channel-group">&nbsp;</div>
      </div>`;
    frag.appendChild(card);
  }
  grid().appendChild(frag);
}

function clearSkeletons() {
  document.querySelectorAll(".channel-card.skeleton").forEach((el) => el.remove());
}

// ─── Count badge ─────────────────────────────────────────────────────────────
function updateCountBadge(total) {
  $("channelCountNum").textContent = total.toLocaleString("pt-BR");
  $("channelCount").style.display = "";
  $("resultCount").textContent = `${total.toLocaleString("pt-BR")} canais`;
}

// ─── Status bar helpers ───────────────────────────────────────────────────────
function showStatus(visible, text = "") {
  $("statusBar").style.display = visible ? "" : "none";
  if (text) $("statusText").textContent = text;
}

// ─── Player ───────────────────────────────────────────────────────────────────
function openPlayer(ch) {
  State.currentStreamUrl = ch.url;
  $("playerTitle").textContent = ch.name;
  $("playerMeta").innerHTML =
    `<span class="tag is-dark">${escHtml(ch.group)}</span>` +
    (ch.tvg_id ? `<span class="tag is-info is-light">${escHtml(ch.tvg_id)}</span>` : "");

  const video = $("videoPlayer");

  // Destroy existing HLS instance
  if (State.hlsInstance) {
    State.hlsInstance.destroy();
    State.hlsInstance = null;
  }
  video.src = "";

  // Try HLS.js first, then native, then direct src
  if (Hls.isSupported() && _isHLS(ch.url)) {
    const hls = new Hls({
      maxBufferLength: 30,
      maxBufferSize: 60 * 1000 * 1000,
      enableWorker: true,
    });
    hls.loadSource(ch.url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
    State.hlsInstance = hls;
  } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = ch.url;
    video.play().catch(() => {});
  } else {
    video.src = ch.url;
    video.play().catch(() => {});
  }

  $("playerModal").classList.add("is-active");
}

function closePlayer() {
  $("playerModal").classList.remove("is-active");
  const video = $("videoPlayer");
  video.pause();
  video.src = "";
  if (State.hlsInstance) {
    State.hlsInstance.destroy();
    State.hlsInstance = null;
  }
}

function copyStreamUrl() {
  if (!State.currentStreamUrl) return;
  navigator.clipboard
    .writeText(State.currentStreamUrl)
    .then(() => showToast("URL copiada para a área de transferência!", "success"))
    .catch(() => showToast("Não foi possível copiar.", "warning"));
}

function _isHLS(url) {
  return /\.(m3u8)(\?.*)?$/i.test(url) || url.includes("m3u8");
}

// ─── Toast ────────────────────────────────────────────────────────────────────
let _toastTimer = null;

function showToast(message, type = "info") {
  const colors = { info: "#3273dc", success: "#48c774", warning: "#f5c518", danger: "#f14668" };
  const toast = $("toast");
  toast.textContent = message;
  toast.style.borderColor = colors[type] || colors.info;
  toast.style.display = "block";
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { toast.style.display = "none"; }, 3500);
}

// ─── Utility ──────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ─── Allow pressing Enter in URL input ───────────────────────────────────────
$("m3uUrl").addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadList();
});
