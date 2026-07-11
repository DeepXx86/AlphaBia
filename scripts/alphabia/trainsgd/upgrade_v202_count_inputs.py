#!/usr/bin/python3
"""
Upgrade a version-201 Makruk checkpoint to version 202 (explicit counting-rule inputs).

V202 adds real input signal on global channels 32-49, which were always zero under V201.
The model's linear_global layer already has weight columns for those channels, but they
were never trained (zero input -> zero gradient), so whatever is in them is noise.
This script zeroes exactly those columns in the model (and swa_model / optimizer moments),
then stamps the checkpoint config as version 202.

Result: the upgraded model's outputs are BIT-IDENTICAL to the old model on every position
until training resumes, at which point the new count features start learning from zero.
Safe, no strength regression possible at the moment of surgery.

Usage (training must be stopped):
  python3 upgrade_v202_count_inputs.py -checkpoint /root/mk192/data/train/az192/checkpoint.ckpt

A .pre_v202.bak backup of the checkpoint is written next to it first.
"""
import argparse
import shutil
import torch

NEW_CHANNELS = slice(32, 50)  # global input channels 32..49 used by V202

parser = argparse.ArgumentParser()
parser.add_argument('-checkpoint', required=True, help='checkpoint.ckpt to upgrade in place')
args = vars(parser.parse_args())
path = args["checkpoint"]

data = torch.load(path, map_location="cpu", weights_only=False)

assert "config" in data, "checkpoint has no config dict"
config = data["config"]
version = config["version"]
if version == 202:
    print("Checkpoint is already version 202; nothing to do.")
    raise SystemExit(0)
assert version == 201, f"expected version 201 checkpoint, got {version}"

def find_linear_global_key(state_dict):
    keys = [k for k in state_dict if k.endswith("linear_global.weight")]
    assert len(keys) == 1, f"expected exactly one linear_global.weight, found {keys}"
    return keys[0]

backup = path + ".pre_v202.bak"
shutil.copy2(path, backup)
print(f"Backup written: {backup}")

# 1. main model weights
key = find_linear_global_key(data["model"])
w = data["model"][key]
assert w.dim() == 2 and w.shape[1] == 64, f"unexpected linear_global shape {tuple(w.shape)}"
before = w[:, NEW_CHANNELS].abs().sum().item()
w[:, NEW_CHANNELS] = 0.0
print(f"model.{key}: zeroed cols 32-49 (abs sum was {before:.6f})")
lg_shape = tuple(w.shape)

# 2. swa model, if present
if "swa_model" in data and data["swa_model"] is not None:
    skey = find_linear_global_key(data["swa_model"])
    sw = data["swa_model"][skey]
    sbefore = sw[:, NEW_CHANNELS].abs().sum().item()
    sw[:, NEW_CHANNELS] = 0.0
    print(f"swa_model.{skey}: zeroed cols 32-49 (abs sum was {sbefore:.6f})")

# 3. optimizer moments for that parameter (matched by shape; linear_global is the
#    only 2D [trunk_channels, 64] parameter in these nets)
if "optimizer" in data and data["optimizer"] is not None:
    n = 0
    for pstate in data["optimizer"].get("state", {}).values():
        for name, t in pstate.items():
            if torch.is_tensor(t) and t.dim() == 2 and tuple(t.shape) == lg_shape:
                t[:, NEW_CHANNELS] = 0.0
                n += 1
    print(f"optimizer: zeroed cols in {n} moment tensor(s) of shape {lg_shape}")

# 4. stamp the new version
config["version"] = 202
data["config"] = config
torch.save(data, path)
print(f"Saved upgraded checkpoint: {path}")
print("Config version is now 202. Next export will produce a V202 model that the engine")
print("feeds explicit Makruk count features (global channels 32-49).")
