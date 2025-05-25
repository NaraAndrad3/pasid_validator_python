import os
import sys
import threading
import time
from src.domain.source import Source 
from src.domain.load_balancer_proxy import LoadBalancerProxy 
from src.domain.abstract_proxy import AbstractProxy 

def execute_stage():
    """
        Função principal que configura e inicia a simulação do sistema PASID.
        Ela é responsável por:
        1. Definir os caminhos dos arquivos de configuração.
        2. Instanciar e iniciar os componentes (Load Balancers e Source).
        3. Registrar os componentes para permitir a comunicação simulada.
        4. Manter a thread principal ativa enquanto a simulação está em andamento.
        5. Lidar com saídas graciosas ou interrupções pelo usuário.
    """
    
    
    script_dir = os.path.dirname(__file__)
   
    config_path = os.path.join(script_dir, "../../../config")
    
    
    load_balancer1_props_path = os.path.join(config_path, "loadbalancer1.properties")
    load_balancer2_props_path = os.path.join(config_path, "loadbalancer2.properties")
    
   
    source_props_path_for_source_obj = os.path.join(script_dir, "../..") 
    
    print("Simulação do sistema PASID iniciada.")
    print(f"Diretório de configuração: {config_path}")

    # 1. Inicia o Load Balancer 2 (porta 3000)
   
    lb2 = LoadBalancerProxy(load_balancer2_props_path)
    lb2.start() 
    # Registra o LB2 no dicionario global
    AbstractProxy.register_proxy(lb2) 

    # 2. Inicia o Load Balancer 1 (porta 2000)
    lb1 = LoadBalancerProxy(load_balancer1_props_path)
    lb1.start() 
    AbstractProxy.register_proxy(lb1) 

    # 3. Inicia a Origem (Source) (porta 1000)
    
    source = Source(config_path) 
    source.start() 
    AbstractProxy.register_proxy(source) 
    print("Todos os componentes simulados foram iniciados.")
    
    
    try:
        
       
        while threading.active_count() > 1: 
            time.sleep(1) # Espera 1 segundo para não consumir CPU desnecessariamente
    except SystemExit:
       
        print("Simulação encerrada graciosamente pela Origem.")
    except KeyboardInterrupt:
        
        print("\nSimulação interrompida pelo usuário.")
        
        for proxy in AbstractProxy._proxy_registry.values():
            if hasattr(proxy, 'is_running'):
                proxy.is_running = False
            if hasattr(proxy, 'interrupt'):
                proxy.interrupt = True
        sys.exit(0) 

if __name__ == "__main__":
   
    execute_stage()