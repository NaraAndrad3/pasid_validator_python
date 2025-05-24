import random
import time

def get_current_millis():
    """
        Retorna a hora atual em milissegundos
        
        Returns:
            int: Hora atual em milissegundos
    """
    return int(time.time() * 1000)

def calculate_delay(mean: float, std_dev: float) -> float:
    """
        Calcula um atraso com base em uma distribuição gaussiana
        
        Returns:
            float: Atraso calculado em segundos
    """
    return random.gauss(mean, std_dev)

def read_properties_file(filepath):
    """
        Lê um arquivo .properties e retorna seu conteúdo como um dicionário.
        
        Returns:
            dict: Dicionário contendo as proprerties do componente ou um dicionário
            vazio se o arquivo não for encontrado ou não puder ser lido.
    """
    properties = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('!'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                elif ':' in line:
                    key, value = line.split(':', 1)
                else:
                    continue # Skip malformed lines

                properties[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"Error: Properties file not found at {filepath}")
    except Exception as e:
        print(f"Error reading properties file {filepath}: {e}")
    return properties

def generate_random_port(min_port = 1000, max_port = 9000):
    """
        Gera um número de porta aleatório dentro de um intervalo especificado
        
        Returns:
            int: Número da porta 
    """
    return random.randint(min_port, max_port)




ret = parse_properties_file('/home/nara/Documentos/2025.1/SD/Trabalho_Final/pasid_validator_python/config/loadbalancer1.properties')


for key, value in ret.items():
    print(f"{key}: {value}")