# Xense-Pico Teleop Interface

Pico teleop interface SDK for XenseVR PC Service in Python.

## Overview

This project provides a teleop interface SDK for XenseVR PC Service.

## Installation

1. Download and install [XenseVR PC Service](https://github.com/Vertax42/XRoboToolkit-PC-Service). Run the installed program before running the following demo.

2. **Clone the repository:**

    ```bash
    git clone https://github.com/Vertax42/Xense-Pico-Teleop-Interface.git
    cd Xense-Pico-Teleop-Interface
    ```

3. **Installation**

    **Note:** The setup scripts are currently only tested on Ubuntu 22.04.
    It is recommended to setup a Conda/Mamba environment and install the project using the included setup script. Highly recommended to use Mamba for faster installation.

    ```bash
    bash setup_env.sh --mamba <optional_env_name>
    mamba activate <optional_env_name>
    bash setup_env.sh --install
    ```

    Or using Conda, you can use the following command:

    ```bash
    bash setup_env.sh --conda <optional_env_name>
    conda activate <optional_env_name>
    bash setup_env.sh --install
    ```

## Usage

Use the following instructions to run example scripts. 

**Example:** [ARX Dual Arm Data Converter](https://github.com/zhigenzhao/openpi/blob/dev/finetuning/examples/arx_r5/arx_dual/convert_dual_arm_data_to_lerobot.py)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
