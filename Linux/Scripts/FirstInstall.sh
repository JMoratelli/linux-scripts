#!/usr/bin/env bash
#
# FirstInstall.sh
#
# Script de pos-instalacao pessoal. Instala o conjunto de aplicativos e
# ferramentas de desenvolvimento normalmente usados, com foco principal em
# CachyOS (Arch-based). Tambem oferece suporte (best-effort) a Fedora e
# Debian/Ubuntu para quando a distro do dia mudar.
#
# Uso:
#   chmod +x FirstInstall.sh
#   ./FirstInstall.sh
#
# O script pergunta a distro no inicio. Cada bloco e independente -- se algo
# falhar (nome de pacote mudou, repositorio fora do ar), o script avisa e
# continua com o resto.

set -uo pipefail

echo "======================================"
echo " FirstInstall - configuracao pos-instalacao"
echo "======================================"
echo ""
echo "Qual distro voce esta instalando?"
echo "  1) CachyOS / Arch Linux (foco principal)"
echo "  2) Fedora"
echo "  3) Debian / Ubuntu"
read -rp "Escolha [1-3]: " DISTRO_CHOICE

case "$DISTRO_CHOICE" in
  1) DISTRO="cachy" ;;
  2) DISTRO="fedora" ;;
  3) DISTRO="debian" ;;
  *) echo "Opcao invalida."; exit 1 ;;
esac

echo ""
echo ">>> Distro selecionada: $DISTRO"
echo ""

FLATPAK_APPS=(
  de.gonicus.gonnect
  com.rtosta.zapzap
  org.onlyoffice.desktopeditors
  com.getpostman.Postman
  io.dbeaver.DBeaverCommunity
  org.telegram.desktop
  com.github.tchx84.Flatseal
  io.github.seadve.Kooha
  io.gitlab.adhami3310.Impression
  it.mijorus.gearlever
  net.nokyan.Resources
)

VSCODE_EXTENSIONS=(
  anthropic.claude-code
  ms-python.debugpy
  ms-python.python
  ms-python.vscode-pylance
  ms-python.vscode-python-envs
  ms-vscode.cmake-tools
  ms-vscode.cpp-devtools
  ms-vscode.cpptools
  ms-vscode.cpptools-extension-pack
  ms-vscode.cpptools-themes
  ms-vscode.powershell
)

install_flatpak_apps() {
  echo "=== Flatpak: adicionando Flathub e instalando apps ==="
  flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
  for app in "${FLATPAK_APPS[@]}"; do
    flatpak install -y flathub "$app" || echo "  [aviso] falha ao instalar flatpak: $app"
  done
}

install_acessos() {
  echo "=== Acessos (JMoratelli/acessos) ==="
  local api_url="https://api.github.com/repos/JMoratelli/acessos/releases/latest"
  local asset_url
  asset_url=$(curl -fsSL "$api_url" | grep -o '"browser_download_url": *"[^"]*\.flatpak"' | head -n1 | sed -E 's/.*"(https[^"]+)"/\1/')
  if [ -z "$asset_url" ]; then
    echo "  [aviso] nao encontrei o .flatpak mais recente, baixe manualmente em https://github.com/JMoratelli/acessos/releases"
    return
  fi
  local tmpfile
  tmpfile=$(mktemp --suffix=.flatpak)
  echo "  baixando $asset_url"
  curl -fsSL -o "$tmpfile" "$asset_url"
  flatpak install -y --user "$tmpfile" || flatpak install -y "$tmpfile" || \
    echo "  [aviso] falha ao instalar o bundle flatpak do Acessos"
  rm -f "$tmpfile"
}

install_vscode_extensions() {
  echo "=== VS Code: instalando extensoes ==="
  if ! command -v code >/dev/null 2>&1; then
    echo "  [aviso] comando 'code' nao encontrado, pulando extensoes."
    return
  fi
  for ext in "${VSCODE_EXTENSIONS[@]}"; do
    code --install-extension "$ext" || echo "  [aviso] falha ao instalar extensao: $ext"
  done
}

# ---------------------------------------------------------------------------
# CachyOS / Arch
# ---------------------------------------------------------------------------
run_cachy() {
  echo "=== Atualizando sistema ==="
  sudo pacman -Syu --noconfirm

  echo "=== Pacotes base para compilar (necessario para AUR) ==="
  sudo pacman -S --needed --noconfirm base-devel git cmake meson ccache

  echo "=== Instalando AUR helper (paru), se necessario ==="
  if ! command -v paru >/dev/null 2>&1 && ! command -v yay >/dev/null 2>&1; then
    tmpdir=$(mktemp -d)
    git clone https://aur.archlinux.org/paru-bin.git "$tmpdir/paru-bin"
    (cd "$tmpdir/paru-bin" && makepkg -si --noconfirm)
    rm -rf "$tmpdir"
  fi
  AUR_HELPER=$(command -v paru || command -v yay)

  echo "=== Navegadores ==="
  sudo pacman -S --needed --noconfirm firefox
  "$AUR_HELPER" -S --needed --noconfirm google-chrome

  echo "=== VS Code e ferramentas de desenvolvimento ==="
  "$AUR_HELPER" -S --needed --noconfirm visual-studio-code-bin
  sudo pacman -S --needed --noconfirm \
    github-cli \
    go rust \
    php php-cli \
    dotnet-sdk \
    nodejs npm yarn \
    mingw-w64-gcc \
    docker docker-compose \
    python python-pip
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"

  echo "=== Virtualizacao (QEMU/KVM completo) ==="
  sudo pacman -S --needed --noconfirm \
    qemu-full qemu-user-static \
    libvirt virt-manager virt-viewer \
    dnsmasq bridge-utils edk2-ovmf swtpm
  sudo systemctl enable --now libvirtd
  sudo usermod -aG libvirt "$USER"

  echo "=== Acesso remoto ==="
  "$AUR_HELPER" -S --needed --noconfirm anydesk-bin
  sudo pacman -S --needed --noconfirm remmina freerdp

  echo "=== Sincronizacao / nuvem ==="
  "$AUR_HELPER" -S --needed --noconfirm insync

  echo "=== Home Assistant agent ==="
  "$AUR_HELPER" -S --needed --noconfirm go-hass-agent

  echo "=== Hardware (perifericos / RGB / GPU) ==="
  sudo pacman -S --needed --noconfirm solaar
  "$AUR_HELPER" -S --needed --noconfirm openrgb corectrl

  echo "=== Impressao / scanner ==="
  sudo pacman -S --needed --noconfirm cups hplip simple-scan system-config-printer
  sudo systemctl enable --now cups
  sudo usermod -aG lp "$USER" 2>/dev/null || true

  echo "=== Firmware (fwupd) ==="
  sudo pacman -S --needed --noconfirm fwupd

  echo "=== Fontes e idioma pt-BR ==="
  sudo pacman -S --needed --noconfirm \
    noto-fonts noto-fonts-cjk noto-fonts-emoji \
    adobe-source-code-pro-fonts \
    ttf-liberation \
    hunspell hunspell-pt_br

  echo "=== Flatpak ==="
  sudo pacman -S --needed --noconfirm flatpak
  install_flatpak_apps
  install_acessos

  install_vscode_extensions
}

# ---------------------------------------------------------------------------
# Fedora
# ---------------------------------------------------------------------------
run_fedora() {
  echo "=== Atualizando sistema ==="
  sudo dnf upgrade --refresh -y

  echo "=== RPM Fusion (necessario para varios pacotes multimidia/terceiros) ==="
  sudo dnf install -y \
    "https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm" \
    "https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"

  echo "=== Navegadores ==="
  sudo dnf install -y https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm

  echo "=== VS Code (repositorio da Microsoft) ==="
  sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
  sudo sh -c 'echo -e "[code]\nname=Visual Studio Code\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\nenabled=1\ngpgcheck=1\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc" > /etc/yum.repos.d/vscode.repo'
  sudo dnf install -y code

  echo "=== Ferramentas de desenvolvimento ==="
  sudo dnf install -y \
    gh \
    golang rust cargo \
    php php-cli \
    dotnet-sdk-10.0 \
    nodejs npm yarnpkg \
    mingw64-gcc \
    docker-compose \
    cmake meson ccache \
    python3 python3-pip

  echo "=== Docker (repositorio oficial) ==="
  sudo dnf install -y dnf-plugins-core
  sudo dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo
  sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"

  echo "=== Virtualizacao (QEMU/KVM completo) ==="
  sudo dnf install -y \
    "@virtualization" \
    qemu-user-static \
    virt-manager virt-viewer \
    edk2-ovmf swtpm
  sudo systemctl enable --now libvirtd
  sudo usermod -aG libvirt "$USER"

  echo "=== Acesso remoto ==="
  sudo dnf install -y https://download.anydesk.com/linux/anydesk-6.4.0-1.fc38.x86_64.rpm || \
    echo "  [aviso] verifique a versao mais recente do AnyDesk em https://anydesk.com/en/downloads/linux"
  sudo dnf install -y remmina freerdp

  echo "=== Sincronizacao / nuvem (Insync) ==="
  sudo rpm --import https://d2t3ff60b2tol4.cloudfront.net/repomd.xml.key 2>/dev/null || true
  echo "  [aviso] confirme o repo atual do Insync em https://www.insynchq.com/downloads e adicione antes de instalar"

  echo "=== Home Assistant agent ==="
  echo "  [aviso] baixe o .rpm mais recente em https://github.com/joshuar/go-hass-agent/releases e instale com 'sudo dnf install ./go-hass-agent-*.rpm'"

  echo "=== Hardware (perifericos / RGB / GPU) ==="
  sudo dnf install -y solaar openrgb corectrl || \
    echo "  [aviso] openrgb/corectrl podem nao estar no repo padrao, considere Flatpak"

  echo "=== Impressao / scanner ==="
  sudo dnf install -y cups hplip simple-scan system-config-printer
  sudo systemctl enable --now cups

  echo "=== Firmware (fwupd) ==="
  sudo dnf install -y fwupd

  echo "=== Fontes e idioma pt-BR ==="
  sudo dnf install -y \
    google-noto-emoji-fonts google-noto-sans-cjk-fonts \
    adobe-source-code-pro-fonts \
    hunspell hunspell-pt-BR

  echo "=== Flatpak ==="
  sudo dnf install -y flatpak
  install_flatpak_apps
  install_acessos

  install_vscode_extensions
}

# ---------------------------------------------------------------------------
# Debian / Ubuntu
# ---------------------------------------------------------------------------
run_debian() {
  echo "=== Atualizando sistema ==="
  sudo apt update && sudo apt upgrade -y

  sudo apt install -y curl wget gpg ca-certificates apt-transport-https software-properties-common

  echo "=== Google Chrome ==="
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
  sudo apt update && sudo apt install -y google-chrome-stable

  echo "=== VS Code ==="
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/packages.microsoft.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" | sudo tee /etc/apt/sources.list.d/vscode.list
  sudo apt update && sudo apt install -y code

  echo "=== Ferramentas de desenvolvimento ==="
  type -p gh >/dev/null || {
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
    sudo apt update
  }
  sudo apt install -y \
    gh \
    golang rustc cargo \
    php php-cli \
    dotnet-sdk-8.0 \
    nodejs npm \
    mingw-w64 \
    cmake meson ccache \
    python3 python3-pip
  sudo npm install -g yarn

  echo "=== Docker (repositorio oficial) ==="
  curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list
  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"

  echo "=== Virtualizacao (QEMU/KVM completo) ==="
  sudo apt install -y \
    qemu-system qemu-user-static \
    libvirt-daemon-system libvirt-clients \
    virt-manager virt-viewer \
    ovmf swtpm
  sudo systemctl enable --now libvirtd
  sudo usermod -aG libvirt "$USER"

  echo "=== Acesso remoto ==="
  wget -O /tmp/anydesk.deb https://download.anydesk.com/linux/anydesk_6.4.0-1_amd64.deb || \
    echo "  [aviso] verifique a versao mais recente em https://anydesk.com/en/downloads/linux"
  sudo apt install -y /tmp/anydesk.deb 2>/dev/null || true
  sudo apt install -y remmina freerdp2-x11

  echo "=== Sincronizacao / nuvem (Insync) ==="
  echo "  [aviso] siga as instrucoes atuais em https://www.insynchq.com/downloads para adicionar o repo apt do Insync"

  echo "=== Home Assistant agent ==="
  echo "  [aviso] baixe o .deb mais recente em https://github.com/joshuar/go-hass-agent/releases e instale com 'sudo apt install ./go-hass-agent_*.deb'"

  echo "=== Hardware (perifericos / RGB / GPU) ==="
  sudo apt install -y solaar || echo "  [aviso] solaar pode precisar de backports"
  echo "  [aviso] openrgb e corectrl geralmente ficam desatualizados no apt; considere Flatpak ou build manual"

  echo "=== Impressao / scanner ==="
  sudo apt install -y cups hplip simple-scan system-config-printer
  sudo systemctl enable --now cups

  echo "=== Firmware (fwupd) ==="
  sudo apt install -y fwupd

  echo "=== Fontes e idioma pt-BR ==="
  sudo apt install -y \
    fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
    fonts-adobe-source-code-pro \
    hunspell hunspell-pt-br

  echo "=== Flatpak ==="
  sudo apt install -y flatpak
  install_flatpak_apps
  install_acessos

  install_vscode_extensions
}

case "$DISTRO" in
  cachy)  run_cachy ;;
  fedora) run_fedora ;;
  debian) run_debian ;;
esac

echo ""
echo "======================================"
echo " Concluido."
echo " Reinicie a sessao para aplicar os grupos (docker/libvirt/lp)."
echo " Itens que pedem verificacao manual: Insync (repo), go-hass-agent"
echo " (release), AnyDesk (versao do pacote), OpenRGB/CoreCtrl no Fedora/Debian."
echo "======================================"
