#!/usr/bin/env bash
set -e
export DEBIAN_FRONTEND=noninteractive

echo "build deps.."
apt-get update -qq
apt-get install -y -qq build-essential cmake git wget zlib1g-dev libzip-dev libeigen3-dev python3 python3-pip python3-venv >/dev/null
cmake --version | head -1
gcc --version | head -1

echo "get cuda.."
cd /tmp
wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb -O cuda-keyring.deb
dpkg -i cuda-keyring.deb >/dev/null 2>&1 || true
apt-get update -qq

echo "install cuda.."
apt-get install -y -qq cuda-nvcc-12-4 cuda-cudart-dev-12-4 libcublas-dev-12-4 cuda-nvrtc-dev-12-4 cuda-cccl-12-4 2>&1 | tail -2
/usr/local/cuda-12.4/bin/nvcc --version | tail -2

echo "KataGo 1.12 compatible.."
apt-get install -y -qq libcudnn8 libcudnn8-dev 2>&1 | tail -2
echo "cudnn header: $(ls /usr/include/cudnn.h /usr/include/x86_64-linux-gnu/cudnn.h 2>/dev/null | head -1 || echo MISSING)"
grep -h CUDNN_MAJOR /usr/include/cudnn_version.h /usr/include/x86_64-linux-gnu/cudnn_version.h 2>/dev/null | head -1 || true

echo "setup venv :)"
python3 -m venv /root/mktorch
/root/mktorch/bin/pip install -q --upgrade pip
/root/mktorch/bin/pip install -q numpy packaging torch --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -2
/root/mktorch/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

echo "SETUP_DONE"
