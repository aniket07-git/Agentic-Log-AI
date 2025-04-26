#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
ENV_NAME="log_gen_env"
PYTHON_VERSION="3.10" # Choose a desired Python version
MINICONDA_DIR="$HOME/miniconda3"
INSTALLER_NAME="" # Will be set based on OS

# --- Detect OS and Architecture ---
OS_TYPE=$(uname)
echo "Detected OS: $OS_TYPE"

if [[ "$OS_TYPE" == "Linux" ]]; then
    ARCH=$(uname -m) # e.g., x86_64
    echo "Detected Architecture: $ARCH"
    # Assuming x86_64 for Linux, add checks for others (aarch64) if needed
    if [[ "$ARCH" == "x86_64" ]]; then
        INSTALLER_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
        INSTALLER_NAME="Miniconda3-latest-Linux-x86_64.sh"
    else
        echo "Unsupported Linux architecture: $ARCH. Please download Miniconda manually."
        exit 1
    fi
elif [[ "$OS_TYPE" == "Darwin" ]]; then # macOS
    ARCH=$(uname -m) # arm64 (Apple Silicon) or x86_64 (Intel)
    echo "Detected Architecture: $ARCH"
    if [[ "$ARCH" == "arm64" ]]; then # Apple Silicon
        INSTALLER_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh"
        INSTALLER_NAME="Miniconda3-latest-MacOSX-arm64.sh"
    elif [[ "$ARCH" == "x86_64" ]]; then # Intel Mac
        INSTALLER_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
        INSTALLER_NAME="Miniconda3-latest-MacOSX-x86_64.sh"
    else
        echo "Unsupported macOS architecture: $ARCH. Please download Miniconda manually."
        exit 1
    fi
else
    echo "Unsupported Operating System: $OS_TYPE. Please install Miniconda manually."
    exit 1
fi

# --- Check if Miniconda is already installed ---
if [ -d "$MINICONDA_DIR" ]; then
    echo "Miniconda seems to be installed in '$MINICONDA_DIR'. Skipping installation."
else
    echo "Miniconda not found in '$MINICONDA_DIR'."
    # --- Download Miniconda Installer ---
    if [ -f "$INSTALLER_NAME" ]; then
        echo "Miniconda installer '$INSTALLER_NAME' already exists. Skipping download."
    else
        echo "Downloading Miniconda installer from $INSTALLER_URL..."
        # Use curl or wget depending on availability
        if command -v curl &> /dev/null; then
            curl -L "$INSTALLER_URL" -o "$INSTALLER_NAME"
        elif command -v wget &> /dev/null; then
            wget "$INSTALLER_URL" -O "$INSTALLER_NAME"
        else
            echo "Error: Neither curl nor wget found. Please install one of them."
            exit 1
        fi
        echo "Download complete."
    fi

    # --- Install Miniconda ---
    echo "Installing Miniconda to '$MINICONDA_DIR'..."
    # -b: Batch mode (no prompts)
    # -p: Installation prefix/path
    bash "$INSTALLER_NAME" -b -p "$MINICONDA_DIR"

    echo "Miniconda installation complete."
    echo "Cleaning up installer..."
    rm "$INSTALLER_NAME"
fi

# --- Set up Conda Environment ---
# Source the conda script to make 'conda' command available in this script session
echo "Initializing conda for this script session..."
source "$MINICONDA_DIR/etc/profile.d/conda.sh"

# Check if the environment already exists
if conda env list | grep -q "^$ENV_NAME\s"; then
    echo "Conda environment '$ENV_NAME' already exists. Skipping creation."
else
    echo "Creating conda environment '$ENV_NAME' with Python $PYTHON_VERSION..."
    conda create --name "$ENV_NAME" python="$PYTHON_VERSION" -y
    echo "Environment '$ENV_NAME' created successfully."
fi

# --- No Packages to Install ---
# The provided Python code uses only standard libraries.
# If dependencies were needed, you would add:
# echo "Activating environment '$ENV_NAME' to install packages..."
# conda activate "$ENV_NAME"
# echo "Installing required packages..."
# pip install package1 package2  # Or: conda install package1 package2 -y
# echo "Deactivating environment..."
# conda deactivate

# --- Final Instructions ---
echo ""
echo "--------------------------------------------------"
echo "Setup Complete!"
echo "--------------------------------------------------"
echo ""
echo "Miniconda is installed at: $MINICONDA_DIR"
echo "A conda environment named '$ENV_NAME' has been created (or verified)."
echo ""
echo "**IMPORTANT:** To use the environment in your terminal, you first need to activate it:"
echo ""
echo "For bash/zsh shells, run:"
echo "  conda activate $ENV_NAME"
echo ""
echo "(You might need to run 'conda init' once and restart your shell if the 'conda activate' command is not found initially)"
echo ""
echo "Once activated, you can run the simulation script from the 'log_generator_repo' directory:"
echo "  python simulate.py"
echo ""
echo "To deactivate the environment when you are finished, run:"
echo "  conda deactivate"
echo ""

exit 0