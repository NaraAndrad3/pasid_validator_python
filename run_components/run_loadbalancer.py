import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.domain.load_balancer_proxy import LoadBalancerProxy
from src.domain.utils import read_properties_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python run_loadbalancer.py <caminho_para_arquivo_de_propriedades_do_loadbalancer>")
        sys.exit(1)

    config_path = sys.argv[1]

    try:
       
        load_balancer = LoadBalancerProxy(config_path)
        
        load_balancer.start() 
        print('\n*****************************************************')
        print(f"[{load_balancer.proxy_name}] Load Balancer iniciado na porta {load_balancer.local_port}. Pressione Enter para parar...")
        time.sleep(3600)
        load_balancer.stop_proxy() 
        load_balancer.join() 
        print(f"[{load_balancer.proxy_name}] Load Balancer parado.")
        print('\n*****************************************************')
    except FileNotFoundError:
        print(f"Erro: Arquivo de propriedades não encontrado em '{config_path}'")
        sys.exit(1)
    except KeyError as e:
        print(f"Erro: Propriedade ausente no arquivo de configuração: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Erro: Valor inválido no arquivo de configuração: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao iniciar o Load Balancer: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)