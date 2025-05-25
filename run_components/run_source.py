import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.domain.source import Source
from src.domain.utils import read_properties_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python run_source.py <caminho_para_arquivo_de_propriedades_da_source>")
        sys.exit(1)

    config_path = sys.argv[1]

    try:
        source = Source(config_path)
        
        source.start() 
        print('\n*****************************************************')
        print(f"[{source.proxy_name}] Source iniciada na porta {source.local_port}. Pressione Enter para parar...")
        print('\n*****************************************************')
        source.join() 
        
        print(f"[{source.proxy_name}] Source parada.")

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
        print(f"Ocorreu um erro inesperado ao iniciar a Source: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)