#!/usr/bin/env bash

# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Tracker — Proxmox LXC Install Script
# Uso: bash -c "$(wget -qLO - https://raw.githubusercontent.com/TUO-USER/portfolio-tool/main/install.sh)"
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colori ───────────────────────────────────────────────────────────────────
RD="\033[01;31m"
GN="\033[1;92m"
YW="\033[33m"
BL="\033[36m"
CL="\033[m"

# ── Config defaults ──────────────────────────────────────────────────────────
APP="portfolio-tracker"
REPO="https://github.com/TUO-USER/portfolio-tool.git"  # <-- MODIFICA CON IL TUO REPO
CT_ID=""
HN="portfolio"
DISK="4"
RAM="512"
CPU="1"
BRIDGE="vmbr0"
STORAGE="local-lvm"
TEMPLATE="local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
PORT="8000"

# ── Funzioni UI ──────────────────────────────────────────────────────────────
msg_info()  { echo -e "${BL}[info]${CL} $1"; }
msg_ok()    { echo -e "${GN}[ok]${CL} $1"; }
msg_error() { echo -e "${RD}[error]${CL} $1"; exit 1; }

header() {
  clear
  echo -e "${BL}"
  echo "  ╔══════════════════════════════════════════╗"
  echo "  ║     Portfolio Tracker — LXC Installer    ║"
  echo "  ╚══════════════════════════════════════════╝"
  echo -e "${CL}"
}

# ── Controlli ────────────────────────────────────────────────────────────────
check_root() {
  [[ $EUID -eq 0 ]] || msg_error "Esegui come root dal nodo Proxmox"
}

check_proxmox() {
  command -v pct &>/dev/null || msg_error "pct non trovato — esegui dal nodo Proxmox"
}

# ── Prossimo CT ID libero ────────────────────────────────────────────────────
next_ct_id() {
  local id=100
  while pct status "$id" &>/dev/null; do
    ((id++))
  done
  echo "$id"
}

# ── Input utente ─────────────────────────────────────────────────────────────
get_settings() {
  CT_ID=$(next_ct_id)

  echo ""
  read -rp "$(echo -e "${YW}CT ID${CL} [$CT_ID]: ")" input
  CT_ID="${input:-$CT_ID}"

  read -rp "$(echo -e "${YW}Hostname${CL} [$HN]: ")" input
  HN="${input:-$HN}"

  read -rp "$(echo -e "${YW}Disco (GB)${CL} [$DISK]: ")" input
  DISK="${input:-$DISK}"

  read -rp "$(echo -e "${YW}RAM (MB)${CL} [$RAM]: ")" input
  RAM="${input:-$RAM}"

  read -rp "$(echo -e "${YW}CPU cores${CL} [$CPU]: ")" input
  CPU="${input:-$CPU}"

  read -rp "$(echo -e "${YW}Bridge${CL} [$BRIDGE]: ")" input
  BRIDGE="${input:-$BRIDGE}"

  read -rp "$(echo -e "${YW}Storage${CL} [$STORAGE]: ")" input
  STORAGE="${input:-$STORAGE}"

  read -rp "$(echo -e "${YW}Porta app${CL} [$PORT]: ")" input
  PORT="${input:-$PORT}"

  read -rp "$(echo -e "${YW}Installare Tailscale?${CL} [s/N]: ")" TS
  TS="${TS,,}"

  echo ""
  echo -e "${BL}── Riepilogo ──────────────────────────────────${CL}"
  echo -e "  CT ID:     ${GN}$CT_ID${CL}"
  echo -e "  Hostname:  ${GN}$HN${CL}"
  echo -e "  Disco:     ${GN}${DISK}GB${CL}"
  echo -e "  RAM:       ${GN}${RAM}MB${CL}"
  echo -e "  CPU:       ${GN}$CPU core(s)${CL}"
  echo -e "  Porta:     ${GN}$PORT${CL}"
  echo -e "  Tailscale: ${GN}${TS:-no}${CL}"
  echo ""

  read -rp "$(echo -e "${YW}Procedi? [S/n]:${CL} ")" confirm
  [[ "${confirm,,}" != "n" ]] || exit 0
}

# ── Crea CT ──────────────────────────────────────────────────────────────────
create_ct() {
  msg_info "Creazione container LXC $CT_ID..."

  pct create "$CT_ID" "$TEMPLATE" \
    --hostname "$HN" \
    --cores "$CPU" \
    --memory "$RAM" \
    --rootfs "$STORAGE:$DISK" \
    --net0 "name=eth0,bridge=$BRIDGE,ip=dhcp" \
    --unprivileged 1 \
    --features nesting=1 \
    --onboot 1 \
    --start 0

  msg_ok "Container $CT_ID creato"
}

# ── Avvia CT ─────────────────────────────────────────────────────────────────
start_ct() {
  msg_info "Avvio container..."
  pct start "$CT_ID"
  sleep 5
  msg_ok "Container avviato"
}

# ── Setup dentro il CT ───────────────────────────────────────────────────────
setup_app() {
  msg_info "Aggiornamento sistema..."
  pct exec "$CT_ID" -- bash -c "apt update && apt upgrade -y" >/dev/null 2>&1
  msg_ok "Sistema aggiornato"

  msg_info "Installazione dipendenze (python3, git)..."
  pct exec "$CT_ID" -- bash -c "apt install -y python3 python3-pip python3-venv git" >/dev/null 2>&1
  msg_ok "Dipendenze installate"

  msg_info "Clone repository..."
  pct exec "$CT_ID" -- bash -c "git clone $REPO /opt/$APP" >/dev/null 2>&1
  msg_ok "Repository clonato"

  msg_info "Setup virtualenv e pip install..."
  pct exec "$CT_ID" -- bash -c "
    cd /opt/$APP
    python3 -m venv venv
    source venv/bin/activate
    pip install --no-cache-dir -r backend/requirements.txt
  " >/dev/null 2>&1
  msg_ok "Dipendenze Python installate"

  msg_info "Configurazione systemd service..."
  pct exec "$CT_ID" -- bash -c "
    cat > /etc/systemd/system/$APP.service <<EOF
[Unit]
Description=Portfolio Tracker API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/$APP/backend
ExecStart=/opt/$APP/venv/bin/uvicorn main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable $APP
    systemctl start $APP
  "
  msg_ok "Servizio configurato e avviato"

  # Script di aggiornamento
  pct exec "$CT_ID" -- bash -c "
    cat > /opt/$APP/update.sh <<'EOF'
#!/bin/bash
cd /opt/$APP
git pull
source venv/bin/activate
pip install --no-cache-dir -r backend/requirements.txt
systemctl restart portfolio-tracker
echo 'Aggiornamento completato!'
EOF
    chmod +x /opt/$APP/update.sh
  "
  msg_ok "Script di aggiornamento creato (/opt/$APP/update.sh)"
}

# ── Tailscale (opzionale) ────────────────────────────────────────────────────
setup_tailscale() {
  if [[ "$TS" == "s" ]]; then
    msg_info "Installazione Tailscale..."
    pct exec "$CT_ID" -- bash -c "curl -fsSL https://tailscale.com/install.sh | sh" >/dev/null 2>&1
    msg_ok "Tailscale installato"
    echo ""
    echo -e "${YW}Per attivare Tailscale entra nel container ed esegui:${CL}"
    echo -e "  pct enter $CT_ID"
    echo -e "  tailscale up"
    echo ""
  fi
}

# ── Risultato finale ─────────────────────────────────────────────────────────
show_result() {
  local IP
  IP=$(pct exec "$CT_ID" -- bash -c "hostname -I 2>/dev/null | awk '{print \$1}'" 2>/dev/null || echo "N/A")

  echo ""
  echo -e "${GN}══════════════════════════════════════════════${CL}"
  echo -e "${GN} Portfolio Tracker installato con successo!${CL}"
  echo -e "${GN}══════════════════════════════════════════════${CL}"
  echo ""
  echo -e "  URL:          ${BL}http://$IP:$PORT/${CL}"
  echo -e "  Container:    ${BL}$CT_ID${CL} ($HN)"
  echo -e "  Entra nel CT: ${BL}pct enter $CT_ID${CL}"
  echo -e "  Aggiorna:     ${BL}pct exec $CT_ID -- bash /opt/$APP/update.sh${CL}"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
header
check_root
check_proxmox
get_settings
create_ct
start_ct
setup_app
setup_tailscale
show_result
