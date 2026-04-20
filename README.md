# BulmaFlix 🎬

Player IPTV web moderno com carregamento sob demanda, interface responsiva e suporte a listas M3U.

## Recursos

- ⚡ **Carregamento sob demanda** — infinite scroll com IntersectionObserver; nunca trava com listas grandes
- 🚀 **Download assíncrono** — a lista M3U é baixada em background sem bloquear a interface
- 🖼️ **Lazy loading de capas** — thumbnails carregam apenas quando ficam visíveis
- 📺 **Player HLS nativo** — suporte a streams HLS/m3u8 via hls.js e fallback HTML5
- 🔍 **Busca e filtro por categoria** — pesquisa em tempo real com debounce
- 🚫 **Filtro de canais 24h** — canais de loop 24 horas são removidos automaticamente
- 🎨 **Interface moderna** — tema escuro com Bulma CSS, animações e skeleton loaders
- 📦 **Auto-instalação de dependências** — as dependências Python são instaladas automaticamente

## Requisitos

- Python 3.10+

## Como Executar

```bash
# 1. Clone o repositório (se necessário)
git clone <repo-url>
cd test

# 2. Execute diretamente — dependências são instaladas automaticamente
python app.py
```

Acesse **http://localhost:5000** no navegador.

## Como Usar

1. Cole a URL da sua lista M3U no campo de texto
2. Clique em **Carregar** (ou pressione Enter)
3. Aguarde o processamento (indicador de progresso)
4. Navegue pelos canais, use a busca ou filtre por categoria
5. Clique em um canal para abrir o player

## Estrutura do Projeto

```
test/
├── app.py                   # Backend Flask (servidor, parsing M3U, proxy de imagens)
├── requirements.txt         # Dependências Python
├── templates/
│   └── index.html           # Interface principal (Bulma CSS)
├── static/
│   ├── css/style.css        # Estilos customizados (tema escuro)
│   ├── js/app.js            # Lógica frontend (lazy loading, player, busca)
│   └── bulmaflix.png        # Logo
└── README.md
```

## Dependências Python

| Pacote      | Uso                                  |
|-------------|--------------------------------------|
| flask       | Servidor web e rotas API             |
| requests    | Download da lista M3U e proxy HTTP   |
| cachetools  | Cache TTL das listas em memória      |

## API Interna

| Endpoint           | Método | Descrição                              |
|--------------------|--------|----------------------------------------|
| `/api/load`        | POST   | Inicia o download assíncrono da lista  |
| `/api/status`      | GET    | Consulta o estado do carregamento      |
| `/api/channels`    | GET    | Retorna canais paginados               |
| `/api/groups`      | GET    | Lista categorias disponíveis           |
| `/api/imgproxy`    | GET    | Proxy de thumbnails (evita CORS)       |
