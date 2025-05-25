# src/domain/load_balancer_proxy.py

import threading
import time
import sys

from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.service_proxy import ServiceProxy
from src.domain.utils import read_properties_file, get_current_millis, generate_random_port

class LoadBalancerProxy(AbstractProxy):
    """ 
        Ele simula o papel de um balanceador de carga, recebendo requisições
        e as distribuindo para um conjunto de serviços.
    """
    
    def __init__(self, config_path):
        # aqui carrega as propriedades dp arquivo
        props = read_properties_file(config_path)

        proxy_name = props.get("server.loadBalancerName", "UnnamedLoadBalancer")
        local_port = int(props.get("server.loadBalancerPort"))
        super().__init__(proxy_name, local_port)
        
        # Aqui tá inicializando os atriybutos com base no que foi lido do arquivo de propiedades
        self.queue_load_balancer_max_size = int(props.get("server.queueLoadBalancerMaxSize"))
       # Número inicial de serviços a serem gerenciados
        self.qtd_services_in_this_cycle = int(props.get("server.qtdServices")) 

        self.service_target_ip = props.get("service.serviceTargetIp")
        self.service_target_port = int(props.get("service.serviceTargetPort"))
        self.service_time = float(props.get("service.serviceTime"))
        self.service_std = float(props.get("service.std"))
        self.target_is_source = props.get("service.targetIsSource").lower() == 'true'
        
        # Inicializa estruturas de dados internas
        self.queue = [] # Fila de mensagens que o Load Balancer precisa processar/despachar
        self.services: list[ServiceProxy] = [] # Lista de instâncias de ServiceProxy
        self.index_current_qtd_services = 0

        # Inicia os serviços iniciais que esse balanceador vai gerenciar
        # Aqui é o ponto de partida, o Load Balancer cria os serviços
        # e os registra no AbstractProxy para que possam ser acessados por outros proxies
        self._create_initial_services()

        # Define o endereço de destino principal do balanceador
        self.target_address = self.service_addresses[0] if self.service_addresses else None
        
        # registra a instancia no dicionario definido na class AbstractProxy
        AbstractProxy.register_proxy(self)
        self.print_load_balancer_parameters()

    def _create_initial_services(self):
        """
            Cria os serviços iniciais que o Load Balancer vai gerenciar.
            Cada serviço é representado por uma instância de ServiceProxy.
            O Load Balancer inicia com um número fixo de serviços, que pode ser alterado posteriormente.
            O número de serviços é definido pelo parâmetro `qtd_services_in_this_cycle`.
            O Load Balancer também registra esses serviços no AbstractProxy para que possam ser acessados por outros proxies.
            Cada serviço é iniciado em uma thread separada, permitindo que o Load Balancer possa gerenciar múltiplos serviços simultaneamente.
            O Load Balancer também define o endereço de destino principal, que é o primeiro serviço criado.
            O Load Balancer é responsável por distribuir as requisições recebidas entre os serviços disponíveis.
        """
        # para armazenar os TargetAddress dos serviços gerenciados.
        self.service_addresses = []  #
        
        port = self.local_port + 1 
        for i in range(self.qtd_services_in_this_cycle):
            ta = TargetAddress("localhost", port)
            # Instancia outro ServiceProxy
            service_proxy = ServiceProxy(
                f"service{port}",
                port,
                TargetAddress(self.service_target_ip, self.service_target_port),
                self.service_time,
                self.service_std,
                self.target_is_source
            )
            self.services.append(service_proxy)
            service_proxy.start() 
            self.service_addresses.append(ta)
            port += 1 # aqui uncrementa a port para o prox serviço

    def print_load_balancer_parameters(self):
        
        """Paenas imprime os parametros de configração do load_banalecr
        """
        
        print("======================================")
        print("Load Balancer Parameters:")
        print(f"Load Balancer Name: {self.proxy_name}")
        print(f"Local Port: {self.local_port}")
        print(f"Queue Load Balancer Max Size: {self.queue_load_balancer_max_size}")
        print(f"Qtd Services (initial): {self.qtd_services_in_this_cycle}")
        print("======================================")

    def run(self):
        """
            O método run é o ponto de entrada para a execução do Load Balancer.
            Ele inicia um loop que processa as mensagens na fila e as distribui para os serviços disponíveis.
            O loop continua até que o Load Balancer seja interrompido.
            O método também verifica se há mensagens na fila e, se houver, as processa.
            O tempo de espera entre as iterações do loop é definido para 0.0001 segundos.
        """
        while self.is_running:
            self._process_queue()
            time.sleep(0.0001) # simulação de atrso 

    def _process_queue(self):
        """
            Processa as mensagens na fila do Load Balancer.
            O método verifica se há mensagens na fila e, se houver, tenta distribuí-las para os serviços disponíveis.
            O Load Balancer tenta enviar a mensagem para o primeiro serviço disponível na lista de serviços.
            Se o serviço estiver ocupado, o Load Balancer tenta enviar a mensagem para o próximo serviço na lista.
        """
        if self.has_something_to_process():
            msg = self.queue.pop(0) 

            sent = False
            
            for service_addr in self.service_addresses:
                
                service_proxy_instance = AbstractProxy.get_proxy_by_port(service_addr.get_port())
                if service_proxy_instance and service_proxy_instance.is_destiny_free(service_proxy_instance.target_address): # Check if the service itself is free (its queue is empty)
                    
                    
                    msg = self._register_time_when_arrives_lb(msg) 
                    msg += f"{get_current_millis()};" 

                    self.send_message_to_destiny(msg + "\n", service_addr)
                    sent = True
                    break
            


    def has_something_to_process(self):
        """
            Verifica se há mensagens na fila do Load Balancer.
            O método retorna True se houver mensagens na fila e False caso contrário.
            O método também verifica se o Load Balancer está livre para processar mensagens.
        """
        return bool(self.queue)

    def create_connection_with_destiny(self):
        """ 
            criação de conexões com os serviços disponíveis.
        """
        print(f"[{self.proxy_name}] Conexões simuladas estabelecidas com serviços ")


    def receiving_messages(self, received_message: str):
        """
            Processa as mensagens recebidas pelo balanecador de carga.
        Args:
            received_message (str): _description_
        """
        
        if received_message is None:
            return

        if received_message.strip().startswith("config;"):
            self._change_service_targets_of_this_server(received_message.strip())
        elif received_message.strip() == "ping":
            
            pass
        else:
            if len(self.queue) < self.queue_load_balancer_max_size:
                self.queue.append(received_message.strip())
            else:
               
                pass 

    def _simulate_is_free(self) -> bool:
        """
            verifica se o Load Balancer está livre para processar mensagens.
        Returns:
            bool: _description_
        """
        return len(self.queue) < self.queue_load_balancer_max_size


    def _change_service_targets_of_this_server(self, config_message: str):
        
        print(f"[{self.proxy_name}] Reconfiguring services with message: {config_message}")
        parts = config_message.split(';')
        new_qtd_services = int(parts[1])

       
        for service_proxy in self.services:
            service_proxy.stop_service()
        self.services.clear()
        self.service_addresses.clear()

        
        port = generate_random_port() 
        for i in range(new_qtd_services):
            service_port = port + i
            ta = TargetAddress("localhost", service_port)
            service_proxy = ServiceProxy(
                f"service{service_port}",
                service_port,
                TargetAddress(self.service_target_ip, self.service_target_port),
                self.service_time,
                self.service_std,
                self.target_is_source
            )
            self.services.append(service_proxy)
            service_proxy.start()
            self.service_addresses.append(ta)
            AbstractProxy.register_proxy(service_proxy) 

       
        self.target_address = self.service_addresses[0] if self.service_addresses else None
        print(f"[{self.proxy_name}] Reconfiguration complete. New services count: {len(self.services)}")
        

    def _register_time_when_arrives_lb(self, received_message: str) -> str:
        """
            Registra o tempo em milissegundos quando a mensagem chega ao Load Balancer.
            O método adiciona o timestamp atual e a duração desde o último timestamp à mensagem recebida.
            
        """
        parts = received_message.split(';')
       
        last_timestamp_str = parts[-1].strip()
        last_timestamp = int(last_timestamp_str) if last_timestamp_str.isdigit() else get_current_millis()

        time_now = get_current_millis()
        duration = time_now - last_timestamp
        
        received_message += f"{time_now};{duration};"
        return received_message