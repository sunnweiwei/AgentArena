model_path=$1 # models/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
server_name=$2 # DeepSeek-R1-Distill-Qwen-7B
port=$3 # 8121 for pitt, 8122 for sf 8123-8130 for babel

source ~/.bashrc
conda activate llm
nvidia-smi
export NCCL_P2P_LEVEL=NVL
export RAY_TMPDIR="$HOME/ray/tmp"
mkdir -p $RAY_TMPDIR
chmod 700 $RAY_TMPDIR

vllm serve $model_path \
    -pp 2 \
    -tp 2 \
    --gpu-memory-utilization 0.8 \
    --host 0.0.0.0 --port $port \
    --served-model-name $server_name \
    --enable-prefix-caching