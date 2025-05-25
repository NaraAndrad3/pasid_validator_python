# src/domain/load_balancer_proxy.py

import threading
import time
import sys
import socket # Importar socket para lidar com possíveis erros específicos
import random # Para generate_random_port

from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
# ServiceProxy não será importado diretamente aqui se cada um for um processo separado,
# a menos que você precise da classe para instanciar (mas elas não estarão no mesmo processo).
# Por enquanto, vou mantê-lo para que o código seja semanticamente similar ao Java,
# mas o comportamento de "criação" mudará.
from src.domain.service_proxy import ServiceProxy # Manter por enquanto para a estrutura
from src.domain.utils import read_properties_file, get_current_millis, generate_random_port

class LoadBalancerProxy(AbstractProxy):
    """ 
        Ele simula o papel de um balanceador de carga, recebendo requisições
        e as distribuindo para um conjunto de serviços (que estarão em processos separados).
    """
    
    def __init__(self, config_path):
        # Carrega as propriedades do arquivo de configuração.
        props = read_properties_file(config_path)

        proxy_name = props.get("server.loadBalancerName", "UnnamedLoadBalancer")
        local_port = int(props.get("server.loadBalancerPort"))
        
       
        service_target_ip = props.get("service.serviceTargetIp")
        service_target_port = int(props.get("service.serviceTargetPort"))
        
        super().__init__(proxy_name, local_port, TargetAddress(service_target_ip, service_target_port))
        
        
        self.queue_load_balancer_max_size = int(props.get("server.queueLoadBalancerMaxSize"))
        self.qtd_services_in_this_cycle = int(props.get("server.qtdServices")) 

        self.service_target_ip = service_target_ip
        self.service_target_port = service_target_port
        self.service_time = float(props.get("service.serviceTime"))
        self.service_std = float(props.get("service.std"))
        self.target_is_source = props.get("service.targetIsSource").lower() == 'true'
        
        # Inicializa estruturas de dados internas.
        self.queue = [] # Fila de mensagens que o Load Balancer precisa processar/despachar.

        self.service_addresses: list[TargetAddress] = [] 

        self._initialize_service_addresses() 


        
        self.print_load_balancer_parameters()

    def _initialize_service_addresses(self):
        """
        Inicializa a lista de endereços dos serviços que o Load Balancer irá gerenciar.
        Em um ambiente distribuído, esses serviços seriam processos separados
        já escutando em suas respectivas portas. O Load Balancer apenas precisa saber
        onde encontrá-los.

        Para a simulação, vamos assumir que as portas dos serviços são sequenciais
        a partir de uma porta inicial (ex: porta do LB + 1), ou lidas de um arquivo.
        """
        
        
        start_service_port = self.local_port + 1 
        for i in range(self.qtd_services_in_this_cycle):
            service_port = start_service_port + i
            # O IP dos serviços gerenciados será localhost se estiverem na mesma máquina.
            ta = TargetAddress("localhost", service_port)
            self.service_addresses.append(ta)
            self.log(f"[{self.proxy_name}] Gerenciando serviço em {ta.get_ip()}:{ta.get_port()}")

    def print_load_balancer_parameters(self):
        """Imprime os parâmetros de configuração do balanceador de carga."""
        self.log("======================================")
        self.log("Parâmetros do Balanceador de Carga:")
        self.log(f"Nome do Balanceador de Carga: {self.proxy_name}")
        self.log(f"Porta Local: {self.local_port}")
        self.log(f"Tamanho Máximo da Fila do Balanceador: {self.queue_load_balancer_max_size}")
        self.log(f"Quantidade de Serviços (inicial): {self.qtd_services_in_this_cycle}")
        self.log(f"Endereços dos serviços gerenciados: {[str(sa) for sa in self.service_addresses]}")
        self.log(f"Destino final dos serviços gerenciados: {self.target_address.get_ip()}:{self.target_address.get_port()}")
        self.log("======================================")

    def run(self):
        """
        O método run é o ponto de entrada para a execução do Load Balancer.
        Ele inicia um loop que processa as mensagens na fila e as distribui para os serviços disponíveis.
        """
        
        while self.is_running:
            self._process_queue()
            time.sleep(0.0001) 
    def _process_queue(self):
        """
        Processa as mensagens na fila do Load Balancer.
        Tenta distribuir mensagens para serviços disponíveis usando sockets.
        """
        if self.has_something_to_process():
            msg = self.queue.pop(0) # Remove a mensagem mais antiga da fila.
            
            sent = False
            # Itera sobre os endereços dos serviços gerenciados.
            for service_addr in self.service_addresses:
                try:
                    
                    if self.is_destiny_free(service_addr):
                        
                        msg = self._register_time_when_arrives_lb(msg) 
                        
                        msg_to_send = msg + f"{get_current_millis()};" 

                        # Envia a mensagem para o serviço disponível.
                        self.send_message_to_destiny(msg_to_send + "\n", service_addr)
                        sent = True
                        break 
                except Exception as e:
                    self.log(f"[{self.proxy_name}] Erro ao tentar enviar/verificar serviço {service_addr}: {e}")
                    
            
            if not sent:
               
                self.log(f"[{self.proxy_name}] Todos os serviços ocupados ou inacessíveis. Mensagem permanece na fila: {msg.strip()}")
                self.queue.insert(0, msg) 


    def has_something_to_process(self):
        """
        Verifica se há mensagens na fila do Load Balancer.
        """
        return bool(self.queue)

    def create_connection_with_destiny(self):
        """
        Sobrescreve o método abstrato. Para o LB, as conexões são gerenciadas
        dinamicamente para os serviços filhos e para seu destino principal.
        Este método não é chamado diretamente no loop principal do LB.
        """
        self.log(f"[{self.proxy_name}] O gerenciamento de conexões é dinâmico para serviços.")

    def receiving_messages(self, received_message: str):
        """
        Processa as mensagens recebidas pelo balanecador de carga via socket.
        """
        if received_message is None or received_message.strip() == "":
            return

        message_stripped = received_message.strip()
        
        if message_stripped.startswith("config;"):
            
            self._change_service_targets_of_this_server(message_stripped)
        elif message_stripped == "ping":
            
            try:
                # O AbstractProxy.py já tem a lógica de enviar "free" ou "busy" em resposta a um ping.
                # Apenas precisamos garantir que _simulate_is_free() reflita o estado do LB.
                response = "free" if self._simulate_is_free() else "busy"
                # A resposta a um ping é enviada de volta pela mesma conexão que o ping chegou.
                # No _handle_client_connection do AbstractProxy, a resposta de ping é enviada automaticamente
                # se o método _simulate_is_free() for chamado.
                # Neste ponto, como a mensagem é recebida, o proxy de entrada já lidou com isso.
                pass 
            except Exception as e:
                self.log(f"[{self.proxy_name}] Erro ao lidar com ping: {e}")
        else:
            
            if len(self.queue) < self.queue_load_balancer_max_size:
                self.queue.append(message_stripped)
                self.log(f"[{self.proxy_name}] Mensagem adicionada à fila ({len(self.queue)}/{self.queue_load_balancer_max_size}): {message_stripped[:50]}...")
            else:
                self.log(f"[{self.proxy_name}] Fila cheia. Mensagem descartada: {message_stripped[:50]}...")

    def _simulate_is_free(self) -> bool:
        """
        Verifica se o Load Balancer está livre para processar mensagens,
        baseando-se no tamanho de sua fila.
        """
        return len(self.queue) < self.queue_load_balancer_max_size


    def _change_service_targets_of_this_server(self, config_message: str):
        """
        Simula a capacidade de reconfigurar dinamicamente o número de serviços que este
        Load Balancer gerencia. Para a comunicação via socket entre processos,
        isso é mais complexo: o LB precisaria enviar mensagens de controle para
        os *outros processos* ServiceProxy para que eles se iniciem/parem,
        ou você os gerencia manualmente.

        Por simplicidade na segunda entrega, esta função apenas atualizará
        a lista de `service_addresses` que o LB conhece, mas não iniciará/parará
        os processos ServiceProxy reais. Você precisará gerenciar os processos
        ServiceProxy separadamente.

        Args:
            config_message (str): A mensagem de configuração que contém o novo número de serviços.
                                  Formato esperado: "config;<nova_qtd_servicos>"
        """
        self.log(f"[{self.proxy_name}] Reconfigurando serviços com a mensagem: {config_message}")
        parts = config_message.split(';')
        new_qtd_services = int(parts[1])

        
        self.service_addresses.clear() 

        start_service_port = self.local_port + 1
        for i in range(new_qtd_services):
            service_port = start_service_port + i 
            ta = TargetAddress("localhost", service_port)
            self.service_addresses.append(ta)
            self.log(f"[{self.proxy_name}] Adicionado novo serviço gerenciado: {ta.get_ip()}:{ta.get_port()}")

        self.log(f"[{self.proxy_name}] Reconfiguração completa. Nova contagem de serviços conhecidos: {len(self.service_addresses)}")
        

    def _register_time_when_arrives_lb(self, received_message: str) -> str:
        """
        Registra o tempo em milissegundos quando a mensagem chega ao Load Balancer.
        Adiciona o timestamp atual e a duração desde o último timestamp (tempo de rede de entrada).
        """
        parts = received_message.split(';')
        
       
        last_timestamp_str = parts[-1].strip()
        last_timestamp = int(last_timestamp_str) if last_timestamp_str.isdigit() else get_current_millis()

        time_now = get_current_millis() # Timestamp de chegada ao Load Balancer.
        duration = time_now - last_timestamp # Duração do tempo de rede de entrada (do hop anterior até o LB).
        
        received_message += f"{time_now};{duration};"
        return received_message