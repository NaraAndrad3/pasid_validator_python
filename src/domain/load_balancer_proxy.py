# src/domain/load_balancer_proxy.py

import threading
import time
import sys
import socket
import random

from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import read_properties_file, get_current_millis

class LoadBalancerProxy(AbstractProxy):
    """ 
        Ele simula o papel de um balanceador de carga, recebendo requisições
        e as distribuindo para um conjunto de serviços (que estarão em processos separados).
    """
    
    def __init__(self, config_path):
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
        
        
        self.queue = [] 
       
        self.queue_lock = threading.Lock() 

        
        self.service_addresses: list[TargetAddress] = [] 
        self._initialize_service_addresses() 

        
        self.active_service_connections: dict[TargetAddress, socket.socket] = {}
       
        self.connections_lock = threading.Lock() 

        
        self.current_service_index = 0
        
        self.print_load_balancer_parameters()

    def _initialize_service_addresses(self):
        """
        Inicializa a lista de endereços dos serviços que o Load Balancer irá gerenciar.
        """
        start_service_port = self.local_port + 1 
        for i in range(self.qtd_services_in_this_cycle):
            service_port = start_service_port + i
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
        self.log(f"[{self.proxy_name}] Iniciando o Load Balancer.")
        while self.is_running:
            try:
                self._process_queue()
            except Exception as e:
                self.log(f"[{self.proxy_name}] ERRO no loop principal de processamento da fila: {e}")
            time.sleep(0.001) 

    def _get_next_service_address_rr(self) -> TargetAddress | None:
        """
        Obtém o próximo endereço de serviço usando a estratégia Round Robin.
        """
        with self.connections_lock: 
            if not self.service_addresses:
                return None
            
           
            
            service_addr = self.service_addresses[self.current_service_index]
            self.current_service_index = (self.current_service_index + 1) % len(self.service_addresses)
            return service_addr

    def _get_or_create_service_connection(self, service_addr: TargetAddress) -> socket.socket | None:
        """
        Tenta obter uma conexão existente ou cria uma nova para o serviço.
        Retorna a socket se bem-sucedido, None caso contrário.
        """
        with self.connections_lock: # Protege o acesso ao dicionário de conexões
            s = self.active_service_connections.get(service_addr)
            if s:
                try:
                   
                    s.sendall(b'') 
                    return s
                except (socket.error, BrokenPipeError, ConnectionResetError) as e:
                    self.log(f"[{self.proxy_name}] Conexão existente para {service_addr} está morta: {e}. Removendo.")
                    del self.active_service_connections[service_addr] # Remove conexão morta
                    s = None 

           
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(45) 
                s.connect((service_addr.get_ip(), service_addr.get_port()))
               
                self.active_service_connections[service_addr] = s
                self.log(f"[{self.proxy_name}] Conexão estabelecida com sucesso para {service_addr}.")
                return s
            except socket.error as e:
                self.log(f"[{self.proxy_name}] Erro ao estabelecer conexão com {service_addr}: {e}")
                return None
            except Exception as e:
                self.log(f"[{self.proxy_name}] Erro inesperado ao criar conexão com {service_addr}: {e}")
                return None

    def _close_service_connection(self, service_addr: TargetAddress):
        """Fecha e remove uma conexão específica do dicionário."""
        with self.connections_lock: # Protege o acesso ao dicionário de conexões
            if service_addr in self.active_service_connections:
                s = self.active_service_connections.pop(service_addr)
                try:
                    s.shutdown(socket.SHUT_RDWR) # Tenta shutdown antes de fechar para garantir o fim da comunicação
                    s.close()
                    self.log(f"[{self.proxy_name}] Conexão fechada para {service_addr}.")
                except Exception as e:
                    self.log(f"[{self.proxy_name}] Erro ao fechar conexão para {service_addr}: {e}")

    def _process_queue(self):
        """
        Processa as mensagens na fila do Load Balancer.
        Tenta distribuir mensagens para serviços disponíveis usando conexões persistentes.
        """
        with self.queue_lock: 
            if not self.queue:
                return

            msg = self.queue[0] # Pega a mensagem mais antiga, mas não a remove ainda.
        
        
        service_addr = self._get_next_service_address_rr()
        if not service_addr:
            self.log(f"[{self.proxy_name}] Nenhum serviço disponível para processar a mensagem. Fila: {len(self.queue)}")
            return

        conn_socket = self._get_or_create_service_connection(service_addr)
        if conn_socket:
            try:
                data_output_stream = conn_socket.makefile('wb')
                data_input_stream = conn_socket.makefile('rb')

                # 1. Enviar "ping" para verificar a disponibilidade do serviço
                data_output_stream.write(b"ping\n")
                data_output_stream.flush()
                
                # Definir um timeout para a leitura da resposta do ping
                conn_socket.settimeout(10.0) # Aumentar o timeout para o ping
                response = data_input_stream.readline().decode().strip()
                conn_socket.settimeout(45.0) # Restaurar o timeout normal da conexão

                if response == "free":
                    msg_processed = self._register_time_when_arrives_lb(msg) 
                    msg_to_send = msg_processed + f"{get_current_millis()};" # Adiciona timestamp de saída do LB

                    data_output_stream.write((msg_to_send + "\n").encode())
                    data_output_stream.flush()
                    self.log(f"[{self.proxy_name}] Mensagem enviada para {service_addr}: {msg_to_send[:50]}...")
                    
                    with self.queue_lock: 
                        self.queue.pop(0) #
                    
                else:
                    self.log(f"[{self.proxy_name}] Serviço {service_addr} está ocupado ({response}). Mensagem permanece na fila.")
                    # A mensagem permanece na fila para ser tentada novamente com outro serviço
            except socket.timeout:
                self.log(f"[{self.proxy_name}] Timeout ao receber resposta de ping de {service_addr}. Mensagem permanece na fila. Considerar serviço offline.")
                self._close_service_connection(service_addr) # Fechar conexão com serviço que deu timeout
            except (socket.error, BrokenPipeError, ConnectionResetError) as e:
                self.log(f"[{self.proxy_name}] Erro de comunicação com {service_addr} na conexão persistente: {e}. Fechando conexão. Mensagem permanece na fila.")
                self._close_service_connection(service_addr)
            except Exception as e:
                self.log(f"[{self.proxy_name}] Erro inesperado ao processar serviço {service_addr}: {e}. Mensagem permanece na fila.")
        else:
            self.log(f"[{self.proxy_name}] Não foi possível estabelecer conexão com {service_addr}. Mensagem permanece na fila.")


    def has_something_to_process(self):
        """
        Verifica se há mensagens na fila do Load Balancer.
        """
        with self.queue_lock:
            return bool(self.queue)

    def create_connection_with_destiny(self):
        """
        Sobrescreve o método abstrato. Para o LB, as conexões são gerenciadas
        dinamicamente para os serviços filhos e para seu destino principal.
        Este método não é chamado diretamente no loop principal do LB.
        """
       
        pass 

    def receiving_messages(self, received_message: str, conn: socket.socket): 
        """
            Processa as mensagens recebidas pelo balanecador de carga via socket.
            Se for uma resposta de um serviço, *ignora*, pois os serviços devem enviar diretamente ao Source.
            Se for uma mensagem de Source/Server1, adiciona à fila.
        """
        if received_message is None or received_message.strip() == "":
            return

        message_stripped = received_message.strip()
        
        if message_stripped.startswith("config;"):
            self._change_service_targets_of_this_server(message_stripped)
            
        elif message_stripped == "ping":
            try:
                output_stream = conn.makefile('wb')
                if self._simulate_is_free(): 
                    output_stream.write(b"free\n")
                    self.log(f"[{self.proxy_name}] Respondeu 'free' ao ping de {conn.getpeername()}.")
                else:
                    output_stream.write(b"busy\n")
                    self.log(f"[{self.proxy_name}] Respondeu 'busy' ao ping de {conn.getpeername()}.")
                output_stream.flush()
            except Exception as e:
                self.log(f"[{self.proxy_name}] ERRO ao responder ping em LoadBalancerProxy: {e}")
        else:
            
            with self.queue_lock:
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
        with self.queue_lock: 
            return len(self.queue) < self.queue_load_balancer_max_size

    def _change_service_targets_of_this_server(self, config_message: str):
        """
        Reconfigura dinamicamente o número de serviços que este Load Balancer gerencia.
        Fecha as conexões existentes e re-inicializa a lista de endereços de serviço.
        """
        self.log(f"[{self.proxy_name}] Reconfigurando serviços com a mensagem: {config_message}")
        parts = config_message.split(';')
        
        try:
            new_qtd_services = int(parts[1])
        except (ValueError, IndexError):
            self.log(f"[{self.proxy_name}] Formato de mensagem de configuração inválido: {config_message}")
            return

       
        current_service_addrs = list(self.service_addresses) 
        for service_addr in current_service_addrs:
            self._close_service_connection(service_addr) 

        with self.connections_lock:
            self.service_addresses.clear() 

  
            start_service_port = self.local_port + 1
            for i in range(new_qtd_services):
                service_port = start_service_port + i 
                ta = TargetAddress("localhost", service_port)
                self.service_addresses.append(ta)
                self.log(f"[{self.proxy_name}] Adicionado novo serviço gerenciado: {ta.get_ip()}:{ta.get_port()}")
            self.current_service_index = 0 # Resetar o índice Round Robin
        self.log(f"[{self.proxy_name}] Reconfiguração completa. Nova contagem de serviços conhecidos: {len(self.service_addresses)}")
        
    def _register_time_when_arrives_lb(self, received_message: str) -> str:
        """
        Registra o tempo em milissegundos quando a mensagem chega ao Load Balancer.
        Adiciona o timestamp atual e a duração desde o último timestamp (tempo de rede de entrada).
        """
        parts = received_message.split(';')
        
       
        last_timestamp_str = parts[-1].strip() if parts else ""
        
        last_timestamp = get_current_millis()
        if last_timestamp_str.isdigit():
            try:
                last_timestamp = int(last_timestamp_str)
            except ValueError:
                self.log(f"[{self.proxy_name}] Aviso: Não foi possível converter timestamp '{last_timestamp_str}' para int. Usando tempo atual.")
        else:
             self.log(f"[{self.proxy_name}] Aviso: Último elemento '{last_timestamp_str}' não é um timestamp válido. Usando tempo atual.")

        time_now = get_current_millis() # Timestamp de chegada ao Load Balancer.
        duration = time_now - last_timestamp # Duração do tempo de rede de entrada (do hop anterior até o LB).
        
        received_message += f"{time_now};{duration};"
        return received_message

    def stop_proxy(self):
        """
        Para o proxy e fecha todas as conexões ativas.
        """
        # Garante que a flag de execução seja definida como False
        self.is_running = False 
        self.log(f"[{self.proxy_name}] Sinal de parada recebido. Encerrando threads e conexões...")

        # Fecha as conexões de serviço gerenciadas
        with self.connections_lock:
            for service_addr, conn_socket in list(self.active_service_connections.items()):
                try:
                    conn_socket.shutdown(socket.SHUT_RDWR)
                    conn_socket.close()
                    self.log(f"[{self.proxy_name}] Conexão de serviço {service_addr} fechada durante a parada.")
                except Exception as e:
                    self.log(f"[{self.proxy_name}] Erro ao fechar conexão de serviço {service_addr}: {e}")
            self.active_service_connections.clear() # Limpa o dicionário

        # Chama o método stop_proxy da classe pai para lidar com sockets de escuta e logs
        super().stop_proxy()

        self.log(f"[{self.proxy_name}] Proxy completamente parado.")