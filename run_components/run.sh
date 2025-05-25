#!/bin/bash


CONFIGS_DIR="../config"

echo "Iniciando os Serviços..."


python3 run_service.py ${CONFIGS_DIR}/service_2001.properties &
python3 run_service.py ${CONFIGS_DIR}/service_2002.properties &


#
python3 run_service.py ${CONFIGS_DIR}/service_3001.properties &
python3 run_service.py ${CONFIGS_DIR}/service_3002.properties &


sleep 2 

echo "Iniciando os Load Balancers..."

python3 run_loadbalancer.py ${CONFIGS_DIR}/loadbalancer2.properties &

sleep 1 

python3 run_loadbalancer.py ${CONFIGS_DIR}/loadbalancer1.properties &

sleep 1 
echo "Iniciando a Source..."


python3 run_source.py ${CONFIGS_DIR}/source.properties &

# echo "Todos os componentes foram iniciados em segundo plano. Verifique os logs em cada terminal."
# echo "Para parar, você precisará encontrar e matar os processos Python ou pressionar Enter em cada janela de terminal onde eles foram iniciados."

