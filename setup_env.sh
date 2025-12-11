#!/bin/bash

# Check the operating system
OS_NAME=$(uname -s)
OS_VERSION=""

if [[ "$OS_NAME" == "Linux" ]]; then
    if command -v lsb_release &>/dev/null; then
        OS_VERSION=$(lsb_release -rs)
    elif [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_VERSION=$VERSION_ID
    fi
    if [[ "$OS_VERSION" != "22.04" && "$OS_VERSION" != "24.04" ]]; then
        echo "Warning: This script has only been tested on Ubuntu 22.04 and 24.04"
        echo "Your system is running Ubuntu $OS_VERSION."
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            exit 1
        fi
    fi
else
    echo "Unsupported operating system: $OS_NAME"
    exit 1
fi

echo "Operating system check passed: $OS_NAME $OS_VERSION"

# Function to create environment
create_environment() {
    local CONDA_CMD=$1
    local ENV_NAME=$2

    # Detect the system's default Python version
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1)
    elif command -v python &>/dev/null; then
        PYTHON_VERSION=$(python --version 2>&1)
    else
        echo "Python is not installed on this system."
        exit 1
    fi

    echo "The system's default Python version is: $PYTHON_VERSION"

    # Extract the major and minor version numbers from the Python version string
    PYTHON_MAJOR_MINOR=$(echo $PYTHON_VERSION | grep -oP '\d+\.\d+')

    # Deactivate current environment if any (use conda deactivate for both conda and mamba)
    conda deactivate 2>/dev/null || true

    # Remove existing environment if it exists
    if $CONDA_CMD env list | grep -q "^$ENV_NAME "; then
        echo "Removing existing environment '$ENV_NAME'..."
        $CONDA_CMD env remove -n "$ENV_NAME" -y
    fi

    # Create new environment
    $CONDA_CMD create -n "$ENV_NAME" python=$PYTHON_MAJOR_MINOR -y

    echo "$CONDA_CMD environment '$ENV_NAME' created with Python $PYTHON_MAJOR_MINOR"

    echo -e "[INFO] Created $CONDA_CMD environment named '$ENV_NAME'.\n"
    echo -e "\t\t1. To activate the environment, run:                $CONDA_CMD activate $ENV_NAME"
    echo -e "\t\t2. To install the package, run:                     bash setup_env.sh --install"
    echo -e "\t\t3. To deactivate the environment, run:              conda deactivate"
    echo -e "\n"
}

# Check if an environment name is provided
if [[ -n "$2" ]]; then
    ENV_NAME="$2"
else
    ENV_NAME="xense_pico_teleop"
fi

# Check if the --conda parameter is passed
if [[ "$1" == "--conda" ]]; then
    # Initialize conda
    if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        . "$HOME/miniconda3/etc/profile.d/conda.sh"
    elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        . "$HOME/anaconda3/etc/profile.d/conda.sh"
    else
        echo "Conda initialization script not found. Please install Miniconda3 or Anaconda3 or Miniforge3."
        exit 1
    fi
    create_environment "conda" "$ENV_NAME"

# Check if the --mamba parameter is passed
elif [[ "$1" == "--mamba" ]]; then
    # Initialize mamba (miniforge)
    if [ -f "$HOME/miniforge3/etc/profile.d/conda.sh" ]; then
        . "$HOME/miniforge3/etc/profile.d/conda.sh"
    elif [ -f "$HOME/mambaforge/etc/profile.d/conda.sh" ]; then
        . "$HOME/mambaforge/etc/profile.d/conda.sh"
    else
        echo "Mamba initialization script not found. Please install Miniforge3 or Mambaforge."
        exit 1
    fi
    # Also source mamba.sh if available for full mamba support
    if [ -f "$HOME/miniforge3/etc/profile.d/mamba.sh" ]; then
        . "$HOME/miniforge3/etc/profile.d/mamba.sh"
    elif [ -f "$HOME/mambaforge/etc/profile.d/mamba.sh" ]; then
        . "$HOME/mambaforge/etc/profile.d/mamba.sh"
    fi
    create_environment "mamba" "$ENV_NAME"

# Check if the --install parameter is passed
elif [[ "$1" == "--install" ]]; then
    # Get the currently activated conda environment name
    if [[ -z "${CONDA_DEFAULT_ENV}" ]]; then
        echo "Error: No conda/mamba environment is currently activated."
        echo "Please activate an environment first with: conda/mamba activate <env_name>"
        exit 1
    fi
    ENV_NAME=${CONDA_DEFAULT_ENV}

    # Detect conda/mamba command
    if [ -f "$HOME/miniforge3/etc/profile.d/conda.sh" ]; then
        CONDA_CMD="mamba"
    else
        CONDA_CMD="conda"
    fi

    # replace conda c++ dependency with libstdcxx-ng
    if [[ "$OS_NAME" == "Linux" ]]; then
        $CONDA_CMD install -c conda-forge pybind11 libstdcxx-ng -y
    fi
    pip install uv
    uv pip install --upgrade pip

    # Save the project root directory
    PROJECT_ROOT=$(pwd)
    PYBIND_DIR="$PROJECT_ROOT/xensevr-pc-service-pybind"

    # Install the required packages
    cd "$PYBIND_DIR"
    mkdir -p dependencies
    cd dependencies

    # Clone if not already cloned
    if [ ! -d "XenseVR-PC-Service" ]; then
        git clone https://github.com/Vertax42/XenseVR-PC-Service.git
    fi

    cd XenseVR-PC-Service/RoboticsService/PXREARobotSDK
    bash build.sh

    # Go back to pybind directory
    cd "$PYBIND_DIR"
    mkdir -p lib
    mkdir -p include

    # Copy files from the cloned repo
    SDK_DIR="$PYBIND_DIR/dependencies/XenseVR-PC-Service/RoboticsService/PXREARobotSDK"
    cp "$SDK_DIR/PXREARobotSDK.h" include/
    cp -r "$SDK_DIR/nlohmann" include/
    cp "$SDK_DIR/build/libPXREARobotSDK.so" lib/

    pip uninstall -y xensevr_pc_service_sdk 2>/dev/null || true
    python setup.py install

    # Go back to project root and install main package
    cd "$PROJECT_ROOT"
    uv pip install -e . || { echo "Failed to install xensepico_teleop with pip"; exit 1; }

    echo -e "\n"
    echo -e "[INFO] xensepico_teleop is installed in $CONDA_CMD environment '$ENV_NAME'.\n"
    echo -e "\n"
else
    echo "Invalid argument. Usage:"
    echo "  --conda [env_name]   Create a conda environment (requires Miniconda/Anaconda)"
    echo "  --mamba [env_name]   Create a mamba environment (requires Miniforge)"
    echo "  --install            Install the package in the currently activated environment"
    exit 1
fi