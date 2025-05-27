import os
import sys
import threading
import time
from src.domain.source import Source
from src.domain.load_balancer_proxy import LoadBalancerProxy
from src.domain.abstract_proxy import AbstractProxy
from src.domain.service_proxy import ServiceProxy  
from src.domain.target_address import TargetAddress  
from src.domain.utils import read_properties_file 

def execute_stage():
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, "../../../config") 

    # Paths to property files
    load_balancer1_props_path = os.path.join(config_path, "loadbalancer1.properties")
    load_balancer2_props_path = os.path.join(config_path, "loadbalancer2.properties")
    source_props_path_for_source_obj = os.path.join(config_path, "source.properties") 

    # Service property paths
    service2001_props_path = os.path.join(config_path, "service2001.properties")
    service2002_props_path = os.path.join(config_path, "service2002.properties")
    service3001_props_path = os.path.join(config_path, "service3001.properties")
    service3002_props_path = os.path.join(config_path, "service3002.properties")

    print("Sistema PASID iniciada.")
    print(f"Diretório de configuração: {config_path}")

   
    target_for_services_behind_lb2 = TargetAddress("localhost", 1025) 

    # Service3001
    props_3001 = read_properties_file(service3001_props_path)
    svc3001 = ServiceProxy(
        props_3001.get("service.name"),
        int(props_3001.get("service.localPort")),
        target_for_services_behind_lb2,
        float(props_3001.get("service.serviceTime")),
        float(props_3001.get("service.std")),
        props_3001.get("service.targetIsSource").lower() == 'true'
    )
    svc3001.start()
    AbstractProxy.register_proxy(svc3001)
    print(f"[{svc3001.proxy_name}] Serviço iniciado na porta {svc3001.local_port}. Pressione Enter para parar...") 

    # Service3002
    props_3002 = read_properties_file(service3002_props_path)
    svc3002 = ServiceProxy(
        props_3002.get("service.name"),
        int(props_3002.get("service.localPort")),
        target_for_services_behind_lb2,
        float(props_3002.get("service.serviceTime")),
        float(props_3002.get("service.std")),
        props_3002.get("service.targetIsSource").lower() == 'true'
    )
    svc3002.start()
    AbstractProxy.register_proxy(svc3002)
    print(f"[{svc3002.proxy_name}] Serviço iniciado na porta {svc3002.local_port}. Pressione Enter para parar...") 


    lb2 = LoadBalancerProxy(load_balancer2_props_path)
    lb2.start()
    AbstractProxy.register_proxy(lb2)
    print(f"[{lb2.proxy_name}] Load Balancer iniciado na porta {lb2.local_port}. Pressione Enter para parar...") 

  
    target_for_services_behind_lb1 = TargetAddress("localhost", 3000) 


    props_2001 = read_properties_file(service2001_props_path)
    svc2001 = ServiceProxy(
        props_2001.get("service.name"),
        int(props_2001.get("service.localPort")),
        target_for_services_behind_lb1,
        float(props_2001.get("service.serviceTime")),
        float(props_2001.get("service.std")),
        props_2001.get("service.targetIsSource").lower() == 'true'
    )
    svc2001.start()
    AbstractProxy.register_proxy(svc2001)
    print(f"[{svc2001.proxy_name}] Serviço iniciado na porta {svc2001.local_port}. Pressione Enter para parar...")
    # Service2002
    props_2002 = read_properties_file(service2002_props_path)
    svc2002 = ServiceProxy(
        props_2002.get("service.name"),
        int(props_2002.get("service.localPort")),
        target_for_services_behind_lb1,
        float(props_2002.get("service.serviceTime")),
        float(props_2002.get("service.std")),
        props_2002.get("service.targetIsSource").lower() == 'true'
    )
    svc2002.start()
    AbstractProxy.register_proxy(svc2002)
    print(f"[{svc2002.proxy_name}] Serviço iniciado na porta {svc2002.local_port}. Pressione Enter para parar...") 



    lb1 = LoadBalancerProxy(load_balancer1_props_path)
    lb1.start()
    AbstractProxy.register_proxy(lb1)
    print(f"[{lb1.proxy_name}] Load Balancer iniciado na porta {lb1.local_port}. Pressione Enter para parar...") 


    source = Source(source_props_path_for_source_obj)
    source.start()
    AbstractProxy.register_proxy(source)
    print(f"[{source.proxy_name}] Source iniciada na porta {source.local_port}. Pressione Enter para parar...") 

    print("\nTodos os componentes simulados foram iniciados.")

    try:
       
        while threading.active_count() > 1:
            time.sleep(1)
    except SystemExit:
        print("Simulação encerrada graciosamente pela Origem.")
    except KeyboardInterrupt:
        print("\nSimulação interrompida pelo usuário.")
    finally:
       
        for proxy in list(AbstractProxy._proxy_registry.values()): 
            if hasattr(proxy, 'stop_proxy'):
                proxy.stop_proxy()
            else:
                proxy.is_running = False 
        sys.exit(0)

if __name__ == "__main__":
    execute_stage()