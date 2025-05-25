import sys
import os
import time


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.domain.service_proxy import ServiceProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import read_properties_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python run_service.py <caminho_para_arquivo_de_propriedades_do_servico>")
        sys.exit(1)

    config_path = sys.argv[1]
    
    try:
        props = read_properties_file(config_path)
        
        service_name = props.get("service.name", "UnnamedService")
        local_port = int(props.get("service.localPort"))
        target_ip = props.get("service.targetIp")
        target_port = int(props.get("service.targetPort"))
        service_time = float(props.get("service.serviceTime"))
        std = float(props.get("service.std"))
        target_is_source = props.get("service.targetIsSource").lower() == 'true'

        target_address = TargetAddress(target_ip, target_port)

        service = ServiceProxy(service_name, local_port, target_address,
                               service_time, std, target_is_source)
        
        service.start() 
        print('\n*****************************************************')
        print(f"[{service_name}] Serviço iniciado na porta {local_port}. Pressione Enter para parar...")
        time.sleep(3600)
        service.stop_service() 
        service.join() 
        print(f"[{service_name}] Serviço parado.")
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
        print(f"Ocorreu um erro inesperado ao iniciar o serviço: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)