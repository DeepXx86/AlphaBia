#!/usr/bin/env bash
# One-time V203 activation. Run with training STOPPED, then start training normally.
set -u
CFG=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src/scripts_makruk/makruk_selfplay_alphazero.cfg
CKPT=/root/mk192/data/train/az192/checkpoint.ckpt

RUNNING=$(ps -eo pgid,cmd | grep '[u]buntu_alphazero_train' | wc -l)
if [ "$RUNNING" -gt 0 ]; then
  echo "REFUSING: training loop is running. Stop it first (bash /root/stop_train.sh)."
  exit 1
fi

export PATH=/root/mktorch/bin:$PATH
python3 /mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src/scripts/alphabia/trainsgd/upgrade_v203_mate_inputs.py -checkpoint "$CKPT" || exit 1

sed -i 's/^inputsVersion = 202$/inputsVersion = 203/' "$CFG"
grep -q 'inputsVersion = 203' "$CFG" && echo "cfg: inputsVersion = 203"
echo "V203 ACTIVE. Start training with the normal launch command."
