#!/bin/bash
# ==============================================================================
# Throttnux Environment Initialization & Dependency Validation Script
# System Requirements: Linux-based OS with Bash 4.0+
# ==============================================================================

PKG_NAME="throttnux"

# Core dependencies
CHECK_DEPS="tc dsniff arp-scan figlet"
REQUIRED_DEPS="iproute2 dsniff arp-scan figlet"
REQUIRED_PY_DEPS="psutil"
HAVE_MISSING_DEPS=0
HAVE_PY_MISSING_DEPS=0

PYTHON=""

# ------------------------------------------------------------------------------
# Terminal UI Configuration
# ------------------------------------------------------------------------------
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

FG_CYAN='\033[36m'
FG_GREEN='\033[32m'
FG_RED='\033[31m'
FG_YELLOW='\033[33m'

BG_INFO='\033[44;97;1m INFO \033[0m'
BG_DONE='\033[42;30;1m DONE \033[0m'
BG_WARN='\033[43;30;1m WARN \033[0m'
BG_FAIL='\033[41;97;1m FAIL \033[0m'
BG_INPUT='\033[46;30;1m INPUT \033[0m'

# ------------------------------------------------------------------------------
# Output Interface
# ------------------------------------------------------------------------------
log_info()    { echo -e "${BG_INFO} $1"; }
log_success() { echo -e "${BG_DONE} ${FG_GREEN}$1${NC}"; }
log_warn()    { echo -e "${BG_WARN} ${FG_YELLOW}$1${NC}"; }
log_fail()    { echo -e "${BG_FAIL} ${FG_RED}$1${NC}" >&2; }
log_prompt()  { echo -n -e "\n${BG_INPUT} ${BOLD}$1${NC}"; }

# ------------------------------------------------------------------------------
# Privilege Verification
# ------------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    echo ""
    log_fail "Administrative privileges required. Please execute via 'sudo'."
    echo ""
    exit 1
fi

cd "$(dirname "$0")" || exit 1

# ------------------------------------------------------------------------------
# Environment Auditing
# ------------------------------------------------------------------------------
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        PYTHON=python3
    elif command -v python >/dev/null 2>&1; then
        PYTHON=python
    else
        log_fail "Python runtime environment could not be resolved."
    fi
}

check_deps() {
    log_info "Evaluating core system dependencies..."
    echo -e "${DIM}──────────────────────────────────────────────────${NC}"

    for dep in $CHECK_DEPS; do
        local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
        for i in {1..2}; do
            for j in {0..9}; do
                printf "\r  ${FG_CYAN}%c${NC} Verifying module: ${BOLD}%s${NC}..." "${spinstr:$j:1}" "$dep"
                sleep 0.02
            done
        done

        path="$(command -v "$dep" 2>/dev/null)"
        if [ -n "$path" ]; then
            printf "\r  ${FG_GREEN}✔${NC} Verified  ${BOLD}%-12s${NC} ${DIM}➔ %s${NC}\n" "$dep" "$path"
        else
            printf "\r  ${FG_RED}✖${NC} Missing   ${FG_RED}${BOLD}%-12s${NC} ${DIM}➔ Resolution failed${NC}\n" "$dep"
            HAVE_MISSING_DEPS=1
        fi
    done
    echo -e "${DIM}──────────────────────────────────────────────────${NC}"
    unset path
}

check_py_deps() {
    log_info "Evaluating Python environment packages..."
    echo -e "${DIM}──────────────────────────────────────────────────${NC}"
    
    for pydep in $REQUIRED_PY_DEPS; do
        local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
        for i in {1..2}; do
            for j in {0..9}; do
                printf "\r  ${FG_CYAN}%c${NC} Verifying package: ${BOLD}%-10s${NC}..." "${spinstr:$j:1}" "$pydep"
                sleep 0.02
            done
        done

        # Validate against virtual environment if present
        if [ -f ".venv/bin/python3" ]; then
            if ! ./.venv/bin/python3 -c "import $pydep" 2>/dev/null; then
                printf "\r  ${FG_RED}✖${NC} Missing   ${FG_RED}${BOLD}%-12s${NC} ${DIM}➔ Resolution failed${NC}\n" "$pydep"
                HAVE_PY_MISSING_DEPS=1
            else
                printf "\r  ${FG_GREEN}✔${NC} Verified  ${BOLD}%-12s${NC} ${DIM}➔ Resolved${NC}\n" "$pydep"
            fi
        else
            if ! $PYTHON -c "import $pydep" 2>/dev/null; then
                printf "\r  ${FG_RED}✖${NC} Missing   ${FG_RED}${BOLD}%-12s${NC} ${DIM}➔ Resolution failed${NC}\n" "$pydep"
                HAVE_PY_MISSING_DEPS=1
            else
                printf "\r  ${FG_GREEN}✔${NC} Verified  ${BOLD}%-12s${NC} ${DIM}➔ Resolved${NC}\n" "$pydep"
            fi
        fi
    done
    echo -e "${DIM}──────────────────────────────────────────────────${NC}"
}

# ------------------------------------------------------------------------------
# Package Management
# ------------------------------------------------------------------------------
install_pkg() {
    pkgs="$*"
    
    if command -v dnf >/dev/null 2>&1; then
        log_info "Package manager resolved: ${BOLD}dnf${NC}"
        dnf install -y $pkgs
    elif command -v pacman >/dev/null 2>&1; then
        log_info "Package manager resolved: ${BOLD}pacman${NC}"
        pacman -Syu --noconfirm $pkgs
    elif command -v apt-get >/dev/null 2>&1; then
        log_info "Package manager resolved: ${BOLD}apt${NC}"
        apt-get update
        apt-get install -y $pkgs
    elif command -v zypper >/dev/null 2>&1; then
        log_info "Package manager resolved: ${BOLD}zypper${NC}"
        zypper install -y $pkgs
    else
        log_fail "Package manager unsupported. Manual installation required."
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Main Execution Flow
# ------------------------------------------------------------------------------
run() {
    clear
    echo -e "${FG_CYAN}┌────────────────────────────────────────────────┐${NC}"
    echo -e "${FG_CYAN}│${NC}          ${BOLD}${FG_CYAN}THROTTNUX${NC} ${DIM}- Environment Setup${NC}         ${FG_CYAN}│${NC}"
    echo -e "${FG_CYAN}└────────────────────────────────────────────────┘${NC}"
    echo ""

    log_info "Initiating deployment environment validation..."
    echo ""

    check_python
    if [ -z "$PYTHON" ]; then
        log_prompt "Python v3 runtime is required. Deploy runtime? (Y/n): "
        read -r proceed

        if [ "$proceed" = 'y' ] || [ "$proceed" = 'Y' ] || [ "$proceed" = '' ]; then
            echo ""
            install_pkg python3 || install_pkg python
            check_python
        else
            echo ""
            log_fail "Initialization aborted. Python dependency unfulfilled."
            exit 1
        fi
        unset proceed
    fi

    check_deps
    if [ "$HAVE_MISSING_DEPS" -eq 1 ]; then
        log_prompt "Required binaries are missing. Automate system setup? (Y/n): "
        read -r proceed

        if [ "$proceed" = 'y' ] || [ "$proceed" = 'Y' ] || [ "$proceed" = '' ]; then
            echo ""
            install_pkg $REQUIRED_DEPS
        else
            echo ""
            log_fail "Initialization aborted. System binaries unfulfilled."
            exit 1
        fi
        unset proceed
    fi

    echo -e "${FG_CYAN}${BG_INFO} Setting up isolated Python Virtual Environment...${NC}"
    
    # Verify venv module availability (Debian/Ubuntu fix)
    if ! $PYTHON -m venv -h >/dev/null 2>&1; then
        echo ""
        log_warn "Python 'venv' module is missing from the system core."
        log_info "Attempting to resolve the dependency automatically..."
        install_pkg python3-venv
    fi

    if [ ! -d ".venv" ]; then
        $PYTHON -m venv .venv
    fi

    echo "Installing Python dependencies inside environment..."
    ./.venv/bin/pip install --upgrade pip
    ./.venv/bin/pip install $REQUIRED_PY_DEPS

    if [ $? -ne 0 ]; then
        echo ""
        log_fail "Initialization aborted. Environment library extension unfulfilled."
        exit 1
    fi

    # Restore .venv ownership to the original non-root user
    if [ -n "$SUDO_USER" ]; then
        chown -R "$SUDO_USER":"$SUDO_USER" .venv
    fi

    echo ""
    check_py_deps

    echo ""
    log_success "Environment initialization finalized successfully."
    echo "Operational state ready. You can now run: sudo .venv/bin/python3 main.py"
}

run