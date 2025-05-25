# main.py
import os
import sys
import time
from src.domain.source import Source
from src.domain.load_balancer_proxy import LoadBalancerProxy
from src.domain.service_proxy import ServiceProxy # Se você quiser rodar services diretamente

def main():
    if len(sys.argv) < 2:
        print("Uso: python main.py <componente> [porta]")
        print("Componentes: source, lb1, lb2, service")
        sys.exit(1)

    component_type = sys.argv[1].lower()
    
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, "config") # Ajustar o caminho se necessário

    instance = None
    if component_type == "source":
        # A Source ainda precisa do caminho para as propriedades
        instance = Source(config_path) 
    elif component_type == "lb1":
        # LB1 precisa do caminho para as propriedades do LB1
        instance = LoadBalancerProxy(os.path.join(config_path, "loadbalancer1.properties"))
    elif component_type == "lb2":
        # LB2 precisa do caminho para as propriedades do LB2
        instance = LoadBalancerProxy(os.path.join(config_path, "loadbalancer2.properties"))
    elif component_type == "service":
        # Para testar um ServiceProxy diretamente, você precisaria passar mais argumentos
        # ou ter um arquivo de propriedades para ServiceProxy também.
        # Por enquanto, focaremos que LBs criam Services.
        print("Para esta etapa, ServiceProxy é criado e gerenciado por LoadBalancerProxy.")
        sys.exit(1)
    else:
        print(f"Componente '{component_type}' desconhecido.")
        sys.exit(1)

    if instance:
        print(f"Iniciando {component_type}...")
        instance.start() # Inicia a thread do componente

        # Mantém o processo vivo até o componente parar
        try:
            while instance.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{component_type} interrompido pelo usuário.")
        finally:
            instance.stop() # Garante que o componente seja parado corretamente
            print(f"{component_type} encerrado.")

if __name__ == "__main__":
    main()