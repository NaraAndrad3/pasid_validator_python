# src/domain/service_proxy.py (Exemplo Adaptado)

import threading
import time
import socket
import random # Assumindo que você tem isso para serviceTime
import os
from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import get_current_millis # Assumindo que você tem isso

class ServiceProxy(AbstractProxy):

    def __init__(self, name: str, local_port: int, target_address: TargetAddress, service_time: float, std: float, target_is_source: bool):
        super().__init__(name, local_port, target_address)
        self.service_time = service_time
        self.std = std
        self.target_is_source = target_is_source
        self.content_to_process = None # Usado para verificar se o serviço está "ocupado"
        self.processing_lock = threading.Lock() # Para proteger o acesso a content_to_process


    def run(self):
        self.log(f"[{self.proxy_name}] Iniciando {self.proxy_name} na porta {self.local_port}...")
        # O listener de socket já é iniciado no __init__ do AbstractProxy
        # A lógica principal de processamento de mensagens em serviço deve ser aqui.
        while self.is_running:
            self.process_and_send_to_destiny() # Tenta processar e enviar mensagem se houver
            time.sleep(0.01) # Pequena pausa para evitar CPU-bound loop


    def receiving_messages(self, received_message: str, conn: socket.socket):
        if received_message is None or received_message.strip() == "":
            return

        message_stripped = received_message.strip()
        
        if message_stripped == "ping":
            self.handle_ping_message(conn) 
        else:
            with self.processing_lock:
                if self.content_to_process is None: 
                    self.content_to_process = self.register_time_when_arrives(message_stripped)
                    self.log(f"[{self.proxy_name}] Recebido e enfileirado para processamento: {self.content_to_process[:50]}...")
                else:
                    self.log(f"[{self.proxy_name}] Serviço ocupado. Mensagem descartada (ou enfileirada, dependendo da sua lógica): {message_stripped[:50]}...")
                   


    def handle_ping_message(self, conn: socket.socket):
        try:
            output_stream = conn.makefile('wb') 
            with self.processing_lock:
                if self.content_to_process is not None:
                    output_stream.write(b"busy\n")
                    self.log(f"[{self.proxy_name}] Respondeu 'busy' ao ping.")
                else:
                    output_stream.write(b"free\n")
                    self.log(f"[{self.proxy_name}] Respondeu 'free' ao ping.")
            output_stream.flush()
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao responder ping: {e}")
            

    def _simulate_is_free(self) -> bool:
        """
        Verifica se o ServiceProxy está livre para processar uma nova mensagem.
        """
        with self.processing_lock:
            return self.content_to_process is None

    def process_and_send_to_destiny(self):
        with self.processing_lock:
            if self.content_to_process is None:
                return

            message_to_process = self.content_to_process
            self.content_to_process = None 

        
        delay = max(0, random.gauss(self.service_time, self.std)) / 1000.0 
        time.sleep(delay)

        
        processed_message = self.register_time_when_go_out(message_to_process)
        self.log(f"[{self.proxy_name}] Mensagem processada. Enviando para destino: {processed_message[:50]}...")

        
        self.send_message_to_destiny(processed_message + "\n", self.target_address)
        
    def register_time_when_arrives(self, received_message: str) -> str:
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

        time_now = get_current_millis()
        duration = time_now - last_timestamp
        
        received_message += f"{time_now};{duration};"
        return received_message

    def register_time_when_go_out(self, received_message: str) -> str:
       
        time_now = get_current_millis()
        
        parts = received_message.split(';')
        
        
        arrival_to_service_timestamp_str = parts[-3] if len(parts) >= 3 else str(get_current_millis())
        
        arrival_to_service_timestamp = int(arrival_to_service_timestamp_str) if arrival_to_service_timestamp_str.isdigit() else get_current_millis()

        processing_time = time_now - arrival_to_service_timestamp
        
        received_message += f"{time_now};{processing_time};"
        return received_message

