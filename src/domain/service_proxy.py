# src/domain/service_proxy.py

import threading
import time
import random
import sys

from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import get_current_millis, calculate_delay

class ServiceProxy(AbstractProxy):
    """
        Representa um serviço no sistema distribuído.
        Simula o processamento de requisições e seu reenvio.
        
        Args:
            AbstractProxy (_type_): _description_
    """
    
    def __init__(self, name, local_port, target_address,
                 service_time, std, target_is_source):
        super().__init__(name, local_port, target_address)
       
        self.service_time = service_time
        self.std = std
        self.target_is_source = target_is_source
        self.interrupt = False # Flag to stop the service
        self.queue = []  # Fila de mensagens aguardando processamento neste serviço
        self.is_running = True  # Flag to control the service loop
        # Registra esta instância do serviço no registro de proxies
        AbstractProxy.register_proxy(self) 

    def run(self):
        
        print(f"Inciando {self.proxy_name} na port {self.local_port}")
        
        while self.is_running and not self.interrupt:
            self.process_and_send_to_destiny()
            time.sleep(0.0001) 

    def process_and_send_to_destiny(self):
        
        """
            responsável por pegar uma mensagem da fila, simular seu processamento
            e depois enviá-la para o próximo destino.
            Processa a fila de mensagens e envia para o destino.
            Se a fila estiver vazia, não faz nada.
            Se a fila não estiver vazia, processa a primeira mensagem da fila,
            simula um atraso no processamento, registra o tempo de chegada e saída,
            e envia a mensagem processada para o destino.
        """
        if self.queue:
            message = self.queue.pop(0) 

            # simula um atarso no processamento do serviço
            delay = max(0, calculate_delay(self.service_time, self.std)) / 1000.0 # Convert ms to seconds
           # marca o timestamp da mensagem
            message = self._register_time_when_arrives(message)
            # pausa a trhresa
            time.sleep(delay)

            
            message = self._register_time_when_go_out(message)

            if self.target_is_source:
                
                message = self._register_mrt_at_the_end(message)
                self.send_message_to_destiny(message + "\n", self.target_address)
            else:
                
                while not self.is_destiny_free(self.target_address) and self.is_running:
                    
                    time.sleep(0.1) 

                if self.is_running: 
                    self.send_message_to_destiny(message + "\n", self.target_address)

            self.content_to_process = None 

    def stop_service(self):
        """
            permite parar o serviço.
            Define a flag de interrupção e altera o estado de execução.
            Se o serviço já estiver parado, não faz nada.
            
        """
        self.interrupt = True
        self.is_running = False
        print(f"Parando -- {self.proxy_name}")

    def create_connection_with_destiny(self):
        """
            cria uma conexão com o destino
        """
        print(f"[{self.proxy_name}] Conexão estabelecida com {self.target_address}")

    def receiving_messages(self, received_message):
        """
         Recebe uma mensagem do destino e a processa.
        """
       
        if received_message is None:
            return

        if received_message.strip() == "ping":
            self._handle_ping_message()
        else:
            self.queue.append(received_message.strip())

    def _handle_ping_message(self):
     
        pass 

    def _simulate_is_free(self) -> bool:
        """        Simula se o serviço está livre para receber novas mensagens.
        Esta função verifica se a fila de mensagens está vazia.
        Returns:
            bool: _description_
        """
        return not bool(self.queue) 


    

    def _register_time_when_arrives(self, received_message: str) -> str:
        """
        Registra o tempo de chegada ao serviço.

        Args:
            received_message (str): _description_

        Returns:
            str: _description_
        """
        
         # Simula o registro de tempo de chegada ao serviço.
        # Adiciona o timestamp de chegada e a duração do tempo de rede de entrada.
        parts = received_message.split(';')
        last_registered_timestamp_string = parts[-1].strip() 
        
        last_timestamp_str = parts[-1].strip()
        last_timestamp = int(last_timestamp_str) if last_timestamp_str.isdigit() else get_current_millis() 

        time_now = get_current_millis()
        duration = time_now - last_timestamp
        received_message += f"{time_now};{duration};" 
        return received_message

    def _register_time_when_go_out(self, received_message):
        
        """
            Adiciona o timestamp de saída da mensagem do ServiceProxy e calcula a 
            duração do tempo de processamento que a mensagem passou dentro do serviço.

            Returns:
                _type_: _description_
        """
        
        parts = received_message.split(';')
        
        current_processing_start_timestamp = get_current_millis()
        
        parts = received_message.split(';')
        
        prev_arrival_timestamp_str = parts[-2].strip()
        prev_arrival_timestamp = int(prev_arrival_timestamp_str) if prev_arrival_timestamp_str.isdigit() else get_current_millis()

        duration_process = current_processing_start_timestamp - prev_arrival_timestamp
     
        current_time_out = get_current_millis()
        parts = received_message.split(';')
        
        arrival_timestamp_str = parts[-2]
        arrival_timestamp = int(arrival_timestamp_str) if arrival_timestamp_str.isdigit() else get_current_millis()

        duration_process = current_time_out - arrival_timestamp
        
        received_message += f"{current_time_out};{duration_process};"
        return received_message

    def _register_mrt_at_the_end(self, received_message):
        """Calcula o Tempo Médio de Resposta (MRT) de uma mensagem completa, desde o momento em
            que ela saiu do Source até o momento em que está prestes a retornar a ele. 

        Args:
            received_message (_type_): _description_

        Returns:
            _type_: _description_
        """
        
        parts = received_message.split(';')
        
      
        first_timestamp_str = parts[2]
        first_timestamp = int(first_timestamp_str) if first_timestamp_str.isdigit() else get_current_millis()

        last_timestamp_str = parts[-2]
        last_timestamp = int(last_timestamp_str) if last_timestamp_str.isdigit() else get_current_millis()

        current_mrt = last_timestamp - first_timestamp
        received_message += f"RESPONSE TIME:;{current_mrt};"
        return received_message