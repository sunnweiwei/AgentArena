node_name=$1
port=$2
suffix=$3
if [ "$suffix" == "3" ]; then
    user="shengyuf"
elif [ "$suffix" == "2" ]; then
    user="weiweis"
else
    user="weihuad"
fi

if [ -z "$port" ]; then
    port=8123
fi

echo "ssh -J babel$suffix $user@$node_name -N -L 0.0.0.0:$port:localhost:$port"
ssh -J babel$suffix $user@$node_name -N -L 0.0.0.0:$port:localhost:$port