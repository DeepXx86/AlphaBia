#!/usr/bin/env python3
import argparse, os, sys, torch

# idk is this script real work because i test but lazy to make az256 more better but it not too stupid it might need more time
_here = os.path.dirname(os.path.abspath(__file__))
_trainsgd = os.path.join(_here, '..', 'scripts', 'alphabia', 'trainsgd')
sys.path.insert(0, _trainsgd if os.path.isdir(_trainsgd) else _here)
import modelconfigs
from model_pytorch import Model

p = argparse.ArgumentParser(description="Expand a KataGo checkpoint to a bigger architecture, preserving play exactly.")
p.add_argument('-checkpoint', required=True)
p.add_argument('-output', required=True)
p.add_argument('-new-kind', default='b20c256')
p.add_argument('-pos-len', type=int, default=8)
args = p.parse_args()

ckpt = torch.load(args.checkpoint, map_location='cpu', weights_only=False)
old_sd = ckpt['model']
old_cfg = ckpt['config']
stock_new = modelconfigs.config_of_name[args.new_kind]
new_cfg = dict(old_cfg)
for k in ('block_kind', 'trunk_num_channels', 'mid_num_channels'):
    new_cfg[k] = stock_new[k]
    print(f"config override: {k}")

tmpl_model = Model(new_cfg, args.pos_len)
tmpl_model.initialize()
new_sd = tmpl_model.state_dict()

n_old_blocks = sum(1 for k in old_sd if k.startswith('blocks.') and k.endswith('normactconv1.norm.beta'))
n_new_blocks = sum(1 for k in new_sd if k.startswith('blocks.') and k.endswith('normactconv1.norm.beta'))
print(f"blocks {n_old_blocks} -> {n_new_blocks}")

copied = padded = fresh = 0
for key in new_sd:
    nt = new_sd[key]
    if key in old_sd:
        ot = old_sd[key]
        if tuple(ot.shape) == tuple(nt.shape):
            new_sd[key] = ot.clone()
            copied += 1
        else:
            if len(ot.shape) != len(nt.shape):
                raise RuntimeError(f"rank mismatch {key}: {ot.shape} vs {nt.shape}")
            out = nt.clone()
            sl = tuple(slice(0, s) for s in ot.shape)
            out[sl] = ot
            if len(ot.shape) >= 2 and nt.shape[1] > ot.shape[1]:
                z = [slice(0, ot.shape[0]), slice(ot.shape[1], nt.shape[1])] + \
                    [slice(None)] * (len(ot.shape) - 2)
                out[tuple(z)] = 0.0
            new_sd[key] = out
            padded += 1
            print(f"  padded {key}: {tuple(ot.shape)} -> {tuple(nt.shape)}")
    else:
        fresh += 1

for i in range(n_old_blocks, n_new_blocks):
    k = f"blocks.{i}.normactconv2.conv.weight"
    if k in new_sd:
        new_sd[k] = torch.zeros_like(new_sd[k])
        print(f"  identity block {i}: zeroed {k}")

print(f"copied={copied} padded={padded} fresh={fresh}")

ckpt['model'] = new_sd
ckpt['config'] = new_cfg
ckpt.pop('optimizer', None)
ckpt.pop('swa_model', None)
torch.save(ckpt, args.output)
print(f"saved {args.output}")
