#!/usr/bin/python3
"""V202 -> V203: activate the rules-exact mate oracle inputs.
Zeroes never-trained input weights (global cols 2-5, spatial in-channel 39) in
model + swa + optimizer moments, then stamps config version 203.
Model output is bit-identical until training resumes. Backup kept.
Run only while training is STOPPED."""
import argparse
import shutil
import torch

GLOBAL_COLS = [2, 3, 4, 5]
SPATIAL_CH = 39

parser = argparse.ArgumentParser()
parser.add_argument('-checkpoint', required=True)
args = vars(parser.parse_args())
path = args["checkpoint"]

data = torch.load(path, map_location="cpu", weights_only=False)
config = data["config"]
version = config["version"]
if version == 203:
    print("Already version 203; nothing to do.")
    raise SystemExit(0)
assert version == 202, f"expected version 202 checkpoint, got {version}"

def find_key(sd, suffix):
    keys = [k for k in sd if k.endswith(suffix)]
    assert len(keys) == 1, (suffix, keys)
    return keys[0]

backup = path + ".pre_v203.bak"
shutil.copy2(path, backup)
print(f"Backup: {backup}")

shapes = []
for name in ["model", "swa_model"]:
    if name not in data or data[name] is None:
        continue
    sd = data[name]
    lg = sd[find_key(sd, "linear_global.weight")]
    cs = sd[find_key(sd, "conv_spatial.weight")]
    a = sum(float(lg[:, c].abs().sum()) for c in GLOBAL_COLS)
    b = float(cs[:, SPATIAL_CH].abs().sum())
    for c in GLOBAL_COLS:
        lg[:, c] = 0.0
    cs[:, SPATIAL_CH] = 0.0
    shapes.append((tuple(lg.shape), tuple(cs.shape)))
    print(f"{name}: zeroed linear_global cols {GLOBAL_COLS} (abs {a:.4f}), conv_spatial ch {SPATIAL_CH} (abs {b:.4f})")

if "optimizer" in data and data["optimizer"] is not None:
    n = 0
    lg_shape, cs_shape = shapes[0]
    for pstate in data["optimizer"].get("state", {}).values():
        for t in pstate.values():
            if not torch.is_tensor(t):
                continue
            if t.dim() == 2 and tuple(t.shape) == lg_shape:
                for c in GLOBAL_COLS:
                    t[:, c] = 0.0
                n += 1
            elif t.dim() == 4 and tuple(t.shape) == cs_shape:
                t[:, SPATIAL_CH] = 0.0
                n += 1
    print(f"optimizer: zeroed {n} moment tensor(s)")

config["version"] = 203
data["config"] = config
torch.save(data, path)
print(f"Saved: {path} (version 203)")
