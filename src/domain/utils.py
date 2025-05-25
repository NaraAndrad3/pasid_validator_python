import random
import time
import os
import math # Adicionar esta importação para math.sqrt

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
        
        Raises:
            FileNotFoundError: Se o arquivo de propriedades não for encontrado.
            Exception: Se ocorrer outro erro durante a leitura do arquivo.
        
        Returns:
            dict: Dicionário contendo as propriedades do componente.
    """
    properties = {}
    if not os.path.exists(filepath):
        # Alterado para re-lançar FileNotFoundError
        raise FileNotFoundError(f"Properties file not found at {filepath}")
    
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
                    continue # Ignorar linhas malformadas

                properties[key.strip()] = value.strip()
    except Exception as e:
        # Captura outras exceções de leitura de arquivo
        raise Exception(f"Error reading properties file {filepath}: {e}")
    return properties

def generate_random_port(min_port = 1000, max_port = 9000):
    """
        Gera um número de porta aleatório dentro de um intervalo especificado
        
        Returns:
            int: Número da porta 
    """
    return random.randint(min_port, max_port)

def calculate_mean(data):
    """
    Calcula a média (average) de uma lista de dados numéricos.
    """
    if not data:
        return 0.0
    return sum(data) / len(data)

def calculate_std_dev(data, mean_val=None):
    """
    Calcula o desvio padrão de uma lista de dados numéricos.
    Se mean_val for fornecido, ele o usa, caso contrário, calcula a média.
    """
    if not data:
        return 0.0
    
    if mean_val is None:
        mean_val = calculate_mean(data)
    
    variance = sum([(x - mean_val) ** 2 for x in data]) / len(data)
    return math.sqrt(variance)

