# src/domain/service_proxy.py

import threading
import time
import random
import sys
import socket # Para lidar com socket.error

from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import get_current_millis, calculate_delay

class ServiceProxy(AbstractProxy):
    """
        Representa um serviço no sistema distribuído.
        Simula o processamento de requisições e seu reenvio via sockets.
    """
    
    def __init__(self, name, local_port, target_address,
                 service_time, std, target_is_source):
        
        super().__init__(name, local_port, target_address)
       
        self.service_time = service_time
        self.std = std
        self.target_is_source = target_is_source
        self.interrupt = False 
        self.queue = [] 
        self.is_running = True  
        
    def run(self):
        self.log(f"Iniciando {self.proxy_name} na porta {self.local_port}...")
        
        
        while self.is_running and not self.interrupt:
            self.process_and_send_to_destiny()
            time.sleep(0.0001) 

    def process_and_send_to_destiny(self):
        """
        Pega uma mensagem da fila, simula seu processamento
        e depois a envia para o próximo destino via socket.
        """
        if self.queue:
            message = self.queue.pop(0) 
            self.log(f"[{self.proxy_name}] Processando mensagem: {message[:50]}...")

           
            delay_ms = max(0, calculate_delay(self.service_time, self.std))
            delay_seconds = delay_ms / 1000.0 
            
            # Marca o timestamp da chegada da mensagem ao serviço.
            message = self._register_time_when_arrives(message)
            
            
            time.sleep(delay_seconds)

           
            message = self._register_time_when_go_out(message)

            if self.target_is_source:
                
                message = self._register_mrt_at_the_end(message)
                self.send_message_to_destiny(message + "\n", self.target_address)
            else:
               
                attempts = 0
                max_attempts = 100 # Evita loop infinito em caso de destino inacessível
                while not self.is_destiny_free(self.target_address) and self.is_running and attempts < max_attempts:
                    self.log(f"[{self.proxy_name}] Destino {self.target_address} ocupado. Esperando...")
                    time.sleep(0.1) 
                    attempts += 1

                if self.is_running and attempts < max_attempts: 
                    self.send_message_to_destiny(message + "\n", self.target_address)
                elif attempts >= max_attempts:
                    self.log(f"[{self.proxy_name}] Destino {self.target_address} inacessível após {max_attempts} tentativas. Mensagem descartada: {message[:50]}...")
                   
        
    def stop_service(self):
        """
            Permite parar o serviço.
            Define a flag de interrupção e altera o estado de execução.
            Se o serviço já estiver parado, não faz nada.
        """
        self.interrupt = True
        self.is_running = False
        self.stop_proxy() 
        self.log(f"Parando -- {self.proxy_name}")

    def create_connection_with_destiny(self):
        """
            O AbstractProxy já lida com a criação/reutilização de conexões de saída.
            Este método pode ser deixado como um placeholder ou removido, dependendo
            se AbstractProxy exige que seja implementado.
        """
        self.log(f"[{self.proxy_name}] Conexão de saída gerenciada pelo AbstractProxy.")

    def receiving_messages(self, received_message):
        """
        Recebe uma mensagem via socket e a processa.
        """
        if received_message is None or received_message.strip() == "":
            return

        message_stripped = received_message.strip()

        if message_stripped == "ping":
            
            self.log(f"[{self.proxy_name}] Recebido ping.")
            pass 
        else:
            
            if len(self.queue) < self.queue_load_balancer_max_size: 
                self.queue.append(message_stripped)
                self.log(f"[{self.proxy_name}] Mensagem adicionada à fila ({len(self.queue)}): {message_stripped[:50]}...")
            else:
                self.log(f"[{self.proxy_name}] Fila cheia. Mensagem descartada: {message_stripped[:50]}...")

    def _simulate_is_free(self) -> bool:
        """        
        Simula se o serviço está livre para receber novas mensagens.
        Para um ServiceProxy, isso significa verificar se sua fila está vazia.
        """
        return not bool(self.queue) 

    def _register_time_when_arrives(self, received_message: str) -> str:
        """
        Registra o tempo de chegada ao serviço.
        """
        parts = received_message.split(';')
        
        
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
        """
        parts = received_message.split(';')
        

        
        arrival_timestamp_str = parts[-2]
        arrival_timestamp = int(arrival_timestamp_str) if arrival_timestamp_str.isdigit() else get_current_millis()

        current_time_out = get_current_millis()
        duration_process = current_time_out - arrival_timestamp
     
        received_message += f"{current_time_out};{duration_process};"
        return received_message

    def _register_mrt_at_the_end(self, received_message):
        """
        Calcula o Tempo Médio de Resposta (MRT) de uma mensagem completa, desde o momento em
        que ela saiu do Source até o momento em que está prestes a retornar a ele.
        """
        parts = received_message.split(';')
        
   
        first_timestamp_str = parts[1] # Timestamp de saída do Source
        first_timestamp = int(first_timestamp_str) if first_timestamp_str.isdigit() else get_current_millis()

      
        last_timestamp_str = parts[-2] # Timestamp de saída do ServiceProxy
        last_timestamp = int(last_timestamp_str) if last_timestamp_str.isdigit() else get_current_millis()

        current_mrt = last_timestamp - first_timestamp
        received_message += f"RESPONSE TIME:;{current_mrt};"
        return received_message